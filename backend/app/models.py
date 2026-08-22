"""
GatherInfo data models — re-exports from sub-modules for backward compatibility.

Sub-modules:
    _models_enums    — SourceChannel, JobStatus, ItemStatus
    _models_sources  — SourceConfig, Category
    _models_items    — Tag, item_tags, CollectionRun, CollectedItem
    _models_config   — Topic, ScheduleConfig, ModelConfig, Report, SearchToolConfig, SystemConfig
"""

from app._models_enums import (
    SourceChannel,
    JobStatus,
    ItemStatus,
)
from app._models_sources import (
    SourceConfig,
    Category,
)
from app._models_items import (
    Tag,
    item_tags,
    CollectionRun,
    CollectionBatch,
    CollectedItem,
    ItemTopicMembership,
)
from app._models_config import (
    Topic,
    ResearchJob,
    ResearchRound,
    ResearchCase,
    ResearchEntity,
    ResearchCaseEntity,
    ResearchEvidence,
    PromptTemplate,
    ScheduleConfig,
    ModelConfig,
    Report,
    SearchToolConfig,
    SystemConfig,
)
from app._models_handoff import MaterialSet, HandoffRun
from app._models_supply_chain import (
    SupplyChainInvestigation,
    SupplyChainEntity,
    SupplyChainCase,
    SupplyChainShipment,
    SupplyChainEvidence,
    SupplyChainOpenSourceEvidence,
    SupplyChainReport,
    SupplyChainDiscoveryCandidate,
)

__all__ = [
    "SourceChannel",
    "JobStatus",
    "ItemStatus",
    "SourceConfig",
    "Category",
    "Tag",
    "item_tags",
    "CollectionRun",
    "CollectionBatch",
    "CollectedItem",
    "ItemTopicMembership",
    "Topic",
    "ResearchJob",
    "ResearchRound",
    "ResearchCase",
    "ResearchEntity",
    "ResearchCaseEntity",
    "ResearchEvidence",
    "PromptTemplate",
    "ScheduleConfig",
    "ModelConfig",
    "Report",
    "SearchToolConfig",
    "SystemConfig",
    "MaterialSet",
    "HandoffRun",
    "SupplyChainInvestigation",
    "SupplyChainEntity",
    "SupplyChainCase",
    "SupplyChainShipment",
    "SupplyChainEvidence",
    "SupplyChainOpenSourceEvidence",
    "SupplyChainReport",
    "SupplyChainDiscoveryCandidate",
]
