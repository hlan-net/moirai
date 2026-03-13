import time
import threading
import importlib
from datetime import datetime, timedelta, timezone
import logging
import uuid # Added for unique leader ID
import redis # Added for Redis client
import requests

from api.db import query_couchdb, update_couchdb_doc_safe
from api.db_config import get_couchdb_uri
from api.validation import ALLOWED_LOGIC_MODULES, AgentStatus, AgentTriggerType
from tasks.agent_config_migration import migrate_legacy_agent_configs

logger = logging.getLogger(__name__)

# Constants for Redis lock
REDIS_LOCK_NAME = "agent_orchestrator_lock"

# Constants for sequence tracking
ORCHESTRATOR_SEQ_DOC_ID = "orchestrator_last_seq"


class AgentOrchestrator(threading.Thread):
    def __init__(self, interval=60, redis_client: redis.Redis = None):
        super().__init__()
        self.interval = interval  # Interval in seconds to check for agents to run
        self.running = False
        self.agent_configs_db = "agent_configs"
        self.articles_db = "articles"
        self.feeds_db = "feeds"
        self.issues_db = "issues"
        self.mcp_client = None  # To be initialized with an MCP client for tool calls

        # Redis distributed locking
        self.redis_client: redis.Redis = redis_client # Assigned here
        self.leader_id = str(uuid.uuid4()) # Unique ID for this orchestrator instance
        self.is_leader = False
        self.lock_name = REDIS_LOCK_NAME
        self.lock_expiry = self.interval * 2 # Lock expiry is twice the check interval, to allow for renewal

        # Changes feed tracking for on_new_article agents
        self.last_seq = "0"

    def _acquire_lock(self) -> bool:
        """Attempts to acquire the distributed lock."""
        if not self.redis_client:
            logger.error("Redis client not initialized for AgentOrchestrator.")
            return False

        # Attempt to set the lock key if it doesn't exist.
        # Set expiry to prevent deadlocks if an orchestrator crashes.
        # Store self.leader_id as the value to identify the lock owner.
        return self.redis_client.set(self.lock_name, self.leader_id, nx=True, ex=self.lock_expiry)

    def _renew_lock(self) -> bool:
        """Attempts to renew the distributed lock if this instance is the leader."""
        if not self.redis_client:
            return False

        # Only renew if we are the current owner of the lock.
        # Use a Lua script for atomic check-and-set to prevent race conditions.
        # Script: if value of key is leader_id, then set new expiry.
        lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("expire", KEYS[1], ARGV[2])
            else
                return 0
            end
        """
        return self.redis_client.eval(lua_script, 1, self.lock_name, self.leader_id, self.lock_expiry) == 1

    def _release_lock(self):
        """Attempts to release the distributed lock if this instance is the leader."""
        if not self.redis_client:
            return

        lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
        """
        self.redis_client.eval(lua_script, 1, self.lock_name, self.leader_id)
        self.is_leader = False
        logger.info(f"Agent Orchestrator {self.leader_id} released lock.")

    # ------------------------------------------------------------------
    # Sequence tracking for changes feed
    # ------------------------------------------------------------------

    def _get_last_seq(self) -> str:
        """Load last processed _changes sequence from config DB."""
        try:
            res = requests.get(
                f"{get_couchdb_uri()}config/{ORCHESTRATOR_SEQ_DOC_ID}", timeout=10
            )
            if res.status_code == 200:
                return res.json().get("value", "0")
            if res.status_code != 404:
                logger.error(
                    f"AgentOrchestrator: unexpected status {res.status_code} loading last_seq"
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"AgentOrchestrator: failed to load last_seq: {e}")
        except ValueError as e:
            logger.error(f"AgentOrchestrator: invalid last_seq response: {e}")
        return "now"

    def _save_last_seq(self, seq: str) -> None:
        """Persist last processed sequence to config DB."""
        try:
            doc = {"_id": ORCHESTRATOR_SEQ_DOC_ID, "value": seq}
            res = requests.get(
                f"{get_couchdb_uri()}config/{ORCHESTRATOR_SEQ_DOC_ID}", timeout=10
            )
            if res.status_code == 200:
                doc["_rev"] = res.json()["_rev"]
            elif res.status_code != 404:
                logger.error(
                    f"AgentOrchestrator: unexpected status {res.status_code} reading last_seq"
                )
            res = requests.put(
                f"{get_couchdb_uri()}config/{ORCHESTRATOR_SEQ_DOC_ID}",
                json=doc,
                timeout=10,
            )
            if res.status_code not in (200, 201):
                logger.error(
                    f"AgentOrchestrator: failed to save last_seq: "
                    f"{res.status_code} {res.text}"
                )
        except requests.exceptions.RequestException as e:
            logger.error(f"AgentOrchestrator: failed to save last_seq: {e}")
        except ValueError as e:
            logger.error(f"AgentOrchestrator: invalid last_seq response: {e}")

    def _update_leadership(self):
        """Helper to handle lock acquisition and renewal."""
        if not self.is_leader:
            # Not a leader, try to acquire lock
            if self._acquire_lock():
                self.is_leader = True
                logger.info(f"Agent Orchestrator {self.leader_id} acquired leadership.")
            else:
                logger.debug(f"Agent Orchestrator {self.leader_id} is not leader. Waiting.")
        else:
            # We are the leader, try to renew lock
            if not self._renew_lock():
                self.is_leader = False # Lost leadership
                logger.warning(f"Agent Orchestrator {self.leader_id} lost leadership.")
            else:
                logger.debug(f"Agent Orchestrator {self.leader_id} renewed leadership.")

    # ------------------------------------------------------------------
    # Changes feed processing for on_new_article agents
    # ------------------------------------------------------------------

    def _run_changes_feed(self) -> None:
        """Daemon thread that longpolls articles/_changes and dispatches on_new_article agents."""
        self.last_seq = self._get_last_seq()
        while self.running:
            if not self.is_leader:
                time.sleep(5)
                continue
            self._process_article_changes()

    def _process_article_changes(self) -> None:
        """Process a batch of article changes and dispatch agents."""
        changes_url = f"{get_couchdb_uri()}{self.articles_db}/_changes"
        params = {
            "feed": "longpoll",
            "since": self.last_seq,
            "include_docs": "true",
            "timeout": 30000,
        }

        try:
            response = requests.get(changes_url, params=params, timeout=35)
        except requests.exceptions.RequestException as e:
            logger.error(f"AgentOrchestrator: changes feed error: {e}")
            time.sleep(5)
            return

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"AgentOrchestrator: invalid changes response: {e}")
                time.sleep(5)
                return

            # Extract documents, excluding design docs
            new_docs = [
                c["doc"]
                for c in data.get("results", [])
                if c.get("doc") and not c["doc"].get("_id", "").startswith("_design/")
            ]

            if new_docs:
                self._dispatch_on_new_article_agents(new_docs)

            # Update and persist sequence
            if data.get("last_seq"):
                self.last_seq = data["last_seq"]
                self._save_last_seq(self.last_seq)

        elif response.status_code == 404:
            # DB doesn't exist yet — wait and retry
            logger.debug("AgentOrchestrator: articles DB not found, retrying...")
            time.sleep(10)
        else:
            logger.error(
                f"AgentOrchestrator: unexpected status {response.status_code} from changes feed"
            )
            time.sleep(5)

    def _dispatch_on_new_article_agents(self, new_docs: list[dict]) -> None:
        """Dispatch on_new_article agents with articles from their own userspace."""
        # Pre-group documents by userspace for efficient dispatch (O(docs + agents) instead of O(docs * agents))
        docs_by_userspace: dict[str, list[dict]] = {}
        for doc in new_docs:
            userspace = doc.get("userspace")
            if userspace:
                if userspace not in docs_by_userspace:
                    docs_by_userspace[userspace] = []
                docs_by_userspace[userspace].append(doc)

        if not docs_by_userspace:
            return

        # Query active on_new_article agents
        active_agents = query_couchdb(
            self.agent_configs_db,
            selector={
                "status": AgentStatus.ACTIVE.value,
                "trigger_type": AgentTriggerType.ON_NEW_ARTICLE.value,
            },
        )

        dispatch_count = 0
        for agent_config in active_agents:
            userspace = agent_config.get("userspace") or agent_config.get("namespace")
            if not userspace:
                logger.warning(
                    f"Agent {agent_config.get('_id')} missing userspace; skipping dispatch."
                )
                continue

            # Get articles for this agent's userspace
            agent_articles = docs_by_userspace.get(userspace)
            if not agent_articles:
                continue

            try:
                logger.info(
                    f"Dispatching on_new_article agent {agent_config.get('_id')} "
                    f"with {len(agent_articles)} articles."
                )
                self.execute_agent_logic(
                    agent_config,
                    new_articles=agent_articles,
                    llm_config=agent_config.get("llm_model_config"),
                )
                dispatch_count += 1
            except Exception as e:
                logger.error(
                    f"Error dispatching on_new_article agent {agent_config.get('_id')}: {e}",
                    exc_info=True,
                )
                update_couchdb_doc_safe(
                    self.agent_configs_db,
                    agent_config["_id"],
                    {"status": AgentStatus.ERROR.value},
                )

        if dispatch_count > 0:
            logger.info(f"Dispatched {dispatch_count} on_new_article agents.")

    def run(self):
        self.running = True
        logger.info(f"Agent Orchestrator {self.leader_id} started.")

        migrate_result = migrate_legacy_agent_configs()
        if migrate_result.get("migrated"):
            logger.info("Migrated %s legacy agent configs", migrate_result.get("migrated"))

        # Start the changes feed thread for on_new_article agents
        changes_thread = threading.Thread(
            target=self._run_changes_feed,
            name="orchestrator-changes-feed",
            daemon=True,
        )
        changes_thread.start()

        while self.running:
            try:
                if not self.redis_client:
                    logger.error("Redis client not available. Exiting orchestrator.")
                    self.stop()
                    break

                self._update_leadership()

                if self.is_leader:
                    logger.debug(f"Agent Orchestrator {self.leader_id} is leader. Checking scheduled agents.")
                    self.check_and_run_agents()
                else:
                    logger.debug(f"Agent Orchestrator {self.leader_id} skipping agent checks (not leader).")

            except Exception as e:
                logger.error(f"Error in Agent Orchestrator loop: {e}", exc_info=True)
                if self.is_leader:
                    self._release_lock()

            time.sleep(self.interval)

        if self.is_leader:
            self._release_lock()
        logger.info(f"Agent Orchestrator {self.leader_id} stopped.")



    def stop(self):
        self.running = False

    def check_and_run_agents(self):
        """Check for and run SCHEDULED agents only.

        ON_NEW_ARTICLE agents are now dispatched via the changes feed thread
        (_run_changes_feed) and do not run from this method.
        """
        active_agents = query_couchdb(
            self.agent_configs_db,
            selector={
                "status": AgentStatus.ACTIVE.value,
                "trigger_type": AgentTriggerType.SCHEDULED.value,
            },
        )

        for agent_config in active_agents:
            agent_id = agent_config.get("_id", "N/A")
            if not (agent_config.get("userspace") or agent_config.get("namespace")):
                logger.error(
                    "Agent %s missing userspace after migration; marking as error.",
                    agent_id,
                )
                update_couchdb_doc_safe(
                    self.agent_configs_db,
                    agent_id,
                    {"status": AgentStatus.ERROR.value},
                )
                continue

            # Ensure last_run_at is initialized for scheduled agents
            if "last_run_at" not in agent_config:
                initial_last_run = (
                    datetime.now(timezone.utc) - timedelta(days=365)
                ).isoformat()
                update_couchdb_doc_safe(
                    self.agent_configs_db,
                    agent_id,
                    {"last_run_at": initial_last_run},
                )
                agent_config["last_run_at"] = initial_last_run

            try:
                self.run_agent_if_due(agent_config)
            except Exception as e:
                logger.error(
                    f"Error running agent {agent_id}: {e}"
                )
                update_couchdb_doc_safe(
                    self.agent_configs_db,
                    agent_id,
                    {"status": AgentStatus.ERROR.value},
                )

    def run_agent_if_due(self, agent_config: dict):
        """Check if a SCHEDULED agent is due and execute it if so."""
        agent_id = agent_config.get("_id", "N/A")
        last_run_at_str = agent_config.get("last_run_at")
        schedule_interval = agent_config.get("schedule_interval")

        if self.is_scheduled_agent_due(last_run_at_str, schedule_interval):
            logger.info(f"Triggering scheduled agent {agent_id}.")
            self.execute_agent_logic(
                agent_config, llm_config=agent_config.get("llm_model_config")
            )

    def is_scheduled_agent_due(
        self, last_run_at_str: str | None, schedule_interval: str | None
    ) -> bool:
        if not schedule_interval:
            return False

        last_run_at = (
            datetime.fromisoformat(last_run_at_str)
            if last_run_at_str
            else datetime.min.replace(tzinfo=timezone.utc)
        )
        now = datetime.now(timezone.utc)

        interval_value = int("".join(filter(str.isdigit, schedule_interval)))
        interval_unit = "".join(filter(str.isalpha, schedule_interval)).lower()

        if interval_unit == "s":
            delta = timedelta(seconds=interval_value)
        elif interval_unit == "m":
            delta = timedelta(minutes=interval_value)
        elif interval_unit == "h":
            delta = timedelta(hours=interval_value)
        elif interval_unit == "d":
            delta = timedelta(days=interval_value)
        else:
            logger.warning(
                f"Unknown schedule interval unit: {schedule_interval}. Agent cannot be run."
            )
            return False

        return (now - last_run_at) > delta

    def execute_agent_logic(self, agent_config: dict, **kwargs):
        logic_module_path = agent_config.get("logic_module")
        if not logic_module_path:
            logger.error(
                f"Agent {agent_config.get('_id')} has no logic_module specified."
            )
            return

        # Security: only execute modules in the shared allowlist (defined in api.validation)
        if logic_module_path not in ALLOWED_LOGIC_MODULES:
            logger.error(f"Logic module {logic_module_path} is not in the allowed whitelist.")
            return

        try:
            module_name, func_name = logic_module_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            logic_function = getattr(module, func_name)

            # Pass agent config and other relevant data
            logic_function(
                agent_config=agent_config, mcp_client=self.mcp_client, **kwargs
            )

            # Update last_run_at using conflict-safe write
            update_couchdb_doc_safe(
                self.agent_configs_db,
                agent_config["_id"],
                {"last_run_at": datetime.now(timezone.utc).isoformat()},
            )

        except Exception as e:
            logger.error(
                f"Failed to execute logic for agent {agent_config.get('_id')} from {logic_module_path}: {e}"
            )
