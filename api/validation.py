"""
Input validation utilities for Moirai API
"""

import uuid
from enum import Enum
from typing import Any, Dict, Optional

import bleach
import validators
from pydantic import BaseModel, Field, HttpUrl, field_validator


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
    ISSUES = "issues"

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

    @field_validator("linked_entity_id")
    @classmethod
    def validate_linked_entity_id(cls, v: Optional[str]) -> Optional[str]:
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

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
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

    @field_validator("linked_entity_id")
    @classmethod
    def validate_linked_entity_id(cls, v: Optional[str]) -> Optional[str]:
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

    @field_validator("url")
    @classmethod
    def validate_feed_url(cls, v: HttpUrl) -> str:
        """Ensure URL is http/https only"""
        if not str(v).startswith(("http://", "https://")):
            raise ValueError("Only HTTP/HTTPS URLs are allowed")
        return str(v)

    @field_validator("title", "category")
    @classmethod
    def sanitize_text(cls, v: Optional[str]) -> Optional[str]:
        """Remove any HTML/script tags"""
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)


class FeedUpdateRequest(BaseModel):
    """Validation for feed updates"""

    title: str = Field(..., min_length=1, max_length=200)
    new_url: Optional[HttpUrl] = None  # Added field

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        return bleach.clean(v, tags=[], strip=True)

    @field_validator("new_url")
    @classmethod
    def validate_new_feed_url(cls, v: Optional[HttpUrl]) -> Optional[str]:
        if v is None:
            return v
        if not str(v).startswith(("http://", "https://")):
            raise ValueError("Only HTTP/HTTPS URLs are allowed for new_url")
        return str(v)


class EventCreateRequest(BaseModel):
    """Validation for event creation"""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=2000)
    article_links: list[str] = Field(default_factory=list, max_length=100)
    userspace: Optional[str] = None

    @field_validator("userspace")
    @classmethod
    def validate_userspace(cls, v: Optional[str]) -> Optional[str]:
        """Validate userspace is a valid UUID/GUID"""
        if v is None:
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("Userspace must be a valid UUID/GUID")

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return bleach.clean(v, tags=[], strip=True)

    @field_validator("article_links")
    @classmethod
    def validate_links(cls, v: list[str]) -> list[str]:
        """Validate article links are valid URLs"""
        for link in v:
            if not validators.url(link):
                raise ValueError(f"Invalid URL: {link}")
        return v


class EventUpdateRequest(BaseModel):
    """Validation for event updates"""

    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    article_links: Optional[list[str]] = Field(None, max_length=100)

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)

    @field_validator("article_links")
    @classmethod
    def validate_links(cls, v: Optional[list[str]]) -> Optional[list[str]]:
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
    event_ids: list[str] = Field(default_factory=list, max_length=50)
    userspace: Optional[str] = None

    @field_validator("userspace")
    @classmethod
    def validate_userspace(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("Userspace must be a valid UUID/GUID")

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return bleach.clean(v, tags=[], strip=True)


class TrendUpdateRequest(BaseModel):
    """Validation for trend updates"""

    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    event_ids: Optional[list[str]] = Field(None, max_length=50)

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)


class ConfigUpdateRequest(BaseModel):
    """Validation for config updates"""

    allow_public_read: Optional[bool] = None
    iteration_interval: Optional[int] = Field(
        None, ge=0, le=86400
    )  # 0 disables, 1 minute to 24 hours
    google_client_id: Optional[str] = None
    entra_client_id: Optional[str] = None
    entra_tenant_id: Optional[str] = None
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None

    @field_validator("iteration_interval")
    @classmethod
    def validate_interval(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v != 0 and v < 60:
            raise ValueError("Iteration interval must be at least 60 seconds")
        return v


def validate_userspace_param(userspace: str) -> str:
    """Validate userspace query parameter"""
    if not userspace:
        return userspace
    try:
        uuid.UUID(userspace)
        return userspace
    except ValueError:
        raise ValueError("Invalid userspace GUID format")


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
