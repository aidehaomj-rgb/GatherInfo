"""Import newly researched hotspots, audit the topic, and build a Top 15 report."""
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
RUN_ID = "run-codex-high-value-hotspots-20260805"
REPORT_ID = "rpt-customs-hotspots-top15-20260805"
DB_PATH = PROJECT_DIR / "data" / "gather.db"
OUTPUT_DIR = PROJECT_DIR.parent / "outputs" / "时政热点信息分析"
OUTPUT_PATH = OUTPUT_DIR / "涉进出口时政热点高价值15条分析报告_2026-08-05.md"


NEW_ITEMS = [
    {
        "id": "codex-high-value-hotspot-20260805-01",
        "title": "中国升级对美无人机及关键部件出口审查，第三国代采与最终用户隐匿风险上升（高风险）",
        "published_at": "2026-08-05",
        "url": "https://apnews.com/article/china-us-sanctions-drone-forced-labor-ad0b637298e9608c5351bca84debeb25",
        "category": "无人机与两用物项出口管制",
        "source_name": "Associated Press",
        "source_type": "新闻报道（转述中国商务部措施）",
        "facts": "中国宣布对输美无人机、关键部件及相关技术实施逐案审查，并禁止与六家美国实体开展交易；报道同时提到美国近期限制进口中国无人机，并将43家中国企业加入UFLPA实体清单。",
        "risk": "受限买方可能转由第三国贸易商或关联企业采购，将整机拆分为电机、飞控、通信、载荷等部件申报，或以维修件、样品和民用终端用途掩盖真实最终用户。",
        "checks": ["HS 8806、8807及无人机关键部件", "出口许可证", "技术参数", "最终用户和最终用途", "目的国突变", "第三国企业关联", "拆分订单和小批量高频出口"],
    },
    {
        "id": "codex-high-value-hotspot-20260805-02",
        "title": "美国将43家中国企业加入UFLPA清单，关联企业代采与第三国加工转口风险显著上升（高风险）",
        "published_at": "2026-07-31",
        "url": "https://www.dhs.gov/news/2026/07/31/dhs-announces-addition-43-companies-uflpa-entity-list",
        "category": "强迫劳动规则与供应链穿透",
        "source_name": "美国国土安全部",
        "source_type": "官方公告（AP交叉印证）",
        "facts": "美国国土安全部宣布将43家中国企业加入《维吾尔强迫劳动预防法》实体清单；8月5日AP关于中美反制措施的报道再次确认该项清单扩容。",
        "risk": "被列企业相关货物可能改由未列名关联企业、贸易商或境外工厂接单，通过变更英文名称、供应商层级、生产地点和原产地证明继续输美，供应链穿透核查压力上升。",
        "checks": ["企业中英文名称和统一社会信用代码", "股东与实际控制人", "上下游供应商", "中国至东盟或墨西哥后再输美链路", "进口后短期复出口", "原产地证", "美国扣留记录"],
    },
    {
        "id": "codex-high-value-hotspot-20260805-03",
        "title": "黑海商船和港口连续受袭，粮食化肥改港转运与货源替换风险上升（高风险）",
        "published_at": "2026-08-04",
        "url": "https://apnews.com/article/russia-ukraine-war-beach-drone-222d8755b524c231faa8fd6de10f38ef",
        "category": "粮食化肥与航运安全",
        "source_name": "Associated Press",
        "source_type": "新闻报道",
        "facts": "俄罗斯与乌克兰相互攻击港口、船舶和港口设施；两艘土耳其船只离开新罗西斯克港后遭无人机攻击。土耳其警告黑海风险可能影响粮食、化肥等关键商品运输和全球食品供应。",
        "risk": "黑海货物可能临时改港、换船或绕行，推动粮食和化肥装货港、原产国与贸易国分离；短期价格波动还可能诱发低价货源冒充高价产地、提单重制及受限货源混装。",
        "checks": ["小麦、玉米、葵花籽油及化肥HS编码", "装货港与原产国", "船旗和IMO", "AIS中断", "改港换船", "单位价格和运保费", "贸易商临时变更"],
    },
    {
        "id": "codex-high-value-hotspot-20260805-04",
        "title": "哈萨克斯坦原油因黑海出口端中断一度减产过半，向东改道可能改变对华油品流向（中高风险）",
        "published_at": "2026-07-27",
        "url": "https://www.lse.co.uk/news/SHEL/kazakhstans-daily-oil-output-halves-after-export-terminal-closure-source-says-g4dxzuvai9kvlhx.html",
        "category": "原油供应与跨境流向",
        "source_name": "Reuters（London South East转载）",
        "source_type": "新闻报道",
        "facts": "哈萨克斯坦原油和凝析油日产量因CPC黑海出口终端关闭一度由约216万桶降至约100万桶；CPC承担该国超过80%的原油出口，报道发布时装船已开始恢复。",
        "risk": "西向出口受阻可能促使部分货源寻求向东管道、铁路或置换贸易，改变对华进口节奏和成交价；不同混合油种、过境贸易商及装运路径变化会增加原产地、品质和价格识别难度。",
        "checks": ["中哈原油管道流量", "铁路罐车和边境口岸", "CPC Blend及其他油种", "原产地和装货地", "贸易商变更", "硫含量与密度", "单位价格偏离"],
    },
]


# Score dimensions: source reliability 25, China transmission 25,
# customs-risk clarity 25, and data verifiability 25.
AUDIT = {
    "codex-high-value-hotspot-20260805-01": (96, "纳入", "直接涉及无人机两用物项、许可证和最终用户，监管抓手明确"),
    "codex-deep-hotspot-20260804-03": (95, "纳入", "官方反规避调查直接指向中国零部件第三国加工和原产地"),
    "codex-customs-risk-hotspot-20260804-08": (94, "纳入", "已发生黄金夹藏和贸易型洗钱案件，执法参考价值高"),
    "codex-high-value-hotspot-20260805-02": (93, "纳入", "43家企业清单可直接开展企业关联和供应链穿透"),
    "codex-customs-risk-hotspot-20260804-01": (92, "纳入", "俄境内燃油短缺可形成中俄边境价差和走私通道风险"),
    "codex-customs-risk-hotspot-20260804-06": (92, "纳入", "两用物项受限实体明确，适合核查代采和最终用户"),
    "codex-customs-risk-hotspot-20260804-05": (91, "纳入", "战略矿产拆分申报和第三国转运已有明确执法信号"),
    "codex-deep-hotspot-20260804-04": (90, "纳入", "关税变化可能系统性推动涉华供应链改道和归类调整"),
    "codex-deep-hotspot-20260804-01": (89, "纳入", "航线和船舶异常可通过舱单、AIS和价格数据验证"),
    "codex-customs-risk-hotspot-20260804-02": (88, "纳入", "俄油改道、混兑和换单与对华能源进口直接相关"),
    "codex-high-value-hotspot-20260805-03": (87, "纳入", "黑海粮食化肥运输风险可落到改港、换船和原产地核查"),
    "codex-high-value-hotspot-20260805-04": (86, "纳入", "哈油西向受阻可能改变中哈跨境流向，量价均可核验"),
    "codex-deep-hotspot-20260804-05": (85, "纳入", "稀土短缺和价差为拆分申报提供动机，商品范围明确"),
    "codex-customs-risk-hotspot-20260804-03": (83, "纳入", "印度化肥缺口与第三国采购、货源替换联系较强"),
    "codex-deep-hotspot-20260804-02": (82, "纳入", "越南新规影响多类涉华中间品的供应链证明和转口"),
    "codex-customs-risk-hotspot-20260804-07": (79, "未纳入", "政策重要，但与稀土及战略矿产条目重合度较高"),
    "5d3dcc660562a378": (75, "未纳入", "措施仍偏授权性质，实际限制清单和生效范围尚待细化"),
    "codex-customs-risk-hotspot-20260804-04": (73, "未纳入", "印度国内降税事件对中国监管传导链相对间接"),
    "codex-customs-risk-hotspot-20260804-10": (68, "未纳入", "菲律宾农资走私推演较泛，对中国通道和主体不够明确"),
    "codex-customs-risk-hotspot-20260804-09": (64, "未纳入", "区域米价波动常见，违法风险推演证据和区分度偏弱"),
}


def item_content(data: dict) -> str:
    checks = "；".join(data["checks"])
    return (
        f"信息来源：{data['source_name']}（{data['source_type']}），{data['published_at']}。\n\n"
        f"原始事件事实：{data['facts']}\n\n"
        f"监管风险推演：{data['risk']}该部分为基于公开事实的分析判断，不代表相关违法行为已经发生。\n\n"
        f"建议数据核查：{checks}。"
    )


def build_report(topic: Topic, selected: list[CollectedItem], all_items: list[CollectedItem], now: datetime) -> str:
    audit_rows = sorted(
        ((item, *AUDIT[item.id]) for item in all_items if item.id in AUDIT),
        key=lambda row: (-row[1], row[0].title),
    )
    lines = [
        f"# {topic.name}高价值15条分析报告",
        "",
        f"- 生成时间：{now.astimezone().strftime('%Y-%m-%d %H:%M')}",
        f"- 审核范围：主题下全部{len(all_items)}条信息",
        "- 入选数量：15条",
        "- 评分方法：来源可靠性、对华传导强度、海关风险明确度、数据可验证性各25分，总分100分",
        "",
        "## 一、综合分析研判",
        "",
        "本轮审核表明，最值得持续跟踪的风险集中在四条链路：一是无人机、两用物项、稀土等受管制商品通过第三国代采、拆分申报和隐匿最终用户规避许可；二是UFLPA、强迫劳动关税及光伏反规避调查推动中国原料和零部件经东南亚、非洲及墨西哥重构供应链；三是俄罗斯炼厂、黑海港口及霍尔木兹航线受扰，放大能源、粮食和化肥的价差、改港、换船、混兑及来源识别风险；四是黄金夹藏与虚假贸易背景交织，形成走私、骗税和洗钱复合风险。",
        "",
        "与一般时政资讯相比，入选条目均能进一步落到海关数据验证。建议优先建立企业关联、货物流向、商品归类、价格偏离、许可证、原产地证和船舶轨迹七类指标，重点识别目的国突变、进口后短期复出口、境外产能与出口规模不匹配、同一货物拆分为多品名小批量申报、贸易商临时替换、AIS长时间中断及装货港与原产国不一致等特征。",
        "",
        "## 二、审核结果",
        "",
        "| 排名 | 分值 | 结论 | 信息条目 | 审核意见 |",
        "|---:|---:|---|---|---|",
    ]
    for rank, (item, score, decision, reason) in enumerate(audit_rows, 1):
        lines.append(f"| {rank} | {score} | {decision} | {item.title} | {reason} |")

    lines.extend([
        "",
        "## 三、重点核查建议",
        "",
        "1. 企业穿透：对受限实体、关联企业、历史曾用名、境外销售公司及共同董监高建立关联图谱。",
        "2. 贸易流向：联查中国出口、第三国进口与第三国对美欧复出口，识别数量、时间和单价闭合关系。",
        "3. 商品识别：围绕无人机部件、稀土合金、磁性组件、化肥品级、油品牌号建立易错归类和成分阈值。",
        "4. 航运核查：联查提单、舱单、IMO、AIS、船旗、装货港、船对船转运和运保费变化。",
        "5. 风险处置：所有推演均须经报关、舱单、企业和资金数据交叉验证后再形成执法线索。",
        "",
        "## 四、入选信息条目",
        "",
    ])
    for rank, item in enumerate(selected, 1):
        score, _, reason = AUDIT[item.id]
        metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
        source_type = metadata.get("source_type") or "公开信息"
        lines.extend([
            f"### {rank}. {item.title}",
            "",
            f"- 价值评分：{score}分",
            f"- 入选理由：{reason}",
            f"- 发布时间：{item.published_at.date().isoformat() if item.published_at else '未知'}",
            f"- 分类：{item.category or '未分类'}",
            f"- 来源类型：{source_type}",
            f"- 原文链接：{item.url or '无'}",
            "",
            item.content or item.summary or "无正文",
            "",
        ])
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    backup_dir = PROJECT_DIR.parent / "work" / "political_hotspots" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"gather-before-top15-hotspot-import-{datetime.now():%Y%m%d-%H%M%S}.db"
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
        run.batch_id = "codex-high-value-hotspots-20260805"
        run.keywords_used = ["境外事件传导", "供应链穿透", "原产地规避", "航运异常", "出口管制", "走私风险"]
        run.items_found = len(NEW_ITEMS)
        run.started_at = now
        run.completed_at = now
        run.duration_ms = 0
        run.window_start = datetime(2026, 7, 16, tzinfo=timezone.utc)
        run.window_end = datetime(2026, 8, 5, 23, 59, 59, tzinfo=timezone.utc)
        run.metadata_json = {"provider": "codex_deep_web_research", "audit_method": "four_dimension_100_point"}

        inserted = 0
        updated = 0
        for data in NEW_ITEMS:
            existing = db.query(CollectedItem).filter(CollectedItem.url == data["url"]).first()
            item = existing or CollectedItem(id=data["id"])
            if not existing:
                db.add(item)
                inserted += 1
            else:
                updated += 1
            content = item_content(data)
            item.source_id = SOURCE_ID
            item.run_id = RUN_ID
            item.topic_id = TOPIC_ID
            item.title = data["title"]
            item.content = content
            item.content_hash = hashlib.sha256(f"{data['url']}\n{content}".encode()).hexdigest()
            item.summary = data["risk"]
            item.url = data["url"]
            item.language = "zh"
            item.category = data["category"]
            item.entities = {"customs_checks": data["checks"]}
            item.status = "enriched"
            item.quality_score = 0.94
            item.relevance_score = 0.96
            item.published_at = datetime.fromisoformat(data["published_at"]).replace(tzinfo=timezone.utc)
            item.collected_at = item.collected_at or now
            item.updated_at = now
            item.authorization_level = "public"
            item.raw_metadata = {
                "provider": "codex_deep_web_research",
                "import_batch": "codex-high-value-hotspots-20260805",
                "source_name": data["source_name"],
                "source_type": data["source_type"],
                "customs_hotspot_review": {
                    "customs_data_checks": data["checks"],
                    "analysis_disclaimer": "监管风险为基于公开事实的分析判断，须经海关数据验证。",
                },
            }

        run.items_new = inserted
        run.items_updated = updated
        run.items_failed = 0
        db.flush()

        all_items = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).all()
        missing = set(AUDIT) - {item.id for item in all_items}
        if missing:
            raise RuntimeError(f"Audit item IDs missing from database: {sorted(missing)}")
        selected = sorted(
            (item for item in all_items if AUDIT.get(item.id, (0, "", ""))[1] == "纳入"),
            key=lambda item: (-AUDIT[item.id][0], item.title),
        )
        if len(selected) != 15:
            raise RuntimeError(f"Expected 15 selected items, found {len(selected)}")

        for item in all_items:
            if item.id not in AUDIT:
                continue
            metadata = dict(item.raw_metadata or {})
            metadata["value_audit_20260805"] = {
                "score": AUDIT[item.id][0],
                "decision": AUDIT[item.id][1],
                "reason": AUDIT[item.id][2],
            }
            item.raw_metadata = metadata

        report_text = build_report(topic, selected, all_items, now)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(report_text, encoding="utf-8")

        report = db.query(Report).filter(Report.id == REPORT_ID).first()
        if not report:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID)
            db.add(report)
        report.title = "涉进出口时政热点高价值15条分析报告（2026年8月5日）"
        report.report_type = "analytical"
        report.content = report_text
        report.summary = "对主题下全部20条信息统一审核，按来源可靠性、对华传导强度、海关风险明确度和数据可验证性筛选15条高价值线索，并提出供应链穿透、贸易流向、商品识别和航运核查建议。"
        report.status = "completed"
        report.model_id = None
        report.tokens_used = 0
        report.item_count = len(selected)
        report.item_ids = [item.id for item in selected]
        report.error_log = None
        report.collection_run_id = RUN_ID
        dates = [item.published_at.date() for item in selected if item.published_at]
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
        print(f"report_id={REPORT_ID} selected={len(selected)}")
        print(f"report_path={OUTPUT_PATH}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
