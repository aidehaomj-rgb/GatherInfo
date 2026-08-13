"""Source config schemas."""
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, computed_field, field_serializer
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
    crawl_delay_seconds: int = Field(default=8, ge=0, le=3600)


class SourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    channel: str | None = None
    source_group: str | None = Field(default=None, min_length=1, max_length=80)
    is_active: bool | None = None
    base_url: str | None = None
    api_endpoint: str | None = None
    homepage_url: str | None = None
    api_key: str | None = None
    auth_config: dict | None = None
    rate_limit_rps: float | None = None
    max_retries: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, gt=0)
    max_items_per_run: int | None = Field(default=None, gt=0)
    default_keywords: list[str] | None = None
    default_categories: list[str] | None = None
    languages: list[str] | None = None
    country_focus: list[str] | None = None
    crawl_delay_seconds: int | None = Field(default=None, ge=0, le=3600)


class SourceComplianceReview(BaseModel):
    """Explicit operator attestation backed by recorded evidence URLs."""

    decision: Literal["approve_full", "approve_excerpt", "block"]
    robots_evidence: Literal["allowed", "api_required", "blocked"]
    terms_evidence: Literal[
        "allowed", "public_domain", "government_conditions",
        "open_government", "us_government", "blocked",
    ]
    discovery_urls: list[AnyHttpUrl] = Field(min_length=1, max_length=20)
    legal_basis: str = Field(min_length=10, max_length=2000)
    compliance_note: str = Field(min_length=20, max_length=4000)
    reviewed_by: str = Field(min_length=2, max_length=200)
    confirmed: bool


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
    legal_basis: str | None = None
    compliance_note: str | None = None
    verification_status: str = "unverified"
    discovery_urls: list[str] | None = None
    robots_status: str = "unverified"
    terms_status: str = "unverified"
    llm_ingest_allowed: bool = False
    origin_resolution_required: bool = True
    crawl_delay_seconds: int = 8
    verified_at: IsoDT = None
    compliance_reviewed_by: str | None = None
    compliance_snapshot: dict | None = None
    last_sync_at: IsoDT = None
    last_error: str | None = None
    items_collected: int = 0
    health_status: str = "unknown"
    health_checked_at: IsoDT = None
    health_detail: str | None = None
    created_at: IsoDT = None
    updated_at: IsoDT = None
    is_configured: bool = False
    model_config = {"from_attributes": True}

    @field_serializer("api_key")
    def hide_api_key(self, _value: str | None) -> None:
        """Source credentials are write-only and never leave the backend."""
        return None

    @computed_field
    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)
