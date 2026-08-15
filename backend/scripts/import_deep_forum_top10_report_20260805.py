"""Import newly verified forum leads, audit the topic, and build a Top-10 report."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from app.database import SessionLocal, _db_file_path
from app.models import CollectionRun, CollectedItem, PromptTemplate, Report, SourceConfig, Topic


TOPIC_ID = "foreign-trade-forum-risk-monitoring"
PROMPT_ID = "forum-social-customs-risk-search"
REPORT_ID = "report-forum-risk-top10-20260805"
NOW = datetime.now(timezone.utc)
WINDOW_START = datetime(2026, 7, 5, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 5, 23, 59, 59, tzinfo=timezone.utc)

SOURCES = [
    {
        "id": "reddit-smallbusinessindia",
        "name": "Reddit - smallbusinessindia",
        "url": "https://www.reddit.com/r/smallbusinessindia/",
        "languages": ["en", "hi"],
        "country_focus": ["India", "China"],
    },
    {
        "id": "reddit-negociosargentina",
        "name": "Reddit - NegociosArgentina",
        "url": "https://www.reddit.com/r/NegociosArgentina/",
        "languages": ["es"],
        "country_focus": ["Argentina", "China"],
    },
]

ITEMS = [
    {
        "id": "codex-foreign-forum-risk-20260805-05",
        "source_id": "reddit-smallbusinessindia",
        "published_at": datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
        "original_language": "en",
        "title": "中国至印度DDP由货代作为进口主体，实际买方无法取得名下报关单",
        "url": "https://www.reddit.com/r/smallbusinessindia/comments/1uxbdlb/help_with_rbi_compliance_for_china_ddp_shipment/",
        "summary": (
            "印度创业者称从四家中国供应商采购家居及生活用品并分别预付30%，货代承诺DDP送至古尔冈仓库，"
            "但拟以货代自身作为进口商，Bill of Entry和GST均不在实际买方名下，导致银行提示无法完成ORM核销。"
        ),
        "content": (
            "主要内容：发帖人从四家中国供应商采购家居及生活用品，每家均已支付30%预付款、余款70%待付；"
            "中国货代承诺以DDP方式送至印度古尔冈仓库，但货代将作为Importer of Record，进口报关单和GST记录"
            "不体现实际买方。发帖人称开户银行提示，缺少本公司名下Bill of Entry将无法按印度外汇管理要求完成ORM核销。\n"
            "风险点：DDP、第三方进口主体、四票采购发票与单一清关主体不对应，且报关单、税务凭证与实际货主脱节。"
            "帖子仅为当事人陈述，尚不能证明低报或逃税已经发生。\n"
            "后续排查方向：核对四家供应商发票、30%/70%付款流水、货代DDP协议、Bill of Entry、GST/TR6凭证、"
            "ORM编号、进口商IEC及送货至古尔冈仓库的运单，确认申报主体、货值和实际货主是否一致。"
        ),
        "entities": {
            "起运国": ["中国"],
            "目的国": ["印度"],
            "目的地": ["古尔冈（Gurgaon）仓库"],
            "货物": ["家居用品", "生活用品"],
            "交易结构": ["四家中国供应商", "30%预付款", "70%尾款", "DDP"],
            "监管单证": ["Bill of Entry", "GST", "ORM", "TR6/Challan", "IEC"],
            "风险主体": ["第三方Importer of Record"],
        },
        "risk_level": "高",
    },
    {
        "id": "codex-foreign-forum-risk-20260805-06",
        "source_id": "reddit-negociosargentina",
        "published_at": datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        "original_language": "es",
        "title": "阿根廷买家年度小件额度用尽后询问借用他人CUIL继续进口",
        "url": "https://www.reddit.com/r/NegociosArgentina/comments/1v2oxol/primera_compra_alibaba/",
        "summary": (
            "阿根廷用户拟通过Alibaba首次采购科技产品，自称当年五次小件进口额度已用完，并询问能否使用他人CUIL"
            "继续下单；回帖者直接建议改用他人CUIT/CUIL。帖子出现额度、身份号、商品和目的地等可核查要素。"
        ),
        "content": (
            "主要内容：发帖人位于阿根廷圣地亚哥-德尔埃斯特罗省，拟在Alibaba采购科技产品，自称本年度五次"
            "小件进口额度已经用完，询问能否借用另一人的CUIL继续进口；回帖中有人建议使用另一人的CUIT/CUIL，"
            "并提到400美元限额。\n"
            "风险点：在已知个人年度额度用尽的情况下，公开讨论更换身份识别号继续申报，具有规避个人进口额度和"
            "拆分实际收货人的直接意图信号。尚无证据证明该建议已被实际执行。\n"
            "后续排查方向：核对Alibaba订单、付款人、收货地址、快递运单、申报CUIT/CUIL、年度进口次数、申报货值"
            "及同地址关联收件人，识别是否存在借名申报、拆单或同一实际货主分散进口。"
        ),
        "entities": {
            "平台": ["Alibaba"],
            "目的国": ["阿根廷"],
            "目的地": ["圣地亚哥-德尔埃斯特罗省"],
            "货物": ["科技产品"],
            "监管标识": ["CUIT", "CUIL"],
            "数量额度": ["年度五次小件进口额度已用完", "回帖提及400美元限额"],
            "风险行为": ["借用他人身份号申报", "可能拆分实际收货人"],
        },
        "risk_level": "高",
    },
    {
        "id": "codex-foreign-forum-risk-20260805-07",
        "source_id": "reddit-negociosargentina",
        "published_at": datetime(2026, 7, 29, 12, tzinfo=timezone.utc),
        "original_language": "es",
        "title": "中国至阿根廷持续性8至9公斤小箱门到门运输并提及上票海关问题",
        "url": "https://www.reddit.com/r/NegociosArgentina/comments/1va1vcp/alguien_conoce_un_importador_puerta_a_puerta/",
        "summary": (
            "用户寻找中国至阿根廷的门到门进口服务，称货物为每箱8至9公斤、需要持续发运、预算每箱160至200美元，"
            "并表示上一票曾遇到海关问题。具体路线、重量、频次和价格具有关联排查价值，但未直接出现低报或改品名。"
        ),
        "content": (
            "主要内容：发帖人寻找可承接中国至阿根廷门到门运输的进口商或货代，货物为8至9公斤小箱，计划持续"
            "发运而非一次性寄送，预算约每箱160至200美元，并称上一票运输出现过海关问题。\n"
            "风险点：持续性小批量门到门、固定重量与报价、既往海关异常及寻找替代清关服务形成组合信号；原帖未"
            "提及具体品名、低报、借名、无需证件或包赔，故列为中等核查优先级。\n"
            "后续排查方向：补充品名、HS编码、起运城市、承运商、运单号、收件主体和上一票异常原因；按相同收件"
            "地址、电话号码、付款人与8至9公斤重复包裹进行关联分析。"
        ),
        "entities": {
            "路线": ["中国—阿根廷"],
            "运输方式": ["门到门", "持续性小箱"],
            "重量": ["每箱8至9公斤"],
            "报价": ["每箱160至200美元"],
            "异常": ["上一票出现海关问题"],
            "未披露": ["具体品名", "承运商", "运单号", "收件主体"],
        },
        "risk_level": "中",
    },
]

# Scores are an intelligence-review priority, not a conclusion that a violation occurred.
# Components: directness (30), traceability (25), customs relevance (15), evidence quality (20), recency (10).
AUDIT = {
    "codex-forum-risk-20260805044348-02": {
        "score": 96, "components": [30, 25, 15, 17, 9], "decision": "top10",
        "signal": "无实质加工换柜转口并制作马来西亚申报/原产地文件",
        "identifiers": "佛山铝材、2×40HQ、蛇口、YML、巴生港Westport、意大利、约14万欧元",
        "reason": "行为链、货物、箱量、港口、承运人和处罚金额同时出现，可沿舱单、箱流与原产地文件交叉核查。",
        "followup": "调取蛇口出口舱单、YML订舱与箱号映射、Westport进出区和换柜记录、马来西亚原产地证及意大利进口申报。",
    },
    "codex-forum-port30d-20260805-02": {
        "score": 95, "components": [30, 24, 15, 16, 10], "decision": "top10",
        "signal": "电子烟买单报关、双清包税、韩国中转及扣货/查验承诺组合",
        "identifiers": "汇智通国际货运（自称）、电子烟/烟弹/烟油、盐田—洛杉矶、威海—仁川—釜山—洛杉矶、ZIM、500/1000公斤",
        "reason": "受监管货物与多条路线、承运人、最低起运量和风险承诺高度聚合。",
        "followup": "核验发帖主体工商和货代资质，按线路调取订舱、舱单、危险品申报、出口抬头、美国进口主体及付款报价。",
    },
    "codex-forum-port30d-20260805-07": {
        "score": 94, "components": [30, 21, 15, 19, 9], "decision": "top10",
        "signal": "客户要求将电池真实参数18.5V/2600mAh虚标为24V/4A并询问海关查验",
        "identifiers": "18.5V/2600mAh、24V/4A、锂电池、UN38.3、华东口岸",
        "reason": "真实参数与拟标参数均明确，存在直接虚假标识意图，且锂电运输申报具有安全监管关联。",
        "followup": "核对电芯/BMS规格、铭牌与包装照片、UN38.3和MSDS、报关品名参数、订舱危险品资料及客户指令。",
    },
    "codex-forum-port30d-20260805-08": {
        "score": 92, "components": [29, 21, 15, 18, 9], "decision": "top10",
        "signal": "买单报关杂货中明确混有食品和有品牌服装",
        "identifiers": "青岛、食品、有品牌服装、杂货、买单报关",
        "reason": "买单主体、混装食品与品牌服装同时出现，兼具检验检疫、知识产权与如实申报风险。",
        "followup": "核对青岛订舱和装箱单、品牌授权、食品准入/检疫资料、申报抬头、实际货主及分票明细。",
    },
    "codex-foreign-forum-risk-20260805-06": {
        "score": 91, "components": [30, 20, 15, 17, 9], "decision": "top10",
        "signal": "年度额度用尽后询问并获建议使用他人CUIT/CUIL继续进口",
        "identifiers": "Alibaba、科技产品、阿根廷、圣地亚哥-德尔埃斯特罗、CUIT/CUIL、五次额度、400美元",
        "reason": "规避额度的主观意图直接，身份号、平台、货物和地域要素可供同址同收件人关联。",
        "followup": "比对订单付款人、申报身份号、收件地址、快递运单和年度次数，识别借名、拆单及实际货主。",
    },
    "codex-forum-port30d-20260805-09": {
        "score": 90, "components": [30, 17, 15, 19, 9], "decision": "top10",
        "signal": "报关数量遗漏导致金额相差近15%，船开后询问能否不改单",
        "identifiers": "出口报关、数量遗漏、金额差近15%、船已开、改单",
        "reason": "差异比例和不改单意向明确，属于可直接用合同、发票、舱单和报关单验证的申报不一致。",
        "followup": "比对合同、商业发票、装箱单、报关单、收汇和舱单，确认遗漏品项、数量、金额及后续更改单状态。",
    },
    "codex-forum-port30d-20260805-04": {
        "score": 89, "components": [26, 24, 15, 14, 10], "decision": "top10",
        "signal": "生物菌粉剂多口岸出口越南，承诺双清包税和单一品名快速放行",
        "identifiers": "递接物流（自称）、生物菌粉剂、广州/深圳/厦门/上海/青岛/天津/宁波—河内/胡志明市、陆运/海运",
        "reason": "生物粉剂与多口岸、多运输方式、单一品名承诺组合，具备较强的品名归类和检疫核查价值。",
        "followup": "核验货代主体、成分和用途、HS编码、检验检疫/危险品属性、各口岸申报品名及越南收货人。",
    },
    "codex-forum-port30d-20260805-03": {
        "score": 88, "components": [30, 18, 15, 15, 10], "decision": "top10",
        "signal": "南沙报关广告公开承接食品、化妆品及仿牌货物",
        "identifiers": "南沙、食品、化妆品、仿牌、拖车报关",
        "reason": "仿牌表述直接，且食品、化妆品涉及准入与检验检疫，适合按联系人和线路扩线。",
        "followup": "留存广告账号与联系方式，核验经营主体、报关抬头、品牌授权、检验检疫资料、车辆和订舱记录。",
    },
    "codex-foreign-forum-risk-20260805-05": {
        "score": 87, "components": [24, 23, 15, 16, 9], "decision": "top10",
        "signal": "DDP由货代作为进口主体，实际买方名下无Bill of Entry且ORM无法核销",
        "identifiers": "中国四家供应商、家居/生活用品、30%/70%付款、古尔冈、Bill of Entry、GST、ORM",
        "reason": "四票交易、付款节点、目的仓和监管单证齐全，能核查实际货主与申报/纳税主体脱节。",
        "followup": "核对四票发票和付款、DDP协议、进口商IEC、Bill of Entry、GST/TR6、ORM及入仓运单。",
    },
    "codex-foreign-forum-risk-20260805-01": {
        "score": 86, "components": [22, 21, 15, 19, 9], "decision": "top10",
        "signal": "中国至欧盟拼柜DDP无法提供实际买方名下MRN",
        "identifiers": "中国、罗马尼亚、欧盟、拼柜DDP、MRN、EORI、Importer of Record",
        "reason": "实际买方与欧盟进口申报记录无法对应，监管单证链明确但尚缺企业、口岸和提单号。",
        "followup": "追查卖方和货代、EORI/进口主体、MRN、拼柜主分单、进口VAT凭证和采购付款。",
    },
    "codex-forum-port30d-20260805-01": {
        "score": 83, "components": [26, 17, 15, 15, 10], "decision": "reserve",
        "signal": "南沙敏感货买单报关并承接南沙—香港整柜",
        "identifiers": "南沙、香港、整柜、敏感货、买单报关",
        "reason": "口岸路线清楚但缺少品名、主体、船名和箱号。",
        "followup": "补充账号联系方式、具体品名、报关抬头、订舱信息、车辆和箱号。",
    },
    "codex-forum-port30d-20260805-06": {
        "score": 82, "components": [20, 21, 15, 17, 9], "decision": "reserve",
        "signal": "二手汽车发动机出口涉及废物属性和残油查验",
        "identifiers": "南沙、黄埔、二手汽车发动机、型号/序列号、残油、固体废物属性",
        "reason": "货物和监管争点具体，但更像合规咨询，主动规避意图弱于前十。",
        "followup": "核验货物状态、清洗记录、序列号、鉴别报告、许可证件和申报品名。",
    },
    "codex-foreign-forum-risk-20260805-02": {
        "score": 80, "components": [25, 15, 15, 16, 9], "decision": "reserve",
        "signal": "DDP、低报说法和原产地标签缺失组合",
        "identifiers": "中国、Alibaba、DDP、原产地标签、低报货值",
        "reason": "组合信号较强，但缺少目的国、具体货物、供应商和单证号。",
        "followup": "补充订单、品名、目的国、供应商、进口申报货值和包装标签照片。",
    },
    "codex-forum-port30d-20260805-05": {
        "score": 78, "components": [20, 18, 15, 15, 10], "decision": "reserve",
        "signal": "南沙蛇口查验审价收紧背景下仍称可接买单和敏感品",
        "identifiers": "南沙、蛇口、查验、审价、敏感品、买单",
        "reason": "具有口岸态势价值，但未出现具体交易或货主。",
        "followup": "按发帖账号和联系方式扩查具体报价、品名、报关抬头与同期舱单。",
    },
    "codex-foreign-forum-risk-20260805-07": {
        "score": 77, "components": [18, 21, 15, 14, 9], "decision": "reserve",
        "signal": "持续性8至9公斤门到门小箱并提及上票海关问题",
        "identifiers": "中国—阿根廷、8至9公斤、160至200美元、持续发运",
        "reason": "物流参数具体但无品名、低报、借名或无需证件等直接信号。",
        "followup": "补充品名、承运商、运单号、收件主体和上一票异常原因，并做同址包裹关联。",
    },
    "codex-forum-port30d-20260805-10": {
        "score": 76, "components": [24, 12, 15, 17, 8], "decision": "reserve",
        "signal": "上海出口同时寻求买单报关和原产地证",
        "identifiers": "上海、买单报关、原产地证",
        "reason": "风险行为直接，但缺少货物、企业、目的国和运输标识。",
        "followup": "补充品名、实际货主、申报抬头、目的国、原产地证申请材料和提运单。",
    },
    "codex-foreign-forum-risk-20260805-03": {
        "score": 74, "components": [20, 17, 15, 14, 8], "decision": "reserve",
        "signal": "中美DDP第三方进口主体和申报货值异常警示",
        "identifiers": "中国—美国、海运DDP、IOR、EIN、Customs Bond",
        "reason": "监管模式清楚但属于从业者泛化警示，缺少可落地的具体交易。",
        "followup": "仅作为模式库；获取具体货代、口岸、IOR、EIN、柜号和申报记录后再升级。",
    },
    "codex-foreign-forum-risk-20260805-04": {
        "score": 65, "components": [16, 13, 15, 13, 8], "decision": "reserve",
        "signal": "入境中国DDP报价可能不足以覆盖税款并滞留海关",
        "identifiers": "中国、空运DDP、不足5公斤、价值超1000元",
        "reason": "仅有报价异常推测，未出现低报、改品名或具体口岸。",
        "followup": "补充品名、运单、入境机场、申报货值、纳税主体和税款凭证。",
    },
}

PROMPT_APPENDIX = """

[2026-08-05 深检增补]
南亚与拉美身份/单证错配词：Bill of Entry不在买方名下、ORM无法核销、第三方Importer of Record、GST不在实际货主名下、IEC、TR6/Challan；CUIT、CUIL、cupo anual agotado、usar CUIT/CUIL de otra persona、puerta a puerta、cinco envíos、courier、misma dirección、mismo destinatario。
优先保留同时出现以下两类以上要素的原帖：①身份或申报主体替换；②年度额度已用尽；③具体平台、货物、城市、重量、报价或付款比例；④报关单、税票、外汇核销等单证无法对应。只出现普通DDP或门到门运输，不得单独判为高风险。
"""


def backup_database() -> str:
    path = _db_file_path()
    if not path or not os.path.exists(path):
        raise RuntimeError("Database path is unavailable")
    backup_dir = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, f"gather.before_forum_top10_audit.{NOW:%Y%m%d_%H%M%S}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    return dest


def upsert_sources(db) -> None:
    keywords = [
        "Bill of Entry", "ORM", "third-party IOR", "CUIT", "CUIL",
        "cupo anual agotado", "puerta a puerta", "usar CUIT de otra persona",
    ]
    for data in SOURCES:
        source = db.get(SourceConfig, data["id"]) or SourceConfig(id=data["id"])
        db.add(source)
        source.name = data["name"]
        source.description = "境外公开中小企业、进出口与物流社区，用于发现非执法通报类的清关主体、单证和额度异常线索。"
        source.channel = "web_scrape"
        source.is_active = True
        source.is_configured = True
        source.base_url = data["url"]
        source.homepage_url = data["url"]
        source.rate_limit_rps = 0.2
        source.timeout_seconds = 20
        source.max_items_per_run = 5
        source.default_keywords = keywords
        source.default_categories = ["境外论坛清关风险线索", "非执法信息"]
        source.languages = data["languages"]
        source.country_focus = data["country_focus"]
        source.legal_basis = "仅采集无需登录即可公开访问的帖子。"
        source.compliance_note = "帖子仅作待核线索，不代表违法事实；不绕过登录、删除或访问限制。"
        source.updated_at = NOW


def upsert_items_and_runs(db) -> tuple[int, int]:
    added = 0
    updated = 0
    source_stats: dict[str, dict[str, int]] = {}
    for data in ITEMS:
        stats = source_stats.setdefault(data["source_id"], {"new": 0, "updated": 0, "found": 0})
        stats["found"] += 1
        item = db.get(CollectedItem, data["id"])
        if item is None:
            item = CollectedItem(id=data["id"], source_id=data["source_id"])
            db.add(item)
            added += 1
            stats["new"] += 1
        else:
            updated += 1
            stats["updated"] += 1
        run_id = f"codex-forum-deep-20260805-{data['source_id']}"
        item.source_id = data["source_id"]
        item.run_id = run_id
        item.topic_id = TOPIC_ID
        item.title = data["title"]
        item.content = data["content"]
        item.content_hash = hashlib.sha256(f"{data['url']}\n{data['content']}".encode("utf-8")).hexdigest()
        item.summary = data["summary"]
        item.url = data["url"]
        item.language = "zh"
        item.category = "境外论坛清关风险线索"
        item.entities = data["entities"]
        item.status = "enriched"
        item.quality_score = 0.90 if data["risk_level"] == "高" else 0.78
        item.relevance_score = 0.97 if data["risk_level"] == "高" else 0.84
        item.published_at = data["published_at"]
        item.collected_at = item.collected_at or NOW
        item.updated_at = NOW
        item.authorization_level = "public"
        item.raw_metadata = {
            "collector": "Codex multilingual public web research",
            "original_language": data["original_language"],
            "evidence_status": "public_forum_post_unverified",
            "risk_level": data["risk_level"],
            "fact_status": "帖子陈述，待交叉验证，不构成违法认定",
            "collection_window": "2026-07-05/2026-08-05",
            "used_project_tavily": False,
            "used_project_baidu": False,
        }

    for source_id, stats in source_stats.items():
        run_id = f"codex-forum-deep-20260805-{source_id}"
        run = db.get(CollectionRun, run_id) or CollectionRun(id=run_id, source_id=source_id)
        db.add(run)
        run.topic_id = TOPIC_ID
        run.status = "completed"
        run.batch_id = "codex-forum-deep-audit-20260805"
        run.keywords_used = ["Bill of Entry", "ORM", "CUIT", "CUIL", "puerta a puerta"]
        run.items_found = stats["found"]
        run.items_new = stats["new"]
        run.items_updated = stats["updated"]
        run.items_failed = 0
        run.started_at = run.started_at or NOW
        run.completed_at = NOW
        dates = [x["published_at"] for x in ITEMS if x["source_id"] == source_id]
        run.window_start = min(dates)
        run.window_end = NOW
        run.error_log = []
        run.metadata_json = {
            "collector": "codex_multilingual_public_web",
            "verification": "manual_source_and_date_review",
            "excludes_enforcement_cases": True,
        }
    return added, updated


def audit_all_items(db) -> list[CollectedItem]:
    items = (
        db.query(CollectedItem)
        .filter(CollectedItem.topic_id == TOPIC_ID)
        .order_by(CollectedItem.published_at.desc(), CollectedItem.id.asc())
        .all()
    )
    item_ids = {item.id for item in items}
    missing = item_ids - set(AUDIT)
    stale = set(AUDIT) - item_ids
    if missing or stale:
        raise RuntimeError(f"Audit mapping mismatch: missing={sorted(missing)} stale={sorted(stale)}")
    if any(not item.published_at or item.published_at < WINDOW_START.replace(tzinfo=None) for item in items):
        raise RuntimeError("Topic contains an item outside the 31-day audit window")
    for item in items:
        review = AUDIT[item.id]
        metadata = dict(item.raw_metadata or {})
        metadata["topic_audit_20260805"] = {
            "value_score": review["score"],
            "score_components": {
                "direct_risk_signal_30": review["components"][0],
                "traceable_identifiers_25": review["components"][1],
                "customs_relevance_15": review["components"][2],
                "evidence_quality_20": review["components"][3],
                "recency_10": review["components"][4],
            },
            "decision": review["decision"],
            "signal": review["signal"],
            "identifiers": review["identifiers"],
            "value_reason": review["reason"],
            "follow_up": review["followup"],
            "legal_notice": "公开帖子待核线索，不构成违法事实认定",
        }
        item.raw_metadata = metadata
        item.updated_at = NOW
    return items


def build_report(topic: Topic, items: list[CollectedItem]) -> tuple[str, list[CollectedItem]]:
    top = sorted(
        (item for item in items if AUDIT[item.id]["decision"] == "top10"),
        key=lambda item: (-AUDIT[item.id]["score"], item.id),
    )
    if len(top) != 10:
        raise RuntimeError(f"Expected 10 selected items, got {len(top)}")

    lines = [
        f"# {topic.name} TOP10审核报告（2026-07-05—2026-08-05）",
        "",
        "## 一、审核结论",
        "",
        f"本次对主题内全部 **{len(items)} 条**近一个月公开帖子逐条复核，并在境外多语种社区补充发现 **3 条**合格线索。按风险行为直接性、可追踪标识、海关监管相关性、证据完整度和时效性评分，筛出最有价值的 **10 条**。",
        "",
        "这些帖子均为公开网络陈述，尚未完成报关单、舱单、企业登记或运输记录的独立验证；本报告中的“高风险”仅指排查优先级，不构成走私或违规认定。普通DDP、双清或第三国转运若没有低报、改品名、借名主体、无需证件、查验包赔等组合信号，不纳入高风险结论。",
        "",
        "本轮未发现可直接验证的完整集装箱号或船名；但已提取到承运人、港口、箱量、线路、货物参数、付款比例、身份号类型和监管单证等更适合进一步核查的标识。",
        "",
        "## 二、统一评分方法",
        "",
        "| 维度 | 权重 | 审核重点 |",
        "|---|---:|---|",
        "| 风险行为直接性 | 30 | 是否明确出现虚标、买单、借名、数量金额差异、换柜/原产地操作等 |",
        "| 可追踪标识 | 25 | 企业、口岸、承运人、路线、箱量、参数、单证、报价或付款信息 |",
        "| 海关监管相关性 | 15 | 是否直连申报、检验检疫、知识产权、税收、原产地或运输安全 |",
        "| 证据完整度 | 20 | 是否为具体交易/问题，能否由多类单证交叉验证 |",
        "| 时效性 | 10 | 距审核日越近得分越高 |",
        "",
        "## 三、价值最高的10条",
        "",
        "| 排名 | 评分 | 日期 | 信息条目 | 关键可核标识 |",
        "|---:|---:|---|---|---|",
    ]
    for rank, item in enumerate(top, 1):
        review = AUDIT[item.id]
        date = item.published_at.strftime("%Y-%m-%d") if item.published_at else "未知"
        lines.append(f"| {rank} | {review['score']} | {date} | [{item.title}]({item.url}) | {review['identifiers']} |")

    lines.extend(["", "## 四、逐条摘要、风险点与排查方向", ""])
    for rank, item in enumerate(top, 1):
        review = AUDIT[item.id]
        lines.extend([
            f"### {rank}. {item.title}（{review['score']}分）",
            "",
            f"- 来源：[{item.source.name if item.source else item.source_id}]({item.url})；发布日期：{item.published_at.strftime('%Y-%m-%d') if item.published_at else '未知'}。",
            f"- 主要内容：{item.summary}",
            f"- 涉及风险点：{review['signal']}。",
            f"- 可核标识：{review['identifiers']}。",
            f"- 入选理由：{review['reason']}",
            f"- 后续排查方向：{review['followup']}",
            "- 证据状态：公开帖子陈述，待报关、舱单、运输、付款或企业资料交叉验证。",
            "",
        ])

    reserve = sorted(
        (item for item in items if AUDIT[item.id]["decision"] == "reserve"),
        key=lambda item: (-AUDIT[item.id]["score"], item.id),
    )
    lines.extend([
        "## 五、其余8条审核处置",
        "",
        "其余条目保留在主题库中作为模式或扩线素材，未删除。未进入前十的主要原因是缺少具体货物/主体/运输标识，或内容偏一般性合规咨询，不能仅凭DDP、门到门或报价异常升级风险。",
        "",
        "| 评分 | 条目 | 未进入前十的主要原因 |",
        "|---:|---|---|",
    ])
    for item in reserve:
        review = AUDIT[item.id]
        lines.append(f"| {review['score']} | [{item.title}]({item.url}) | {review['reason']} |")

    lines.extend([
        "",
        "## 六、综合风险画像",
        "",
        "1. **申报主体错配**：DDP拼柜、第三方Importer of Record、实际买方名下无MRN/Bill of Entry，以及借用CUIT/CUIL，均指向“实际货主—付款人—申报人—纳税人”链条断裂。",
        "2. **伪瞒报与标签异常**：电池参数虚标、报关数量遗漏近15%、食品和品牌服装混入买单杂货，是本批次最直接的申报一致性风险。",
        "3. **原产地和转口链**：蛇口—巴生港—意大利铝材换柜转口线索同时出现承运人、2×40HQ、保税仓和原产地文件，最适合优先做箱流与单证穿透。",
        "4. **重点货物**：电子烟、锂电池、生物菌粉剂、食品、化妆品、仿牌服装、铝材兼具许可证件、检验检疫、知识产权、危险品或贸易救济风险。",
        "5. **重点节点**：南沙、蛇口、盐田、青岛，以及巴生港Westport、仁川/釜山、洛杉矶、罗马尼亚、古尔冈和圣地亚哥-德尔埃斯特罗可作为后续线路交叉检索锚点。",
        "",
        "## 七、建议核查顺序",
        "",
        "- 第一优先：马来西亚换柜转口铝材、电子烟多路线DDP、电池参数虚标、青岛混装食品及品牌服装。",
        "- 第二优先：借用CUIT/CUIL、近15%报关差异、生物菌粉剂单一品名放行、南沙仿牌货物。",
        "- 第三优先：中国—印度第三方进口主体、中国—欧盟拼柜DDP无MRN；先补齐企业、运单和申报单号后再升级。",
        "",
        f"> 审核时间：{NOW.astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}。采集仅使用公开网页，未使用项目百度或Tavily额度。",
    ])
    return "\n".join(lines), top


def main() -> None:
    backup = backup_database()
    with SessionLocal() as db:
        topic = db.get(Topic, TOPIC_ID)
        prompt = db.get(PromptTemplate, PROMPT_ID)
        if topic is None or prompt is None:
            raise RuntimeError("Required topic or prompt template is missing")

        upsert_sources(db)
        db.flush()
        added, updated = upsert_items_and_runs(db)

        source_ids = [data["id"] for data in SOURCES]
        source_urls = [data["url"] for data in SOURCES]
        topic.source_ids = list(dict.fromkeys((topic.source_ids or []) + source_ids))
        topic.target_urls = list(dict.fromkeys((topic.target_urls or []) + source_urls))
        topic.focus_languages = list(dict.fromkeys((topic.focus_languages or []) + ["en", "hi", "es"]))
        topic.keywords = list(dict.fromkeys((topic.keywords or []) + [
            "Bill of Entry不在买方名下", "ORM无法核销", "CUIT", "CUIL",
            "cupo anual agotado", "usar CUIT de otra persona", "puerta a puerta",
        ]))
        if "[2026-08-05 深检增补]" not in prompt.content:
            prompt.content = prompt.content.rstrip() + PROMPT_APPENDIX
        prompt.updated_at = NOW

        db.flush()
        all_items = audit_all_items(db)
        report_text, top_items = build_report(topic, all_items)

        report = db.get(Report, REPORT_ID)
        if report is None:
            report = Report(id=REPORT_ID, topic_id=TOPIC_ID, title="")
            db.add(report)
        report.title = "外贸论坛违规清关与走私风险线索TOP10审核报告（2026-07-05—2026-08-05）"
        report.report_type = "analytical"
        report.content = report_text
        report.summary = (
            f"审核主题内全部{len(all_items)}条近一个月论坛/社交平台线索，新增3条境外多语种信息，"
            "按直接风险信号与可追踪标识筛出10条最高价值线索；不包含执法案例。"
        )
        report.status = "completed"
        report.model_id = "codex-public-web-audit"
        report.tokens_used = 0
        report.item_count = len(top_items)
        report.item_ids = [item.id for item in top_items]
        report.error_log = None
        report.collection_run_id = None
        report.date_range_start = WINDOW_START
        report.date_range_end = WINDOW_END
        report.output_files = None
        report.output_dir = None
        report.generated_at = NOW
        report.created_at = report.created_at or NOW

        topic.total_items_collected = len(all_items)
        topic.last_run_at = NOW
        topic.last_collection_run_id = "codex-forum-deep-20260805-reddit-negociosargentina"
        topic.updated_at = NOW
        for source_id in source_ids:
            source = db.get(SourceConfig, source_id)
            source.items_collected = db.query(CollectedItem).filter(CollectedItem.source_id == source_id).count()
            source.last_sync_at = NOW
        db.commit()

        print(f"backup={backup}")
        print(f"new_sources={len(source_ids)} added_items={added} updated_items={updated}")
        print(f"topic_sources={len(topic.source_ids or [])} audited_items={len(all_items)}")
        print(f"report_id={report.id} top_items={report.item_count}")
        print("top10=" + ",".join(report.item_ids or []))


if __name__ == "__main__":
    main()
