"""CollectionRun, CollectedItem, Tag — collection execution and item models."""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Float, JSON, Boolean,
    ForeignKey, Table,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.database import Base
from app._models_enums import JobStatus, ItemStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── Item ↔ Tag (many-to-many) ────────────────────────────────────────────────

item_tags = Table(
    "item_tags",
    Base.metadata,
    Column("item_id", String(120), ForeignKey("collected_items.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(80), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class ItemTopicMembership(Base):
    """Auditable many-to-many topic membership for globally deduplicated items."""
    __tablename__ = "item_topic_memberships"

    item_id = Column(
        String(120), ForeignKey("collected_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    topic_id = Column(
        String(80), ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    )
    first_run_id = Column(String(80), nullable=True)
    last_run_id = Column(String(80), nullable=True)
    relevance_score = Column(Float, nullable=True)
    relevance_tier = Column(String(30), nullable=True)
    evidence_grade = Column(String(10), nullable=True)
    customs_value = Column(String(40), nullable=True)
    information_type = Column(String(40), nullable=True)
    relevance_metadata = Column(JSON, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=_utc_now)
    last_seen_at = Column(DateTime(timezone=True), default=_utc_now)


class Tag(Base):
    """Structured dimension tag with namespace:value pattern."""
    __tablename__ = "tags"

    id = Column(String(80), primary_key=True)
    namespace = Column(String(50), nullable=False, index=True)
    value = Column(String(200), nullable=False)
    label = Column(String(200), nullable=True)
    color = Column(String(20), nullable=True)
    icon = Column(String(40), nullable=True)
    extra = Column(JSON, nullable=True)

    item_count = Column(Integer, default=0)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)

    items = relationship("CollectedItem", secondary=item_tags, back_populates="tags", lazy="selectin")

    def __repr__(self):
        return f"<Tag {self.id}>"


class CollectionRun(Base):
    """每次采集的执行记录。"""
    __tablename__ = "collection_runs"

    id = Column(String(80), primary_key=True)
    source_id = Column(String(80), ForeignKey("source_configs.id"), nullable=False)
    topic_id = Column(String(80), ForeignKey("topics.id"), nullable=True)
    job_id = Column(String(80), nullable=True, index=True)

    status = Column(String(20), default="pending")
    batch_id = Column(String(80), nullable=True, index=True)
    keywords_used = Column(JSON, nullable=True)

    # Metrics
    items_found = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    items_discovered = Column(Integer, default=0)
    items_date_rejected = Column(Integer, default=0)
    items_topic_rejected = Column(Integer, default=0)
    items_quality_rejected = Column(Integer, default=0)
    items_reused = Column(Integer, default=0)
    items_duplicate = Column(Integer, default=0)
    model_failures = Column(Integer, default=0)
    source_failures = Column(Integer, default=0)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Information time window applied during this run (by item published_at)
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_end = Column(DateTime(timezone=True), nullable=True)

    # Diagnostics
    error_log = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    progress_events = Column(JSON, nullable=True)

    # 本次采集结果明细：
    #   duplicate_items — 与本地库比对后判定为“重复”的信息（保留标题/链接，供任务查看展示）
    #   source_verdict  — 信息源结论（可连接/可爬取/可下载/语言类型）
    duplicate_items = Column(JSON, nullable=True)
    source_verdict = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utc_now)

    # Relationships
    source = relationship("SourceConfig", back_populates="runs")
    topic = relationship("Topic", back_populates="runs")

    def __repr__(self):
        return f"<CollectionRun id={self.id} status={self.status}>"


class CollectionBatch(Base):
    """Persistent audit record for one topic's bounded collection loop."""
    __tablename__ = "collection_batches"

    id = Column(String(80), primary_key=True)
    topic_id = Column(String(80), ForeignKey("topics.id"), nullable=True, index=True)
    status = Column(String(20), default="pending", nullable=True, index=True)
    current_round = Column(Integer, default=0, nullable=True)
    max_rounds = Column(Integer, default=2, nullable=True)
    target = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    acceptance = Column(JSON, nullable=True)
    gaps = Column(JSON, nullable=True)
    source_plan = Column(JSON, nullable=True)
    round_summaries = Column(JSON, nullable=True)
    stop_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    def __repr__(self):
        return f"<CollectionBatch id={self.id} status={self.status}>"


class CollectedItem(Base):
    """采集到的单条信息 — 系统的核心数据实体。

    每条信息有:
      - 来源溯源 (source, run, URL)
      - 内容 (title, content, summary)
      - 语言
      - 发布时间
      - 标签 (多对多 Tag)
      - 结构化维度 (categories, entities, hs_codes if applicable)
      - 质量评分
      - 状态流转 (raw → tagged → enriched → archived)
    """
    __tablename__ = "collected_items"

    id = Column(String(120), primary_key=True)
    source_id = Column(String(80), ForeignKey("source_configs.id"), nullable=False)
    run_id = Column(String(80), nullable=True, index=True)
    topic_id = Column(String(80), nullable=True, index=True)

    # Content
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    url = Column(String(2000), nullable=True)
    language = Column(String(10), nullable=True)

    # Classification (high-level category buckets)
    category = Column(String(100), nullable=True)

    # Entities extracted (products, companies, countries, people, events, etc.)
    entities = Column(JSON, nullable=True)

    # Quality
    status = Column(String(20), default="raw")
    quality_score = Column(Float, default=0.0)
    relevance_score = Column(Float, default=0.0)

    # Provenance
    published_at = Column(DateTime(timezone=True), nullable=True)
    collected_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)
    raw_metadata = Column(JSON, nullable=True)

    # 重点信息配图：从信息源头页面解析下载的本地图片 URL（/static/featured-images/...）
    featured_image_url = Column(String(2000), nullable=True)

    # Compliance
    authorization_level = Column(String(20), default="public")

    # Relationships
    source = relationship("SourceConfig", back_populates="items")
    tags = relationship("Tag", secondary=item_tags, back_populates="items", lazy="selectin")

    def tags_from_metadata(self) -> list:
        """Extract tag IDs from raw_metadata harvested by connectors."""
        tags = []
        if self.raw_metadata and isinstance(self.raw_metadata, dict):
            for key in ("tags", "keywords", "categories", "sectors", "countries", "topics"):
                vals = self.raw_metadata.get(key, [])
                if isinstance(vals, list):
                    tags.extend(str(v) for v in vals if v)
        return list(dict.fromkeys(tags))

    def __repr__(self):
        return f"<CollectedItem id={self.id} title={self.title[:30] if self.title else ''}>"
