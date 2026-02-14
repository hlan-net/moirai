import time
import threading
import importlib
from datetime import datetime, timedelta, timezone
import logging
from api.db import query_couchdb, update_couchdb_doc
from api.validation import AgentStatus, AgentTriggerType

logger = logging.getLogger(__name__)


class AgentOrchestrator(threading.Thread):
    def __init__(self, interval=60):
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

    def run(self):
        self.running = True
        logger.info("Agent Orchestrator started.")
        while self.running:
            try:
                self.check_and_run_agents()
            except Exception as e:
                logger.error(f"Error in Agent Orchestrator loop: {e}")
            time.sleep(self.interval)
        logger.info("Agent Orchestrator stopped.")

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
