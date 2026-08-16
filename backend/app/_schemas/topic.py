"""Topic, schedule, and category schemas."""
from pydantic import BaseModel, Field, model_validator
from .common import IsoDT


class TopicCreate(BaseModel):
    id: str | None = Field(default=None, max_length=80, description="留空则由后端从 name 自动生成")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: str | None = None
    keywords: list[str] = Field(default_factory=list, max_length=50)
    synonyms: list[str] | None = None
    exclude_keywords: list[str] | None = None
    categories: list[str] | None = None
    focus_countries: list[str] | None = None
    focus_languages: list[str] | None = None
    source_ids: list[str] | None = None
    collection_model_ids: list[str] | None = None
    prompt_template_ids: list[str] | None = None
    target_urls: list[str] | None = None
    auto_tag_rules: list[dict] | None = None
    schedule_cron: str | None = None
    is_scheduled: bool = False
    is_active: bool = True
    auto_report: bool = False
    auto_report_model_id: str | None = None
    auto_report_type: str = Field(default="analytical", pattern="^(analytical|archive)$")
    weekly_digest_enabled: bool = False
    weekly_digest_model_id: str | None = None
    weekly_digest_target_items: int = Field(default=80, ge=60, le=80)
    weekly_digest_part_size: int = Field(default=40, ge=30, le=40)
    weekly_digest_min_items: int = Field(default=60, ge=60, le=80)
    keyword_tags: list[dict] | None = None
    description_prompt: str | None = None
    ai_research_model_id: str | None = None
    collect_window_days: int = Field(default=7, ge=0, le=365)

    @model_validator(mode="after")
    def validate_weekly_digest_contract(self):
        if self.weekly_digest_target_items > self.weekly_digest_part_size * 2:
            raise ValueError("weekly digest target exceeds two-volume capacity")
        if self.weekly_digest_min_items > self.weekly_digest_target_items:
            raise ValueError("weekly digest minimum exceeds target")
        return self


class TopicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: str | None = None
    keywords: list[str] | None = None
    synonyms: list[str] | None = None
    categories: list[str] | None = None
    focus_countries: list[str] | None = None
    focus_languages: list[str] | None = None
    source_ids: list[str] | None = None
    collection_model_ids: list[str] | None = None
    prompt_template_ids: list[str] | None = None
    target_urls: list[str] | None = None
    auto_tag_rules: list[dict] | None = None
    schedule_cron: str | None = None
    is_scheduled: bool | None = None
    is_active: bool | None = None
    auto_report: bool | None = None
    auto_report_model_id: str | None = None
    auto_report_type: str | None = Field(default=None, pattern="^(analytical|archive)$")
    weekly_digest_enabled: bool | None = None
    weekly_digest_model_id: str | None = None
    weekly_digest_target_items: int | None = Field(default=None, ge=60, le=80)
    weekly_digest_part_size: int | None = Field(default=None, ge=30, le=40)
    weekly_digest_min_items: int | None = Field(default=None, ge=60, le=80)
    keyword_tags: list[dict] | None = None
    description_prompt: str | None = None
    ai_research_model_id: str | None = None
    collect_window_days: int | None = None


class TopicOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    category_id: str | None = None
    category_name: str | None = None
    keywords: list[str] = []
    keyword_tags: list[dict] | None = None
    description_prompt: str | None = None
    synonyms: list[str] | None = None
    categories: list[str] | None = None
    focus_countries: list[str] | None = None
    focus_languages: list[str] | None = None
    source_ids: list[str] | None = None
    collection_model_ids: list[str] | None = None
    prompt_template_ids: list[str] | None = None
    target_urls: list[str] | None = None
    auto_tag_rules: list[dict] | None = None
    collect_window_days: int = 7
    schedule_cron: str | None = None
    is_scheduled: bool = False
    is_active: bool = True
    auto_report: bool = False
    auto_report_model_id: str | None = None
    auto_report_type: str = "analytical"
    weekly_digest_enabled: bool = False
    weekly_digest_model_id: str | None = None
    weekly_digest_target_items: int = 80
    weekly_digest_part_size: int = 40
    weekly_digest_min_items: int = 60
    ai_research_model_id: str | None = None
    last_collection_run_id: str | None = None
    source_names: list[str] = []
    total_items_collected: int = 0
    current_item_count: int = 0
    last_run_at: IsoDT = None
    next_run_at: IsoDT = None
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}


class PromptTemplateCreate(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    content: str = Field(min_length=1, max_length=50000)
    is_active: bool = True


class PromptTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    content: str | None = Field(default=None, min_length=1, max_length=50000)
    is_active: bool | None = None


class PromptTemplateOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    content: str
    is_active: bool = True
    topic_count: int = 0
    linked_experts: list[str] = Field(default_factory=list)
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}


class ScheduleCreate(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    source_ids: list[str] | None = None
    topic_ids: list[str] | None = None
    cron_expression: str = Field(default="0 8 * * *", max_length=100)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    is_active: bool = True


class ScheduleOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    source_ids: list[str] | None = None
    topic_ids: list[str] | None = None
    cron_expression: str
    timezone: str = "Asia/Shanghai"
    is_active: bool
    last_run_at: IsoDT = None
    next_run_at: IsoDT = None
    run_count: int = 0
    last_status: str | None = None
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class CategoryOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}
