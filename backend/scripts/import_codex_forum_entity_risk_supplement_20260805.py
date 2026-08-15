"""Import a direct-entity supplement for the foreign-trade forum risk topic.

The source pages are public forum posts.  Their statements are leads for
verification, not findings of fact or determinations that any named entity
committed an offence.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal, _db_file_path
from app.models import CollectionRun, CollectedItem, Report, SourceConfig, Topic


TOPIC_ID = "foreign-trade-forum-risk-monitoring"
SOURCE_ID = "forum-fobshanghai"
REPORT_ID = "report-forum-risk-20260805044348"
RUN_ID = "codex-forum-deep-20260805-forum-fobshanghai"
CHINA_TZ = timezone(timedelta(hours=8))


def _published(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=CHINA_TZ)


ITEMS = [
    {
        "id": "codex-forum-risk-20260805-deep-01",
        "title": "报关价格异常并出现疑似“疏通放行费”自述，涉及上海物流企业及马士基船期",
        "url": "https://bbs.fobshanghai.com/thread-1975475-1-1.html",
        "published_at": _published("2009-06-24 19:30"),
        "content": (
            "福步论坛发帖人自述：2009年5月22日将订舱与委托资料交给上海永道物流有限公司，"
            "一台烤箱和两台压面机拟于6月2日搭乘马士基船期由上海发往马里。货物被告知遭海关查验，"
            "其中价格较低的压面机被申报为4.3万美元。帖文称货代先提出8900元用于“搞定相关人员”"
            "并放行，后续又出现3万余元报价，最终谈至2万元；发帖人称整票货值约4万元人民币。"
            "以上均为论坛单方陈述，未见报关单、查验记录、付款凭证或执法文书，企业与费用说法未经独立核验。"
        ),
        "summary": (
            "直接实体包括上海永道物流有限公司、上海出运口岸语境、马士基承运计划和上海—马里路线；"
            "风险信号为申报价格显著异常、海关查验及疑似以费用疏通放行。具体船名、航次、提单号和箱号未公开。"
        ),
        "entities": {
            "企业名称": ["上海永道物流有限公司（帖文所称受托企业，未经核验）"],
            "口岸名称": ["上海口岸（帖文语境，具体码头未明）"],
            "承运人或船公司": ["马士基（仅提拟搭乘船期，未给出具体船名/航次）"],
            "航线": ["上海—马里"],
            "货物": ["烤箱1台", "压面机2台"],
            "金额": ["压面机申报4.3万美元（帖文自述）", "8900元/3万余元/2万元费用（帖文自述）", "整票货值约4万元人民币（帖文自述）"],
            "风险方式": ["申报价格异常", "海关查验", "疑似疏通放行费"],
        },
        "quality_score": 93.0,
        "relevance_score": 99.0,
        "risk_level": "very_high_lead",
        "evidence_strength": "forum_first_person_unverified",
        "identifier_presence": {
            "port_name": True,
            "enterprise_name": True,
            "carrier_name": True,
            "vessel_name_actual": False,
            "voyage_actual": False,
            "container_number_actual": False,
            "bill_of_lading_actual": False,
        },
    },
    {
        "id": "codex-forum-risk-20260805-deep-02",
        "title": "洋山港箱封号改变但无查验通知，费用单涉及上海深水港国际物流有限公司",
        "url": "https://bbs.fobshanghai.com/thread-5788351-1-1.html",
        "published_at": _published("2015-05-20 21:12"),
        "content": (
            "福步论坛发帖人自述：一票货于2015年5月14日报关，货代称15日10时收到查验通知，"
            "但海关网站至17日仍显示“已接受”，18日才显示放行。费用清单列报关150元、查验585元、"
            "箱体拖运536元、理货改配50元、查验代理300元、专用封志100元，合计1721元。"
            "帖文称模糊发票的销货单位为上海深水港国际物流有限公司，货物经洋山港；"
            "申报单位和仓库拒绝提供海关查验通知单及彩色发票。标题明确称箱封号发生改变，"
            "但帖子未公开变更前后的实际封志号码。以上信息未取得海关或企业方面确认。"
        ),
        "summary": (
            "直接实体包括洋山港及上海深水港国际物流有限公司；同时具备报关—查验—放行时间线、"
            "六项费用、箱封号变更及查验通知缺失等可核查要素。实际箱号和新旧封志号未公开。"
        ),
        "entities": {
            "企业名称": ["上海深水港国际物流有限公司（帖文所述发票销货单位，未经核验）"],
            "口岸名称": ["洋山港"],
            "时间节点": ["2015-05-14报关", "2015-05-15 10:00货代称收到查验通知", "2015-05-18网站显示放行"],
            "费用": ["报关150元", "查验585元", "箱体拖运536元", "理货改配50元", "查验代理300元", "专用封志100元", "合计1721元"],
            "监管状态": ["已接受", "放行"],
            "风险方式": ["箱封号改变", "查验通知单缺失", "状态时间差异", "查验费用真实性待核"],
        },
        "quality_score": 94.0,
        "relevance_score": 99.0,
        "risk_level": "very_high_lead",
        "evidence_strength": "forum_first_person_with_invoice_description_unverified",
        "identifier_presence": {
            "port_name": True,
            "enterprise_name": True,
            "container_seal_change": True,
            "container_number_actual": False,
            "seal_numbers_actual": False,
            "inspection_notice_actual": False,
        },
    },
    {
        "id": "codex-forum-risk-20260805-deep-03",
        "title": "上海港/洋山港拼箱机械查验费用争议，发帖人称掌握报关单号、箱号、船名和提单号",
        "url": "https://bbs.fobshanghai.com/thread-5479931-1-1.html",
        "published_at": _published("2014-11-28 17:41"),
        "content": (
            "福步论坛发帖人自述：客户指定货代承运两台机器、约6立方米拼箱货物，"
            "被告知在上海洋山港遭海关查验并产生1600余元费用。发帖人质疑为何没有查验通知，"
            "货代解释洋山不出查验通知且按票而非整箱查验，并提供一份模糊的深水港发票PDF。"
            "发帖人称其掌握报关单号、集装箱号、船名和提单号，希望核实是否实际查验，"
            "但帖子没有公开这些编号或船名。发帖人还称客户指定货代的货物查验频率约为十票六票，"
            "该比例同样未获独立验证。"
        ),
        "summary": (
            "直接实体为上海港、洋山港；运输方式为两台机器约6立方米拼箱。"
            "帖文明确称存在报关单号、箱号、船名和提单号，但实际值未发布，因此仅能作为核查入口，不能直接串联轨迹。"
        ),
        "entities": {
            "口岸名称": ["上海港", "洋山港"],
            "货物": ["机器2台", "约6立方米"],
            "运输方式": ["拼箱"],
            "费用": ["查验相关费用1600余元（帖文自述）"],
            "标识符类型": ["报关单号（称掌握但未公开）", "集装箱号（称掌握但未公开）", "船名（称掌握但未公开）", "提单号（称掌握但未公开）"],
            "风险方式": ["查验真实性争议", "查验通知缺失", "查验费用真实性待核"],
        },
        "quality_score": 87.0,
        "relevance_score": 95.0,
        "risk_level": "high_lead",
        "evidence_strength": "forum_first_person_unverified",
        "identifier_presence": {
            "port_name": True,
            "enterprise_name": False,
            "container_number_mentioned": True,
            "container_number_actual": False,
            "vessel_name_mentioned": True,
            "vessel_name_actual": False,
            "customs_declaration_number_actual": False,
            "bill_of_lading_actual": False,
        },
    },
]


REPORT_CONTENT = """# 外贸论坛违规清关与走私风险线索专题报告（深度增补版）

**深度增补日期：** 2026-08-05  
**采集方式：** Codex直接检索和读取论坛公开页面，未调用项目内百度搜索API或Tavily；未登录、未加入私域群组、未联系发帖人。

## 一、结论

本轮补入3条具备更直接监管实体的历史论坛线索，现有报告共6条。最值得优先核查的是：（1）报关价格明显异常并出现疑似“疏通放行费”的自述，帖文点名受托物流企业并给出上海—马里路线及马士基船期；（2）洋山港箱封号改变、无查验通知且费用发票涉及具体物流企业；（3）上海/洋山港拼箱机械查验争议，发帖人称掌握报关单号、箱号、船名和提单号。

本轮仍未发现“高风险事件 + 公开完整集装箱号/船名/提单号”同时出现的可靠帖子。部分帖子称掌握这些标识符但未公开实际值。所有企业名称、金额和事件经过均来自论坛发帖人自述，未经海关、企业或司法文书独立核验；风险标注只表示核查优先级，不构成违法认定。

## 二、新增高价值线索

### 1. 报关价格异常与疑似疏通放行费（极高优先级线索）

[原帖：这票货我还要吗？报关行勒索2万搞定费](https://bbs.fobshanghai.com/thread-1975475-1-1.html)

- 直接实体：上海永道物流有限公司（帖文所称受托企业）、上海出运口岸语境、马士基承运计划、上海—马里路线。
- 货物：烤箱1台、压面机2台；拟于2009年6月2日出运。
- 核心异常：帖文称价格较低的压面机被申报为4.3万美元；货物查验后出现8900元、3万余元、2万元等“搞定/放行”费用说法，而整票货值据称约4万元人民币。
- 缺口：未公开报关单、箱号、船名/航次、提单及付款凭证；需核对历史申报数据与资金凭证。

### 2. 洋山港箱封号改变、无查验通知及费用单争议（极高优先级线索）

[原帖：箱封号有改变但无查验通知单是否能确认海关查验了呢](https://bbs.fobshanghai.com/thread-5788351-1-1.html)

- 直接实体：洋山港；上海深水港国际物流有限公司（帖文所述发票销货单位）。
- 时间线：2015年5月14日报关；货代称15日10时收到查验通知；网站至17日仍显示“已接受”，18日显示放行。
- 费用：报关150元、查验585元、箱体拖运536元、理货改配50元、查验代理300元、专用封志100元，合计1721元。
- 核心异常：标题称箱封号改变，但申报单位和仓库拒绝提供查验通知及彩色发票。
- 缺口：未公开实际箱号和新旧封志号，需调取海关查验、码头作业、封志领用及发票记录交叉核验。

### 3. 上海/洋山港拼箱机械查验真实性争议（高优先级线索）

[原帖：上海港海关查验，大家帮个忙](https://bbs.fobshanghai.com/thread-5479931-1-1.html)

- 直接实体：上海港、洋山港；两台机器、约6立方米、拼箱运输。
- 核心异常：客户指定货代称被查验并收取1600余元，但未提供查验通知，仅提供模糊发票。
- 标识符：发帖人称掌握报关单号、集装箱号、船名和提单号，但未在帖子中公开实际值。
- 缺口：需由原始单证或海关/码头系统核验，帖子本身不足以确认是否真实查验或存在违规收费。

## 三、原报告中仍应保留的两类风险

1. [马来西亚转口铝材案例](https://bbs.fobshanghai.com/thread-9327008-1-1.html)：已具备蛇口码头、阳明海运、巴生港西港、2×40HQ、铝材、马来西亚—意大利路线及14万欧元处罚自述等组合要素，适合围绕箱轨迹、换柜、原产地证及贸易救济税追溯。
2. [双清包税异常申报讨论](https://www.tradeach.com/club/goto.php?itemid=9904)：出现混报、换品名、虚报价值数量和买单报关等方式，但缺少企业、口岸和单证编号，宜作为模式词库而非直接案件线索。

## 四、建议核查顺序

1. 以“企业 + 口岸 + 日期”为第一层关联，查询对应报关单、查验记录、码头作业及发票。
2. 对箱封号变更，核对原封志、查验专用封志领用、开箱/复封时间和操作主体。
3. 对疑似疏通费，核对货代报价、收款账户、付款凭证、会计科目及查验代理委托关系。
4. 对第三国转口，串联原箱号/换箱号、船名航次、提单、原产地证和第三国加工能力。
5. 只有在报关、物流、资金或官方文书形成相互印证后，才升级为确定性风险结论。

## 五、后续关键词增强

主题已追加：箱封号、封志号、集装箱号、船名、航次、提单号、报关单号、查验通知单、查验费、查验代理、码头作业、换柜、改配、放行费、疏通费。后续优先保留同时命中“口岸/企业/运输标识符”和“查验/申报/放行异常”的帖子。
"""


def _backup_database() -> str | None:
    path = _db_file_path()
    if not path or not os.path.exists(path):
        return None
    backup_dir = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"gather.before_forum_entity_supplement.{stamp}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    return dest


def _upsert_item(db, data: dict, now: datetime) -> tuple[CollectedItem, bool]:
    item = db.get(CollectedItem, data["id"])
    is_new = item is None
    if item is None:
        item = CollectedItem(id=data["id"], source_id=SOURCE_ID, topic_id=TOPIC_ID)
        db.add(item)
    item.run_id = RUN_ID
    item.title = data["title"]
    item.content = data["content"]
    item.content_hash = hashlib.sha256(data["content"].encode("utf-8")).hexdigest()
    item.summary = data["summary"]
    item.url = data["url"]
    item.language = "zh"
    item.category = "海关进出口监管风险/论坛历史线索"
    item.entities = data["entities"]
    item.status = "enriched"
    item.quality_score = data["quality_score"]
    item.relevance_score = data["relevance_score"]
    item.published_at = data["published_at"]
    item.collected_at = item.collected_at or now
    item.updated_at = now
    item.authorization_level = "public"
    item.raw_metadata = {
        "collector": "Codex browser direct deep search",
        "public_access": True,
        "historical_case": True,
        "risk_level": data["risk_level"],
        "evidence_type": data["evidence_strength"],
        "independent_verification": "pending",
        "allegation_notice": "论坛发帖人自述，未经独立核验，不构成对相关企业或个人的违法认定",
        "identifier_presence": data["identifier_presence"],
        "contact_details_stored": False,
        "used_baidu_search_api": False,
        "used_tavily": False,
    }
    return item, is_new


def main() -> None:
    backup = _backup_database()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        topic = db.get(Topic, TOPIC_ID)
        source = db.get(SourceConfig, SOURCE_ID)
        report = db.get(Report, REPORT_ID)
        if not topic or not source or not report:
            raise RuntimeError("Required topic, source, or report is missing")

        added = 0
        for data in ITEMS:
            _, is_new = _upsert_item(db, data, now)
            added += int(is_new)

        run = db.get(CollectionRun, RUN_ID)
        if run is None:
            run = CollectionRun(id=RUN_ID, source_id=SOURCE_ID, topic_id=TOPIC_ID)
            db.add(run)
        run.status = "completed"
        run.batch_id = "codex-forum-entity-deep-20260805"
        run.keywords_used = [
            "箱封号", "封志号", "集装箱号", "船名", "航次", "提单号", "报关单号",
            "查验通知单", "查验费", "洋山港", "企业名称", "放行费", "疏通费",
        ]
        run.items_found = len(ITEMS)
        # This stable run ID represents the original deep-search import.  Keep
        # its metrics stable when the script is re-run for verification.
        run.items_new = len(ITEMS)
        run.items_updated = 0
        run.items_failed = 0
        run.started_at = run.started_at or now
        run.completed_at = now
        run.duration_ms = 0
        run.window_start = min(item["published_at"] for item in ITEMS)
        run.window_end = now
        run.error_log = []
        run.metadata_json = {
            "collector": "codex_browser_direct_deep_search",
            "scope": "public_forum_historical_entity_leads",
            "used_baidu_search_api": False,
            "used_tavily": False,
            "actual_container_numbers_found_in_risk_posts": 0,
            "verification_status": "pending",
        }
        run.progress_events = [
            {"at": now.isoformat(), "message": "深度检索并结构化3条含口岸、企业或运输标识符的论坛历史线索"}
        ]

        enhanced_keywords = [
            "箱封号", "封志号", "集装箱号", "船名", "航次", "提单号", "报关单号",
            "查验通知单", "查验费", "查验代理", "码头作业", "换柜", "改配", "放行费", "疏通费",
        ]
        topic.keywords = list(dict.fromkeys((topic.keywords or []) + enhanced_keywords))
        topic.last_run_at = now
        topic.last_collection_run_id = RUN_ID
        topic.last_error = None
        topic.updated_at = now

        all_item_ids = list(report.item_ids or [])
        for data in ITEMS:
            if data["id"] not in all_item_ids:
                all_item_ids.append(data["id"])
        report.title = "外贸论坛违规清关与走私风险线索专题报告（深度增补版，2026-08-05）"
        report.content = REPORT_CONTENT
        report.summary = (
            "深度增补3条含直接监管实体的历史论坛线索；现共6条。最高优先级为申报价格异常及疑似疏通放行费、"
            "洋山港箱封号改变且无查验通知两帖。尚未发现与高风险事件同时公开完整箱号、船名或提单号的可靠帖子。"
        )
        report.status = "completed"
        report.item_ids = all_item_ids
        report.item_count = len(all_item_ids)
        report.collection_run_id = RUN_ID
        db.flush()
        report.date_range_start = min(
            row[0] for row in db.query(CollectedItem.published_at).filter(
                CollectedItem.id.in_(all_item_ids), CollectedItem.published_at.isnot(None)
            ).all()
        )
        report.date_range_end = now
        report.generated_at = now

        topic.total_items_collected = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).count()
        source.items_collected = db.query(CollectedItem).filter(CollectedItem.source_id == SOURCE_ID).count()
        source.last_sync_at = now
        source.last_error = None
        db.commit()

        print(f"backup={backup}")
        print(f"added={added} updated={len(ITEMS) - added}")
        print(f"topic_items={topic.total_items_collected}")
        print(f"report_id={report.id} report_items={report.item_count}")
        print(f"run_id={run.id}")


if __name__ == "__main__":
    main()
