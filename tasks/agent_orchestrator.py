import time
import threading
import importlib
from datetime import datetime, timedelta, timezone
import logging
import uuid # Added for unique leader ID
import redis # Added for Redis client

from api.db import query_couchdb, update_couchdb_doc
from api.validation import AgentStatus, AgentTriggerType

logger = logging.getLogger(__name__)

# Constants for Redis lock
REDIS_LOCK_NAME = "agent_orchestrator_lock"


class AgentOrchestrator(threading.Thread):
    def __init__(self, interval=60, redis_client: redis.Redis = None):
        super().__init__()
        self.interval = interval  # Interval in seconds to check for agents to run
        self.running = False
        self.last_article_check_time = datetime.now(timezone.utc)
        self.agent_configs_db = "agent_configs"
        self.articles_db = "articles"
        self.feeds_db = "feeds"
        self.events_db = "events"
        self.trends_db = "trends"
        self.mcp_client = None  # To be initialized with an MCP client for tool calls

        # Redis distributed locking
        self.redis_client: redis.Redis = redis_client # Assigned here
        self.leader_id = str(uuid.uuid4()) # Unique ID for this orchestrator instance
        self.is_leader = False
        self.lock_name = REDIS_LOCK_NAME
        self.lock_expiry = self.interval * 2 # Lock expiry is twice the check interval, to allow for renewal

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

    def run(self):
        self.running = True
        logger.info(f"Agent Orchestrator {self.leader_id} started.")
        
        while self.running:
            try:
                if not self.redis_client:
                    logger.error("Redis client not available. Exiting orchestrator.")
                    self.stop()
                    break

                self._update_leadership()

                if self.is_leader:
                    logger.info(f"Agent Orchestrator {self.leader_id} is leader. Checking agents.")
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
        active_agents = query_couchdb(
            self.agent_configs_db, selector={"status": AgentStatus.ACTIVE.value}
        )

        # Check for new articles (simple polling for now)
        # This should ideally be event-driven via CouchDB _changes feed
        new_articles = []
        # Query only if there are 'on_new_article' agents to avoid unnecessary DB calls
        if any(
            a.get("trigger_type") == AgentTriggerType.ON_NEW_ARTICLE.value
            for a in active_agents
        ):
            new_articles = query_couchdb(
                self.articles_db,
                selector={
                    "published": {"$gt": self.last_article_check_time.isoformat()}
                },
                sort=[{"published": "asc"}],
            )
            if new_articles:
                logger.info(f"Found {len(new_articles)} new articles since last check.")

        # Always update last_article_check_time after checking
        self.last_article_check_time = datetime.now(timezone.utc)

        for agent_config in active_agents:
            # Ensure last_run_at is initialized for scheduled agents
            if (
                agent_config.get("trigger_type") == AgentTriggerType.SCHEDULED.value
                and "last_run_at" not in agent_config
            ):
                agent_config["last_run_at"] = (
                    datetime.now(timezone.utc) - timedelta(days=365)
                ).isoformat()  # Initialize to a year ago
                update_couchdb_doc(
                    self.agent_configs_db, agent_config["_id"], agent_config
                )  # Persist update

            try:
                self.run_agent_if_due(agent_config, new_articles)
            except Exception as e:
                logger.error(
                    f"Error running agent {agent_config.get('_id', 'N/A')}: {e}"
                )
                # Optionally update agent status to ERROR
                agent_config["status"] = AgentStatus.ERROR.value
                update_couchdb_doc(
                    self.agent_configs_db, agent_config["_id"], agent_config
                )

    def run_agent_if_due(self, agent_config: dict, new_articles: list[dict]):
        trigger_type = agent_config.get("trigger_type")
        agent_id = agent_config.get("_id", "N/A")

        if trigger_type == AgentTriggerType.ON_NEW_ARTICLE.value:
            if new_articles:
                logger.info(
                    f"Triggering on_new_article agent {agent_id} for new articles."
                )
                self.execute_agent_logic(
                    agent_config,
                    new_articles=new_articles,
                    llm_config=agent_config.get("llm_model_config"),
                )
        elif trigger_type == AgentTriggerType.SCHEDULED.value:
            last_run_at_str = agent_config.get("last_run_at")
            schedule_interval = agent_config.get("schedule_interval")

            if self.is_scheduled_agent_due(last_run_at_str, schedule_interval):
                logger.info(f"Triggering scheduled agent {agent_id}.")
                self.execute_agent_logic(
                    agent_config, llm_config=agent_config.get("llm_model_config")
                )

    def is_scheduled_agent_due(
        self, last_run_at_str: str, schedule_interval: str
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

        # Security: Whitelist allowed logic modules to prevent arbitrary code execution
        ALLOWED_LOGIC_MODULES = [
            "tasks.agent_logic.create_event_from_articles",
            "tasks.agent_logic.add_articles_to_event",
            "tasks.agent_logic.check_event_staleness",
        ]

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

            # Update last_run_at
            agent_config["last_run_at"] = datetime.now(timezone.utc).isoformat()
            update_couchdb_doc(self.agent_configs_db, agent_config["_id"], agent_config)

        except Exception as e:
            logger.error(
                f"Failed to execute logic for agent {agent_config.get('_id')} from {logic_module_path}: {e}"
            )
