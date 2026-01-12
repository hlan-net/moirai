"""
Input validation utilities for Moirai API
"""
from typing import Optional
from pydantic import BaseModel, Field, validator, HttpUrl
import validators
import bleach
import uuid


class FeedCreateRequest(BaseModel):
    """Validation for feed creation"""
    url: HttpUrl
    title: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)
    
    @validator('url')
    def validate_feed_url(cls, v):
        """Ensure URL is http/https only"""
        if not str(v).startswith(('http://', 'https://')):
            raise ValueError('Only HTTP/HTTPS URLs are allowed')
        return str(v)
    
    @validator('title', 'category')
    def sanitize_text(cls, v):
        """Remove any HTML/script tags"""
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)


class FeedUpdateRequest(BaseModel):
    """Validation for feed updates"""
    title: str = Field(..., min_length=1, max_length=200)
    
    @validator('title')
    def sanitize_title(cls, v):
        return bleach.clean(v, tags=[], strip=True)


class EventCreateRequest(BaseModel):
    """Validation for event creation"""
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=2000)
    article_links: list[str] = Field(default_factory=list, max_items=100)
    namespace: Optional[str] = None
    
    @validator('namespace')
    def validate_namespace(cls, v):
        """Validate namespace is a valid UUID/GUID"""
        if v is None:
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Namespace must be a valid UUID/GUID')
    
    @validator('title', 'description')
    def sanitize_text(cls, v):
        return bleach.clean(v, tags=[], strip=True)
    
    @validator('article_links')
    def validate_links(cls, v):
        """Validate article links are valid URLs"""
        for link in v:
            if not validators.url(link):
                raise ValueError(f'Invalid URL: {link}')
        return v


class EventUpdateRequest(BaseModel):
    """Validation for event updates"""
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    article_links: Optional[list[str]] = Field(None, max_items=100)
    
    @validator('title', 'description')
    def sanitize_text(cls, v):
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)
    
    @validator('article_links')
    def validate_links(cls, v):
        if v is None:
            return v
        for link in v:
            if not validators.url(link):
                raise ValueError(f'Invalid URL: {link}')
        return v


class TrendCreateRequest(BaseModel):
    """Validation for trend creation"""
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(..., min_length=1, max_length=2000)
    event_ids: list[str] = Field(default_factory=list, max_items=50)
    namespace: Optional[str] = None
    
    @validator('namespace')
    def validate_namespace(cls, v):
        if v is None:
            return v
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Namespace must be a valid UUID/GUID')
    
    @validator('title', 'description')
    def sanitize_text(cls, v):
        return bleach.clean(v, tags=[], strip=True)


class TrendUpdateRequest(BaseModel):
    """Validation for trend updates"""
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    event_ids: Optional[list[str]] = Field(None, max_items=50)
    
    @validator('title', 'description')
    def sanitize_text(cls, v):
        if v is None:
            return v
        return bleach.clean(v, tags=[], strip=True)


class ConfigUpdateRequest(BaseModel):
    """Validation for config updates"""
    allow_public_read: Optional[bool] = None
    iteration_interval: Optional[int] = Field(None, ge=60, le=86400)  # 1 minute to 24 hours
    
    @validator('iteration_interval')
    def validate_interval(cls, v):
        if v is not None and v < 60:
            raise ValueError('Iteration interval must be at least 60 seconds')
        return v


def validate_namespace_param(namespace: str) -> str:
    """Validate namespace query parameter"""
    if not namespace:
        return namespace
    try:
        uuid.UUID(namespace)
        return namespace
    except ValueError:
        raise ValueError('Invalid namespace GUID format')


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
    allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre']
    allowed_attrs = {'a': ['href', 'title']}
    
    cleaned = bleach.clean(
        html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        strip=True
    )
    
    return cleaned
