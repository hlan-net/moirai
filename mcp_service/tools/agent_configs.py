from mcp_service.db import query_couchdb, fetch_from_couchdb, update_couchdb_doc, delete_from_couchdb
from mcp_service.core import mcp_tool
from api.validation import AgentConfigCreateRequest, AgentConfigUpdateRequest
from pydantic import ValidationError
import uuid

# Database name for agent configurations
AGENT_CONFIGS_DB = "agent_configs"

@mcp_tool(name="add_agent_config", description="Adds a new agent configuration.")
def add_agent_config(user_id: str, name: str, trigger_type: str, target_db: str, logic_module: str,
                       schedule_interval: str = None, llm_model_config: dict = None,
                       parameters: dict = None, linked_entity_id: str = None) -> dict:
    """
    Adds a new agent configuration to monitor and act on data.
    Args:
        user_id: The GUID of the user creating the agent config.
        name: A descriptive name for the agent config.
        trigger_type: How the agent is triggered ('on_new_article', 'scheduled').
        target_db: The database the agent primarily monitors ('articles', 'events', 'trends').
        logic_module: Reference to a Python module/function for agent logic (e.g., 'tasks.agent_logic.create_event').
        schedule_interval: (Optional) If trigger_type is 'scheduled', the interval (e.g., '1h', '1d', 'every 30m').
        llm_model_config: (Optional) LLM specific configurations (model_name, provider).
        parameters: (Optional) User-defined parameters for the agent logic.
        linked_entity_id: (Optional) ID of a specific event or trend this agent is managing.
    Returns:
        A dictionary representing the created agent configuration.
    """
    try:
        # Pydantic validation
        agent_config_data = {
            "user_id": user_id,
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
            
        validated_data = AgentConfigCreateRequest(**agent_config_data).dict()
    except ValidationError as e:
        return {"status": "error", "message": str(e)}

    agent_id = str(uuid.uuid4())
    doc = {
        "_id": agent_id,
        **validated_data
    }

    if update_couchdb_doc(AGENT_CONFIGS_DB, agent_id, doc):
        return {"status": "success", "agent_config": doc}
    else:
        return {"status": "error", "message": "Failed to add agent configuration."}

@mcp_tool(name="get_agent_config", description="Retrieves an agent configuration by ID.")
def get_agent_config(agent_id: str) -> dict:
    """
    Retrieves a specific agent configuration.
    Args:
        agent_id: The GUID of the agent configuration.
    Returns:
        A dictionary representing the agent configuration or an error message.
    """
    config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if config:
        return {"status": "success", "agent_config": config}
    else:
        return {"status": "error", "message": f"Agent configuration {agent_id} not found."}

@mcp_tool(name="list_agent_configs", description="Lists agent configurations, optionally filtered by user_id.")
def list_agent_configs(user_id: str = None) -> list[dict]:
    """
    Lists all agent configurations, or those belonging to a specific user.
    Args:
        user_id: (Optional) Filter agent configurations by this user ID.
    Returns:
        A list of dictionaries, each representing an agent configuration.
    """
    selector = {}
    if user_id:
        selector["user_id"] = user_id
    
    configs = query_couchdb(AGENT_CONFIGS_DB, selector=selector)
    return {"status": "success", "agent_configs": configs}

@mcp_tool(name="update_agent_config", description="Updates an existing agent configuration.")
def update_agent_config(agent_id: str, name: str = None, status: str = None,
                         trigger_type: str = None, target_db: str = None, logic_module: str = None,
                         schedule_interval: str = None, llm_model_config: dict = None,
                         parameters: dict = None, linked_entity_id: str = None) -> dict:
    """
    Updates an existing agent configuration.
    Args:
        agent_id: The GUID of the agent configuration to update.
        name: (Optional) A descriptive name for the agent config.
        status: (Optional) New status for the agent ('active', 'paused', 'error').
        trigger_type: (Optional) How the agent is triggered ('on_new_article', 'scheduled').
        target_db: (Optional) The database the agent primarily monitors ('articles', 'events', 'trends').
        logic_module: (Optional) Reference to a Python module/function for agent logic.
        schedule_interval: (Optional) If trigger_type is 'scheduled', the interval.
        llm_model_config: (Optional) LLM specific configurations.
        parameters: (Optional) User-defined parameters for the agent logic.
        linked_entity_id: (Optional) ID of a specific event or trend this agent is managing.
    Returns:
        A dictionary representing the updated agent configuration or an error message.
    """
    existing_config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if not existing_config:
        return {"status": "error", "message": f"Agent configuration {agent_id} not found."}

    update_data = {k: v for k, v in locals().items() if v is not None and k not in ['agent_id', 'existing_config', 'update_data']}

    # Validate update data using Pydantic model
    try:
        validated_data = AgentConfigUpdateRequest(**update_data).dict(exclude_unset=True)
    except ValidationError as e:
        return {"status": "error", "message": str(e)}

    # Apply updates
    existing_config.update(validated_data)

    if update_couchdb_doc(AGENT_CONFIGS_DB, agent_id, existing_config):
        return {"status": "success", "agent_config": existing_config}
    else:
        return {"status": "error", "message": "Failed to update agent configuration."}

@mcp_tool(name="delete_agent_config", description="Deletes an agent configuration.")
def delete_agent_config(agent_id: str) -> dict:
    """
    Deletes a specific agent configuration.
    Args:
        agent_id: The GUID of the agent configuration to delete.
    Returns:
        A dictionary indicating success or failure.
    """
    config = fetch_from_couchdb(AGENT_CONFIGS_DB, agent_id)
    if not config:
        return {"status": "error", "message": f"Agent configuration {agent_id} not found."}

    if delete_from_couchdb(AGENT_CONFIGS_DB, agent_id, config["_rev"]):
        return {"status": "success", "message": f"Agent configuration {agent_id} deleted."}
    else:
        return {"status": "error", "message": "Failed to delete agent configuration."}
