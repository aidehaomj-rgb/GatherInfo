"""Import Codex-researched customs-risk hotspots and their analytical report."""
from __future__ import annotations

import hashlib
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, CollectionRun, Report, SourceConfig, Topic  # noqa: E402


TOPIC_ID = "weekly-trade-current-affairs"
SOURCE_ID = "ai-smart-web-research"
RUN_ID = "run-codex-customs-risk-hotspots-20260804"
REPORT_ID = "rpt-codex-customs-risk-hotspots-20260804"
REPORT_PATH = ROOT_DIR / "outputs" / "时政热点信息分析" / "近一个月海关进出口监管风险热点_2026-08-04.md"
DB_PATH = BACKEND_DIR.parent / "data" / "gather.db"

ITEM_META = [
    ("2026-07-29", "https://apnews.com/article/russia-ukraine-war-oil-refinery-trump-zelenskyy-4275c2280107aedba37df8704f226ce6", "能源与边境走私"),
    ("2026-07-02", "https://www.spglobal.com/energy/en/news-research/latest-news/refined-products/070226-refinery-attacks-boost-june-russian-crude-exports-dampen-products", "能源转运与原产地"),
    ("2026-07-22", "https://m.economictimes.com/news/economy/agriculture/fertiliser-vessels-stuck-at-ports-raise-supply-fears-for-peak-kharif-sowing/amp_articleshow/132546416.cms", "化肥与转口贸易"),
    ("2026-07-24", "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2288857&lang=1&reg=48", "化工品与税号风险"),
    ("2026-07-01", "https://www.morganlewis.com/pubs/2026/07/recent-china-export-control-actions-signal-active-enforcement-for-rare-earths-and-strategic-minerals", "战略矿产出口管制"),
    ("2026-07-24", "https://apnews.com/article/china-eu-sanctions-russia-export-control-war-cfb75918077b268eb76b0f19c1673511", "两用物项出口管制"),
    ("2026-07-20", "https://www.investing.com/news/stock-market-news/trump-orders-tightening-of-defense-supply-chain-waiver-rules-4801571", "关键矿产原产地"),
    ("2026-07-08", "https://www.channelnewsasia.com/singapore/money-laundering-scheme-gold-china-smuggling-6240356", "贵金属走私与骗税"),
    ("2026-07-27", "https://agriculture.economictimes.indiatimes.com/news/markets-and-trade/indian-rice-export-prices-climb-to-near-10-month-high-on-monsoon-worries-and-tight-supply/132655066", "粮食原产地与检疫"),
    ("2026-07-15", "https://cpbrd.congress.gov.ph/dp2026-17-seeds-of-a-food-crisis-fertilizer-supply-disruptions-in-the-philippines-amidst-the-us-iran-conflict/", "农资走私与质量"),
]


def parse_sections(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"^###\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else text.find("\n## 三、", match.end())
        if end < 0:
            end = len(text)
        sections.append((match.group(2).strip(), text[match.end():end].strip()))
    return sections


def field(body: str, name: str) -> str:
    match = re.search(rf"\*\*{re.escape(name)}：\*\*\s*(.+?)(?=\n\n\*\*|\Z)", body, re.DOTALL)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def main() -> int:
    if not REPORT_PATH.exists():
        raise FileNotFoundError(REPORT_PATH)
    text = REPORT_PATH.read_text(encoding="utf-8")
    sections = parse_sections(text)
    if len(sections) != 10:
        raise ValueError(f"Expected 10 hotspot sections, found {len(sections)}")

    backup_dir = ROOT_DIR / "work" / "political_hotspots" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"gather-before-codex-hotspot-import-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(DB_PATH, backup)

    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        topic = db.query(Topic).filter(Topic.id == TOPIC_ID).first()
        source = db.query(SourceConfig).filter(SourceConfig.id == SOURCE_ID).first()
        if not topic or not source:
            raise RuntimeError("Required topic or source is missing")

        run = db.query(CollectionRun).filter(CollectionRun.id == RUN_ID).first()
        if not run:
            run = CollectionRun(id=RUN_ID, source_id=SOURCE_ID, topic_id=TOPIC_ID)
            db.add(run)
        run.status = "completed"
        run.batch_id = "codex-customs-risk-hotspots-20260804"
        run.keywords_used = ["走私风险", "第三国转运", "原产地", "出口管制", "化肥", "能源", "战略矿产"]
        run.items_found = 10
        run.items_new = 10
        run.items_updated = 0
        run.items_failed = 0
        run.started_at = now
        run.completed_at = now
        run.duration_ms = 0
        run.window_start = datetime(2026, 7, 5, tzinfo=timezone.utc)
        run.window_end = datetime(2026, 8, 4, 23, 59, 59, tzinfo=timezone.utc)
        run.metadata_json = {"provider": "codex_deep_web_research", "report_path": str(REPORT_PATH)}

        item_ids = []
        inserted = 0
        for index, ((title, body), (published, url, category)) in enumerate(zip(sections, ITEM_META), 1):
            item_id = f"codex-customs-risk-hotspot-20260804-{index:02d}"
            item_ids.append(item_id)
            item = db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
            if not item:
                item = CollectedItem(id=item_id)
                db.add(item)
                inserted += 1
            source_note = field(body, "信息来源")
            facts = field(body, "事实依据")
            risk = field(body, "监管风险")
            checks = field(body, "数据核查")
            content = f"信息来源：{source_note}\n\n事实依据：{facts}\n\n监管风险：{risk}\n\n数据核查：{checks}"
            item.source_id = SOURCE_ID
            item.run_id = RUN_ID
            item.topic_id = TOPIC_ID
            item.title = title
            item.content = content
            item.content_hash = hashlib.sha256(f"{url}\n{content}".encode("utf-8")).hexdigest()
            item.summary = risk
            item.url = url
            item.language = "zh"
            item.category = category
            item.entities = {"risk_type": category, "research_window": "2026-07-05/2026-08-04"}
            item.status = "enriched"
            item.quality_score = 0.92
            item.relevance_score = 0.96
            item.published_at = datetime.fromisoformat(published).replace(tzinfo=timezone.utc)
            item.collected_at = now
            item.updated_at = now
            item.authorization_level = "public"
            item.raw_metadata = {
                "provider": "codex_deep_web_research",
                "import_batch": "codex-customs-risk-hotspots-20260804",
                "source_note": source_note,
                "facts": facts,
                "customs_risk_assessment": risk,
                "customs_data_checks": checks,
                "analysis_disclaimer": "监管风险为待海关数据验证的研判，不代表已发生违法行为。",
                "tags": ["涉进出口时政热点", "海关监管风险", category],
            }

        report = db.query(Report).filter(Report.id == REPORT_ID).first()
        if not report:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID, title="近一个月海关进出口监管风险热点")
            db.add(report)
        report.topic_id = TOPIC_ID
        report.title = "近一个月海关进出口监管风险热点"
        report.report_type = "analytical"
        report.content = text
        report.summary = "近一个月筛选10条与海关进出口监管紧密相关的时政热点，重点研判能源、化肥、战略矿产、两用物项、黄金和粮食领域的走私、转运、原产地及申报风险。"
        report.status = "completed"
        report.model_id = None
        report.tokens_used = 0
        report.item_count = 10
        report.item_ids = item_ids
        report.error_log = None
        report.collection_run_id = RUN_ID
        report.date_range_start = datetime(2026, 7, 5, tzinfo=timezone.utc)
        report.date_range_end = datetime(2026, 8, 4, 23, 59, 59, tzinfo=timezone.utc)
        report.output_files = {"md": str(REPORT_PATH)}
        report.output_dir = str(REPORT_PATH.parent)
        report.generated_at = now
        report.created_at = report.created_at or now

        source.items_collected = int(source.items_collected or 0) + inserted
        source.last_sync_at = now
        db.commit()
        print(f"backup={backup}")
        print(f"run_id={RUN_ID} inserted={inserted} total=10")
        print(f"report_id={REPORT_ID} status=completed item_count=10")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
