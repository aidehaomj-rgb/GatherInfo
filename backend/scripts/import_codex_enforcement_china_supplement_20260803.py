"""Import verified China-related enforcement cases found by multilingual search."""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal  # noqa: E402
from app.models import CollectedItem, CollectionRun, SourceConfig, Tag, Topic  # noqa: E402


TOPIC_ID = "weekly-enforcement-intelligence"
SOURCE_ID = "ai-smart-web-research"
BATCH_ID = "codex-enforcement-china-supplement-20260803"

CASES = [
    {
        "key": "ph-china-vapes-20260708",
        "url": "https://customs.gov.ph/boc-seizes-%E2%82%B1137m-worth-of-smuggled-vape-products-at-micp/",
        "published_at": "2026-07-08T12:00:00+08:00",
        "language": "en",
        "title": "BOC Seizes PHP137 Million Worth of Smuggled Vape Products at MICP",
        "content": (
            "The Philippine Bureau of Customs intercepted nine containers of misdeclared vape "
            "products at the Manila International Container Port. The shipments originated from "
            "China and were declared as cardboard boxes, accessories, kitchenware, underwear, "
            "clothes hangers, shoe boxes and footwear. A full physical examination found vape kits, "
            "disposable devices, cartridges and related products valued at PHP136.92 million."
        ),
        "title_zh": "菲律宾海关查获9个中国来源货柜夹带电子烟产品案",
        "summary_zh": "菲律宾海关在马尼拉国际集装箱港查获9个来自中国的误报货柜，内有价值约1.37亿比索的电子烟及配套产品。",
        "content_zh": (
            "菲律宾海关2026年7月8日通报，马尼拉国际集装箱港根据风险信息对9个货柜实施预警并开展100%实货查验。"
            "货物来自中国，申报品名包括纸箱、配件、包装袋、厨具、内衣、衣架、鞋盒和鞋类等，实际查获大量电子烟套装、"
            "一次性电子烟、烟弹及相关产品，估值约1.3692亿比索。菲律宾贸易工业部和国家调查局参与货物核验，案件进入后续调查和处置程序。"
        ),
        "category": "违禁及管制商品走私",
        "authority": "Philippine Bureau of Customs",
        "jurisdiction": "Philippines",
        "subject": "中国来源9个货柜及电子烟进口经营主体",
        "case_type": "misdeclared vape products",
        "action": "发布预警、实施100%查验、扣押货物并调查",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "The Philippine Bureau of Customs states that all nine misdeclared shipments originated from China.",
        "evidence": "Nine containers from China contained misdeclared vape products valued at PHP136,924,250.",
        "source_name": "Philippine Bureau of Customs",
        "source_tier": "official",
        "confidence": 99,
    },
    {
        "key": "ph-china-frozen-food-20260721",
        "url": "https://customs.gov.ph/boc-seizes-%E2%82%B123-million-worth-of-misdeclared-frozen-agricultural-products-and-foodstuffs-through-coordinated-efforts-with-da/",
        "published_at": "2026-07-21T12:00:00+08:00",
        "language": "en",
        "title": "BOC Seizes PHP23 Million of Misdeclared Frozen Agricultural Products from China",
        "content": (
            "The Philippine Bureau of Customs inspected five containers of misdeclared frozen "
            "agricultural products and foodstuffs from China. Customs intelligence and risk profiling "
            "led to control and alert orders. The examination found chicken breast, frozen pigeon, "
            "Peking duck, frozen duck meat and other products valued at PHP23.27 million including duties and taxes."
        ),
        "title_zh": "菲律宾海关查获5个中国来源货柜误报冷冻农产品案",
        "summary_zh": "菲律宾海关查获5个来自中国的误报冷冻农产品和食品货柜，含税总值约2327万比索，并按大规模农业走私方向调查。",
        "content_zh": (
            "菲律宾海关2026年7月21日通报，海关情报分析、风险评估和企业画像发现异常后，对5个中国来源货柜签发装货前控制令和预警令。"
            "货柜原申报为鱼丸、鱼豆腐等食品，100%查验发现去皮鸡胸、无皮鸡胸、冻鸽、北京鸭、冻鸭肉等误报和非法进口农产品，"
            "货物价值及税费合计约2327万比索。海关已签发扣押令，并调查是否构成大规模农业走私。"
        ),
        "category": "农产品走私",
        "authority": "Philippine Bureau of Customs",
        "jurisdiction": "Philippines",
        "subject": "中国来源5个货柜及冷冻农产品进口主体",
        "case_type": "agricultural smuggling and misdeclaration",
        "action": "风险布控、100%查验、签发扣押令并调查大规模农业走私",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "The five misdeclared frozen-food shipments were officially identified as originating from China.",
        "evidence": "Five containers from China held misdeclared frozen goods worth PHP23,268,889.74 including duties and taxes.",
        "source_name": "Philippine Bureau of Customs",
        "source_tier": "official",
        "confidence": 99,
    },
    {
        "key": "us-chinese-turtle-trafficking-20260723",
        "url": "https://www.justice.gov/opa/pr/two-chinese-nationals-plead-guilty-trafficking-turtles-hong-kong",
        "published_at": "2026-07-23T12:00:00-04:00",
        "language": "en",
        "title": "Two Chinese Nationals Plead Guilty to Trafficking Turtles to Hong Kong",
        "content": (
            "Kin Keung Ho and Lihua Owen Ma, both Chinese nationals living in New York, pleaded guilty "
            "to Lacey Act felonies for exporting protected U.S. native turtles to Asia without permits "
            "or declarations and using false package labels. Ho admitted shipping approximately 99 packages "
            "containing 578 turtles, often falsely labeled as crystals or stones."
        ),
        "title_zh": "两名中国籍人员在美承认向香港非法贩运受保护龟类",
        "summary_zh": "美国司法部通报，两名中国籍人员承认以虚假标签、无许可证和无申报方式向亚洲非法出口受保护龟类，其中一人涉及578只龟。",
        "content_zh": (
            "美国司法部2026年7月23日通报，居住在纽约的中国籍人员Kin Keung Ho和Lihua Owen Ma分别承认违反《莱西法》。"
            "两人将美国本土箱龟、斑点龟和菱背水龟等受保护物种出口至亚洲，未取得所需许可证、未依法申报，并将包裹虚假标注为水晶或石头。"
            "其中Ho承认寄送约99个包裹、共578只龟。案件由美国鱼类及野生动物管理局执法部门会同邮政检查部门调查。"
        ),
        "category": "濒危物种走私",
        "authority": "U.S. Department of Justice and U.S. Fish and Wildlife Service",
        "jurisdiction": "United States",
        "subject": "Kin Keung Ho、Lihua Owen Ma及578只受保护龟类",
        "case_type": "wildlife trafficking and false customs labels",
        "action": "刑事认罪并等待量刑",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "The defendants are Chinese nationals and the protected turtles were trafficked toward Hong Kong and the Chinese pet market.",
        "evidence": "The defendants admitted false labels and permit-free exports; one shipped 578 protected turtles in about 99 packages.",
        "source_name": "U.S. Department of Justice",
        "source_tier": "official",
        "confidence": 99,
    },
    {
        "key": "us-chinese-meth-australia-20260724",
        "url": "https://www.justice.gov/usao-cdca/pr/chinese-national-sentenced-over-7-years-federal-prison-role-group-attempted-ship-over",
        "published_at": "2026-07-24T12:00:00-07:00",
        "language": "en",
        "title": "Chinese National Sentenced for Attempting to Ship More Than One Metric Ton of Meth to Australia",
        "content": (
            "A U.S. federal court sentenced Chinese national Jing Tang Li to 87 months in prison for his role "
            "in a drug trafficking group that attempted to export more than one metric ton of methamphetamine "
            "from Los Angeles to Australia. CBP found drugs concealed in shipments falsely described as carpets, "
            "furniture, wheel-hub testing equipment and a casting machine."
        ),
        "title_zh": "中国籍人员因企图从美国向澳大利亚走私逾1吨冰毒被判刑",
        "summary_zh": "美国联邦法院判处中国籍人员Jing Tang Li有期徒刑87个月，其团伙利用虚假企业和伪报货物企图向澳大利亚出口逾1吨冰毒。",
        "content_zh": (
            "美国司法部2026年7月24日通报，中国籍人员Jing Tang Li因参与跨国贩毒被判处87个月监禁。"
            "2023年，美国海关与边境保护局先后检查7票拟运往澳大利亚的货物，申报品名包括地毯、家具、轮毂测试设备和铸造机，"
            "实际在橡胶垫、金属管和设备中夹藏冰毒，执法部门合计查获超过1000公斤。美国国土安全调查局、海关与边境保护局及澳大利亚联邦警察联合调查。"
        ),
        "category": "毒品走私",
        "authority": "U.S. Department of Justice, CBP and Homeland Security Investigations",
        "jurisdiction": "United States",
        "subject": "中国籍人员Jing Tang Li及美澳跨境贩毒团伙",
        "case_type": "methamphetamine export smuggling",
        "action": "查扣7票货物、刑事起诉并判处87个月监禁",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "The convicted organizer is a Chinese national and the case involved a coordinated U.S.-Australia customs investigation.",
        "evidence": "More than 1,000 kilograms of methamphetamine were hidden in seven falsely declared export shipments.",
        "source_name": "U.S. Department of Justice",
        "source_tier": "official",
        "confidence": 99,
    },
    {
        "key": "us-fentanyl-from-china-20260708",
        "url": "https://www.justice.gov/usao-mdga/pr/two-georgians-sentenced-trafficking-fentanyl-china",
        "published_at": "2026-07-08T12:00:00-04:00",
        "language": "en",
        "title": "Two Georgians Sentenced for Trafficking Fentanyl from China",
        "content": (
            "Two Georgia men received federal prison sentences for a prison-directed organization that "
            "acquired and distributed fentanyl and synthetic cannabinoids from China. Two China-based "
            "co-conspirators, Xin Wang and Gao Yong, remain charged and at large. Investigators linked the "
            "scheme to 2,610 fentanyl pills and 5,502 grams of synthetic cannabinoid."
        ),
        "title_zh": "美国法院判处从中国获取芬太尼和合成大麻素的贩毒团伙成员监禁",
        "summary_zh": "美国司法部通报，两名佐治亚州团伙成员因从中国获取并分销芬太尼和合成大麻素分别获刑，另有两名中国境内涉案人员被起诉。",
        "content_zh": (
            "美国司法部2026年7月8日通报，两名佐治亚州人员因参与由监狱内遥控的跨境贩毒网络，被分别判处327个月和262个月监禁。"
            "案件涉及从中国获取并向美国分销2610粒芬太尼药片和5502克合成大麻素。中国境内人员Xin Wang和Gao Yong被控参与共谋，"
            "目前尚未归案。案件由美国联邦调查局和邮政检查部门等机构调查。"
        ),
        "category": "毒品走私",
        "authority": "U.S. Department of Justice, FBI and U.S. Postal Inspection Service",
        "jurisdiction": "United States",
        "subject": "美国监狱遥控贩毒网络及中国境内涉案人员Xin Wang、Gao Yong",
        "case_type": "fentanyl and synthetic cannabinoid trafficking",
        "action": "判处团伙成员监禁并追捕中国境内被告",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Court records identify China as the source and name two China-based alleged co-conspirators.",
        "evidence": "The organization moved 2,610 fentanyl pills and 5,502 grams of synthetic cannabinoid acquired from China.",
        "source_name": "U.S. Department of Justice",
        "source_tier": "official",
        "confidence": 99,
    },
    {
        "key": "us-unapproved-chinese-drugs-20260723",
        "url": "https://www.justice.gov/usao-wdmi/pr/2026_0723_Piper_Sentencing_PR",
        "published_at": "2026-07-23T12:00:00-04:00",
        "language": "en",
        "title": "Michigan Man Sentenced for Selling Chinese Drugs Without FDA Approval",
        "content": (
            "Brandon Piper was sentenced to 21 months in prison for helping import and sell unapproved, "
            "misbranded prescription drugs, including semaglutide and tirzepatide, from China. Some products "
            "were marketed as products of the United States even though the conspirators bought them from China, "
            "and the drugs were distributed without prescriptions or adequate directions and warnings."
        ),
        "title_zh": "美国男子因进口销售中国来源未获批减重药物被判刑",
        "summary_zh": "美国司法部通报，密歇根州男子因从中国进口未获FDA批准且虚假标识的处方药并通过网站销售，被判处21个月监禁。",
        "content_zh": (
            "美国司法部2026年7月23日通报，Brandon Piper因共谋将未获批准、标签不实的处方药引入美国市场，被判处21个月监禁。"
            "涉案药物包括司美格鲁肽和替尔泊肽等减重药，实际从中国采购，部分却标注为美国制造，并在无处方、无充分用药说明和风险警示的情况下销售。"
            "案件由美国食品药品监督管理局刑事调查办公室办理。"
        ),
        "category": "药品进口合规执法",
        "authority": "U.S. Department of Justice and FDA Office of Criminal Investigations",
        "jurisdiction": "United States",
        "subject": "Brandon Piper及中国来源未获批处方药销售网络",
        "case_type": "misbranded and unapproved drug imports",
        "action": "刑事判决21个月监禁并继续追诉共同被告",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Sentencing filings established that the misbranded drugs were purchased and imported from China.",
        "evidence": "Unapproved semaglutide, tirzepatide and other drugs were bought from China and falsely marketed in the United States.",
        "source_name": "U.S. Department of Justice",
        "source_tier": "official",
        "confidence": 99,
    },
    {
        "key": "sri-lanka-chinese-cigarettes-20260717",
        "url": "https://frontpage.lk/amp/chilled-panels-hot-cargo-sri-lanka-seize-rs-450-million-chinese-cigarette-haul/",
        "published_at": "2026-07-17T12:00:00+05:30",
        "language": "en",
        "title": "Sri Lanka Customs Seizes 3.6 Million Chinese Cigarettes Hidden in Cold Storage Panels",
        "content": (
            "Sri Lanka Customs seized approximately 3.6 million smuggled cigarettes concealed inside "
            "imported cold storage panels. The Central Intelligence Directorate acted on information from "
            "international partners. Customs assessed the cigarettes at more than Rs450 million and suspected "
            "links to Chinese nationals living or working in Sri Lanka."
        ),
        "title_zh": "斯里兰卡海关查获冷库板夹藏360万支中国来源香烟",
        "summary_zh": "斯里兰卡海关情报部门查获藏于进口冷库板内的约360万支走私香烟，市值超过4.5亿卢比，并调查在斯中国籍人员关联。",
        "content_zh": (
            "斯里兰卡媒体2026年7月17日援引海关消息称，斯里兰卡海关中央情报局根据国际合作伙伴提供的信息，"
            "在申报为冷库板的进口货物中查获约1.8万条、360万支走私香烟。货物通过在冷库板内部设置夹层实施藏匿，"
            "估计市值超过4.5亿卢比，可能造成超过4亿卢比税收损失。海关正调查在斯里兰卡生活或工作的部分中国籍人员是否与案件有关。"
        ),
        "category": "烟草走私",
        "authority": "Sri Lanka Customs Central Intelligence Directorate",
        "jurisdiction": "Sri Lanka",
        "subject": "中国来源香烟、进口企业及可能关联的在斯中国籍人员",
        "case_type": "cigarette smuggling by concealment",
        "action": "情报查验、扣押香烟并追查进口和人员关联",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Multiple Sri Lankan reports identify the cigarettes as Chinese-origin and report that Customs is examining links to Chinese nationals.",
        "evidence": "Customs seized about 3.6 million cigarettes hidden in imported cold-storage panels.",
        "source_name": "FrontPage / Newswire, citing Sri Lanka Customs",
        "source_tier": "authoritative_media",
        "confidence": 92,
    },
    {
        "key": "pakistan-china-air-conditioners-20260716",
        "url": "https://propakistani.pk/2026/07/16/importer-booked-after-customs-finds-nearly-900-acs-hidden-in-scrap/",
        "published_at": "2026-07-16T21:47:00+05:00",
        "language": "en",
        "title": "Pakistan Customs Finds Nearly 900 Air Conditioners from China and Thailand Hidden in Scrap",
        "content": (
            "Pakistan Customs Enforcement Karachi registered an FIR after examining four consignments "
            "declared as scrap. Officers found 897 new air conditioners, 113 dehumidifiers and three used "
            "water dispensers, mainly Midea branded and originating from Thailand and China, concealed behind "
            "compressor scrap. The assessed goods were worth Rs63.39 million."
        ),
        "title_zh": "巴基斯坦海关查获废料后夹藏近900台中泰来源空调案",
        "summary_zh": "巴基斯坦海关在4票申报废料的货物中查获897台新空调、113台除湿机等，中泰来源且以美的品牌为主，涉嫌逃税约4795万卢比。",
        "content_zh": (
            "巴基斯坦媒体2026年7月16日援引海关立案材料报道，卡拉奇海关执法部门对4票申报为压缩机、钢铁和铝制冷凝器废料的货物实施查验，"
            "在废料托盘后发现897台新便携式及窗式空调、113台除湿机和3台二手饮水机，货物主要为美的品牌，来源包括泰国和中国。"
            "海关估值6339万卢比，认定涉嫌少缴关税和税款约4795万卢比，已对进口商、报关代理及其他协助人员登记刑事案件并扣押货物。"
        ),
        "category": "商业瞒报与逃税",
        "authority": "Pakistan Customs Enforcement, Karachi",
        "jurisdiction": "Pakistan",
        "subject": "M/s Shareef Enterprises、报关代理及中泰来源空调等货物",
        "case_type": "commercial goods concealed behind declared scrap",
        "action": "拦截查验、登记刑事案件、扣押货物并追捕涉案人员",
        "basis": "weak_china_nexus",
        "level": "weak",
        "nexus": "The seized appliances had mixed Thailand and China origins; the report does not allocate individual units by origin.",
        "evidence": "Customs found 897 air conditioners and 113 dehumidifiers, mainly Midea branded, concealed behind scrap.",
        "source_name": "ProPakistani, citing Pakistan Customs FIR",
        "source_tier": "authoritative_media",
        "confidence": 89,
    },
]


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def get_tag(db, tag_id: str) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag:
        return tag
    namespace, value = tag_id.split(":", 1)
    tag = Tag(id=tag_id, namespace=namespace, value=value, label=value)
    db.add(tag)
    db.flush()
    return tag


def tags_for(case: dict) -> list[str]:
    level_label = {"strong": "强涉华关联", "weak": "弱涉华关联"}[case["level"]]
    return ["weekly:执法查获", "weekly:贸易合规", "weekly:涉华执法", f"china_relevance:{level_label}"]


def main() -> int:
    db = SessionLocal()
    try:
        if not db.get(Topic, TOPIC_ID):
            raise RuntimeError(f"Topic not found: {TOPIC_ID}")
        source = db.get(SourceConfig, SOURCE_ID)
        if not source:
            raise RuntimeError(f"Source not found: {SOURCE_ID}")

        now = datetime.now(timezone.utc)
        run = db.query(CollectionRun).filter(CollectionRun.batch_id == BATCH_ID).first()
        if not run:
            run = CollectionRun(
                id=f"run-{uuid4().hex[:12]}",
                source_id=SOURCE_ID,
                topic_id=TOPIC_ID,
                status="running",
                batch_id=BATCH_ID,
                keywords_used=[
                    "China customs seizure",
                    "中国 来源 走私 查获",
                    "中国人 海关 查获",
                    "contrabando China aduanas",
                    "contrebande Chine douane",
                    "penyelundupan China bea cukai",
                    "中国産 密輸 税関",
                    "중국산 밀수 세관",
                ],
                started_at=now,
                window_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
                window_end=now,
                metadata_json={
                    "provider": "codex_web_search",
                    "review_mode": "multilingual_verified_china_nexus",
                    "languages": ["zh", "en", "es", "pt", "fr", "id", "ms", "ja", "ko"],
                },
            )
            db.add(run)
            db.flush()

        inserted = 0
        existing = 0
        item_ids: list[str] = []
        for case in CASES:
            item = db.query(CollectedItem).filter(CollectedItem.url == case["url"]).first()
            if item:
                existing += 1
                item_ids.append(item.id)
                continue

            case_tags = tags_for(case)
            label = {"strong": "强涉华关联", "weak": "弱涉华关联"}[case["level"]]
            review = {
                "decision": "approve",
                "confidence": case["confidence"],
                "basis": "已核验发布日期、具体执法行为、涉华关联及来源等级。",
                "inclusion_basis": case["basis"],
                "evidence_quote": case["evidence"],
                "mainland_nexus_evidence": case["nexus"],
                "enforcement_action": case["action"],
                "jurisdiction": case["jurisdiction"],
                "authority": case["authority"],
                "case_type": case["case_type"],
                "subject": case["subject"],
                "source_name": case["source_name"],
                "source_tier": case["source_tier"],
                "source_domain": urlparse(case["url"]).netloc.casefold(),
                "china_relevance_level": case["level"],
                "china_relevance_label": label,
                "reviewer": "codex_multilingual_web_search",
            }
            metadata = {
                "provider": "codex_web_search",
                "import_batch": BATCH_ID,
                "source_name": case["source_name"],
                "source_tier": case["source_tier"],
                "original_language": case["language"],
                "translation_zh": {
                    "title_zh": case["title_zh"],
                    "summary_zh": case["summary_zh"],
                    "content_zh": case["content_zh"],
                    "status": "translated",
                },
                "enforcement_review": review,
                "date_verified": True,
                "date_source": case["url"],
                "tags": case_tags,
            }
            content_hash = hashlib.sha256(f'{case["url"]}\n{case["content"]}'.encode("utf-8")).hexdigest()
            item = CollectedItem(
                id=f'codex-{case["key"]}',
                source_id=SOURCE_ID,
                run_id=run.id,
                topic_id=TOPIC_ID,
                title=case["title"],
                content=case["content"],
                content_hash=content_hash,
                summary=case["summary_zh"],
                url=case["url"],
                language=case["language"],
                category=case["category"],
                entities={
                    "countries": [case["jurisdiction"], "China"],
                    "authorities": [case["authority"]],
                    "subjects": [case["subject"]],
                },
                status="enriched",
                quality_score=case["confidence"] / 100,
                relevance_score=0.96 if case["level"] == "strong" else 0.86,
                published_at=parse_datetime(case["published_at"]),
                collected_at=now,
                updated_at=now,
                raw_metadata=metadata,
                authorization_level="public",
            )
            item.tags = [get_tag(db, tag_id) for tag_id in case_tags]
            db.add(item)
            inserted += 1
            item_ids.append(item.id)

        run.status = "completed"
        run.items_found = len(CASES)
        run.items_new = inserted
        run.items_updated = 0
        run.items_failed = 0
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = int((run.completed_at - (run.started_at or now)).total_seconds() * 1000)
        run.metadata_json = {
            **(run.metadata_json or {}),
            "item_ids": item_ids,
            "inserted": inserted,
            "existing": existing,
        }
        source.items_collected = int(source.items_collected or 0) + inserted
        source.last_sync_at = run.completed_at
        db.commit()
        print(f"run_id={run.id} inserted={inserted} existing={existing} total={len(CASES)}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
