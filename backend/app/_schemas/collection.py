"""Collection, item, and batch schemas."""
from pydantic import BaseModel, Field
from .common import IsoDT


class CollectRequest(BaseModel):
    topic_id: str | None = None
    source_id: str | None = None
    source_ids: list[str] | None = None
    keywords: list[str] | None = None
    research_prompt: str | None = None
    research_model_id: str | None = None


class RunOut(BaseModel):
    id: str
    source_id: str
    topic_id: str | None = None
    status: str
    items_found: int = 0
    items_new: int = 0
    items_failed: int = 0
    started_at: IsoDT = None
    completed_at: IsoDT = None
    duration_ms: int | None = None
    error_log: list | None = None
    model_config = {"from_attributes": True}


class CollectResultOut(BaseModel):
    run: RunOut | None = None
    total_items: int = 0
    items_new: int = 0
    errors: list[str] | None = None


class ItemOut(BaseModel):
    id: str
    source_id: str
    run_id: str | None = None
    topic_id: str | None = None
    title: str
    title_zh: str | None = None
    content: str | None = None
    content_zh: str | None = None
    summary: str | None = None
    summary_zh: str | None = None
    url: str | None = None
    language: str | None = None
    translation_status: str | None = None
    enforcement_review: dict | None = None
    quality_review: dict | None = None
    category: str | None = None
    tags: list[dict] = []
    entities: dict | None = None
    quality_score: float = 0.0
    relevance_score: float = 0.0
    status: str = "raw"
    collected_at: IsoDT = None
    published_at: IsoDT = None
    fetched_at: IsoDT = None
    model_config = {"from_attributes": True}


class ItemListOut(BaseModel):
    items: list[ItemOut] = []
    total: int = 0
    page: int = 1
    page_size: int = 50


class ItemDeleteRequest(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=500)


class ItemTranslateRequest(BaseModel):
    item_ids: list[str] = Field(default_factory=list, max_length=100)


class ItemQualityReviewRequest(BaseModel):
    item_ids: list[str] = Field(default_factory=list, max_length=500)
    limit: int = Field(default=100, ge=1, le=500)


class BatchRunOut(BaseModel):
    id: str
    source_id: str
    topic_id: str | None = None
    status: str
    items_new: int = 0
    items_found: int = 0
    items_failed: int = 0
    started_at: IsoDT = None
    completed_at: IsoDT = None
    duration_ms: int | None = None
    error_log: list | None = None
    source_name: str | None = None


class BatchOut(BaseModel):
    batch_id: str
    topic_id: str | None = None
    topic_name: str | None = None
    batch_label: str | None = None
    status: str
    total_items: int = 0
    total_new: int = 0
    started_at: IsoDT = None
    completed_at: IsoDT = None
    source_count: int = 0
    runs: list[BatchRunOut] = []


class ActiveRunOut(BaseModel):
    id: str
    source_id: str
    source_name: str | None = None
    topic_id: str | None = None
    topic_name: str | None = None
    status: str
    keywords_used: list[str] = []
    items_found: int = 0
    items_new: int = 0
    started_at: IsoDT = None
    duration_seconds: int | None = None
    batch_id: str | None = None
