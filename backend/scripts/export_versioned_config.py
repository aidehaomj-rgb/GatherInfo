"""Export reviewable application configuration without local credentials."""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    PromptTemplate,
    SearchToolConfig,
    SourceConfig,
    Topic,
)

OUTPUT_DIR = ROOT / "config" / "snapshots"
SECRET_NAMES = {
    "api_key",
    "access_token",
    "authorization",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}

CATEGORY_FIELDS = ("id", "name", "description")
SOURCE_FIELDS = (
    "id", "name", "description", "channel", "source_group", "is_active",
    "is_configured", "base_url", "api_endpoint", "homepage_url", "api_key_ref",
    "auth_config", "rate_limit_rps", "max_retries", "timeout_seconds",
    "max_items_per_run", "default_keywords", "default_categories", "languages",
    "country_focus", "legal_basis", "compliance_note",
)
PROMPT_FIELDS = ("id", "name", "description", "content", "is_active")
TOPIC_FIELDS = (
    "id", "name", "description", "is_active", "category_id", "keywords",
    "synonyms", "exclude_keywords", "categories", "focus_countries",
    "focus_languages", "target_urls", "is_scheduled", "keyword_tags",
    "auto_tag_rules", "source_ids", "collection_model_ids", "prompt_template_ids",
    "schedule_cron", "collect_window_days", "auto_report", "auto_report_model_id",
    "auto_report_type", "description_prompt", "ai_research_model_id",
)
TOOL_FIELDS = (
    "id", "name", "tool_type", "is_active", "config_json", "api_key_ref",
    "is_default",
)


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SECRET_NAMES or normalized.endswith("_secret") or normalized.endswith("_token")


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "${REDACTED}" if _is_secret_key(str(key)) and item else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def serialize_rows(rows: list[Any], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        sanitize({field: getattr(row, field) for field in fields})
        for row in sorted(rows, key=lambda item: item.id)
    ]


def write_snapshot(filename: str, rows: list[Any], fields: tuple[str, ...]) -> None:
    payload = serialize_rows(rows, fields)
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{filename}: {len(payload)}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        write_snapshot("collection_categories.json", db.query(Category).all(), CATEGORY_FIELDS)
        write_snapshot("information_sources.json", db.query(SourceConfig).all(), SOURCE_FIELDS)
        write_snapshot("prompt_templates.json", db.query(PromptTemplate).all(), PROMPT_FIELDS)
        write_snapshot("topics.json", db.query(Topic).all(), TOPIC_FIELDS)
        write_snapshot("mcp_tools.json", db.query(SearchToolConfig).all(), TOOL_FIELDS)


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
