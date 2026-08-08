"""Persist the three-round forum research iteration and its audit report."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from app.database import SessionLocal, _db_file_path
from app.models import CollectionRun, CollectedItem, PromptTemplate, Report, SourceConfig, Topic


TOPIC_ID = "foreign-trade-forum-risk-monitoring"
PROMPT_ID = "forum-social-customs-risk-search"
REPORT_ID = "report-forum-risk-3round-iteration-20260805"
NOW = datetime.now(timezone.utc)
WINDOW_START = datetime(2026, 7, 5, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 5, 23, 59, 59, tzinfo=timezone.utc)

SOURCES = [
    {
        "id": "hangsunbang-logistics-community",
        "name": "航隼帮货代网-物流交流圈",
        "url": "https://www.hangsunbang.com/",
        "languages": ["zh"],
        "role": "论坛原帖与货代账号交叉验证",
    },
    {
        "id": "reddit-askargentina",
        "name": "Reddit - AskArgentina",
        "url": "https://www.reddit.com/r/AskArgentina/",
        "languages": ["es"],
        "role": "拉美跨境进口讨论与同作者交叉帖",
    },
    {
        "id": "yict-vessel-schedule",
        "name": "盐田国际集装箱码头船期服务",
        "url": "https://www.yict.com.cn/service-vesselSchedule/vessel-schedule.html?locale=en_US",
        "languages": ["zh", "en"],
        "role": "口岸、航线和船期结构佐证",
    },
    {
        "id": "zim-service-updates",
        "name": "ZIM航线与服务更新",
        "url": "https://www.zim.com/global-network/asia-oceania/china/news-updates/zex-reinstatement-ca",
        "languages": ["en"],
        "role": "承运人航线和港序佐证",
    },
    {
        "id": "nvoccs-registry",
        "name": "无船承运人备案信息服务",
        "url": "https://www.nvoccs.cn/list/136.html",
        "languages": ["zh", "en"],
        "role": "货代主体名称与备案身份佐证",
    },
]

NEW_ITEMS = [
    {
        "id": "codex-forum-iterative-risk-20260805-01",
        "source_id": "reddit-negociosargentina",
        "run_id": "codex-forum-iter-round1-20260805",
        "published_at": datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
        "original_language": "es",
        "title": "阿根廷经营者自述7次courier进口并使用本人及熟人CUIT",
        "url": "https://www.reddit.com/r/NegociosArgentina/comments/1utvtm7/factur%C3%A9_30m_el_mes_pasado_con_un_producto_que/",
        "summary": (
            "发帖人自述一个月销售额约3000万阿根廷比索、500笔销售、利润约600万比索，已完成7次courier进口并"
            "售出1000余件，明确称使用本人及熟人的CUIT进口；同时披露CABA履约仓和Andreani末端配送。"
        ),
        "content": (
            "主要内容：阿根廷电商经营者称其销售一种未披露具体品名的商品，平均客单价约6万比索；上月完成500笔"
            "销售、销售额约3000万比索、利润约600万比索，累计已完成7次进口并售出1000余件。发帖人自称为"
            "monotributista，通过courier进口，明确表示使用本人CUIT和若干熟人CUIT，并询问这种做法还能持续多久。"
            "履约环节披露CABA fulfillment、Andreani末端配送和Mercado Pago收款。\n"
            "风险点：商业销售规模、7次进口和1000余件数量，与个人/熟人多个CUIT和courier路径同时出现，具有实际"
            "货主拆分至多个申报身份、个人进口转商业销售的直接风险信号。Andreani、Mercado Pago和履约仓仅是发帖"
            "人披露的物流/支付节点，不能据此认定其参与违规。\n"
            "后续排查方向：以公开账号为起点补充商品/网店/品牌；核对7次courier运单、申报CUIT、收货地址、付款人、"
            "包裹品名和数量，并与CABA履约仓入库记录、Andreani末端单号、平台订单及收款流水做同货主关联。"
        ),
        "entities": {
            "国家": ["阿根廷"],
            "进口方式": ["courier", "使用本人CUIT", "使用熟人CUIT"],
            "业务规模": ["7次进口", "售出1000余件", "月销售500笔", "月销售额约3000万比索", "利润约600万比索"],
            "物流节点": ["CABA fulfillment", "Andreani末端配送"],
            "支付节点": ["Mercado Pago"],
            "主体状态": ["monotributista"],
            "未披露": ["商品名称", "网店名称", "实际CUIT号码", "courier公司", "运单号"],
        },
        "risk_level": "高",
        "actionability": "A2",
    },
    {
        "id": "codex-forum-iterative-risk-20260805-02",
        "source_id": "hangsunbang-logistics-community",
        "run_id": "codex-forum-iter-round2-20260805",
        "published_at": datetime(2026, 7, 6, 10, 35, 43, tzinfo=timezone.utc),
        "original_language": "zh",
        "title": "汇智通公布盐田至洛杉矶电子烟柜计划，买单报关件称须经釜山中转",
        "url": "https://www.hangsunbang.com/topic_content/6867.html",
        "summary": (
            "深圳汇智通国际货运代理有限公司账号公布7月盐田至洛杉矶电子烟40HQ/DG柜计划，列出美森、ZIM、"
            "EMC HTW的截单、开船和到港日期，并称买单报关件须经韩国釜山中转；同时披露联系人、电话、最低重量和装板限制。"
        ),
        "content": (
            "主要内容：帖子自称由深圳汇智通国际货运代理有限公司发布，联系人为刘经理，公开业务电话/微信"
            "13710430264。货物包括电子烟整机、烟油、烟弹和配件，柜型为40HQ、DG柜。正式报关件可走盐田至"
            "洛杉矶直航，买单报关件则称须经韩国釜山中转。帖子列出美森、ZIM、EMC HTW三组7月截单、开船和"
            "到港日期；每柜限22个卡板、不堆叠不拆板，最低500公斤起收。\n"
            "风险点：电子烟及烟油、DG柜、买单报关、釜山中转和按货值赔付等信号，与具体企业、电话、港口、船公司"
            "和时间窗同时出现，已具备调取订舱/舱单的条件。帖子未披露真实客户、订舱号、提单号、船名航次或箱号，"
            "且不能仅凭广告认定企业实施了违法活动。\n"
            "后续排查方向：以企业全称、电话和7月各开船日查询盐田DG订舱记录、主分提单、出口报关抬头及实际货主；"
            "对买单件重点核对釜山中转的前后程提单、箱号映射和进口主体，对直航件核对美森/ZIM/EMC HTW实际船名航次。"
        ),
        "entities": {
            "企业": ["深圳汇智通国际货运代理有限公司", "COSMART（企业自述英文品牌）"],
            "联系人": ["刘经理"],
            "公开业务联系方式": ["13710430264（微信同号）", "QQ 971125951（货代名片页）"],
            "货物": ["电子烟整机", "烟油", "烟弹", "电子烟配件"],
            "柜型": ["40HQ", "DG柜", "每柜22个卡板", "最低500KG"],
            "口岸路线": ["盐田—洛杉矶", "买单件经釜山中转"],
            "承运人或服务": ["美森", "ZIM/ZEX", "EMC HTW"],
            "船期": [
                "美森：7月15/22/29日及8月5日开船",
                "ZIM：7月15/22/29日开船",
                "EMC HTW：7月14/21/28日及8月4日开船",
            ],
            "未披露": ["客户名称", "订舱号", "提单号", "船名航次", "集装箱号", "出口报关抬头"],
        },
        "risk_level": "高",
        "actionability": "A1",
    },
]

PROMPT_APPENDIX = r"""

[2026-08-05 三轮迭代采集逻辑]
目标：减少普通DDP、政策讨论和执法案例噪声，优先形成可直接调取企业登记、订舱、舱单、报关单、提单、箱流或快递清单的线索。

一、第一轮发现规则（风险词与实体锚点必须共现）
风险词至少一项：买单/借抬头/借身份号/低报/改品名/虚标/夹带/仿牌/无需证件/查验包赔/扣货赔付/转口洗产地。
实体锚点至少一项：企业全称、公开业务电话/邮箱、账号、口岸、城市、承运人、船名航次、柜型、箱量、重量、报价、付款比例、监管单证或业务规模。
只出现“双清、DDP、门到门、第三国中转、IOR/BOND”而无上述组合信号的，降为背景材料。

二、第二轮交叉规则（对高价值候选做精确反查）
用引号检索企业全称、电话、邮箱、用户名、精确技术参数、完整帖子标题和路线；至少两项稳定标识一致才合并为同一主体/事件，例如“同电话+同企业”“同账号+同重量报价”“同企业+同路线货物”。
同一帖子跨社区发布时不得重复建条，应更新原条目并记录crosspost URL、作者回复和新增实体。
企业仅在合法合规建议中被提到时不得标风险；承运人、码头、支付和末端配送企业默认只作为运输/支付节点，不推定参与风险行为。

三、第三轮穿透规则（登记与运输信息佐证）
企业：反查统一社会信用代码、法定代表人、注册地址、成立日期、NVOCC/货代备案；注意近似名称，必须逐字核对，禁止把“中汇智通”等近似企业合并到“汇智通”。
运输：以口岸+承运人/服务代码+开船日期反查官方码头/船公司船期，再提取船名、航次、港序、码头；官方页面只能证明航线结构，不能证明具体风险货物已订舱。
单证：优先识别集装箱号正则[A-Z]{4}[0-9]{7}、主/分提单号、订舱号、MRN、Bill of Entry、EORI/IOR/EIN、CUIT/CUIL、报关单号、车牌/航班/列车号。号码必须来自原帖或可验证页面，不得根据船期猜测。

四、可行动等级
A1：企业/公开业务联系方式 + 口岸路线 + 具体时间窗/承运人/柜型，或直接出现提单/箱号/船名航次；可进入订舱、舱单和报关数据核查。
A2：账号或申报身份 + 明确数量/金额/频次 + 物流或支付节点；可进入同址、同收件人、同付款人关联核查。
B：风险行为直接但缺少可追踪主体或运输标识；保留并继续扩线。
C：普通服务、政策讨论、泛化经验或只有推测；不进入高风险报告。

五、时间与证据门槛
只采原帖发布日期位于当前31天窗口的内容；旧帖子只能作为主体画像或交叉佐证，不新增为当期事件。执法机关通报、处罚公告和媒体转述执法案件继续排除。每条必须分别记录“帖子直接披露”“跨站交叉结果”“登记/官方佐证”“仍缺字段”，并注明公开帖子不构成违法认定。
"""


def backup_database() -> str:
    path = _db_file_path()
    if not path or not os.path.exists(path):
        raise RuntimeError("Database path is unavailable")
    backup_dir = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, f"gather.before_forum_3round_iteration.{NOW:%Y%m%d_%H%M%S}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    return dest


def upsert_sources(db) -> None:
    for data in SOURCES:
        source = db.get(SourceConfig, data["id"]) or SourceConfig(id=data["id"])
        db.add(source)
        source.name = data["name"]
        source.description = data["role"]
        source.channel = "web_scrape"
        source.is_active = True
        source.is_configured = True
        source.base_url = data["url"]
        source.homepage_url = data["url"]
        source.rate_limit_rps = 0.2
        source.timeout_seconds = 25
        source.max_items_per_run = 10
        source.default_keywords = [
            "企业全称", "公开业务电话", "港口", "船名航次", "提单号", "集装箱号",
            "买单报关", "借用CUIT", "DG柜", "中转港",
        ]
        source.default_categories = ["论坛风险原帖", "企业与运输标识佐证"]
        source.languages = data["languages"]
        source.legal_basis = "仅采集无需登录即可公开访问的信息。"
        source.compliance_note = "区分原帖陈述、交叉信息和官方佐证；节点企业不得因被提及而自动标风险。"
        source.updated_at = NOW


def upsert_new_items(db) -> tuple[int, int]:
    added = 0
    updated = 0
    for data in NEW_ITEMS:
        item = db.get(CollectedItem, data["id"])
        if item is None:
            item = CollectedItem(id=data["id"], source_id=data["source_id"])
            db.add(item)
            added += 1
        else:
            updated += 1
        item.source_id = data["source_id"]
        item.run_id = data["run_id"]
        item.topic_id = TOPIC_ID
        item.title = data["title"]
        item.content = data["content"]
        item.content_hash = hashlib.sha256(f"{data['url']}\n{data['content']}".encode("utf-8")).hexdigest()
        item.summary = data["summary"]
        item.url = data["url"]
        item.language = "zh"
        item.category = "论坛高可核清关风险线索"
        item.entities = data["entities"]
        item.status = "enriched"
        item.quality_score = 0.95 if data["actionability"] == "A1" else 0.92
        item.relevance_score = 0.99 if data["actionability"] == "A1" else 0.97
        item.published_at = data["published_at"]
        item.collected_at = item.collected_at or NOW
        item.updated_at = NOW
        item.authorization_level = "public"
        item.raw_metadata = {
            "collector": "Codex three-round iterative public web research",
            "original_language": data["original_language"],
            "evidence_status": "public_post_unverified",
            "risk_level": data["risk_level"],
            "actionability": data["actionability"],
            "collection_window": "2026-07-05/2026-08-05",
            "fact_status": "帖子陈述，待企业、报关、舱单、运输和付款资料验证",
            "used_project_tavily": False,
            "used_project_baidu": False,
        }
    return added, updated


def enrich_existing_items(db) -> list[str]:
    updated_ids: list[str] = []

    argentina = db.get(CollectedItem, "codex-foreign-forum-risk-20260805-07")
    if argentina is None:
        raise RuntimeError("Expected Argentina door-to-door item is missing")
    marker = "[三轮深检交叉验证]"
    appendix = (
        "\n\n[三轮深检交叉验证] 同一作者在r/AskArgentina发布相同标题和相同8至9公斤、160至200美元参数的交叉帖。"
        "在回复中，作者进一步说明货物为仿牌服装，承认因复制品牌无法按正规方式进口，并对他人“是否想走私”的提问"
        "作肯定回应。该内容提高主观意图和货物属性的直接性，但仍未出现货代企业、运单、口岸或收件主体。"
    )
    if marker not in (argentina.content or ""):
        argentina.content = (argentina.content or "") + appendix
    argentina.title = "中国至阿根廷8至9公斤仿牌服装门到门需求获同作者交叉帖确认"
    argentina.summary = (
        "同一作者在两个阿根廷社区发布持续性中国至阿根廷门到门需求，参数均为每箱8至9公斤、160至200美元；"
        "交叉帖回复进一步确认货物为仿牌服装并承认规避正规进口意图。"
    )
    entities = dict(argentina.entities or {})
    entities.update({
        "货物": ["仿牌服装"],
        "公开账号": ["No_Advantage_4493"],
        "交叉社区": ["r/NegociosArgentina", "r/AskArgentina"],
        "交叉帖": ["https://www.reddit.com/r/AskArgentina/comments/1va1ujw/alguien_conoce_un_importador_puerta_a_puerta/"],
        "明确回复": ["承认货物为复制品牌服装", "对走私意图追问作肯定回应"],
        "仍缺": ["货代企业", "运单号", "进出口口岸", "收件主体", "具体品牌"],
    })
    argentina.entities = entities
    metadata = dict(argentina.raw_metadata or {})
    metadata["three_round_enrichment_20260805"] = {
        "round": 1,
        "actionability": "A2",
        "crosspost_url": "https://www.reddit.com/r/AskArgentina/comments/1va1ujw/alguien_conoce_un_importador_puerta_a_puerta/",
        "matching_keys": ["same_author", "same_title", "8-9kg", "USD160-200", "same_route"],
        "new_direct_signal": "replica_clothing_and_affirmative_evasion_intent",
        "evidence_notice": "作者公开回复，尚无实际运输或申报记录验证",
    }
    argentina.raw_metadata = metadata
    argentina.quality_score = max(float(argentina.quality_score or 0), 0.93)
    argentina.relevance_score = max(float(argentina.relevance_score or 0), 0.98)
    argentina.content_hash = hashlib.sha256(f"{argentina.url}\n{argentina.content}".encode("utf-8")).hexdigest()
    argentina.updated_at = NOW
    updated_ids.append(argentina.id)

    vape = db.get(CollectedItem, "codex-forum-port30d-20260805-02")
    if vape is None:
        raise RuntimeError("Expected electronic-cigarette item is missing")
    vape_entities = dict(vape.entities or {})
    vape_entities.update({
        "企业全称": ["深圳汇智通国际货运代理有限公司"],
        "统一社会信用代码": ["914403000663312240（第三方企业信息页，待官方登记复核）"],
        "法定代表人": ["余堂成（第三方企业信息页，待官方登记复核）"],
        "注册地址": ["深圳市宝安区福永街道福围社区下沙十二巷2号"],
        "公开业务联系方式": ["刘经理", "13710430264（微信同号）", "QQ 971125951"],
        "备案线索": ["同名企业见无船承运人备案信息页"],
        "船期交叉帖": ["https://www.hangsunbang.com/topic_content/6867.html"],
        "官方航线佐证": ["YICT列示ZEX盐田—洛杉矶服务", "ZIM说明ZEX盐田—洛杉矶约12.5天"],
        "仍缺": ["真实客户", "订舱号", "主分提单号", "船名航次", "集装箱号", "出口报关抬头"],
    })
    vape.entities = vape_entities
    vape_metadata = dict(vape.raw_metadata or {})
    vape_metadata["three_round_enrichment_20260805"] = {
        "rounds": [2, 3],
        "actionability": "A1",
        "entity_match_keys": ["exact_company_name", "phone_13710430264", "same_e-cigarette_routes"],
        "company_record": {
            "name": "深圳汇智通国际货运代理有限公司",
            "unified_social_credit_code": "914403000663312240",
            "legal_representative": "余堂成",
            "registered_address": "深圳市宝安区福永街道福围社区下沙十二巷2号",
            "registration_source": "https://www.job5156.com/comp/1859017",
            "verification_note": "第三方企业信息聚合页，正式核查应以国家企业信用信息公示系统为准",
        },
        "nvocc_corroboration": "https://www.nvoccs.cn/list/136.html",
        "schedule_post": "https://www.hangsunbang.com/topic_content/6867.html",
        "official_route_sources": [
            "https://www.yict.com.cn/service-vesselSchedule/vessel-schedule.html?locale=en_US",
            "https://www.zim.com/global-network/asia-oceania/china/news-updates/zex-reinstatement-ca",
        ],
        "carrier_notice": "船公司和码头仅作为线路节点；公开资料未证明具体风险货物实际订舱",
    }
    vape.raw_metadata = vape_metadata
    vape.quality_score = max(float(vape.quality_score or 0), 0.97)
    vape.relevance_score = max(float(vape.relevance_score or 0), 0.99)
    vape.updated_at = NOW
    updated_ids.append(vape.id)
    return updated_ids


def upsert_runs(db, added: int, updated: int, enriched_ids: list[str]) -> None:
    run_defs = [
        {
            "id": "codex-forum-iter-round1-20260805",
            "source_id": "reddit-negociosargentina",
            "keywords": ["CUIT de conocidos", "courier", "importe", "ventas", "aduana", "8-9 kg"],
            "found": 2, "new": 1 if added else 0, "updated": 1,
            "result": "1条新增强线索；1个同作者交叉帖增强既有条目",
        },
        {
            "id": "codex-forum-iter-round2-20260805",
            "source_id": "hangsunbang-logistics-community",
            "keywords": ["企业全称", "电话", "盐田", "洛杉矶", "40HQ", "DG", "买单", "釜山"],
            "found": 2, "new": 1 if added else 0, "updated": 1,
            "result": "取得企业、联系人、电话、柜型、船公司和具体船期",
        },
        {
            "id": "codex-forum-iter-round3-20260805",
            "source_id": "yict-vessel-schedule",
            "keywords": ["企业信用代码", "NVOCC", "ZEX", "HTW", "船名航次", "提单", "集装箱号"],
            "found": 5, "new": 0, "updated": len(enriched_ids),
            "result": "取得工商和NVOCC标识并确认航线结构；未找到可验证船名航次、提单号或箱号",
        },
    ]
    for data in run_defs:
        run = db.get(CollectionRun, data["id"]) or CollectionRun(id=data["id"], source_id=data["source_id"])
        db.add(run)
        run.source_id = data["source_id"]
        run.topic_id = TOPIC_ID
        run.status = "completed"
        run.batch_id = "codex-forum-three-round-20260805"
        run.keywords_used = data["keywords"]
        run.items_found = data["found"]
        run.items_new = data["new"]
        run.items_updated = data["updated"]
        run.items_failed = 0
        run.started_at = run.started_at or NOW
        run.completed_at = NOW
        run.window_start = WINDOW_START
        run.window_end = WINDOW_END
        run.error_log = []
        run.metadata_json = {
            "iteration_result": data["result"],
            "strict_recent_original_posts": True,
            "enforcement_cases_excluded": True,
            "used_project_tavily": False,
            "used_project_baidu": False,
        }


def build_report(topic: Topic, new_items: list[CollectedItem], enriched: list[CollectedItem]) -> str:
    return f"""# {topic.name}三轮迭代采集与可核标识报告

## 一、最终效果

本次在近31天、非执法案例、公开原帖范围内连续完成三轮检索。新增 **{len(new_items)} 条**信息，增强 **{len(enriched)} 条**既有信息。最重要的结果是把一条电子烟物流广告从“风险词线索”推进到可按企业、电话、统一社会信用代码、注册地址、盐田港、船公司、柜型和具体开船日开展订舱/舱单核查的 **A1级**线索。

公开网页仍未出现可验证的真实提单号、订舱号、集装箱号或能够与具体风险货物绑定的船名航次。官方码头/船公司页面只能佐证航线结构，不能证明帖子中的货物已实际装船。

## 二、三轮结果与逻辑优化

| 轮次 | 检索方法 | 有效结果 | 检查结论 | 下一轮优化 |
|---|---|---|---|---|
| 第一轮 | 多语种风险词 + 企业/金额/次数/重量/物流节点 | 新增“7次courier进口并使用熟人CUIT”；发现8—9公斤小箱同作者交叉帖 | 金额、频次和身份号比普通DDP更有核查价值；跨帖可补足货物属性和主观意图 | 对电话、账号、精确参数和企业名加引号反查，至少两项标识一致才合并 |
| 第二轮 | 企业名、电话、精确参数和路线反查 | 找到汇智通7月40HQ/DG电子烟柜计划，取得刘经理、13710430264、QQ、盐田—洛杉矶、美森/ZIM/EMC HTW及具体日期 | 已具备按时间窗查询订舱、舱单的条件；仅提到合法IOR/Bond服务的帖子不能标风险 | 反查工商/NVOCC；用口岸+承运人+日期查询官方船期，禁止根据广告猜船名 |
| 第三轮 | 企业登记、NVOCC、官方码头/承运人航线反查 | 取得信用代码、法定代表人、注册地址和同名NVOCC记录；YICT/ZIM确认盐田—洛杉矶服务结构 | 企业主体可落地，但未获得具体提单/箱号；承运人、码头仅为线路节点 | 将A1/A2/B/C分级、近似企业名隔离、缺失字段自动生成下一步核查任务 |

## 三、可直接用于下一步核查的信息

### 1. 深圳汇智通电子烟线路（A1）

- 论坛原帖：[{new_items[1].title}]({new_items[1].url})。
- 企业：深圳汇智通国际货运代理有限公司；公开业务联系人刘经理；电话/微信13710430264；货代名片页另列QQ 971125951。
- 企业登记线索：统一社会信用代码914403000663312240、法定代表人余堂成、注册地址深圳市宝安区福永街道福围社区下沙十二巷2号。该组工商信息来自第三方企业信息页，须再以国家企业信用信息公示系统核准。
- 备案线索：[无船承运人信息页](https://www.nvoccs.cn/list/136.html)列有完全相同企业名称和英文名称。
- 货物与运输：电子烟整机、烟油、烟弹和配件；40HQ/DG柜；每柜22个卡板；最低500KG；盐田—洛杉矶；买单报关件称经釜山中转。
- 时间窗：美森7月15/22/29日及8月5日开船；ZIM 7月15/22/29日；EMC HTW 7月14/21/28日及8月4日。
- 官方结构佐证：[盐田国际船期页](https://www.yict.com.cn/service-vesselSchedule/vessel-schedule.html?locale=en_US)列示ZEX等盐田—洛杉矶服务；[ZIM服务页](https://www.zim.com/global-network/asia-oceania/china/news-updates/zex-reinstatement-ca)说明ZEX港序和约12.5天航程。
- 仍缺：真实客户、订舱号、主/分提单号、出口报关抬头、实际船名航次、集装箱号。
- 建议：按企业全称/电话 + 上述开船日前后3天检索盐田DG订舱和出口舱单；买单件比对釜山前后程提单、箱号映射和出口抬头；直航件在承运人或码头历史船期中锁定实际船名航次后再查箱流。

### 2. 阿根廷多CUIT商业进口（A2）

- 原帖：[{new_items[0].title}]({new_items[0].url})。
- 申报与规模：本人及熟人CUIT、courier、7次进口、1000余件、月销售500笔、销售额约3000万比索。
- 关联节点：CABA fulfillment、Andreani末端配送、Mercado Pago。上述企业只作为帖子披露的物流/支付节点，不代表其参与违规。
- 仍缺：商品和网店名称、具体CUIT、courier企业、运单号、履约仓主体。
- 建议：以同收货地址、电话、付款人和履约仓为中心，归集7次courier清单及不同CUIT；再与平台订单、入仓记录、Andreani末端单号和收款流水匹配实际货主。

### 3. 阿根廷仿牌服装交叉帖（A2）

- 原条目：[{enriched[0].title}]({enriched[0].url})；[同作者交叉帖](https://www.reddit.com/r/AskArgentina/comments/1va1ujw/alguien_conoce_un_importador_puerta_a_puerta/)。
- 稳定匹配：同作者、同标题、中国—阿根廷、每箱8至9公斤、每箱160至200美元、持续发运。
- 新增直接信号：作者回复确认货物为仿牌服装，并对规避正规进口意图作明确回应。
- 仍缺：具体品牌、货代、运单、口岸和收件主体；当前适合做账号和同参数扩线，尚不能直接落到报关单。

## 四、最终采集逻辑

1. **原帖门槛**：只收近31天原帖，排除执法通报和旧帖事件；旧网页仅作企业/路线佐证。
2. **组合门槛**：风险行为词必须与企业、联系方式、口岸、运输标识、金额/频次/重量或单证至少一类共现。
3. **交叉门槛**：至少两项稳定标识相同才关联；同作者跨帖更新原条目，不重复入库。
4. **主体隔离**：严格区分近似企业名；承运人、码头、支付机构和配送商默认是中性节点。
5. **证据分层**：分别保存帖子直接披露、跨站交叉、登记/官方佐证和仍缺字段。
6. **可行动分级**：A1可直接查企业/订舱/舱单；A2可做同址同身份关联；B继续扩线；C不进入风险报告。
7. **号码提取**：优先识别集装箱号、主分提单、订舱号、MRN、Bill of Entry、CUIT/CUIL、船名航次、车牌/航班/列车号；禁止根据日期和航线推测号码。

## 五、结论

三轮优化后，信息质量从“风险关键词”提升为“可核企业 + 公开业务联系方式 + 口岸路线 + 柜型/重量 + 承运人 + 时间窗”。当前最接近下一步实查的是汇智通电子烟线路；下一阶段应转入订舱、舱单或提单数据库，而不是继续扩大普通论坛关键词。所有帖子仍属待核线索，不构成对相关企业或个人违法行为的认定。
"""


def main() -> None:
    backup = backup_database()
    with SessionLocal() as db:
        topic = db.get(Topic, TOPIC_ID)
        prompt = db.get(PromptTemplate, PROMPT_ID)
        if topic is None or prompt is None:
            raise RuntimeError("Required topic or prompt template is missing")

        upsert_sources(db)
        db.flush()
        added, updated = upsert_new_items(db)
        enriched_ids = enrich_existing_items(db)
        upsert_runs(db, added, updated, enriched_ids)

        source_ids = [data["id"] for data in SOURCES]
        source_urls = [data["url"] for data in SOURCES]
        topic.source_ids = list(dict.fromkeys((topic.source_ids or []) + source_ids))
        topic.target_urls = list(dict.fromkeys((topic.target_urls or []) + source_urls))
        topic.focus_languages = list(dict.fromkeys((topic.focus_languages or []) + ["zh", "en", "es"]))
        topic.keywords = list(dict.fromkeys((topic.keywords or []) + [
            "企业全称+公开业务电话+口岸", "船名航次", "主分提单号", "订舱号", "集装箱号",
            "40HQ", "DG柜", "CUIT de conocidos", "7 importaciones", "同作者交叉帖",
            "统一社会信用代码", "NVOCC备案", "ZEX", "HTW",
        ]))
        if "[2026-08-05 三轮迭代采集逻辑]" not in prompt.content:
            prompt.content = prompt.content.rstrip() + PROMPT_APPENDIX
        prompt.updated_at = NOW

        db.flush()
        all_items = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).all()
        new_items = [db.get(CollectedItem, data["id"]) for data in NEW_ITEMS]
        enriched_items = [db.get(CollectedItem, item_id) for item_id in enriched_ids]
        report_text = build_report(topic, new_items, enriched_items)

        report = db.get(Report, REPORT_ID)
        if report is None:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID, title="")
            db.add(report)
        report.title = "外贸论坛违规清关与走私风险线索三轮迭代采集报告（2026-08-05）"
        report.report_type = "analytical"
        report.content = report_text
        report.summary = (
            "连续完成三轮近一个月论坛与互联网检索，新增2条、增强2条；提取企业信用代码、公开业务联系方式、"
            "盐田—洛杉矶线路、40HQ/DG柜、船公司和具体船期，并明确尚缺真实提单号、箱号和可绑定货物的船名航次。"
        )
        report.status = "completed"
        report.model_id = "codex-three-round-public-web-audit"
        report.tokens_used = 0
        report.item_count = 4
        report.item_ids = [item.id for item in new_items + enriched_items]
        report.error_log = None
        report.collection_run_id = "codex-forum-iter-round3-20260805"
        report.date_range_start = WINDOW_START
        report.date_range_end = WINDOW_END
        report.output_files = None
        report.output_dir = None
        report.generated_at = NOW
        report.created_at = report.created_at or NOW

        topic.total_items_collected = len(all_items)
        topic.last_run_at = NOW
        topic.last_collection_run_id = "codex-forum-iter-round3-20260805"
        topic.updated_at = NOW
        for source_id in source_ids + ["reddit-negociosargentina"]:
            source = db.get(SourceConfig, source_id)
            if source:
                source.items_collected = db.query(CollectedItem).filter(CollectedItem.source_id == source_id).count()
                source.last_sync_at = NOW
        db.commit()

        print(f"backup={backup}")
        print(f"sources_added_or_updated={len(source_ids)}")
        print(f"items_added={added} items_upsert_updated={updated} enriched={len(enriched_ids)}")
        print(f"topic_sources={len(topic.source_ids or [])} topic_items={topic.total_items_collected}")
        print(f"report_id={report.id} report_items={report.item_count}")


if __name__ == "__main__":
    main()
