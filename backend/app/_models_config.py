"""Topic, ScheduleConfig, SystemConfig, ModelConfig, Report, SearchToolConfig."""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, JSON, Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Topic(Base):
    """Collection topic — drives automated collection with keywords, sources, schedule."""
    __tablename__ = "topics"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    category_id = Column(String(80), nullable=True)
    keywords = Column(JSON, nullable=True)
    synonyms = Column(JSON, nullable=True)
    exclude_keywords = Column(JSON, nullable=True)
    categories = Column(JSON, nullable=True)
    focus_countries = Column(JSON, nullable=True)
    focus_languages = Column(JSON, nullable=True)
    target_urls = Column(JSON, nullable=True)
    is_scheduled = Column(Boolean, default=False)
    keyword_tags = Column(JSON, nullable=True)
    auto_tag_rules = Column(JSON, nullable=True)
    source_ids = Column(JSON, nullable=True)
    collection_model_ids = Column(JSON, nullable=True)

    schedule_cron = Column(String(100), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    collect_window_days = Column(Integer, default=7)

    auto_report = Column(Boolean, default=False)
    auto_report_model_id = Column(String(80), nullable=True)
    auto_report_type = Column(String(20), default="analytical")
    description_prompt = Column(Text, nullable=True)
    ai_research_model_id = Column(String(80), nullable=True)

    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_collection_run_id = Column(String(80), nullable=True)
    last_error = Column(Text, nullable=True)

    total_items_collected = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    runs = relationship("CollectionRun", back_populates="topic")

    def __repr__(self):
        return f"<Topic id={self.id} name={self.name}>"


class ScheduleConfig(Base):
    """Global schedule configuration — binds topics, sources, and a cron expression."""
    __tablename__ = "schedule_configs"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)

    topic_ids = Column(JSON, nullable=True)
    source_ids = Column(JSON, nullable=True)

    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    def __repr__(self):
        return f"<ScheduleConfig id={self.id} cron={self.cron_expression}>"


class ModelConfig(Base):
    """AI model configuration for report generation and item translation."""
    __tablename__ = "model_configs"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    provider = Column(String(50), nullable=False, default="ollama")
    base_url = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    model_name = Column(String(200), nullable=False, default="")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)
    top_p = Column(Float, default=0.9)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    def __repr__(self):
        return f"<ModelConfig id={self.id} name={self.name}>"


class Report(Base):
    """Auto-generated report from collected items under a topic."""
    __tablename__ = "reports"

    id = Column(String(80), primary_key=True)
    topic_id = Column(String(80), ForeignKey("topics.id"), nullable=False)
    title = Column(String(500), nullable=False)
    report_type = Column(String(20), default="analytical")
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    model_id = Column(String(80), nullable=True)
    tokens_used = Column(Integer, default=0)
    item_count = Column(Integer, default=0)
    item_ids = Column(JSON, nullable=True)
    error_log = Column(Text, nullable=True)

    collection_run_id = Column(String(80), nullable=True)
    date_range_start = Column(DateTime(timezone=True), nullable=True)
    date_range_end = Column(DateTime(timezone=True), nullable=True)

    output_files = Column(JSON, nullable=True)
    output_dir = Column(String(800), nullable=True)

    generated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)

    def __repr__(self):
        return f"<Report id={self.id} topic={self.topic_id} status={self.status}>"


class SearchToolConfig(Base):
    """Configurable search/collection tool definitions."""
    __tablename__ = "search_tool_configs"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    tool_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    config_json = Column(JSON, nullable=True)
    api_key_ref = Column(String(200), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    def __repr__(self):
        return f"<SearchToolConfig id={self.id} type={self.tool_type}>"


class SystemConfig(Base):
    """Global system settings — single-row table (id='global')."""
    __tablename__ = "system_config"

    id = Column(String(20), primary_key=True, default="global")
    report_title_format = Column(String(300), default="{topic}_情报报告_{date}")
    report_output_dir = Column(String(800), nullable=True)
    report_dir_pattern = Column(String(100), default="%Y-%m-%d")
    report_formats = Column(JSON, default=lambda: ["docx", "pdf"])
    featured_item_ids = Column(JSON, nullable=True)
    featured_updated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    def __repr__(self):
        return f"<SystemConfig id={self.id}>"
