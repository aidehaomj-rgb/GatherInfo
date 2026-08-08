"""Import the 2026-08-08 full-source forum-risk refresh."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from app.database import SessionLocal, _db_file_path
from app.models import CollectedItem, CollectionRun, PromptTemplate, Report, SourceConfig, Topic
from app._models_enums import SourceChannel

from forum_full_refresh_data_20260808 import (
    BATCH_ID,
    DATE_RANGE_END,
    DATE_RANGE_START,
    NEW_KEYWORDS,
    NEW_LEADS,
    NEW_SOURCES,
    OUTPUT_DIR,
    OUTPUT_DOCX,
    PROMPT_APPENDIX,
    PROMPT_ID,
    REPORT_ID,
    REPORT_LEADS,
    REPORT_TITLE,
    SEASONAL_PROMPT_APPENDIX,
    SOURCE_AUDIT,
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
    destination = os.path.join(backup_dir, f"gather.before_forum_full_refresh.{NOW:%Y%m%d_%H%M%S}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return destination


def upsert_new_source(db, spec: dict) -> SourceConfig:
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
    source.default_categories = ["外贸论坛", "报关清关", "企业核验", "公开网络风险线索"]
    source.languages = spec["languages"]
    source.country_focus = ["CN"]
    source.legal_basis = "仅采集无需登录即可访问的公开页面，用于海关风险线索初筛和后续依法核查。"
    source.compliance_note = "网页和用户帖子不构成事实认定；须以主体登记、平台订单、报关与运输单证、实货和资金记录交叉验证。"
    source.rate_limit_rps = 0.5
    source.max_retries = 2
    source.timeout_seconds = 30
    source.max_items_per_run = 30
    source.last_sync_at = NOW
    source.last_error = None
    source.updated_at = NOW
    return source


def item_content(lead: dict) -> str:
    return "\n\n".join(
        [
            "采集内容：" + lead["content_summary"],
            "中国实体/标识：" + "；".join(lead["china_entities"]),
            "风险信号：" + "；".join(lead["risk_signals"]),
            "风险分析：" + "；".join(lead["risk_points"]),
            "下一步核查：" + "；".join(lead["next_steps"]),
            "缺失字段：" + lead["missing_fields"],
            "来源说明：" + lead["source_note"],
            "法律提示：本条为公开网络待核线索，不构成对任何主体违法违规的认定。",
        ]
    )


def upsert_item(db, lead: dict) -> bool:
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
        "collector": "Codex full-source public-web refresh",
        "batch_id": BATCH_ID,
        "date_window_verified": True,
        "enforcement_case": False,
        "china_entity_gate": lead["china_entity_gate"],
        "duplicate_group": lead["duplicate_group"],
        "crosspost_url": lead.get("crosspost_url"),
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
    return existed


def upsert_audit_run(db, audit: dict, items_new: int) -> CollectionRun:
    run_id = f"codex-forum-risk-audit-20260808-{audit['id']}"
    run = db.get(CollectionRun, run_id)
    if run is None:
        run = CollectionRun(id=run_id, source_id=audit["id"])
        db.add(run)
    found_counts = {
        "reddit-alibaba": 3,
        "reddit-freightforwarding": 1,
        "web-hc23-transport-directory": 1,
        "web-bq-biquwang-marketplace": 1,
        "web-jinxiu-logistics": 1,
        "community-bokee-business-blog": 1,
    }
    run.source_id = audit["id"]
    run.topic_id = TOPIC_ID
    run.status = "completed"
    run.batch_id = BATCH_ID
    run.keywords_used = NEW_KEYWORDS
    run.items_found = found_counts.get(audit["id"], 0)
    run.items_new = items_new
    run.items_updated = 0
    run.items_failed = 0
    run.started_at = NOW
    run.completed_at = NOW
    run.duration_ms = 0
    run.window_start = parse_datetime(DATE_RANGE_START + "T00:00:00+08:00")
    run.window_end = parse_datetime(DATE_RANGE_END + "T23:59:59+08:00")
    run.error_log = []
    run.metadata_json = {
        "collector": "Codex full-source public-web refresh",
        "batch_id": BATCH_ID,
        "audit_status": audit["status"],
        "audit_note": audit["note"],
        "selection_logic": "近30天+非执法案例+中国可核对象+强风险组合+跨版去重",
        "legal_notice": "公开网络待核线索，不构成违法事实认定",
    }
    run.progress_events = [
        {"stage": "source_search", "status": "completed"},
        {"stage": "internet_supplement", "status": "completed"},
        {"stage": "date_filter", "status": "completed"},
        {"stage": "china_entity_gate", "status": "completed"},
        {"stage": "deduplicate", "status": "completed"},
        {"stage": "risk_analysis", "status": "completed"},
    ]
    return run


def main() -> None:
    if not os.path.isfile(OUTPUT_DOCX):
        raise RuntimeError(f"DOCX must be built before import: {OUTPUT_DOCX}")

    backup = backup_database()
    with SessionLocal() as db:
        topic = db.get(Topic, TOPIC_ID)
        prompt = db.get(PromptTemplate, PROMPT_ID)
        if topic is None or prompt is None:
            raise RuntimeError("Required topic or prompt template is missing")

        for spec in NEW_SOURCES:
            upsert_new_source(db, spec)
        db.flush()

        source_ids = list(topic.source_ids or [])
        for audit in SOURCE_AUDIT:
            if audit["id"] not in source_ids:
                source_ids.append(audit["id"])
        topic.source_ids = source_ids

        new_by_source: dict[str, int] = {}
        new_count = 0
        updated_count = 0
        for lead in NEW_LEADS:
            existed = upsert_item(db, lead)
            if existed:
                updated_count += 1
            else:
                new_count += 1
                new_by_source[lead["source_id"]] = new_by_source.get(lead["source_id"], 0) + 1

        for audit in SOURCE_AUDIT:
            source = db.get(SourceConfig, audit["id"])
            if source is None:
                raise RuntimeError(f"Configured source missing: {audit['id']}")
            source.last_sync_at = NOW
            source.last_error = None
            source.updated_at = NOW
            upsert_audit_run(db, audit, new_by_source.get(audit["id"], 0))

        keywords = list(topic.keywords or [])
        for keyword in NEW_KEYWORDS:
            if keyword not in keywords:
                keywords.append(keyword)
        topic.keywords = keywords
        topic.collect_window_days = 30
        topic.last_run_at = NOW
        topic.last_collection_run_id = "codex-forum-risk-audit-20260808-reddit-alibaba"
        topic.last_error = None
        topic.updated_at = NOW
        topic_marker = "[2026-08-08 全源复核]"
        if topic_marker not in (topic.description_prompt or ""):
            topic.description_prompt = (
                (topic.description_prompt or "").rstrip()
                + "\n\n[2026-08-08 全源复核] 逐源检索后再进行互联网补充；原帖时间硬过滤；中国可核对象硬门槛；帖子陈述、评论推断和官网信息分层；同名主体消歧；跨版去重；超窗直接风险词仅进入模式库。"
            ).strip()
        seasonal_topic_marker = "[2026-08-08 时令生鲜专项]"
        if seasonal_topic_marker not in (topic.description_prompt or ""):
            topic.description_prompt = (
                (topic.description_prompt or "").rstrip()
                + "\n\n[2026-08-08 时令生鲜专项] 中秋国庆前60天监测大闸蟹、活体水产、冻品和礼盒的商业代带；个人合理自用不升级；重点识别收费代送、高频往返、多人拆分、口岸交收、商业收货和缺少卫生/销售文件的组合。"
            ).strip()

        prompt_marker = "[2026-08-08 全源复核与互联网补充规则]"
        if prompt_marker not in prompt.content:
            prompt.content = prompt.content.rstrip() + PROMPT_APPENDIX
        seasonal_prompt_marker = "[2026-08-08 中秋国庆时令生鲜夹藏与商业代带专项规则]"
        if seasonal_prompt_marker not in prompt.content:
            prompt.content = prompt.content.rstrip() + SEASONAL_PROMPT_APPENDIX
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
            f"完成{len(SOURCE_AUDIT)}个已配置/新增来源的逐源复核并进行一次开放互联网补充。新增3组近30天线索，"
            "与既有4组近月线索合并形成7组核查清单；重点是Alibaba订单号可锁定中国卖家的提单货名差异、"
            "Linktrans同名货代低报询问，以及宁波—多伦多线路的查验规避营销话术。另增加中秋、国庆时令生鲜商业代带专项预警，"
            "明确区分个人合理自用与收费代送、多人拆分、高频往返和商业销售。所有内容均按待核线索处理。"
        )
        report.status = "completed"
        report.model_id = "codex-full-source-public-web-refresh"
        report.tokens_used = 0
        report.item_count = len(REPORT_LEADS)
        report.item_ids = [lead["id"] for lead in REPORT_LEADS]
        report.error_log = None
        report.collection_run_id = "codex-forum-risk-audit-20260808-reddit-alibaba"
        report.date_range_start = parse_datetime(DATE_RANGE_START + "T00:00:00+08:00")
        report.date_range_end = parse_datetime(DATE_RANGE_END + "T23:59:59+08:00")
        report.output_files = {"docx": OUTPUT_DOCX}
        report.output_dir = OUTPUT_DIR
        report.generated_at = NOW
        report.created_at = report.created_at or NOW

        db.flush()
        topic.total_items_collected = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).count()
        for source_id in source_ids:
            source = db.get(SourceConfig, source_id)
            source.items_collected = db.query(CollectedItem).filter(CollectedItem.source_id == source_id).count()

        db.commit()
        print(f"backup={backup}")
        print(f"new={new_count} updated={updated_count} total_topic_items={topic.total_items_collected}")
        print(f"report_id={REPORT_ID} items={len(REPORT_LEADS)} sources={len(topic.source_ids or [])}")
        print(f"docx={OUTPUT_DOCX}")


if __name__ == "__main__":
    main()
