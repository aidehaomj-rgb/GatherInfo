"""Report schemas."""
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator
from .common import IsoDT


class ReportOut(BaseModel):
    id: str
    topic_id: str
    title: str
    report_type: Literal["analytical", "archive", "weekly_digest"] = "analytical"
    content: str | None = None
    summary: str | None = None
    status: str
    model_id: str | None = None
    tokens_used: int = 0
    item_count: int = 0
    item_ids: list[str] | None = None
    error_log: str | None = None
    series_id: str | None = None
    period_key: str | None = None
    part_index: int | None = None
    part_total: int | None = None
    selection_policy: dict | None = None
    selection_audit: dict | None = None
    retry_count: int = 0
    last_error_at: IsoDT = None
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


class WeeklyReportGenerateRequest(BaseModel):
    topic_id: str = Field(min_length=1, max_length=80)
    model_id: str | None = None
    week_start: str | None = None
    target_items: int | None = Field(default=None, ge=2, le=200)
    part_size: int | None = Field(default=None, ge=30, le=40)
    min_items: int | None = Field(default=None, ge=2, le=200)
    allow_partial: bool = False

    @model_validator(mode="after")
    def validate_two_volume_contract(self):
        if self.target_items is not None and self.part_size is not None and self.target_items > self.part_size * 2:
            raise ValueError("target_items 不能超过两卷容量")
        if self.min_items is not None and self.min_items < 60:
            raise ValueError("min_items 至少为 60，确保每卷不少于 30 条")
        if self.min_items is not None and self.target_items is not None and self.min_items > self.target_items:
            raise ValueError("min_items 不能超过 target_items")
        return self


class WeeklyReportGenerateResult(BaseModel):
    series_id: str
    period_key: str
    date_from: str
    date_to: str
    candidate_count: int
    selected_count: int
    target_count: int
    documents: list[ReportOut] = Field(default_factory=list)
    selection_audit: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    reused: bool = False
