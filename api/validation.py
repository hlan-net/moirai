"""
Input validation utilities for Moirai API
"""

from typing import Optional, Dict, Any
from enum import Enum  # Import Enum
from pydantic import BaseModel, Field, validator, HttpUrl
import validators
import bleach
import uuid


# Enums for AgentConfig
class AgentTriggerType(str, Enum):
    ON_NEW_ARTICLE = "on_new_article"
    SCHEDULED = "scheduled"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class AgentTargetDB(str, Enum):
    ARTICLES = "articles"
    EVENTS = "events"
    TRENDS = "trends"


class AgentConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    status: AgentStatus = Field(AgentStatus.ACTIVE)
    trigger_type: AgentTriggerType
    schedule_interval: Optional[str] = Field(
        None, description="e.g., '1h', '1d', 'every 30m'"
    )
    target_db: AgentTargetDB
    logic_module: str = Field(
        ...,
        description="Reference to Python module/function (e.g., 'tasks.agent_logic.create_event')",
    )
    llm_model_config: Optional[Dict[str, Any]] = Field(
        None, description="LLM specific configs like model_name, provider, etc."
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None, description="User-defined parameters for agent logic"
    )
    linked_entity_id: Optional[str] = Field(
        None, description="ID of a specific event or trend this agent is managing"
    )

    @validator("linked_entity_id")
    def validate_linked_entity_id(cls, v):
        if v is None:
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("Linked entity ID must be a valid UUID/GUID")


class AgentConfigCreateRequest(AgentConfigBase):
    user_id: str = Field(
        ..., description="The user who created this configuration (GUID)"
    )

    @validator("user_id")
    def validate_user_id(cls, v):
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("User ID must be a valid UUID/GUID")


class AgentConfigUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[AgentStatus] = None
    trigger_type: Optional[AgentTriggerType] = None
    schedule_interval: Optional[str] = Field(
        None, description="e.g., '1h', '1d', 'every 30m'"
    )
    target_db: Optional[AgentTargetDB] = None
    logic_module: Optional[str] = Field(
        None,
        description="Reference to Python module/function (e.g., 'tasks.agent_logic.create_event')",
    )
    llm_model_config: Optional[Dict[str, Any]] = Field(
        None, description="LLM specific configs like model_name, provider, etc."
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None, description="User-defined parameters for agent logic"
    )
    linked_entity_id: Optional[str] = Field(
        None, description="ID of a specific event or trend this agent is managing"
    )

    @validator("linked_entity_id")
    def validate_linked_entity_id(cls, v):
        if v is None:
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("Linked entity ID must be a valid UUID/GUID")


class FeedCreateRequest(BaseModel):
    """Validation for feed creation"""

    url: HttpUrl
    title: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)

    @validator("url")
    def validate_feed_url(cls, v):
        """Ensure URL is http/https only"""
        if not str(v).startswith(("http://", "https://")):
            raise ValueError("Only HTTP/HTTPS URLs are allowed")
        return str(v)

    @validator("title", "category")
    def sanitize_text(cls, v):
        """Remove any HTML/script tags"""
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)


class FeedUpdateRequest(BaseModel):
    """Validation for feed updates"""

    title: str = Field(..., min_length=1, max_length=200)
    new_url: Optional[HttpUrl] = None  # Added field

    @validator("title")
    def sanitize_title(cls, v):
        return bleach.clean(v, tags=[], strip=True)

    @validator("new_url")  # New validator for new_url
    def validate_new_feed_url(cls, v):
        if v is None:
            return v
        if not str(v).startswith(("http://", "https://")):
            raise ValueError("Only HTTP/HTTPS URLs are allowed for new_url")
        return str(v)


class EventCreateRequest(BaseModel):
    """Validation for event creation"""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=2000)
    article_links: list[str] = Field(default_factory=list, max_items=100)
    namespace: Optional[str] = None

    @validator("namespace")
    def validate_namespace(cls, v):
        """Validate namespace is a valid UUID/GUID"""
        if v is None:
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("Namespace must be a valid UUID/GUID")

    @validator("title", "description")
    def sanitize_text(cls, v):
        return bleach.clean(v, tags=[], strip=True)

    @validator("article_links")
    def validate_links(cls, v):
        """Validate article links are valid URLs"""
        for link in v:
            if not validators.url(link):
                raise ValueError(f"Invalid URL: {link}")
        return v


class EventUpdateRequest(BaseModel):
    """Validation for event updates"""

    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    article_links: Optional[list[str]] = Field(None, max_items=100)

    @validator("title", "description")
    def sanitize_text(cls, v):
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)

    @validator("article_links")
    def validate_links(cls, v):
        if v is None:
            return v
        for link in v:
            if not validators.url(link):
                raise ValueError(f"Invalid URL: {link}")
        return v


class TrendCreateRequest(BaseModel):
    """Validation for trend creation"""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=2000)
    event_ids: list[str] = Field(default_factory=list, max_items=50)
    namespace: Optional[str] = None

    @validator("namespace")
    def validate_namespace(cls, v):
        if v is None:
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("Namespace must be a valid UUID/GUID")

    @validator("title", "description")
    def sanitize_text(cls, v):
        return bleach.clean(v, tags=[], strip=True)


class TrendUpdateRequest(BaseModel):
    """Validation for trend updates"""

    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    event_ids: Optional[list[str]] = Field(None, max_items=50)

    @validator("title", "description")
    def sanitize_text(cls, v):
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)


class ConfigUpdateRequest(BaseModel):
    """Validation for config updates"""

    allow_public_read: Optional[bool] = None
    iteration_interval: Optional[int] = Field(
        None, ge=60, le=86400
    )  # 1 minute to 24 hours
    google_client_id: Optional[str] = None
    entra_client_id: Optional[str] = None
    entra_tenant_id: Optional[str] = None
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None

    @validator("iteration_interval")
    def validate_interval(cls, v):
        if v is not None and v < 60:
            raise ValueError("Iteration interval must be at least 60 seconds")
        return v


def validate_namespace_param(namespace: str) -> str:
    """Validate namespace query parameter"""
    if not namespace:
        return namespace
    try:
        uuid.UUID(namespace)
        return namespace
    except ValueError:
        raise ValueError("Invalid namespace GUID format")


def sanitize_html_content(html: str, max_length: int = 10000) -> str:
    """
    Sanitize HTML content from RSS feeds
    Allows safe HTML tags but removes scripts and dangerous attributes
    """
    if not html:
        return ""

    # Truncate if too long
    html = html[:max_length]

    # Allow only safe tags and attributes
    allowed_tags = [
        "p",
        "br",
        "strong",
        "em",
        "u",
        "a",
        "ul",
        "ol",
        "li",
        "blockquote",
        "code",
        "pre",
    ]
    allowed_attrs = {"a": ["href", "title"]}

    cleaned = bleach.clean(
        html, tags=allowed_tags, attributes=allowed_attrs, strip=True
    )

    return cleaned
