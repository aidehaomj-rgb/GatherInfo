"""Import foreign forum sources, multilingual prompt terms, and recent public leads."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

from app.database import SessionLocal, _db_file_path
from app.models import CollectionRun, CollectedItem, PromptTemplate, SourceConfig, Topic


TOPIC_ID = "foreign-trade-forum-risk-monitoring"
PROMPT_ID = "forum-social-customs-risk-search"
NOW = datetime.now(timezone.utc)

SOURCES = [
    ("reddit-customsbroker", "Reddit - CustomsBroker", "https://www.reddit.com/r/CustomsBroker/", ["en"]),
    ("reddit-freightforwarding", "Reddit - freightforwarding", "https://www.reddit.com/r/freightforwarding/", ["en"]),
    ("reddit-alibaba", "Reddit - Alibaba", "https://www.reddit.com/r/Alibaba/", ["en"]),
    ("reddit-internationaltrade", "Reddit - Internationaltrade", "https://www.reddit.com/r/Internationaltrade/", ["en"]),
    ("reddit-business-in-china", "Reddit - Business_in_China", "https://www.reddit.com/r/Business_in_China/", ["en", "zh"]),
    ("reddit-china", "Reddit - China", "https://www.reddit.com/r/China/", ["en", "zh"]),
    ("reddit-logistics", "Reddit - logistics", "https://www.reddit.com/r/logistics/", ["en"]),
    ("reddit-india-business", "Reddit - IndiaBusiness", "https://www.reddit.com/r/IndiaBusiness/", ["en", "hi"]),
    ("vc-ru-marketplace", "VC.ru - Marketplace/Transport", "https://vc.ru/marketplace", ["ru"]),
]

ITEMS = [
    {
        "id": "codex-foreign-forum-risk-20260805-01",
        "source_id": "reddit-customsbroker",
        "published_at": datetime(2026, 7, 30, 12, tzinfo=timezone.utc),
        "title": "罗马尼亚企业反映中国至欧盟拼柜DDP无法取得企业名下MRN",
        "url": "https://www.reddit.com/r/CustomsBroker/comments/1vapp74/ddp_vs_dap_for_eu_imports_customs_documentation/",
        "summary": "罗马尼亚一家小企业称，多家中国至欧盟DDP货代无法提供以该企业名义出具的进口申报单、MRN或其他清关文件，理由是多个客户货物拼柜后统一申报。讨论进一步提出部分货代可能通过低报货值降低进口增值税和关税，但未披露货代名称、口岸、提单号或申报单号。",
        "content": "主要内容：发帖企业计划从中国进口货物至罗马尼亚，使用拼柜DDP时只能取得交付或运输文件，无法取得与本企业关联的欧盟进口申报及MRN。\n风险点：拼柜DDP、进口责任主体不透明、企业名下无MRN、申报与实际货主难以逐票对应，并伴随低报货值疑虑。上述内容均为发帖人与回复者陈述，尚未独立核验。\n后续排查方向：核对卖方、货代、欧盟Importer of Record及EORI；调取MRN、进口增值税凭证、拼柜舱单、分拨清单、采购发票和付款金额，确认各票货物是否如实申报。",
        "entities": {"起运国": ["中国"], "目的地": ["罗马尼亚", "欧盟"], "运输方式": ["拼柜DDP"], "监管标识": ["MRN", "EORI", "Importer of Record"], "未披露": ["企业名称", "货代名称", "口岸", "提单号"]},
        "risk_level": "中高",
    },
    {
        "id": "codex-foreign-forum-risk-20260805-02",
        "source_id": "reddit-business-in-china",
        "published_at": datetime(2026, 7, 15, 12, tzinfo=timezone.utc),
        "title": "采购者称中国供应商以DDP为由不做原产地标签并出现低报说法",
        "url": "https://www.reddit.com/r/Business_in_China/comments/1uxk4a4/country_of_origin_labels/",
        "summary": "采购者询问中国商品是否必须逐件标注Made in China，称供应商以采用DDP为由表示无需标注。回复中出现供应方可能低报货值并寄希望于不被海关查验的说法，形成“DDP＋低报＋原产地标识缺失＋不查验预期”的组合风险信号。",
        "content": "主要内容：一名首次通过Alibaba采购的用户称，报关代理和商业导师要求商品逐件标注中国制造，但供应商及其他卖家表示使用DDP后无需标注。\n风险点：帖子回复明确出现低报货值、希望海关不查验以及DDP可免除标签要求等表述。单一回复不能证明供应商实际实施低报，但组合信号明显高于一般DDP咨询。\n后续排查方向：提取订单商品、供应商、货代和目的国；核对进口申报货值、原产国标识、产品包装照片、Importer of Record、采购合同与付款记录。",
        "entities": {"来源地": ["中国"], "采购平台": ["Alibaba"], "运输方式": ["DDP"], "风险行为": ["低报货值", "原产地标签缺失", "寄希望于不查验"], "未披露": ["供应商名称", "货代名称", "目的国", "运单号"]},
        "risk_level": "中高",
    },
    {
        "id": "codex-foreign-forum-risk-20260805-03",
        "source_id": "reddit-freightforwarding",
        "published_at": datetime(2026, 7, 6, 12, tzinfo=timezone.utc),
        "title": "中美DDP从业者提示第三方进口主体和申报货值异常风险",
        "url": "https://www.reddit.com/r/freightforwarding/comments/1uol0a2/warning_for_us_importers_ddp_sea_freight_has/",
        "summary": "一名自称长期从事中美运输的发帖人称，近期部分中国至美国DDP货物因第三方进口责任主体记录不清、申报货值差异而遭遇扣查、罚款、滞港或退运风险，并称部分低价货代在查验后追加费用。帖子未披露具体货代、美国口岸或柜号。",
        "content": "主要内容：发帖人以行业经验提醒美国进口商关注中国至美国海运DDP中的第三方Importer of Record、申报价格差异和低价报价问题。\n风险点：第三方IOR信息不清、申报货值与实际交易可能不一致、低价DDP、扣查后追加隐性费用。该帖属于从业者自述，不是执法通报，也没有提供可独立验证的具体案件编号。\n后续排查方向：核验IOR美国法人、EIN、连续Bond、报关代理资质及进口主体更换频率；比对采购发票、付款金额、申报价格和税款凭证。",
        "entities": {"路线": ["中国—美国"], "运输方式": ["海运DDP"], "监管标识": ["Importer of Record", "EIN", "Customs Bond"], "风险行为": ["申报货值差异", "第三方IOR不透明", "追加费用"], "未披露": ["货代名称", "美国口岸", "柜号"]},
        "risk_level": "中",
    },
    {
        "id": "codex-foreign-forum-risk-20260805-04",
        "source_id": "reddit-china",
        "published_at": datetime(2026, 7, 12, 12, tzinfo=timezone.utc),
        "title": "入境中国DDP小包报价明显不足以覆盖预计税款并滞留清关",
        "url": "https://www.reddit.com/r/China/comments/1uued18/asking_for_help_about_import_into_china/",
        "summary": "用户称从境外购买不足5公斤、价值超过1000元人民币的货物，货代承诺DDP送达中国，但报价明显低于其预计税费，轨迹随后显示货物进入中国海关等待处理。帖子未明确出现低报、改品名或具体入境机场，只能作为报价与纳税义务不匹配的异常线索。",
        "content": "主要内容：境外货物以DDP方式空运进入中国，重量不足5公斤、价值超过1000元人民币；发帖人认为货代报价没有覆盖应缴税款，货物状态显示正在中国海关处理。\n风险点：DDP报价与预计税费明显不匹配、境内清关主体不清、货物进入海关环节。原帖没有证明低报或伪报行为，风险等级应控制在中等。\n后续排查方向：核对运单、入境机场、品名、申报价格、纳税主体、货代及境内代理资质，确认是否补充申报或缴税。",
        "entities": {"目的地": ["中国"], "运输方式": ["空运DDP"], "重量": ["不足5公斤"], "货值": ["超过1000元人民币"], "风险行为": ["报价与预计税费不匹配", "清关主体不明"], "未披露": ["货物品名", "入境机场", "运单号", "货代名称"]},
        "risk_level": "中",
    },
]

MULTILINGUAL_PROMPT = """

九、境外论坛多语种扩展词
英语：grey channel, under-declare, undervalued invoice, misdeclare value, wrong HS code, change product description, no buyer-named declaration, no MRN, third-party importer of record, consolidated DDP, DDP per kg, no duty receipt, sensitive goods, customs guarantee, DM for quote。
西班牙语：canal gris, subfacturación, valor subdeclarado, cambiar descripción, clasificación arancelaria falsa, importador de registro, despacho consolidado, sin licencia, precio por kilo。
俄语：серая доставка, серый импорт, карго из Китая, занижение стоимости, смена наименования, чужой импортёр, без декларации, доставка за килограмм, свой человек на границе。
马来语：laluan kelabu, kurang isytihar nilai, tukar nama barang, barang sensitif, tanpa permit, pengisytiharan pihak ketiga, harga sekilo。
印尼语：jalur abu-abu, under invoice, nilai impor diturunkan, ubah nama barang, tanpa izin, importir pihak ketiga, borongan per kilogram。
多语种内容仍执行组合信号规则：不得因DDP、包税、第三国转运或importer of record单独出现而判定高风险；优先保留其与低报、错报HS编码、无申报凭证、无许可证、查验包赔、具体货物路线、报价、收款或联系方式共同出现的原帖。
"""


def backup_database() -> str:
    path = _db_file_path()
    if not path or not os.path.exists(path):
        raise RuntimeError("Database path is unavailable")
    backup_dir = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, f"gather.before_foreign_forum_import.{NOW:%Y%m%d_%H%M%S}.db")
    with sqlite3.connect(path) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    return dest


def upsert_sources(db) -> None:
    keywords = ["grey channel", "under-declare", "wrong HS code", "DDP per kg", "third-party IOR", "no MRN"]
    for source_id, name, url, languages in SOURCES:
        source = db.get(SourceConfig, source_id) or SourceConfig(id=source_id)
        db.add(source)
        source.name = name
        source.description = "境外公开贸易、报关或货代社区，用于发现尚未进入执法通报体系的社会面清关风险线索。"
        source.channel = "web_scrape"
        source.is_active = True
        source.is_configured = True
        source.base_url = url
        source.homepage_url = url
        source.rate_limit_rps = 0.2
        source.timeout_seconds = 20
        source.max_items_per_run = 4
        source.default_keywords = keywords
        source.default_categories = ["外贸论坛与社会面线索", "国外贸易及货代社区"]
        source.languages = languages
        source.legal_basis = "仅采集无需登录即可公开访问的帖子。"
        source.compliance_note = "帖子仅作待核线索，不代表违法事实；不绕过登录、删除或访问限制。"
        source.updated_at = NOW


def upsert_items_and_runs(db) -> tuple[int, int]:
    added = 0
    updated = 0
    grouped: dict[str, list[dict]] = {}
    for data in ITEMS:
        grouped.setdefault(data["source_id"], []).append(data)
        item = db.get(CollectedItem, data["id"])
        if item is None:
            item = CollectedItem(id=data["id"], source_id=data["source_id"])
            db.add(item)
            added += 1
        else:
            updated += 1
        item.run_id = f"codex-foreign-forum-20260805-{data['source_id']}"
        item.topic_id = TOPIC_ID
        item.title = data["title"]
        item.content = data["content"]
        item.content_hash = hashlib.sha256(data["content"].encode("utf-8")).hexdigest()
        item.summary = data["summary"]
        item.url = data["url"]
        item.language = "zh"
        item.category = "境外论坛清关风险线索"
        item.entities = data["entities"]
        item.status = "enriched"
        item.quality_score = 88.0
        item.relevance_score = 96.0
        item.published_at = data["published_at"]
        item.collected_at = item.collected_at or NOW
        item.updated_at = NOW
        item.authorization_level = "public"
        item.raw_metadata = {
            "collector": "Codex multilingual public web research",
            "original_language": "en",
            "evidence_status": "public_forum_post_unverified",
            "risk_level": data["risk_level"],
            "fact_status": "帖子陈述，待交叉验证，不构成违法认定",
            "used_project_tavily": False,
            "used_project_baidu": False,
        }
    for source_id, records in grouped.items():
        run_id = f"codex-foreign-forum-20260805-{source_id}"
        run = db.get(CollectionRun, run_id) or CollectionRun(id=run_id, source_id=source_id)
        db.add(run)
        run.topic_id = TOPIC_ID
        run.status = "completed"
        run.batch_id = "codex-foreign-forum-multilingual-20260805"
        run.keywords_used = ["DDP", "grey channel", "under-declare", "third-party IOR", "no MRN"]
        run.items_found = len(records)
        run.items_new = len(records)
        run.items_updated = 0
        run.items_failed = 0
        run.started_at = run.started_at or NOW
        run.completed_at = NOW
        run.window_start = min(record["published_at"] for record in records)
        run.window_end = NOW
        run.error_log = []
        run.metadata_json = {"collector": "codex_multilingual_public_web", "verification": "pending"}
    return added, updated


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
        source_ids = [source[0] for source in SOURCES]
        urls = [source[2] for source in SOURCES]
        topic.source_ids = list(dict.fromkeys((topic.source_ids or []) + source_ids))
        topic.target_urls = list(dict.fromkeys((topic.target_urls or []) + urls))
        topic.focus_languages = list(dict.fromkeys((topic.focus_languages or []) + ["en", "es", "ru", "ms", "id", "hi"]))
        topic.keywords = list(dict.fromkeys((topic.keywords or []) + [
            "grey channel", "under-declare", "undervalued invoice", "wrong HS code", "no MRN",
            "third-party importer of record", "consolidated DDP", "DDP per kg", "серая доставка",
            "занижение стоимости", "canal gris", "subfacturación", "laluan kelabu", "jalur abu-abu",
        ]))
        if "九、境外论坛多语种扩展词" not in prompt.content:
            prompt.content = prompt.content.rstrip() + MULTILINGUAL_PROMPT
        prompt.updated_at = NOW
        topic.last_run_at = NOW
        topic.last_collection_run_id = "codex-foreign-forum-20260805-reddit-customsbroker"
        db.flush()
        topic.total_items_collected = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).count()
        topic.updated_at = NOW
        for source_id in source_ids:
            source = db.get(SourceConfig, source_id)
            source.items_collected = db.query(CollectedItem).filter(CollectedItem.source_id == source_id).count()
        db.commit()
        print(f"backup={backup}")
        print(f"sources={len(source_ids)} added_items={added} updated_items={updated}")
        print(f"topic_sources={len(topic.source_ids or [])} topic_items={topic.total_items_collected}")
        print(f"prompt_chars={len(prompt.content)}")


if __name__ == "__main__":
    main()
