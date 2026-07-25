"""GatherInfo model enums."""

import enum


class SourceChannel(str, enum.Enum):
    OFFICIAL = "official"
    RSS = "rss"
    COMMERCIAL = "commercial"
    WEB_SCRAPE = "web_scrape"
    API_SEARCH = "api_search"
    AI_RESEARCH = "ai_research"
    JSON_API = "json_api"
    SOCIAL = "social"
    DEEP_WEB = "deepweb"
    MANUAL = "manual"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ItemStatus(str, enum.Enum):
    RAW = "raw"
    TAGGED = "tagged"
    ENRICHED = "enriched"
    ARCHIVED = "archived"
    DISCARDED = "discarded"
