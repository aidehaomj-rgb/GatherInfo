"""Import the verified Codex supplement for the 2026-08-03 enforcement run."""
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
BATCH_ID = "codex-enforcement-supplement-20260803"

CASES = [
    {
        "key": "us-alibaba-illegal-imports-20260701",
        "url": "https://www.justice.gov/opa/pr/alibaba-group-and-aus-merchant-services-agree-pay-600-million-resolve-allegations-they",
        "published_at": "2026-07-01T12:00:00-04:00",
        "language": "en",
        "title": "Alibaba Group and AUS Merchant Services Agree to Pay $600 Million over Illegal Product Imports",
        "content": (
            "The U.S. Department of Justice announced that Alibaba Group and AUS Merchant Services "
            "entered non-prosecution agreements and agreed to pay a combined $600 million. Alibaba "
            "admitted that its platforms failed to prevent about 80,000 sales involving illegal "
            "pharmaceuticals, controlled chemicals and pill presses imported into the United States."
        ),
        "title_zh": "美国司法部就阿里巴巴平台非法商品进口问题达成6亿美元执法和解",
        "summary_zh": "美国司法部与阿里巴巴集团及AUS Merchant Services达成不起诉协议，两家公司合计支付6亿美元，并承诺强化平台合规控制。",
        "content_zh": (
            "美国司法部2026年7月1日通报，阿里巴巴集团及其美国支付服务商AUS Merchant Services与司法部达成不起诉协议。"
            "阿里巴巴承认，2016年至2024年间未能有效阻止商户通过Alibaba.com和AliExpress向美国销售并进口非法药品、"
            "受控化学品和压片机等设备，相关交易约8万笔、商品交易总额超过2亿美元。阿里巴巴同意支付1.25亿美元刑事罚款并没收2亿美元，"
            "AUS同意支付8500万美元刑事罚款并没收1.9亿美元，两家公司合计承担6亿美元，并须持续完善合规机制。"
        ),
        "category": "跨境电商合规执法",
        "authority": "U.S. Department of Justice",
        "jurisdiction": "United States",
        "subject": "Alibaba Group、AUS Merchant Services及平台非法商品进口交易",
        "case_type": "illegal pharmaceutical imports and platform compliance",
        "action": "达成不起诉协议、处以刑事罚款和没收并责令整改",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Alibaba Group is a China-based company, and the enforcement action concerns illegal products imported into the United States through its platforms.",
        "evidence": "Alibaba admitted approximately 80,000 product sales involving illegal imports into the United States.",
        "source_name": "U.S. Department of Justice",
        "confidence": 99,
    },
    {
        "key": "malaysia-drug-seizures-20260702",
        "url": "https://www.customs.gov.my/en/archive/news-medias/news-medias/jkdm-ibu-pejabat-tumpaskan-sindiket-pengedaran-dadah-antarabangsa-melibatkan-rampasan-4-83-tan-dadah-bernilai-rm300-72-juta",
        "published_at": "2026-07-02T09:00:00+08:00",
        "language": "ms",
        "title": "JKDM tumpaskan sindiket pengedaran dadah antarabangsa melibatkan rampasan 4.83 tan dadah bernilai RM300.72 juta",
        "content": (
            "Jabatan Kastam Diraja Malaysia menumpaskan sindiket pengedaran dadah antarabangsa "
            "menerusi lima siri serbuan di Kuala Lumpur dan Lembah Klang. Rampasan 4.83 tan "
            "melibatkan Cannabis Bud, Cocaine, MDMA, Ketamine, Amphetamine, Heroin dan Erimin-5."
        ),
        "title_zh": "马来西亚海关侦破国际贩毒网络并查获4.83吨毒品",
        "summary_zh": "马来西亚皇家海关通过5次行动查获4.83吨各类毒品，估值3.0072亿林吉特，拘留3名外籍人员和2名本国人员。",
        "content_zh": (
            "马来西亚皇家海关2026年7月2日发布消息，总部执法部门、缉毒分支、COBRA队伍和情报部门在吉隆坡及巴生谷地区开展5次行动，"
            "捣毁国际毒品分销网络，共查获4.83吨大麻花、可卡因、MDMA、氯胺酮、安非他明、海洛因和Erimin-5等毒品，"
            "估值3.0072亿林吉特；3名外籍人员和2名马来西亚人员被拘留协助调查。"
        ),
        "category": "毒品查获",
        "authority": "Royal Malaysian Customs Department",
        "jurisdiction": "Malaysia",
        "subject": "国际毒品分销网络及4.83吨毒品",
        "case_type": "international drug trafficking",
        "action": "查获毒品、拘留涉案人员并开展刑事调查",
        "basis": "major_non_china",
        "level": "major_non_china",
        "nexus": "No verified China nexus; included as a major cross-border customs drug case.",
        "evidence": "Five operations seized 4.83 tonnes of drugs valued at RM300.72 million.",
        "source_name": "Royal Malaysian Customs Department",
        "confidence": 98,
    },
    {
        "key": "korea-counterfeit-filters-20260703",
        "url": "https://www.customs.go.kr/kcs/na/ntt/selectNttInfo.do?nttSn=10168643&nttSnUrl=480ab0a63b752e7a601d278344f12d68",
        "published_at": "2026-07-03T09:00:00+09:00",
        "language": "ko",
        "title": "70억원 상당 해외 유명브랜드 짝퉁 공기청정기 필터 등 밀수·유통조직 검거",
        "content": (
            "인천공항세관은 해외 유명브랜드를 도용한 가짜 공기청정기 필터 등 6만 9천점을 "
            "중국에서 불법 수입해 유통한 조직을 검거했다. 총책을 구속 송치하고 중국 체류 "
            "공급책을 지명수배했으며, 일부 필터에서는 사용금지 유해물질이 검출됐다."
        ),
        "title_zh": "韩国海关侦破中国来源假冒空气净化器滤芯走私销售案",
        "summary_zh": "韩国仁川机场海关查处从中国非法进口并销售约6.9万件假冒滤芯的团伙，涉案正品市值约70亿韩元。",
        "content_zh": (
            "韩国关税厅2026年7月3日通报，仁川机场海关侦破一个从中国非法进口并在韩国销售假冒空气净化器滤芯的团伙，"
            "涉案假冒滤芯等约6.9万件，按正品计价约70亿韩元。主犯已被拘捕移送检察机关，位于中国的供应人员被通缉，"
            "另有3名参与网络销售的人员被移送。抽检的10种滤芯中有3种检出韩国禁止使用的有害物质，相关产品已被禁止进口、销售并责令召回。"
        ),
        "category": "知识产权与产品安全执法",
        "authority": "Korea Customs Service, Incheon Airport Customs",
        "jurisdiction": "South Korea",
        "subject": "中国供应人员、韩国进口销售团伙及6.9万件假冒滤芯",
        "case_type": "counterfeit goods smuggling",
        "action": "拘捕移送、通缉供应人员、查扣并召回违规产品",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Korea Customs states that approximately 69,000 counterfeit filters were illegally imported from China.",
        "evidence": "The organization illegally imported and distributed 69,000 counterfeit filters from China.",
        "source_name": "Korea Customs Service",
        "confidence": 99,
    },
    {
        "key": "singapore-gold-carousel-20260708",
        "url": "https://www.police.gov.sg/Media-Hub/News/2026/07/20260708_four_persons_charged_in_multi_national_trade_based_money_laundering_scheme",
        "published_at": "2026-07-08T12:00:00+08:00",
        "language": "en",
        "title": "Four Persons Charged in Multi-National Trade-Based Money Laundering Scheme Involving Gold Smuggling",
        "content": (
            "Singapore Police charged four people in a trade-based money laundering scheme. "
            "A PRC syndicate concealed gold in signal converters, declared them to China Customs "
            "as high-tech products and exported them at inflated prices to Singapore entities. "
            "Mainboards were later sent back to China through Hong Kong for reuse."
        ),
        "title_zh": "新加坡起诉跨国黄金走私及贸易型洗钱网络涉案人员",
        "summary_zh": "新加坡警方起诉4名涉案人员，案件涉及中国境内团伙将黄金藏入信号转换器并虚高申报出口，形成经香港回流的循环贸易链。",
        "content_zh": (
            "新加坡警察部队2026年7月8日通报，4名人员因涉嫌参与黄金走私相关的增值税循环欺诈和贸易型洗钱被起诉。"
            "初步调查显示，中国境内犯罪团伙将黄金藏入信号转换器，以高科技产品名义向中国海关申报并虚高价格出口至3家新加坡企业，"
            "从而骗取出口退税。货物抵达新加坡后被拆解取出黄金出售，主板再经香港企业出口回中国用于下一批组装。"
            "新加坡商业事务局、新加坡海关及中方执法部门共同开展调查。"
        ),
        "category": "黄金走私与贸易型洗钱",
        "authority": "Singapore Police Force and Singapore Customs",
        "jurisdiction": "Singapore",
        "subject": "中国境内犯罪团伙、新加坡注册企业及黄金循环贸易链",
        "case_type": "gold smuggling and trade-based money laundering",
        "action": "起诉涉案人员并追查跨境循环贸易和洗钱链条",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "The scheme was operated with PRC suppliers, false declarations to China Customs and return shipments through Hong Kong.",
        "evidence": "Gold was concealed in signal converters exported from China to Singapore at inflated prices.",
        "source_name": "Singapore Police Force",
        "confidence": 99,
    },
    {
        "key": "japan-hong-kong-gold-20260708",
        "url": "https://www.customs.go.jp/kyotsu/hodo/jikenhodo/2026jiken/jiken2026.htm#gold",
        "published_at": "2026-07-08T12:00:00+09:00",
        "language": "ja",
        "title": "香港来航空貨物内の電気スタンド等に隠匿された板状の金密輸入事犯を告発",
        "content": (
            "大阪税関関西空港税関支署は、香港からの航空貨物の電気スタンドと充電器に "
            "隠匿された板状の金、合計25,184.2グラムの密輸入事犯について、犯則者2名を告発した。"
        ),
        "title_zh": "日本大阪海关查办香港航空货物夹藏25.18公斤黄金案",
        "summary_zh": "日本大阪海关对两名涉案人员提起告发，案件涉及从香港空运、藏于电灯和充电器内的合计25.18公斤板状黄金。",
        "content_zh": (
            "日本海关2026年7月8日发布，大阪海关关西机场支署会同警方调查两起从中国香港特别行政区输入黄金案件。"
            "涉案人员将288块、重12.0114公斤的板状黄金藏入电灯，并将1368块、重13.1728公斤的板状黄金藏入充电器，"
            "企图未经许可进口并逃避消费税及地方消费税，均在海关检查中被发现。两案黄金合计25.1842公斤，"
            "鉴定价值合计约3.6323亿日元，2名涉案人员已被告发至检察机关。"
        ),
        "category": "黄金走私",
        "authority": "Osaka Customs, Kansai Airport Customs Branch",
        "jurisdiction": "Japan",
        "subject": "香港来源航空货物、2名涉案人员及25.18公斤板状黄金",
        "case_type": "gold smuggling and tax evasion",
        "action": "海关查获、联合调查并向检察机关告发",
        "basis": "weak_china_nexus",
        "level": "weak",
        "nexus": "Both shipments originated in the Hong Kong Special Administrative Region of China.",
        "evidence": "Customs found 25,184.2 grams of gold concealed in lamps and chargers from Hong Kong.",
        "source_name": "Japan Customs",
        "confidence": 99,
    },
    {
        "key": "thailand-heroin-transit-20260713",
        "url": "https://enforcement.customs.go.th/cont_strc_simple_with_date.php?current_id=14232d324148505e4e&ini_menu=&lang=th&left_menu=menu_office_news&top_menu=menu_homepage",
        "published_at": "2026-07-13T09:29:45+07:00",
        "language": "th",
        "title": "กรมศุลกากรจับกุมผู้โดยสารชายต่างชาติลักลอบขนเฮโรอีน 17.5 กิโลกรัม",
        "content": (
            "กรมศุลกากรตรวจค้นผู้โดยสารชายสัญชาติแอฟริกาใต้ ซึ่งเดินทางจากกัวลาลัมเปอร์ "
            "ผ่านท่าอากาศยานสุวรรณภูมิไปมาดากัสการ์ และพบเฮโรอีน 17.5 กิโลกรัมซุกซ่อนในถุงกาแฟและชาเขียว"
        ),
        "title_zh": "泰国海关查获南非籍旅客过境走私17.5公斤海洛因案",
        "summary_zh": "泰国海关在素万那普机场查获一名南非籍过境旅客，其行李咖啡袋和绿茶袋内夹藏17.5公斤海洛因。",
        "content_zh": (
            "泰国海关执法部门2026年7月13日发布，海关于7月9日在素万那普机场检查一名南非籍男性旅客行李。"
            "该旅客从马来西亚吉隆坡出发，经泰国前往马达加斯加，执法人员在咖啡袋和绿茶袋内查获17.5公斤海洛因，"
            "在泰国估值超过730万泰铢、在目的地估值约2275万泰铢。案件按未经许可输入第一类毒品等违法行为办理。"
        ),
        "category": "毒品查获",
        "authority": "Thai Customs Enforcement Division",
        "jurisdiction": "Thailand",
        "subject": "南非籍过境旅客及17.5公斤海洛因",
        "case_type": "international heroin smuggling",
        "action": "机场检查、查获毒品并依法追究责任",
        "basis": "major_non_china",
        "level": "major_non_china",
        "nexus": "No verified China nexus; included as a major multi-jurisdiction customs drug case.",
        "evidence": "Thai Customs seized 17.5 kilograms of heroin concealed in coffee and green-tea bags.",
        "source_name": "Thai Customs Department",
        "confidence": 99,
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
    level_label = {
        "strong": "强涉华关联",
        "weak": "弱涉华关联",
        "major_non_china": "重大案件不涉华",
    }[case["level"]]
    return ["weekly:执法查获", "weekly:贸易合规", f"china_relevance:{level_label}"]


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
                keywords_used=["Codex Web Search", "多国海关执法", "涉华执法案件"],
                started_at=now,
                window_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
                window_end=now,
                metadata_json={
                    "provider": "codex_web_search",
                    "review_mode": "verified_official_source_supplement",
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
            label = {
                "strong": "强涉华关联",
                "weak": "弱涉华关联",
                "major_non_china": "重大案件（非涉华）",
            }[case["level"]]
            review = {
                "decision": "approve",
                "confidence": case["confidence"],
                "basis": "已核验官方来源、发布日期、具体执法行为及案件关联证据。",
                "inclusion_basis": case["basis"],
                "evidence_quote": case["evidence"],
                "mainland_nexus_evidence": case["nexus"],
                "enforcement_action": case["action"],
                "jurisdiction": case["jurisdiction"],
                "authority": case["authority"],
                "case_type": case["case_type"],
                "subject": case["subject"],
                "source_name": case["source_name"],
                "source_domain": urlparse(case["url"]).netloc.casefold(),
                "china_relevance_level": case["level"],
                "china_relevance_label": label,
                "reviewer": "codex_web_search",
            }
            metadata = {
                "provider": "codex_web_search",
                "import_batch": BATCH_ID,
                "source_name": case["source_name"],
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
            content_hash = hashlib.sha256(
                f'{case["url"]}\n{case["content"]}'.encode("utf-8")
            ).hexdigest()
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
                relevance_score=0.95 if case["level"] == "strong" else 0.86,
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
