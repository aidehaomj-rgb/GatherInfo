"""Report schemas."""
from typing import Literal, Optional
from pydantic import BaseModel
from .common import IsoDT


class ReportOut(BaseModel):
    id: str
    topic_id: str
    title: str
    report_type: Literal["analytical", "archive"] = "analytical"
    content: str | None = None
    summary: str | None = None
    status: str
    model_id: str | None = None
    tokens_used: int = 0
    item_count: int = 0
    item_ids: list[str] | None = None
    error_log: str | None = None
    collection_run_id: str | None = None
    date_range_start: IsoDT = None
    date_range_end: IsoDT = None
    output_files: dict | None = None
    output_dir: str | None = None
    generated_at: IsoDT = None
    created_at: IsoDT = None
    topic_name: Optional[str] = None
    model_config = {"from_attributes": True}


class ReportListOut(BaseModel):
    reports: list[ReportOut] = []
    total: int = 0


class ReportGenerateRequest(BaseModel):
    topic_id: str
    report_type: Literal["analytical", "archive"] = "analytical"
    model_id: str | None = None
    model_name_override: str | None = None
    title: str | None = None
    collection_run_id: str | None = None
    collection_run_ids: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    include_content: bool = True
    language: str = "zh"


class BatchGenerateRequest(BaseModel):
    topic_ids: list[str] = []
    report_type: Literal["analytical", "archive"] = "analytical"
    model_id: str | None = None
    model_name_override: str | None = None
    collection_run_ids: list[str] | None = None
    collection_run_ids_list: list[list[str]] | None = None


class BatchGenerateResult(BaseModel):
    results: list[ReportOut] = []
    failed: int = 0
