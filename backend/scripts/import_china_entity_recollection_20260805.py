"""Import a fresh China-entity forum-risk collection and analytical report."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from app.database import SessionLocal, _db_file_path
from app.models import CollectedItem, CollectionRun, PromptTemplate, Report, SourceConfig, Topic
from app._models_enums import SourceChannel

from china_entity_recollection_data_20260805 import (
    BATCH_ID,
    DATE_RANGE_END,
    DATE_RANGE_START,
    LEADS,
    OUTPUT_DIR,
    OUTPUT_DOCX,
    PROMPT_APPENDIX,
    PROMPT_ID,
    REPORT_ID,
    REPORT_TITLE,
    SOURCES,
    TOPIC_ID,
    build_markdown,
)


NOW = datetime.now(timezone.utc)


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def backup_database() -> str:
    path = _db_file_path()
    if not path or not os.path.isfile(path):
        raise RuntimeError("Database file is unavailable")
    backup_dir = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    destination = os.path.join(backup_dir, f"gather.before_cn_recollect.{NOW:%Y%m%d_%H%M%S}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return destination


def item_content(lead: dict) -> str:
    parts = [
        "采集内容：" + lead["content_summary"],
        "中国实体/标识：" + "；".join(lead["china_entities"]),
        "风险信号：" + "；".join(lead["risk_signals"]),
        "风险分析：" + "；".join(lead["risk_points"]),
        "下一步核查：" + "；".join(lead["next_steps"]),
        "缺失字段：" + lead["missing_fields"],
        "来源说明：" + lead["source_note"],
        "法律提示：公开页面仅作为待核线索，不构成对任何主体违法违规的认定。",
    ]
    return "\n\n".join(parts)


def upsert_source(db, spec: dict) -> SourceConfig:
    source = db.get(SourceConfig, spec["id"])
    if source is None:
        source = SourceConfig(id=spec["id"], name=spec["name"], channel=SourceChannel.WEB_SCRAPE)
        db.add(source)
    source.name = spec["name"]
    source.description = spec["description"]
    source.channel = SourceChannel.WEB_SCRAPE
    source.is_active = True
    source.is_configured = True
    source.base_url = spec["base_url"]
    source.homepage_url = spec["homepage_url"]
    source.default_keywords = spec["keywords"]
    source.default_categories = ["外贸论坛", "报关清关", "公开商贸信息", "中国实体核查"]
    source.languages = ["zh-CN"]
    source.country_focus = ["CN"]
    source.legal_basis = "仅采集无需登录即可访问的公开页面，用于海关风险线索初筛和后续依法核查。"
    source.compliance_note = (
        "企业自述、目录、博客和供求信息不代表事实认定；不得据此直接认定企业或个人违法，"
        "须与工商登记、海关申报、运输单证、实货和资金记录交叉验证。"
    )
    source.rate_limit_rps = 0.5
    source.max_retries = 2
    source.timeout_seconds = 30
    source.max_items_per_run = 30
    source.last_sync_at = NOW
    source.last_error = None
    source.updated_at = NOW
    return source


def upsert_run(db, lead: dict, existed: bool) -> CollectionRun:
    run = db.get(CollectionRun, lead["run_id"])
    if run is None:
        run = CollectionRun(id=lead["run_id"], source_id=lead["source_id"])
        db.add(run)
    run.source_id = lead["source_id"]
    run.topic_id = TOPIC_ID
    run.status = "completed"
    run.batch_id = BATCH_ID
    run.keywords_used = lead["risk_signals"]
    run.items_found = 1
    run.items_new = 0 if existed else 1
    run.items_updated = 1 if existed else 0
    run.items_failed = 0
    run.started_at = NOW
    run.completed_at = NOW
    run.duration_ms = 0
    run.window_start = parse_datetime(DATE_RANGE_START + "T00:00:00+08:00")
    run.window_end = parse_datetime(DATE_RANGE_END + "T23:59:59+08:00")
    run.error_log = []
    run.metadata_json = {
        "collector": "Codex direct public-web collection",
        "batch_id": BATCH_ID,
        "selection_logic": "近30天+非执法案例+强风险组合+中国实体硬门槛+同主体去重",
        "source_reliability": lead["source_note"],
        "legal_notice": "公开网络待核线索，不构成违法事实认定",
    }
    run.progress_events = [
        {"stage": "search", "status": "completed"},
        {"stage": "date_and_scope_filter", "status": "completed"},
        {"stage": "china_entity_gate", "status": "completed"},
        {"stage": "deduplicate", "status": "completed"},
        {"stage": "risk_analysis", "status": "completed"},
    ]
    return run


def upsert_item(db, lead: dict) -> tuple[CollectedItem, bool]:
    item = db.get(CollectedItem, lead["id"])
    existed = item is not None
    if item is None:
        item = CollectedItem(id=lead["id"], source_id=lead["source_id"], title=lead["title"])
        db.add(item)
    content = item_content(lead)
    item.source_id = lead["source_id"]
    item.run_id = lead["run_id"]
    item.topic_id = TOPIC_ID
    item.title = lead["title"]
    item.content = content
    item.content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    item.summary = lead["content_summary"]
    item.url = lead["url"]
    item.language = "zh-CN"
    item.category = "外贸论坛违规清关与走私风险线索"
    item.entities = {
        "china_entities": lead["china_entities"],
        "risk_signals": lead["risk_signals"],
        "risk_level": lead["risk_level"],
    }
    item.status = "enriched"
    item.quality_score = lead["quality_score"]
    item.relevance_score = lead["relevance_score"]
    item.published_at = parse_datetime(lead["published_at"])
    item.collected_at = item.collected_at or NOW
    item.updated_at = NOW
    item.raw_metadata = {
        "collector": "Codex direct public-web collection",
        "batch_id": BATCH_ID,
        "date_window_verified": True,
        "enforcement_case": False,
        "china_entity_gate": "passed",
        "duplicate_group": lead["china_entities"][0],
        "risk_level": lead["risk_level"],
        "risk_signals": lead["risk_signals"],
        "china_entities": lead["china_entities"],
        "risk_analysis": lead["risk_points"],
        "next_steps": lead["next_steps"],
        "missing_fields": lead["missing_fields"],
        "source_reliability": lead["source_note"],
        "legal_notice": "公开网络待核线索，不构成违法事实认定",
    }
    item.authorization_level = "public"
    return item, existed


def main() -> None:
    backup = backup_database()
    with SessionLocal() as db:
        topic = db.get(Topic, TOPIC_ID)
        prompt = db.get(PromptTemplate, PROMPT_ID)
        if topic is None or prompt is None:
            raise RuntimeError("Required topic or prompt template is missing")

        for source_spec in SOURCES:
            upsert_source(db, source_spec)

        source_ids = list(topic.source_ids or [])
        for source_spec in SOURCES:
            if source_spec["id"] not in source_ids:
                source_ids.append(source_spec["id"])
        topic.source_ids = source_ids

        new_count = 0
        updated_count = 0
        for lead in LEADS:
            _item, existed = upsert_item(db, lead)
            upsert_run(db, lead, existed)
            if existed:
                updated_count += 1
            else:
                new_count += 1

        keywords = list(topic.keywords or [])
        for keyword in [
            "特殊关系报关", "包柜买单", "CIQ监装买单", "名牌货疑难杂货", "买单清关3C",
            "查验协调", "备案外贸抬头", "柜号封条司机资料", "口岸+公开电话+报价", "中国企业反查",
        ]:
            if keyword not in keywords:
                keywords.append(keyword)
        topic.keywords = keywords
        topic.collect_window_days = 30
        topic.last_run_at = NOW
        topic.last_collection_run_id = LEADS[0]["run_id"]
        topic.last_error = None
        topic.updated_at = NOW

        rule_marker = "[中国实体新一轮重采集]"
        if rule_marker not in (topic.description_prompt or ""):
            topic.description_prompt = (
                (topic.description_prompt or "").rstrip()
                + "\n\n[中国实体新一轮重采集] 近30天、非执法案例、强风险组合、中国实体硬门槛；"
                  "同一企业/电话/路线/模板合并；每条必须输出原帖、摘要、风险、核查建议和缺失字段。"
            ).strip()

        prompt_marker = "[2026-08-05 新一轮中国实体重采集规则]"
        if prompt_marker not in prompt.content:
            prompt.content = prompt.content.rstrip() + PROMPT_APPENDIX
        prompt.updated_at = NOW

        report = db.get(Report, REPORT_ID)
        if report is None:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID, title=REPORT_TITLE)
            db.add(report)
        report.topic_id = TOPIC_ID
        report.title = REPORT_TITLE
        report.report_type = "analytical"
        report.content = build_markdown()
        report.summary = (
            "近一个月重新采集并去重后新增4组可在中国境内核查的公开线索，逐条列明原帖、"
            "中国企业/联系方式/口岸或运输标识、风险点、核查建议和缺失字段；执法案例、超期帖子及境外个人线索已排除。"
        )
        report.status = "completed"
        report.model_id = "codex-china-entity-direct-web-recollection"
        report.tokens_used = 0
        report.item_count = len(LEADS)
        report.item_ids = [lead["id"] for lead in LEADS]
        report.error_log = None
        report.collection_run_id = LEADS[0]["run_id"]
        report.date_range_start = parse_datetime(DATE_RANGE_START + "T00:00:00+08:00")
        report.date_range_end = parse_datetime(DATE_RANGE_END + "T23:59:59+08:00")
        report.output_files = {"docx": OUTPUT_DOCX} if os.path.isfile(OUTPUT_DOCX) else {}
        report.output_dir = OUTPUT_DIR if os.path.isfile(OUTPUT_DOCX) else None
        report.generated_at = NOW
        report.created_at = report.created_at or NOW

        db.flush()
        topic.total_items_collected = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).count()
        for source_spec in SOURCES:
            source = db.get(SourceConfig, source_spec["id"])
            source.items_collected = db.query(CollectedItem).filter(CollectedItem.source_id == source.id).count()

        db.commit()
        print(f"backup={backup}")
        print(f"new={new_count} updated={updated_count} total_topic_items={topic.total_items_collected}")
        print(f"report_id={REPORT_ID} items={len(LEADS)} docx_registered={os.path.isfile(OUTPUT_DOCX)}")
        print(f"topic_sources={len(topic.source_ids or [])} output={OUTPUT_DOCX}")


if __name__ == "__main__":
    main()

