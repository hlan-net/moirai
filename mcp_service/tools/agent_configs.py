import uuid
from typing import Any, Optional

from pydantic import ValidationError

from api.db import (
    query_couchdb,
    fetch_from_couchdb,
    update_couchdb_doc,
    delete_from_couchdb,
)
from api.validation import AgentConfigCreateRequest, AgentConfigUpdateRequest
from mcp_service.core import mcp
from tasks.agent_config_migration import migrate_legacy_agent_configs

from .userspace import extract_userspace

# Database name for agent configurations
AGENT_CONFIGS_DB = "agent_configs"


@mcp.tool(name="add_agent_config", description="Adds a new agent configuration.")
def add_agent_config(
    userspace: str,
    name: str,
    trigger_type: str,
    target_db: str,
    logic_module: str,
    owner_user_id: Optional[str] = None,
    user_id: Optional[str] = None,
    schedule_interval: Optional[str] = None,
    llm_model_config: Optional[dict[str, Any]] = None,
    parameters: Optional[dict[str, Any]] = None,
    linked_entity_id: Optional[str] = None,
) -> dict:
    """
    Adds a new agent configuration to monitor and act on data.
    Args:
        userspace: The userspace GUID where this agent can operate.
        name: A descriptive name for the agent config.
        trigger_type: How the agent is triggered ('on_new_article', 'scheduled').
        target_db: The database the agent primarily monitors ('articles', 'issues', 'feeds').
        logic_module: Reference to a Python module/function for agent logic (e.g., 'tasks.agent_logic.create_event').
        owner_user_id: The GUID of the user that owns model credentials for this agent.
        user_id: Deprecated alias for owner_user_id.
        schedule_interval: (Optional) If trigger_type is 'scheduled', the interval (e.g., '1h', '1d', 'every 30m').
        llm_model_config: (Optional) LLM specific configurations (model_name, provider).
        parameters: (Optional) User-defined parameters for the agent logic.
        linked_entity_id: (Optional) ID of a specific issue (event or trend) this agent is managing.
    Returns:
        A dictionary representing the created agent configuration.
    """
    try:
        resolved_owner_user_id = owner_user_id or user_id
        agent_config_data: dict[str, Any] = {
            "userspace": userspace,
            "owner_user_id": resolved_owner_user_id,
            "name": name,
            "trigger_type": trigger_type,
            "target_db": target_db,
            "logic_module": logic_module,
        }
        if schedule_interval is not None:
            agent_config_data["schedule_interval"] = schedule_interval
        if llm_model_config is not None:
            agent_config_data["llm_model_config"] = llm_model_config
        if parameters is not None:
            agent_config_data["parameters"] = parameters
        if linked_entity_id is not None:
            agent_config_data["linked_entity_id"] = linked_entity_id

        validated_data = AgentConfigCreateRequest(**agent_config_data).model_dump()
    except ValidationError as e:
        return {"status": "error", "message": str(e)}

    agent_id = str(uuid.uuid4())
    doc = {"_id": agent_id, **validated_data}

    if update_couchdb_doc(AGENT_CONFIGS_DB, agent_id, doc):
        return {"status": "success", "agent_config": doc}
    else:
        return {"status": "error", "message": "Failed to add agent configuration."}


@mcp.tool(
    name="get_agent_config", description="Retrieves an agent configuration by ID."
)
def get_agent_config(agent_id: str, userspace: str) -> dict:
    """
    Retrieves a specific agent configuration.
    Args:
        agent_id: The GUID of the agent configuration.
        userspace: Userspace GUID for scope enforcement.
    Returns:
        A dictionary representing the agent configuration or an error message.
    """
    config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if isinstance(config, dict) and extract_userspace(config) == userspace:
        return {"status": "success", "agent_config": config}

    return {
        "status": "error",
        "message": f"Agent configuration {agent_id} not found.",
    }


@mcp.tool(
    name="list_agent_configs",
    description="Lists agent configurations filtered by userspace.",
)
def list_agent_configs(userspace: str, owner_user_id: Optional[str] = None) -> dict:
    """
    Lists all agent configurations in a userspace.
    Args:
        userspace: Required userspace to filter agent configurations.
        owner_user_id: (Optional) Filter by owner user ID.
    Returns:
        A list of dictionaries, each representing an agent configuration.
    """
    migrate_legacy_agent_configs()

    userspace_selector: dict[str, Any] = {
        "$or": [{"userspace": userspace}, {"namespace": userspace}]
    }
    selector: dict[str, Any] = userspace_selector
    if owner_user_id:
        selector = {"$and": [userspace_selector, {"owner_user_id": owner_user_id}]}

    configs = query_couchdb(AGENT_CONFIGS_DB, selector=selector)
    return {"status": "success", "agent_configs": configs}


@mcp.tool(
    name="update_agent_config", description="Updates an existing agent configuration."
)
def update_agent_config(
    agent_id: str,
    userspace: str,
    name: Optional[str] = None,
    status: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    target_db: Optional[str] = None,
    logic_module: Optional[str] = None,
    schedule_interval: Optional[str] = None,
    llm_model_config: Optional[dict[str, Any]] = None,
    parameters: Optional[dict[str, Any]] = None,
    linked_entity_id: Optional[str] = None,
) -> dict:
    """
    Updates an existing agent configuration.
    """
    existing_config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if (
        not isinstance(existing_config, dict)
        or extract_userspace(existing_config) != userspace
    ):
        return {
            "status": "error",
            "message": f"Agent configuration {agent_id} not found.",
        }

    update_data: dict[str, Any] = {
        k: v
        for k, v in locals().items()
        if v is not None and k not in ["agent_id", "existing_config", "update_data"]
    }

    try:
        validated_data = AgentConfigUpdateRequest(**update_data).model_dump(
            exclude_unset=True
        )
    except ValidationError as e:
        return {"status": "error", "message": str(e)}

    existing_config.update(validated_data)

    if update_couchdb_doc(AGENT_CONFIGS_DB, agent_id, existing_config):
        return {"status": "success", "agent_config": existing_config}
    else:
        return {"status": "error", "message": "Failed to update agent configuration."}


@mcp.tool(name="delete_agent_config", description="Deletes an agent configuration.")
def delete_agent_config(agent_id: str, userspace: str) -> dict:
    """
    Deletes a specific agent configuration.
    """
    config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if not isinstance(config, dict) or extract_userspace(config) != userspace:
        return {
            "status": "error",
            "message": f"Agent configuration {agent_id} not found.",
        }

    if delete_from_couchdb(AGENT_CONFIGS_DB, agent_id, config["_rev"]):
        return {
            "status": "success",
            "message": f"Agent configuration {agent_id} deleted.",
        }
    else:
        return {"status": "error", "message": "Failed to delete agent configuration."}


@mcp.tool(
    name="migrate_agent_configs_userspace",
    description="Migrates legacy agent configs to userspace + owner_user_id fields.",
)
def migrate_agent_configs_userspace() -> dict:
    return migrate_legacy_agent_configs()
