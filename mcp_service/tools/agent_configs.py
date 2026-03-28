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
from ..responses import (
    success,
    validation_error,
    not_found_error,
    internal_error,
)

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

    Returns:
        Standardized MCPResponse as dict.
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
        return validation_error(str(e)).to_dict()

    agent_id = str(uuid.uuid4())
    doc = {"_id": agent_id, **validated_data}

    if update_couchdb_doc(AGENT_CONFIGS_DB, agent_id, doc):
        return success(
            data={"agent_config": doc},
            message=f"Agent configuration '{name}' created with ID: {agent_id}",
        ).to_dict()
    else:
        return internal_error(
            message="Failed to add agent configuration."
        ).to_dict()


@mcp.tool(
    name="get_agent_config", description="Retrieves an agent configuration by ID."
)
def get_agent_config(agent_id: str, userspace: str) -> dict:
    """
    Retrieves a specific agent configuration.

    Returns:
        Standardized MCPResponse as dict.
    """
    config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if isinstance(config, dict) and extract_userspace(config) == userspace:
        return success(
            data={"agent_config": config},
            message=f"Retrieved agent configuration {agent_id}",
        ).to_dict()

    return not_found_error("agent_config", agent_id).to_dict()


@mcp.tool(
    name="list_agent_configs",
    description="Lists agent configurations filtered by userspace.",
)
def list_agent_configs(userspace: str, owner_user_id: Optional[str] = None) -> dict:
    """
    Lists all agent configurations in a userspace.

    Returns:
        Standardized MCPResponse as dict.
    """
    userspace_selector: dict[str, Any] = {
        "$or": [{"userspace": userspace}, {"namespace": userspace}]
    }
    selector: dict[str, Any] = userspace_selector
    if owner_user_id:
        selector = {"$and": [userspace_selector, {"owner_user_id": owner_user_id}]}

    configs = query_couchdb(AGENT_CONFIGS_DB, selector=selector)
    return success(
        data={"agent_configs": configs, "count": len(configs)},
        message=f"Found {len(configs)} agent configuration(s)",
    ).to_dict()


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

    Returns:
        Standardized MCPResponse as dict.
    """
    existing_config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if (
        not isinstance(existing_config, dict)
        or extract_userspace(existing_config) != userspace
    ):
        return not_found_error("agent_config", agent_id).to_dict()

    update_data: dict[str, Any] = {}
    excluded_keys = {"agent_id", "existing_config", "update_data", "userspace"}
    for key, value in locals().items():
        if value is not None and key not in excluded_keys:
            update_data[key] = value

    try:
        validated_data = AgentConfigUpdateRequest(**update_data).model_dump(
            exclude_unset=True
        )
    except ValidationError as e:
        return validation_error(str(e)).to_dict()

    existing_config.update(validated_data)

    if update_couchdb_doc(AGENT_CONFIGS_DB, agent_id, existing_config):
        return success(
            data={"agent_config": existing_config},
            message=f"Agent configuration {agent_id} updated",
        ).to_dict()
    else:
        return internal_error(
            message="Failed to update agent configuration."
        ).to_dict()


@mcp.tool(name="delete_agent_config", description="Deletes an agent configuration.")
def delete_agent_config(agent_id: str, userspace: str) -> dict:
    """
    Deletes a specific agent configuration.

    Returns:
        Standardized MCPResponse as dict.
    """
    config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if not isinstance(config, dict) or extract_userspace(config) != userspace:
        return not_found_error("agent_config", agent_id).to_dict()

    if delete_from_couchdb(AGENT_CONFIGS_DB, agent_id, config["_rev"]):
        return success(
            data={"agent_id": agent_id},
            message=f"Agent configuration {agent_id} deleted.",
        ).to_dict()
    else:
        return internal_error(
            message="Failed to delete agent configuration."
        ).to_dict()


@mcp.tool(
    name="migrate_agent_configs_userspace",
    description="Migrates legacy agent configs to userspace + owner_user_id fields.",
)
def migrate_agent_configs_userspace() -> dict:
    """
    Migrates legacy agent configs.

    Returns:
        Standardized MCPResponse as dict.
    """
    result = migrate_legacy_agent_configs()
    return success(
        data={
            "migrated": result.get("migrated", 0),
            "skipped": result.get("skipped", 0),
        },
        message=f"Migration complete: {result.get('migrated', 0)} migrated, {result.get('skipped', 0)} skipped",
    ).to_dict()
