"""SourceConfig, Category — information source and category models."""
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, JSON, Boolean
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.database import Base
from app._models_enums import SourceChannel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceConfig(Base):
    """Configurable information source. Each source maps to a channel + config."""
    __tablename__ = "source_configs"

    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    channel = Column(SAEnum(SourceChannel), nullable=False)
    source_group = Column(
        String(80), nullable=False, default="other", server_default="other"
    )
    is_active = Column(Boolean, default=True)
    is_configured = Column(Boolean, default=False)

    base_url = Column(String(800), nullable=True)
    api_endpoint = Column(String(800), nullable=True)
    homepage_url = Column(String(800), nullable=True)
    api_key_ref = Column(String(200), nullable=True)
    api_key = Column(String(500), nullable=True)
    auth_config = Column(JSON, nullable=True)

    rate_limit_rps = Column(Float, default=1.0)
    max_retries = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=30)
    max_items_per_run = Column(Integer, default=100)

    default_keywords = Column(JSON, nullable=True)
    default_categories = Column(JSON, nullable=True)
    languages = Column(JSON, nullable=True)
    country_focus = Column(JSON, nullable=True)

    legal_basis = Column(Text, nullable=True)
    compliance_note = Column(Text, nullable=True)

    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    items_collected = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    runs = relationship("CollectionRun", back_populates="source", cascade="all, delete-orphan")
    items = relationship("CollectedItem", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SourceConfig id={self.id} name={self.name}>"


class Category(Base):
    """Top-level category for topics — tree-structure root."""
    __tablename__ = "categories"
    id = Column(String(80), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)

    def __repr__(self):
        return f"<Category id={self.id} name={self.name}>"
