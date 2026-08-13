"""Source config schemas."""
from pydantic import BaseModel, Field
from .common import IsoDT


class SourceCreate(BaseModel):
    id: str | None = Field(default=None, max_length=80, description="留空则由后端从 name 自动生成")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    channel: str = Field(description="official | rss | commercial | web_scrape | api_search | ai_research | social | deepweb | manual")
    source_group: str = Field(default="other", min_length=1, max_length=80)
    is_active: bool = True
    base_url: str | None = None
    api_endpoint: str | None = None
    homepage_url: str | None = None
    api_key_ref: str | None = None
    api_key: str | None = None
    auth_config: dict | None = None
    rate_limit_rps: float = Field(default=1.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    timeout_seconds: int = Field(default=30, gt=0)
    max_items_per_run: int = Field(default=100, gt=0)
    default_keywords: list[str] | None = None
    default_categories: list[str] | None = None
    languages: list[str] | None = None
    country_focus: list[str] | None = None
    legal_basis: str | None = None
    compliance_note: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    channel: str | None = None
    source_group: str | None = Field(default=None, min_length=1, max_length=80)
    is_active: bool | None = None
    base_url: str | None = None
    api_endpoint: str | None = None
    homepage_url: str | None = None
    api_key_ref: str | None = None
    api_key: str | None = None
    auth_config: dict | None = None
    rate_limit_rps: float | None = None
    max_retries: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
    max_items_per_run: int | None = Field(default=None, gt=0)
    default_keywords: list[str] | None = None
    default_categories: list[str] | None = None
    languages: list[str] | None = None


class SourceOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    channel: str
    source_group: str = "other"
    is_active: bool
    base_url: str | None = None
    api_endpoint: str | None = None
    homepage_url: str | None = None
    api_key: str | None = None
    rate_limit_rps: float = 1.0
    timeout_seconds: int = 30
    max_items_per_run: int = 100
    default_keywords: list | None = None
    default_categories: list | None = None
    languages: list | None = None
    country_focus: list | None = None
    last_sync_at: IsoDT = None
    last_error: str | None = None
    items_collected: int = 0
    created_at: IsoDT = None
    updated_at: IsoDT = None
    is_configured: bool = False
    model_config = {"from_attributes": True}
