"""Import the approved items from the 2026-08-08 customs hotspot review."""
from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
ROOT_DIR = PROJECT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, CollectionRun, SourceConfig, Topic  # noqa: E402


TOPIC_ID = "weekly-trade-current-affairs"
SOURCE_ID = "ai-smart-web-research"
RUN_ID = "run-customs-hotspot-deep-review-20260808"
BATCH_ID = "customs-hotspot-deep-review-20260808"
DB_PATH = PROJECT_DIR / "data" / "gather.db"
WINDOW_START = datetime(2026, 7, 20, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 8, 23, 59, 59, tzinfo=timezone.utc)


APPROVED_ITEMS = [
    {
        "id": "customs-hotspot-reviewed-20260808-01",
        "title": "中国保税船用燃料油出口单月增长55%，舟山上海价差扩大需核查保税油账实与供船单证（高风险）",
        "published_at": "2026-07-20",
        "url": "https://au.marketscreener.com/news/china-s-june-fuel-oil-exports-for-bunkers-up-55-from-may-data-shows-ce7f51dad189ff25",
        "category": "保税燃料与港口监管",
        "source_name": "Reuters（MarketScreener转载）",
        "source_type": "行业数据报道（引用中国海关统计数据）",
        "facts": (
            "报道援引中国海关数据称，2026年6月中国燃料油出口量为272.70万吨，环比增长55%、同比增长18%，"
            "为当年最高；相关出口主要为国际航行船舶加注燃料。同期燃料油进口量为98.28万吨，环比增长76%，"
            "普通贸易进口为零，全部进入保税仓储。市场数据显示，舟山、上海交付的0.5%低硫船用燃料油"
            "较新加坡便宜约50美元/吨。"
        ),
        "transmission_chain": (
            "中国港口船燃价差扩大和加注需求上升→保税燃料油进口、储存及供船出口周转加快→"
            "保税账册、罐容计量、供船单证和出口舱单之间的一致性风险上升。"
        ),
        "customs_stage": "中国港口与舱单、保税监管、出口申报",
        "risk": (
            "该变化直接发生在中国海关保税监管和供船出口环节。业务量快速增长本身不代表违规，但在明显价差下，"
            "需防范保税油数量账实不符、合理损耗异常放大、保税油违规内销、同批货物进出区信息不一致，"
            "以及供油船、受油船与出口舱单无法闭环等风险。"
        ),
        "checks": [
            "HS 2710项下燃料油进口、保税入库和供船出口数据",
            "保税账册、储罐液位和计量单",
            "供油确认单、受油船IMO编号和AIS轨迹",
            "进口舱单、出口舱单及报关单数量",
            "企业单月环比增幅、合理损耗率和库存周转率",
            "舟山、上海与新加坡同期价格及异常低报价格",
        ],
        "scores": {
            "china_customs_score": 98,
            "transmission_evidence_score": 96,
            "executable_check_score": 98,
            "source_reliability_score": 94,
        },
        "quality_score": 0.96,
        "relevance_score": 0.99,
    },
    {
        "id": "customs-hotspot-reviewed-20260808-02",
        "title": "哈萨克斯坦三周查获1342起燃油非法外运，已有中国方向改装油箱案例需强化中哈口岸联查（高风险）",
        "published_at": "2026-07-23",
        "url": "https://fbrk.kz/en-gb/news/knb-has-stopped-over-thousand-attempts-illegally-export-fuel-kazakhstan",
        "related_urls": [
            "https://www.gov.kz/memleket/entities/kgd-vko/press/news/details/1260706?lang=ru",
        ],
        "category": "中哈边境燃油走私",
        "source_name": "FBRK转引哈萨克斯坦国家安全委员会通报；哈萨克斯坦东哈州国家收入局",
        "source_type": "媒体转引官方执法通报 + 政府部门执法通报",
        "facts": (
            "哈萨克斯坦国家安全委员会边防部门通报，2026年7月1日至21日共制止1342起燃油非法外运尝试，"
            "涉及汽油、柴油等超过112吨。东哈萨克斯坦州国家收入局另行披露，7月10日迈卡普恰盖海关检查"
            "驶往中国的4辆空载货车时，在非原厂加装油箱内发现约2640升柴油，车辆由中国公民驾驶。"
            "哈方当时对HS 2709、2710、2902、3403、3811、382600等相关油品实施阶段性出口限制。"
        ),
        "transmission_chain": (
            "哈萨克斯坦燃油出口限制和境内外价差→车辆利用非原厂油箱、小批量高频方式向边境外运→"
            "已有驶往中国的实际案例→中国对应陆路口岸面临未申报燃油入境和车辆夹藏风险。"
        ),
        "customs_stage": "中外陆路边境、中国进境申报与查验",
        "risk": (
            "汇总通报没有说明1342起案件均流向中国，不能将其全部认定为对华走私；但哈方已公布中国方向的"
            "实案，证明传导通道客观存在。需重点关注空载返程货车、非原厂副油箱、车辆自重异常、"
            "同一车辆短期高频往返，以及将柴油改报为润滑油、溶剂油或车辆自用燃料的风险。"
        ),
        "checks": [
            "中哈公路口岸车辆进出境记录和道路载货清单",
            "车牌、车架号、驾驶人和运输企业关联",
            "原厂油箱容积、改装痕迹、车辆自重与实测油量",
            "空载返程和短期高频往返异常",
            "HS 2710及润滑油、溶剂油相近品名申报",
            "哈方查获车辆名单、时间和中国口岸入境记录碰撞",
        ],
        "scores": {
            "china_customs_score": 96,
            "transmission_evidence_score": 94,
            "executable_check_score": 97,
            "source_reliability_score": 93,
        },
        "quality_score": 0.95,
        "relevance_score": 0.99,
    },
    {
        "id": "customs-hotspot-reviewed-20260808-03",
        "title": "农产品出口配额二次分配明确边贸粮食限口岸、供港澳小麦粉禁转口，需核查配额与物流一致性（中高风险）",
        "published_at": "2026-07-27",
        "url": "https://wms.mofcom.gov.cn/zcfb/wmgl/art/2026/art_304de80295e34e5db1b0525dfb4c5483.html",
        "category": "农产品出口配额与许可证",
        "source_name": "中华人民共和国商务部外贸司",
        "source_type": "政府部门通知（原创政策文件）",
        "facts": (
            "商务部7月27日发布2026年农产品出口配额第二次分配通知，涉及供港澳活猪和活牛、边贸大米、"
            "边贸小麦粉、锯材及供港澳小麦粉。通知明确，边贸大米和小麦粉仅限向本地区毗邻国家的传统边贸市场出口，"
            "不得跨省或从本地区非边贸口岸报关；供港澳小麦粉仅限香港、澳门市场，不得转口其他国家和地区，"
            "出口许可证备注栏须加注限向和禁转口信息。"
        ),
        "transmission_chain": (
            "农产品出口配额二次分配并限定企业、地区、口岸和目的地→企业配额使用与实际物流必须对应→"
            "跨省报关、非边贸口岸出口、借港澳转口或许可证备注缺失可直接形成中国出境监管风险。"
        ),
        "customs_stage": "中国出境、出口许可证、边境贸易和供港澳监管",
        "risk": (
            "风险直接落在中国海关出口申报和许可证验核环节。需防范非配额企业借用抬头、同一配额重复或超量使用、"
            "边贸粮食跨省或改走非边贸口岸、目的国与毗邻市场不符，以及供港澳小麦粉通过中间收货人再转口。"
        ),
        "checks": [
            "配额分配表、出口许可证和报关单核销数量",
            "企业注册地、配额分配地区与申报口岸",
            "大米HS 1006、小麦粉HS 1101及锯材HS 4407等商品范围",
            "合同目的国、收货人、运输路线和实际离境口岸",
            "许可证备注栏的限向和禁转口信息",
            "香港、澳门收货人后续仓储、提单和异常短期再出口线索",
        ],
        "scores": {
            "china_customs_score": 100,
            "transmission_evidence_score": 100,
            "executable_check_score": 99,
            "source_reliability_score": 100,
        },
        "quality_score": 0.98,
        "relevance_score": 1.0,
    },
]


REVIEWED_CANDIDATES = [
    {
        "candidate": "中国保税船用燃料油进出口与供船出口增长",
        "decision": "approved",
        "reason": "直接进入中国保税、港口舱单和出口监管，具有明确统计异常与可核查单证。",
    },
    {
        "candidate": "哈萨克斯坦燃油非法外运及中国方向改装油箱案例",
        "decision": "approved",
        "reason": "存在官方披露的中国方向实案，可落到中哈陆路口岸车辆和进境申报核查。",
    },
    {
        "candidate": "2026年农产品出口配额第二次分配",
        "decision": "approved",
        "reason": "政策直接限定中国出口企业、配额、口岸、目的地和许可证备注。",
    },
    {
        "candidate": "中国7月贸易及稀土出口量价变化",
        "decision": "observe",
        "reason": "只有全国汇总数据，尚缺具体商品、企业或路线异常，不单独形成风险条目。",
    },
    {
        "candidate": "中国与胡塞方面沟通赴华油轮红海通行",
        "decision": "duplicate",
        "reason": "与主题内既有霍尔木兹、红海改道及对华能源舱单风险条目高度重合。",
    },
    {
        "candidate": "美国LNG进入中国保税仓储后复出口",
        "decision": "duplicate",
        "reason": "与主题内既有LNG保税转口条目重复。",
    },
    {
        "candidate": "美国新增UFLPA实体",
        "decision": "duplicate",
        "reason": "主题内已有同一事件，且主要属于外国进口执法，不能重复作为中国海关风险入库。",
    },
    {
        "candidate": "韩国成品油运往俄罗斯远东",
        "decision": "rejected",
        "reason": "没有足够证据证明货物流入中国或改变中国进出口监管风险。",
    },
    {
        "candidate": "进出境特殊货物物品卫生检疫新规生效",
        "decision": "out_of_window",
        "reason": "本期虽进入实施日，但原始公告和解读发布时间不在近20天采集窗口内。",
    },
]


def build_content(data: dict) -> str:
    checks = "；".join(data["checks"])
    return (
        f"信息来源：{data['source_name']}；来源性质：{data['source_type']}；发布时间：{data['published_at']}。\n\n"
        f"原始事实：{data['facts']}\n\n"
        f"对华传导研判：{data['transmission_chain']}\n\n"
        f"中国海关监管落点：{data['customs_stage']}。{data['risk']}\n\n"
        f"建议数据核查：{checks}。\n\n"
        "审核结论：涉及中国进出口监管风险，准予纳入主题。风险研判用于确定数据核查方向，"
        "不代表相关违法行为已经发生。"
    )


def main() -> int:
    backup_dir = ROOT_DIR / "work" / "political_hotspots" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"gather-before-hotspot-review-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(DB_PATH, backup_path)

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

        inserted = 0
        updated = 0
        imported_ids: list[str] = []
        for data in APPROVED_ITEMS:
            item = db.query(CollectedItem).filter(CollectedItem.url == data["url"]).first()
            if item is None:
                item = db.query(CollectedItem).filter(CollectedItem.id == data["id"]).first()
            if item is None:
                item = CollectedItem(id=data["id"])
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
            item.content_hash = hashlib.sha256(
                f"{data['url']}\n{content}".encode("utf-8")
            ).hexdigest()
            item.summary = data["risk"]
            item.url = data["url"]
            item.language = "zh"
            item.category = data["category"]
            item.entities = {
                "countries": ["中国"],
                "customs_stage": data["customs_stage"],
                "customs_checks": data["checks"],
            }
            item.status = "enriched"
            item.quality_score = data["quality_score"]
            item.relevance_score = data["relevance_score"]
            item.published_at = datetime.fromisoformat(data["published_at"]).replace(
                tzinfo=timezone.utc
            )
            item.collected_at = item.collected_at or now
            item.updated_at = now
            item.authorization_level = "public"
            item.raw_metadata = {
                "provider": "iterative_open_source_review",
                "import_batch": BATCH_ID,
                "research_window": "2026-07-20/2026-08-08",
                "source_name": data["source_name"],
                "source_type": data["source_type"],
                "related_urls": data.get("related_urls", []),
                "customs_hotspot_review": {
                    "decision": "approved",
                    "foreign_enforcement_only": False,
                    "china_customs_stage": data["customs_stage"],
                    "transmission_chain": data["transmission_chain"],
                    "customs_data_checks": data["checks"],
                    **data["scores"],
                },
                "analysis_disclaimer": (
                    "风险研判用于确定海关数据核查方向，不代表相关违法行为已经发生。"
                ),
                "tags": ["涉进出口时政热点", "中国海关监管风险", data["category"]],
            }
            imported_ids.append(item.id)

        run.source_id = SOURCE_ID
        run.topic_id = TOPIC_ID
        run.status = "completed"
        run.batch_id = BATCH_ID
        run.keywords_used = [
            "中国进出口监管风险",
            "保税燃料油",
            "中哈边境燃油非法外运",
            "农产品出口配额",
            "口岸与舱单异常",
            "可执行数据核查",
        ]
        run.items_found = len(REVIEWED_CANDIDATES)
        run.items_new = inserted
        run.items_updated = updated
        run.items_failed = 0
        run.started_at = now
        run.completed_at = now
        run.duration_ms = 0
        run.window_start = WINDOW_START
        run.window_end = WINDOW_END
        run.error_log = None
        run.metadata_json = {
            "provider": "iterative_open_source_review",
            "review_method": "china_customs_transmission_and_actionability",
            "reviewed_count": len(REVIEWED_CANDIDATES),
            "approved_count": len(APPROVED_ITEMS),
            "imported_item_ids": imported_ids,
            "candidate_reviews": REVIEWED_CANDIDATES,
        }

        source.items_collected = int(source.items_collected or 0) + inserted
        source.last_sync_at = now
        source.last_error = None
        topic.last_run_at = now
        topic.last_collection_run_id = RUN_ID
        topic.last_error = None
        db.flush()
        topic.total_items_collected = db.query(CollectedItem).filter(
            CollectedItem.topic_id == TOPIC_ID
        ).count()
        db.commit()

        print(f"backup={backup_path}")
        print(
            f"run_id={RUN_ID} reviewed={len(REVIEWED_CANDIDATES)} "
            f"approved={len(APPROVED_ITEMS)} inserted={inserted} updated={updated}"
        )
        print("imported_ids=" + ",".join(imported_ids))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
