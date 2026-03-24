"""
Input validation utilities for Moirai API
"""

import re
import uuid
from enum import Enum
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import bleach
import validators
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


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


def _validate_uuid(value: str, field_label: str) -> str:
    try:
        uuid.UUID(value)
        return value
    except ValueError as exc:
        raise ValueError(f"{field_label} must be a valid UUID/GUID") from exc


def _validate_optional_uuid(value: Optional[str], field_label: str) -> Optional[str]:
    if value is None:
        return value
    return _validate_uuid(value, field_label)


def _sanitize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    return bleach.clean(value, tags=[], strip=True)


def _sanitize_text(value: str) -> str:
    return bleach.clean(value, tags=[], strip=True)


def _validate_http_or_https_url(value: str, error_message: str) -> str:
    if urlparse(value).scheme not in {"http", "https"}:
        raise ValueError(error_message)
    return value


def _ensure_valid_url_list(values: list[str]) -> None:
    for link in values:
        if not validators.url(link):
            raise ValueError(f"Invalid URL: {link}")


# Valid schedule interval format: a positive (non-zero) integer followed by s/m/h/d
SCHEDULE_INTERVAL_PATTERN = re.compile(r"^[1-9]\d*[smhd]$")


def _validate_schedule_interval_format(value: str) -> str:
    """Validate that a schedule_interval string matches the expected format (e.g. '30m', '2h')."""
    if not SCHEDULE_INTERVAL_PATTERN.match(value):
        raise ValueError(
            f"Invalid schedule_interval '{value}'. "
            "Must be a positive integer followed by a unit: s (seconds), "
            "m (minutes), h (hours), or d (days). Example: '30m', '2h', '1d'."
        )
    return value


# Allowlist of permitted agent logic modules.
# Single source of truth shared by API validation, MCP layer, orchestrator, and UI.
ALLOWED_LOGIC_MODULES: list[str] = [
    "tasks.agent_logic.create_event_from_articles",
    "tasks.agent_logic.add_articles_to_event",
    "tasks.agent_logic.check_event_staleness",
]


def _validate_logic_module_value(v: str) -> str:
    """Reject logic_module values not in the allowlist.

    Shared by AgentConfigBase and AgentConfigUpdateRequest to avoid
    duplicating the same validation logic in both classes.
    """
    if v not in ALLOWED_LOGIC_MODULES:
        raise ValueError(
            f"logic_module '{v}' is not permitted. "
            f"Allowed values: {ALLOWED_LOGIC_MODULES}"
        )
    return v


class AgentConfigBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    status: AgentStatus = Field(AgentStatus.ACTIVE)
    trigger_type: AgentTriggerType
    schedule_interval: Optional[str] = Field(
        None, description="e.g., '30m', '2h', '1d' (integer + unit s/m/h/d)"
    )
    target_db: AgentTargetDB
    logic_module: str = Field(
        ...,
        description=(
            "Python module path for agent logic. "
            f"Allowed values: {ALLOWED_LOGIC_MODULES}"
        ),
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

    @field_validator("schedule_interval")
    @classmethod
    def validate_schedule_interval(cls, v: Optional[str]) -> Optional[str]:
        """Validate the format of schedule_interval when provided."""
        if v is None:
            return v
        return _validate_schedule_interval_format(v)

    @field_validator("logic_module")
    @classmethod
    def validate_logic_module(cls, v: str) -> str:
        """Reject logic_module values not in the allowlist at write time."""
        return _validate_logic_module_value(v)

    @field_validator("linked_entity_id")
    @classmethod
    def validate_linked_entity_id(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_uuid(v, "Linked entity ID")

    @model_validator(mode="after")
    def validate_schedule_cross_fields(self) -> "AgentConfigBase":
        """Enforce cross-field rules between trigger_type and schedule_interval."""
        if self.trigger_type == AgentTriggerType.SCHEDULED and not self.schedule_interval:
            raise ValueError(
                "schedule_interval is required when trigger_type is 'scheduled'."
            )
        if self.trigger_type == AgentTriggerType.ON_NEW_ARTICLE and self.schedule_interval:
            raise ValueError(
                "schedule_interval must not be set when trigger_type is 'on_new_article'."
            )
        return self


class AgentConfigCreateRequest(AgentConfigBase):
    userspace: str = Field(..., description="Userspace GUID for this agent configuration")
    owner_user_id: str = Field(
        ..., description="The user who owns credentials for this agent (GUID)"
    )

    @field_validator("userspace")
    @classmethod
    def validate_userspace(cls, v: str) -> str:
        return _validate_uuid(v, "Userspace")

    @field_validator("owner_user_id")
    @classmethod
    def validate_owner_user_id(cls, v: str) -> str:
        return _validate_uuid(v, "Owner user ID")


class AgentConfigUpdateRequest(BaseModel):
    """Partial update model for agent configs — all fields are optional.

    Per-field format validators are applied where applicable.  Cross-field
    validation (e.g. trigger_type vs schedule_interval consistency) requires
    the full current document state and is therefore performed in
    api/agent_routes.py after merging the update into the existing doc.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[AgentStatus] = None
    userspace: Optional[str] = None
    owner_user_id: Optional[str] = None
    trigger_type: Optional[AgentTriggerType] = None
    schedule_interval: Optional[str] = Field(
        None, description="e.g., '30m', '2h', '1d' (positive integer + unit s/m/h/d)"
    )
    target_db: Optional[AgentTargetDB] = None
    logic_module: Optional[str] = Field(
        None,
        description=(
            "Python module path for agent logic. "
            f"Allowed values: {ALLOWED_LOGIC_MODULES}"
        ),
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

    @field_validator("schedule_interval")
    @classmethod
    def validate_schedule_interval(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_schedule_interval_format(v)

    @field_validator("logic_module")
    @classmethod
    def validate_logic_module(cls, v: Optional[str]) -> Optional[str]:
        """Reject logic_module values not in the allowlist at write time."""
        if v is None:
            return v
        return _validate_logic_module_value(v)

    @field_validator("linked_entity_id")
    @classmethod
    def validate_linked_entity_id(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_uuid(v, "Linked entity ID")

    @field_validator("userspace")
    @classmethod
    def validate_userspace(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_uuid(v, "Userspace")

    @field_validator("owner_user_id")
    @classmethod
    def validate_owner_user_id(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_uuid(v, "Owner user ID")


class FeedCreateRequest(BaseModel):
    """Validation for feed creation"""

    url: HttpUrl
    title: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)

    @field_validator("url")
    @classmethod
    def validate_feed_url(cls, v: HttpUrl) -> str:
        """Ensure URL is http/https only"""
        return _validate_http_or_https_url(str(v), "Only HTTP/HTTPS URLs are allowed")

    @field_validator("title", "category")
    @classmethod
    def sanitize_text(cls, v: Optional[str]) -> Optional[str]:
        """Remove any HTML/script tags"""
        return _sanitize_optional_text(v)


class FeedUpdateRequest(BaseModel):
    """Validation for feed updates"""

    title: str = Field(..., min_length=1, max_length=200)
    new_url: Optional[HttpUrl] = None  # Added field

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        return _sanitize_text(v)

    @field_validator("new_url")
    @classmethod
    def validate_new_feed_url(cls, v: Optional[HttpUrl]) -> Optional[str]:
        if v is None:
            return v
        return _validate_http_or_https_url(
            str(v), "Only HTTP/HTTPS URLs are allowed for new_url"
        )


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
        return _validate_optional_uuid(v, "Userspace")

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return _sanitize_text(v)

    @field_validator("article_links")
    @classmethod
    def validate_links(cls, v: list[str]) -> list[str]:
        """Validate article links are valid URLs"""
        _ensure_valid_url_list(v)
        return v


class EventUpdateRequest(BaseModel):
    """Validation for event updates"""

    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    article_links: Optional[list[str]] = Field(None, max_length=100)

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: Optional[str]) -> Optional[str]:
        return _sanitize_optional_text(v)

    @field_validator("article_links")
    @classmethod
    def validate_links(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        _ensure_valid_url_list(v)
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
        return _validate_optional_uuid(v, "Userspace")

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return _sanitize_text(v)


class TrendUpdateRequest(BaseModel):
    """Validation for trend updates"""

    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    event_ids: Optional[list[str]] = Field(None, max_length=50)

    @field_validator("title", "description")
    @classmethod
    def sanitize_text(cls, v: Optional[str]) -> Optional[str]:
        return _sanitize_optional_text(v)


class ConfigUpdateRequest(BaseModel):
    """Validation for config updates"""

    allow_public_read: Optional[bool] = None
    chat_export_verbose: Optional[bool] = None
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


class IssueCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=2000)
    article_links: list[str] = Field(..., min_length=1)
    longevity: str = Field("transient")

    @field_validator("name", "description")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return _sanitize_text(v)

    @field_validator("longevity")
    @classmethod
    def validate_longevity(cls, v: str) -> str:
        if v not in {"transient", "temporal", "epic"}:
            raise ValueError("longevity must be one of: transient, temporal, epic")
        return v

    @field_validator("article_links")
    @classmethod
    def validate_links(cls, v: list[str]) -> list[str]:
        _ensure_valid_url_list(v)
        return v


class LLMConfigRequest(BaseModel):
    """LLM provider configuration stored on a userspace."""

    provider: str = Field("ollama", description="ollama | openai | gemini")
    model: str = Field("llama3.1", min_length=1, max_length=200)
    openai_api_key: Optional[str] = Field(None, max_length=500)
    gemini_api_key: Optional[str] = Field(None, max_length=500)
    ollama_endpoint: Optional[str] = Field(None, max_length=500)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"ollama", "openai", "gemini"}
        if v not in allowed:
            raise ValueError(f"provider must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("model")
    @classmethod
    def sanitize_model(cls, v: str) -> str:
        return _sanitize_text(v)

    @field_validator("ollama_endpoint")
    @classmethod
    def validate_ollama_endpoint(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_http_or_https_url(v, "ollama_endpoint must be an HTTP/HTTPS URL")


class UserspaceCreateRequest(BaseModel):
    """Validation for creating a new userspace."""

    name: str = Field(..., min_length=1, max_length=100)
    llm_config: Optional[LLMConfigRequest] = None
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        return _sanitize_text(v)


class UserspaceUpdateRequest(BaseModel):
    """Partial update for a userspace — all fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    llm_config: Optional[LLMConfigRequest] = None
    preferences: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        return _sanitize_optional_text(v)


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
