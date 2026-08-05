"""Import the approved deep-search preview and build an all-item topic report."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, CollectionRun, Report, SourceConfig, Topic  # noqa: E402


TOPIC_ID = "weekly-trade-current-affairs"
SOURCE_ID = "ai-smart-web-research"
RUN_ID = "run-codex-deep-hotspots-20260804-supplement"
REPORT_ID = "rpt-customs-hotspots-all-items-20260804"
PREVIEW_DIR = BACKEND_DIR / "data" / "previews" / "customs_hotspots"
PREVIEW_JSON = PREVIEW_DIR / "codex_deep_latest_preview.json"
DB_PATH = PROJECT_DIR / "data" / "gather.db"
OUTPUT_DIR = PROJECT_DIR.parent / "outputs" / "时政热点信息分析"
OUTPUT_PATH = OUTPUT_DIR / "涉进出口时政热点全部条目综合报告_2026-08-04.md"


DETAILS = {
    "https://theprint.in/world/bab-el-mandeb-shipping-rises-amid-hopes-of-resolution-in-us-iran-war/2998759/": {
        "facts": "Kpler数据显示，曼德海峡单日通行船舶回升至28艘，但霍尔木兹海峡流量仍低；一艘装载约200万桶沙特原油、驶往中国舟山的香港旗VLCC经红海航线通行。",
        "risk": "霍尔木兹低通行量可能推动油轮绕航、换船、临时仓储和船对船转运增加。对华进口原油及成品油可能出现装货港与原产国不一致、运输链异常拉长、运保费计价异常及贸易商临时变更，也可能被利用于掩饰受限货源或调换货物身份。",
    },
    "https://en.vneconomy.vn/importation-and-exportation-of-goods-produced-by-forced-labor-are-not-allowed.htm": {
        "facts": "越南第292/2026/ND-CP号法令规定，禁止进口或出口全部或部分由强迫劳动开采、生产或制造的产品。",
        "risk": "越南是纺织服装、光伏、电子和家具等产业的重要加工及转口节点。新规可能引发供应链调整，也可能增加原料来源、生产工序和实际控制关系隐匿，以及简单加工后变更原产地等风险。",
    },
    "https://thefederalregister.org/documents/2026-14416/crystalline-silicon-photovoltaic-cells-whether-or-not-assembled-into-modules-from-the-people-s-republic-of-china-initiat": {
        "facts": "美国商务部启动全国范围反规避调查，审查使用中国零部件在埃塞俄比亚完成的晶硅光伏电池或组件，以及在埃塞俄比亚完成后再使用中国投入品于越南组装并输美的产品。",
        "risk": "调查将提高第三国加工深度、物料来源和企业关联关系的核查强度，可能推动订单改变中转国、拆分零部件申报、夸大境外加工增值或隐匿最终用户。",
    },
    "https://www.investing.com/news/economic-indicators/trump-imposes-forced-labor-duties-on-60-trading-partners-as-10-us-tariffs-expire-4810447": {
        "facts": "美国对60个经济体的部分货物实施10%或12.5%的关税，理由涉及相关经济体未能遏制强迫劳动产品经供应链进入贸易体系；报道列及中国。",
        "risk": "新增关税可能促使含中国原料或零部件的货物改经东南亚、墨西哥等地加工，增加原产地证重签、供应商层级拆分、商品归类调整和低报价格的动机。",
    },
    "https://www.iea.org/news/supply-concentration-export-restrictions-and-declining-investment-put-critical-mineral-security-at-risk": {
        "facts": "国际能源署警告，关键矿产供应高度集中、出口限制和投资下降正在放大供应安全风险，并估计相关稀土限制可能影响中国境外约6.5万亿美元的下游产出。",
        "risk": "境内外价差和境外短缺加剧时，受管制稀土化合物、金属及磁材可能被改报为低含量合金、普通磁性零件、样品、废料或维修件，也可能经第三国换单转运。",
    },
}


def build_content(item: dict) -> str:
    detail = DETAILS[item["url"]]
    checks = "；".join(item["customs_checks"])
    return (
        f"信息来源：{item['source_name']}（{item['source_type']}），{item['published_at'][:10]}。\n\n"
        f"原始事件事实：{detail['facts']}\n\n"
        f"监管风险推演：{detail['risk']}该部分为基于公开事实的分析判断，不代表相关违法行为已经发生。\n\n"
        f"建议数据核查：{checks}。"
    )


def build_report(topic: Topic, items: list[CollectedItem], now: datetime) -> str:
    dated = [item.published_at.date() for item in items if item.published_at]
    start = min(dated).isoformat() if dated else "未知"
    end = max(dated).isoformat() if dated else "未知"
    lines = [
        f"# {topic.name}全部条目综合报告",
        "",
        f"- 生成时间：{now.astimezone().strftime('%Y-%m-%d %H:%M')}",
        f"- 信息范围：{start}至{end}",
        f"- 条目数量：{len(items)}条",
        "",
        "## 一、综合分析研判",
        "",
        "近期境外能源设施受损、重要海峡通行受阻、化肥和粮食供需波动、贸易救济及强迫劳动规则扩张、关键矿产出口管制等事件相互叠加，正在改变国际商品价差、贸易方向和加工转运路径。部分事件原文并不直接涉及中国，但其形成的区域短缺、利润空间和合规压力，可能经边境贸易、第三国加工、船对船转运及供应链重组传导至我国进出口环节。",
        "",
        "从监管风险看，一是能源、化肥、粮食等商品因境内外价差扩大，可能诱发边境走私、低报价格、品名错配及货源替换；二是光伏、稀土、两用物项等受贸易救济和出口管制影响，可能出现第三国简单加工、原产地洗白、拆分申报和最终用户隐匿；三是黄金及高价值货物可能与贸易型洗钱、夹藏运输和虚假贸易背景交织；四是航线受阻和制裁规避会增加换船、换单、AIS中断及装货港与原产国不一致等异常。",
        "",
        "建议围绕报关单、舱单、原产地证、许可证、企业关联、船舶轨迹和贸易价格开展联合分析，重点识别目的国突然变化、进口后短期复出口、境外产能与出口规模不匹配、单位价格显著偏离、同一货物频繁变更贸易商、异常小批量高频申报以及高风险口岸集中进出等特征。分析结论均应结合实际海关数据进一步验证，不宜直接认定违法行为。",
        "",
        "## 二、重点风险方向",
        "",
        "1. 能源与航运：关注俄罗斯燃油供应变化、中俄边境价差、霍尔木兹及红海绕航、船对船转运和油品来源识别。",
        "2. 农产品与化肥：关注印度及菲律宾等市场短缺、米价和肥价分化、货源替换、假劣农资及第三国转口。",
        "3. 关键矿产与两用物项：关注许可证拆分、低含量合金或废料伪报、境外代采、最终用户隐匿和原产地洗白。",
        "4. 光伏及制造业供应链：关注中国零部件经埃塞俄比亚、越南等地简单加工后输往欧美的增值率和真实产能。",
        "5. 高价值货物与贸易型洗钱：关注黄金夹藏、电子设备掩护、价格异常和资金流与货物流不匹配。",
        "",
        "## 三、采集信息条目",
        "",
    ]
    for index, item in enumerate(items, 1):
        source_type = ""
        metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
        if metadata.get("source_type"):
            source_type = f"；来源类型：{metadata['source_type']}"
        lines.extend([
            f"### {index}. {item.title}",
            "",
            f"- 发布时间：{item.published_at.date().isoformat() if item.published_at else '未知'}",
            f"- 分类：{item.category or '未分类'}{source_type}",
            f"- 原文链接：{item.url or '无'}",
            "",
            item.content or item.summary or "无正文",
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    preview = json.loads(PREVIEW_JSON.read_text(encoding="utf-8"))
    backup_dir = PROJECT_DIR.parent / "work" / "political_hotspots" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"gather-before-deep-hotspot-supplement-{datetime.now():%Y%m%d-%H%M%S}.db"
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
        run.batch_id = "codex-deep-hotspots-20260804-supplement"
        run.keywords_used = ["境外事件传导", "进出口监管风险", "第三国转运", "价差走私", "原产地规避"]
        run.items_found = len(preview["items"])
        run.started_at = now
        run.completed_at = now
        run.duration_ms = 0
        run.window_start = datetime(2026, 7, 15, tzinfo=timezone.utc)
        run.window_end = datetime(2026, 8, 4, 23, 59, 59, tzinfo=timezone.utc)
        run.metadata_json = {"provider": "codex_deep_web_research", "preview_path": str(PREVIEW_JSON)}

        inserted = 0
        updated = 0
        for index, data in enumerate(preview["items"], 1):
            existing = db.query(CollectedItem).filter(CollectedItem.url == data["url"]).first()
            item = existing
            if not item:
                item = CollectedItem(id=f"codex-deep-hotspot-20260804-{index:02d}")
                db.add(item)
                inserted += 1
            else:
                updated += 1
            content = build_content(data)
            item.source_id = SOURCE_ID
            item.run_id = RUN_ID
            item.topic_id = TOPIC_ID
            item.title = data["title"]
            item.content = content
            item.content_hash = hashlib.sha256(f"{data['url']}\n{content}".encode()).hexdigest()
            item.summary = DETAILS[data["url"]]["risk"]
            item.url = data["url"]
            item.language = "zh"
            item.category = data["category"]
            item.entities = {"risk_level": data["risk_level"], "customs_checks": data["customs_checks"]}
            item.status = "enriched"
            item.quality_score = 0.92
            item.relevance_score = 0.95
            item.published_at = datetime.fromisoformat(data["published_at"])
            item.collected_at = item.collected_at or now
            item.updated_at = now
            item.authorization_level = "public"
            item.raw_metadata = {
                "provider": "codex_deep_web_research",
                "import_batch": "codex-deep-hotspots-20260804-supplement",
                "source_name": data["source_name"],
                "source_type": data["source_type"],
                "customs_hotspot_review": {
                    "risk_level": data["risk_level"],
                    "customs_data_checks": data["customs_checks"],
                    "inference_notice": data["inference_notice"],
                },
            }

        run.items_new = inserted
        run.items_updated = updated
        run.items_failed = 0
        db.flush()

        all_items = (
            db.query(CollectedItem)
            .filter(CollectedItem.topic_id == TOPIC_ID)
            .order_by(CollectedItem.published_at.desc(), CollectedItem.id.asc())
            .all()
        )
        report_text = build_report(topic, all_items, now)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(report_text, encoding="utf-8")

        report = db.query(Report).filter(Report.id == REPORT_ID).first()
        if not report:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID)
            db.add(report)
        report.title = "涉进出口时政热点全部条目综合报告（2026年8月4日）"
        report.report_type = "analytical"
        report.content = report_text
        report.summary = f"综合分析涉进出口时政热点主题下全部{len(all_items)}条信息，研判能源、农资、关键矿产、两用物项、光伏供应链及贸易型洗钱风险，并附全部采集条目。"
        report.status = "completed"
        report.model_id = None
        report.tokens_used = 0
        report.item_count = len(all_items)
        report.item_ids = [item.id for item in all_items]
        report.error_log = None
        report.collection_run_id = RUN_ID
        dates = [item.published_at.date() for item in all_items if item.published_at]
        report.date_range_start = datetime.combine(min(dates), datetime.min.time()) if dates else None
        report.date_range_end = datetime.combine(max(dates), datetime.max.time()) if dates else None
        report.output_files = {"md": str(OUTPUT_PATH)}
        report.output_dir = str(OUTPUT_DIR)
        report.generated_at = now
        report.created_at = report.created_at or now

        source.items_collected = int(source.items_collected or 0) + inserted
        source.last_sync_at = now
        db.commit()
        print(f"backup={backup}")
        print(f"inserted={inserted} updated={updated} total_topic_items={len(all_items)}")
        print(f"report_id={REPORT_ID} item_count={report.item_count}")
        print(f"report_path={OUTPUT_PATH}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
