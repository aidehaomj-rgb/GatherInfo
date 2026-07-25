"""
Pydantic schemas for GatherInfo management API.

This module re-exports all schemas from the _schemas package.
Import from here to get any schema class.
"""
from app._schemas.common import (
    IsoDT,
    StatsOut,
    TagStatsOut,
    ConnectorInfo,
    SystemConfigOut,
    SystemConfigUpdate,
)
from app._schemas.source import SourceCreate, SourceUpdate, SourceOut
from app._schemas.topic import (
    TopicCreate, TopicUpdate, TopicOut,
    ScheduleCreate, ScheduleOut,
    CategoryCreate, CategoryUpdate, CategoryOut,
)
from app._schemas.collection import (
    CollectRequest, RunOut, CollectResultOut,
    ItemOut, ItemListOut, ItemDeleteRequest, ItemTranslateRequest,
    BatchRunOut, BatchOut, ActiveRunOut,
)
from app._schemas.tag import (
    TagUpdateIn, TagUpdateSchema, TagOut,
    TagMergeRequest, TagMergeResult,
)
from app._schemas.model import (
    ModelConfigCreate, ModelConfigUpdate, ModelConfigOut,
    ModelTestResult, ListModelsResult, ModelListRequest,
    DiscoveredProvider, AutoDiscoverResult,
)
from app._schemas.report import (
    ReportOut, ReportListOut,
    ReportGenerateRequest, BatchGenerateRequest, BatchGenerateResult,
)
from app._schemas.search import (
    SearchToolConfigCreate, SearchToolConfigUpdate, SearchToolConfigOut,
)

__all__ = [
    # common
    "IsoDT", "StatsOut", "TagStatsOut", "ConnectorInfo",
    "SystemConfigOut", "SystemConfigUpdate",
    # source
    "SourceCreate", "SourceUpdate", "SourceOut",
    # topic
    "TopicCreate", "TopicUpdate", "TopicOut",
    "ScheduleCreate", "ScheduleOut",
    "CategoryCreate", "CategoryUpdate", "CategoryOut",
    # collection
    "CollectRequest", "RunOut", "CollectResultOut",
    "ItemOut", "ItemListOut", "ItemDeleteRequest",
    "BatchRunOut", "BatchOut", "ActiveRunOut",
    # tag
    "TagUpdateIn", "TagUpdateSchema", "TagOut",
    "TagMergeRequest", "TagMergeResult",
    # model
    "ModelConfigCreate", "ModelConfigUpdate", "ModelConfigOut",
    "ModelTestResult", "ListModelsResult", "ModelListRequest",
    "DiscoveredProvider", "AutoDiscoverResult",
    # report
    "ReportOut", "ReportListOut",
    "ReportGenerateRequest", "BatchGenerateRequest", "BatchGenerateResult",
    # search
    "SearchToolConfigCreate", "SearchToolConfigUpdate", "SearchToolConfigOut",
]
