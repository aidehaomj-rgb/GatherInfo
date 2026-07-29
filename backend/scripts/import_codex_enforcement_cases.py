"""Import enforcement cases found by a reviewed Codex web-search batch.

The import is idempotent by canonical URL. It preserves the source-language
synopsis and stores the reviewed Chinese rendition in ``translation_zh`` so
both versions are available in the item detail view.
"""
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
from app.models import (  # noqa: E402
    CollectedItem,
    CollectionRun,
    SourceConfig,
    Tag,
    Topic,
)


TOPIC_ID = "weekly-enforcement-intelligence"
SOURCE_ID = "ai-smart-web-research"
BATCH_ID = "codex-web-search-20260729"


CASES = [
    {
        "key": "thailand-origin-fraud-20260722",
        "url": "https://thailand.prd.go.th/en/content/category/detail/id/2078/iid/524617",
        "published_at": "2026-07-22T00:00:00+07:00",
        "language": "en",
        "title": 'Thailand Cracks Down on Fake "Made in Thailand" Goods Worth Over US$2.97 Million',
        "content": (
            "Thai Customs and the Department of Foreign Trade seized imported goods at "
            "Laem Chabang Port that were falsely labelled as Thai-origin products. The "
            "shipments, imported from China, included 5.37 million TWOMOON cigarettes "
            "and more than 202,000 utility-knife and multi-purpose-tool sets. Their total "
            "value exceeded 100 million baht."
        ),
        "title_zh": "泰国海关查获中国进口货物伪造“泰国制造”案",
        "summary_zh": (
            "泰国海关与对外贸易部门在林查班港联合查获两批伪造泰国产地的中国进口货物，"
            "包括537万支TWOMOON香烟和超过20.2万套工具，货值超过1亿泰铢。"
        ),
        "content_zh": (
            "据泰国政府公共关系部2026年7月22日发布，泰国海关与对外贸易部门在林查班港"
            "开展联合执法，查获两批由中国进口但在包装上标注“泰国制造”的货物。其中一批"
            "为537万支TWOMOON香烟，另一批为超过20.2万套美工刀及多用途工具，涉案货值"
            "超过1亿泰铢。两批货物涉嫌利用海关及自由区便利实施原产地调换。"
        ),
        "category": "原产地欺诈",
        "authority": "Thai Customs Department",
        "jurisdiction": "Thailand",
        "subject": "中国来源香烟、工具及相关进口经营主体",
        "case_type": "origin fraud",
        "action": "查获并调查伪造原产地进口货物",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "The products were imported from China and falsely labelled as Made in Thailand.",
        "evidence": "The total value of the seized goods exceeds 100 million baht.",
        "source_name": "Thailand Government Public Relations Department",
        "confidence": 99,
        "tags": ["weekly:执法查获", "weekly:贸易合规", "china_relevance:强涉华关联"],
    },
    {
        "key": "pakistan-sost-smuggling-20260728",
        "url": "https://mettisglobal.news/Pakistan-Customs-foils-two-smuggling-bids-seizes-goods-worth-Rs158m-62206",
        "published_at": "2026-07-28T16:15:00+05:00",
        "language": "en",
        "title": "Pakistan Customs Foils Two Smuggling Bids, Seizes Goods Worth Rs158 Million",
        "content": (
            "Pakistan Customs reported two intelligence-led operations at the Sost Dry "
            "Port. Officers found 317 concealed used smartphones in a China-bound prime "
            "mover. A separate container held about 3,540 bottles of foreign-origin "
            "liquor, pork meat and other Chinese food items."
        ),
        "title_zh": "巴基斯坦海关在中巴边境查获手机及违规进口货物案",
        "summary_zh": (
            "巴基斯坦海关在索斯特陆港连续查获两起走私案件，包括一辆拟驶往中国车辆内"
            "藏匿的317部二手手机，以及一批外国产酒、猪肉和中国食品。"
        ),
        "content_zh": (
            "据Mettis Global 2026年7月28日报道，巴基斯坦海关根据情报于7月24日至27日"
            "在吉尔吉特-巴尔蒂斯坦索斯特陆港开展两次行动。第一起案件中，执法人员在一辆"
            "拟驶往中国的牵引车车门、仪表台等特制夹层内查获317部二手翻新手机，估值约"
            "7700万卢比；第二起案件中，海关从一只待查集装箱内查获约3540瓶外国产酒、"
            "猪肉及其他中国食品，相关货物涉嫌违规进口。"
        ),
        "category": "边境走私",
        "authority": "Pakistan Customs",
        "jurisdiction": "Pakistan",
        "subject": "藏匿手机车辆及违规进口酒类、食品",
        "case_type": "customs smuggling",
        "action": "查获藏匿手机及违规进口货物",
        "basis": "weak_china_nexus",
        "level": "weak",
        "nexus": "The vehicle was China-bound and the second shipment included Chinese food items.",
        "evidence": "Customs seized 317 concealed mobile phones and 3,540 bottles of liquor.",
        "source_name": "Mettis Global / Pakistan Customs",
        "confidence": 91,
        "tags": ["weekly:执法查获", "weekly:贸易合规", "china_relevance:弱涉华关联"],
    },
    {
        "key": "portugal-ipr-bags-20260710",
        "url": "https://info.portaldasfinancas.gov.pt/pt/destaques/Paginas/Direitos_propriedade_intelectual_10_07.aspx",
        "published_at": "2026-07-10T00:00:00+01:00",
        "language": "pt",
        "title": "Direitos de propriedade intelectual: suspensão do desalfandegamento de mercadorias contrafeitas",
        "content": (
            "No segundo trimestre de 2026, a Alfândega de Alverca suspendeu o "
            "desalfandegamento de uma remessa proveniente da República Popular da China "
            "com 250 malas e sacos, avaliada em 8.747,50 euros. A infração de direitos de "
            "propriedade intelectual foi confirmada e as mercadorias foram destruídas."
        ),
        "title_zh": "葡萄牙海关扣停并销毁中国来源侵权箱包",
        "summary_zh": (
            "葡萄牙阿尔韦卡海关扣停一批来自中国的250件箱包，商业价值8747.50欧元，"
            "经权利人确认侵犯知识产权后依法销毁。"
        ),
        "content_zh": (
            "据葡萄牙税务和海关管理局2026年7月10日发布，阿尔韦卡海关在2026年第二季度"
            "暂停放行一批来自中华人民共和国的货物，内有250件箱包，商业价值8747.50欧元。"
            "海关实施实物查验后，由相关权利人的法律代表确认货物侵犯知识产权，涉案货物"
            "随后依法销毁。"
        ),
        "category": "知识产权执法",
        "authority": "Alverca Customs",
        "jurisdiction": "Portugal",
        "subject": "中国来源侵权箱包",
        "case_type": "intellectual property infringement",
        "action": "暂停放行并销毁侵权货物",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "A remessa era proveniente da República Popular da China.",
        "evidence": "A Alfândega suspendeu o desalfandegamento de 250 malas e sacos.",
        "source_name": "Portuguese Tax and Customs Authority",
        "confidence": 99,
        "tags": ["weekly:执法查获", "weekly:贸易合规", "china_relevance:强涉华关联"],
    },
    {
        "key": "singapore-duty-unpaid-liquor-20260701",
        "url": "https://isomer-user-content.by.gov.sg/174/d56d2779-b3f2-4da9-82d6-5b7ade6ea54d/SingaporeCustoms-MediaRelease-1Jul2026.pdf",
        "published_at": "2026-07-01T00:00:00+08:00",
        "language": "en",
        "title": "Man Arrested and Over 1,100 Bottles of Duty-Unpaid Liquor Seized",
        "content": (
            "Singapore Customs arrested a 40-year-old male Chinese national and seized "
            "1,188 bottles of duty-unpaid liquor during an enforcement operation. The "
            "estimated duty and GST evaded amounted to about S$75,835."
        ),
        "title_zh": "新加坡海关查获中国籍人员经营1188瓶未完税酒",
        "summary_zh": (
            "新加坡海关逮捕一名40岁中国籍男子，从货车和仓储设施中查获1188瓶未完税酒，"
            "涉嫌逃避关税及消费税约7.58万新元。"
        ),
        "content_zh": (
            "据新加坡海关2026年7月1日通报，执法人员根据线报于6月22日在加基武吉一带"
            "开展行动，发现一名40岁中国籍男子将箱装货物从货车运入自助仓储设施。海关在"
            "货车内查获396瓶、在仓库内查获792瓶未完税酒，共计1188瓶，并扣押涉案货车。"
            "案件涉嫌逃避关税和商品及服务税约75835新元，该男子已被起诉。"
        ),
        "category": "税收走私",
        "authority": "Singapore Customs",
        "jurisdiction": "Singapore",
        "subject": "中国籍男子及1188瓶未完税酒",
        "case_type": "duty evasion",
        "action": "逮捕、查获未完税酒并提起诉讼",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Singapore Customs arrested a 40-year-old male Chinese national.",
        "evidence": "Customs seized 1,188 bottles of duty-unpaid liquor.",
        "source_name": "Singapore Customs",
        "confidence": 99,
        "tags": ["weekly:执法查获", "weekly:贸易合规", "china_relevance:强涉华关联"],
    },
    {
        "key": "australia-people-smuggling-20260702",
        "url": "https://www.abf.gov.au/newsroom-subsite/Pages/Second-man-charged-by-North-Queensland-Joint-Organised-Crime-Taskforce-over-alleged-people-smuggling-attempt.aspx",
        "published_at": "2026-07-02T00:00:00+10:00",
        "language": "en",
        "title": "Second Man Charged over Alleged People Smuggling Attempt in North Queensland",
        "content": (
            "The Australian Federal Police and Australian Border Force charged a "
            "30-year-old Chinese national with an aggravated people-smuggling offence "
            "involving at least five persons. A 34-year-old Taiwanese national had "
            "already been charged over the same failed venture."
        ),
        "title_zh": "澳大利亚边境执法部门起诉中国籍人员涉嫌组织偷渡",
        "summary_zh": (
            "澳大利亚联邦警察和边防局起诉一名30岁中国籍男子，指控其参与至少5人的"
            "严重组织偷渡活动；同案一名中国台湾地区人员此前已被起诉。"
        ),
        "content_zh": (
            "据澳大利亚边防局2026年7月2日发布，北昆士兰联合有组织犯罪工作组对一起"
            "未遂偷渡活动展开调查。澳大利亚联邦警察和边防局在韦帕接触并拘留一名30岁"
            "中国籍男子，随后以涉及至少5人的严重组织偷渡罪对其提起指控。同案一名34岁"
            "中国台湾地区人员此前已被捕并受到起诉，案件仍在调查。"
        ),
        "category": "边境执法",
        "authority": "Australian Border Force and Australian Federal Police",
        "jurisdiction": "Australia",
        "subject": "中国籍及中国台湾地区涉案人员",
        "case_type": "people smuggling",
        "action": "逮捕并起诉涉嫌组织偷渡人员",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "The accused is a Chinese national and a Taiwanese national was charged in the same case.",
        "evidence": "He was charged with an aggravated people-smuggling offence involving at least five persons.",
        "source_name": "Australian Border Force",
        "confidence": 98,
        "tags": ["weekly:执法查获", "weekly:边境执法", "china_relevance:强涉华关联"],
    },
    {
        "key": "india-undeclared-cash-20260703",
        "url": "https://www.ndtv.com/india-news/3-chinese-nationals-held-at-delhi-airport-for-carrying-rs-19-lakh-undeclared-cash-11719828",
        "published_at": "2026-07-03T00:18:00+05:30",
        "language": "en",
        "title": "Three Chinese Nationals Held at Delhi Airport with Undeclared Cash",
        "content": (
            "Three Chinese nationals bound for Shanghai were apprehended at Delhi "
            "airport with Rs 18.95 lakh in undeclared Indian currency. They could not "
            "produce supporting documents and were handed over to Customs for further "
            "investigation."
        ),
        "title_zh": "印度机场查获3名中国籍旅客携带未申报现金",
        "summary_zh": (
            "3名拟前往上海的中国籍旅客在印度德里机场被查出携带合计189.5万卢比"
            "未申报现金，因无法提供合法证明被移交海关调查。"
        ),
        "content_zh": (
            "据印度报业托拉斯、NDTV 2026年7月3日报道，印度中央工业安全部队在德里"
            "英迪拉·甘地国际机场检查一名拟飞往上海的旅客时发现60万卢比现金，随后又"
            "查出两名同行中国籍旅客。3人合计携带189.5万卢比，未能提供证明现金合法"
            "来源及携带依据的文件，已被移交印度海关进一步调查并被禁止登机。"
        ),
        "category": "现金申报违规",
        "authority": "Indian Customs and Central Industrial Security Force",
        "jurisdiction": "India",
        "subject": "3名中国籍出境旅客及未申报现金",
        "case_type": "currency declaration violation",
        "action": "拦截旅客并移交海关调查",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Three Chinese nationals were bound for Shanghai.",
        "evidence": "They carried Rs 18.95 lakh in undeclared cash.",
        "source_name": "Press Trust of India / NDTV",
        "confidence": 97,
        "tags": ["weekly:执法查获", "weekly:贸易合规", "china_relevance:强涉华关联"],
    },
    {
        "key": "indonesia-gold-smuggling-20260709",
        "url": "https://m.antaranews.com/amp/berita/5641907/bea-cukai-gagalkan-penyelundupan-emas-29-kilogram-ke-malaysia",
        "published_at": "2026-07-09T11:55:00+07:00",
        "language": "id",
        "title": "Bea Cukai gagalkan penyelundupan emas 2,9 kilogram ke Malaysia",
        "content": (
            "Bea Cukai Banda Aceh menangkap seorang warga negara China berinisial GP "
            "yang diduga hendak menyelundupkan 2,989 kilogram emas batangan melalui "
            "Bandara Sultan Iskandar Muda menuju Malaysia. Nilai emas diperkirakan "
            "mencapai Rp7,254 miliar."
        ),
        "title_zh": "印尼海关查获中国籍人员走私近3公斤黄金",
        "summary_zh": (
            "印尼班达亚齐海关在苏丹伊斯坎达尔·穆达国际机场抓获一名中国籍旅客，"
            "从其随身包内查获2.989公斤未申报金条，目的地为马来西亚。"
        ),
        "content_zh": (
            "据印度尼西亚安塔拉通讯社2026年7月9日报道，班达亚齐海关等部门根据情报"
            "在苏丹伊斯坎达尔·穆达国际机场实施检查，从一名拟乘机前往马来西亚的中国籍"
            "旅客GP随身小包中查获两根金条，重2.989公斤，估值约72.54亿印尼盾。该旅客"
            "未向海关申报，涉嫌逃避出口税，目前已被移交警方调查。"
        ),
        "category": "贵金属走私",
        "authority": "Banda Aceh Customs",
        "jurisdiction": "Indonesia",
        "subject": "中国籍旅客及2.989公斤金条",
        "case_type": "gold smuggling",
        "action": "抓获旅客并查扣未申报黄金",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Pelaku merupakan seorang warga negara China.",
        "evidence": "Petugas menemukan dua batang emas dengan berat 2,989 kilogram.",
        "source_name": "ANTARA / Banda Aceh Customs",
        "confidence": 98,
        "tags": ["weekly:执法查获", "weekly:贸易合规", "china_relevance:强涉华关联"],
    },
    {
        "key": "indonesia-illegal-used-phones-20260710",
        "url": "https://www.humas.polri.go.id/news/detail/2454574-penyidikan-jaringan-impor-ilegal-ponsel-bekas-rampung-tiga-tersangka-sudah-p-21-dan-satu-buron",
        "published_at": "2026-07-10T01:42:00+07:00",
        "language": "id",
        "title": "Penyidikan Jaringan Impor Ilegal Ponsel Bekas Rampung, Tiga Tersangka Sudah P-21",
        "content": (
            "Bareskrim Polri menuntaskan penyidikan jaringan importasi ilegal ponsel "
            "bekas dari China. Dua tersangka merupakan warga negara China. Penyidik "
            "menyita sekitar 50.000 ponsel dan suku cadang serta barang lain dengan "
            "nilai keseluruhan sekitar Rp253,07 miliar."
        ),
        "title_zh": "印尼警方侦结中国来源二手手机非法进口网络案",
        "summary_zh": (
            "印尼国家警察侦结从中国非法进口二手手机及配件案件，两名嫌疑人为中国籍，"
            "查扣约5万部手机及配件等物品，涉案总值约2530.7亿印尼盾。"
        ),
        "content_zh": (
            "据印度尼西亚国家警察公共关系部门2026年7月10日发布，经济特种犯罪调查局"
            "侦结一起从中国向印尼关境非法进口二手手机及电子配件的网络案件。案件涉及"
            "4名嫌疑人，其中DCP和SJ为中国籍，另有1名嫌疑人在逃。警方搜查雅加达北部"
            "和泗水等地4处场所，查扣约5万部手机及液晶屏、电池、主机等配件，以及其他"
            "货物，涉案总值约2530.7亿印尼盾，3名嫌疑人的案卷已移送检察机关。"
        ),
        "category": "非法进口",
        "authority": "Indonesian National Police Criminal Investigation Department",
        "jurisdiction": "Indonesia",
        "subject": "中国来源二手手机、配件及两名中国籍嫌疑人",
        "case_type": "illegal import network",
        "action": "侦结案件、查扣货物并移送起诉",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "Ponsel bekas diimpor dari China dan dua tersangka merupakan warga negara China.",
        "evidence": "Penyidik menyita sekitar 50.000 unit ponsel dan suku cadangnya.",
        "source_name": "Indonesian National Police",
        "confidence": 99,
        "tags": ["weekly:执法查获", "weekly:贸易合规", "china_relevance:强涉华关联"],
    },
    {
        "key": "argentina-chinese-drug-network-20260703",
        "url": "https://www.elancasti.com.ar/edicion-impresa/desbaratan-banda-narcos-chinos-y-secuestran-catinonas-n616363",
        "published_at": "2026-07-03T00:05:00-03:00",
        "language": "es",
        "title": 'Desbaratan banda de narcos chinos y secuestran "catinonas"',
        "content": (
            "La Aduana argentina y la Policía Federal detuvieron a dos sospechosos de "
            "integrar una organización narcocriminal cuyo presunto líder es un ciudadano "
            "chino. La investigación comenzó tras detectar 6,8 kilos de cocaína en el "
            "equipaje de una pasajera con destino a Malasia."
        ),
        "title_zh": "阿根廷海关侦破中国籍人员主导的跨国毒品网络",
        "summary_zh": (
            "阿根廷海关与联邦警察侦破一个涉嫌由中国公民主导的跨国贩毒组织，"
            "案件源于海关查获一名拟前往马来西亚旅客夹藏的6.8公斤可卡因。"
        ),
        "content_zh": (
            "据阿根廷《El Ancasti》2026年7月3日报道，阿根廷海关和联邦警察经过近10个月"
            "调查，抓获两名涉嫌参与跨国贩毒组织的人员，该组织疑由一名中国公民主导。"
            "案件起因是海关于2025年9月在埃塞萨国际机场查获一名拟飞往马来西亚的旅客，"
            "其行李食品包装中藏有6.8公斤可卡因。后续搜查还查获伪麻黄碱和629片合成卡西酮，"
            "案件由经济刑事法院继续办理。"
        ),
        "category": "跨国毒品犯罪",
        "authority": "Argentina Customs and Federal Police",
        "jurisdiction": "Argentina",
        "subject": "涉嫌由中国公民主导的跨国贩毒组织",
        "case_type": "transnational narcotics",
        "action": "联合侦查、逮捕并查扣毒品",
        "basis": "strong_china_nexus",
        "level": "strong",
        "nexus": "El presunto líder de la organización es un ciudadano chino.",
        "evidence": "La Aduana detectó 6,8 kilos de cocaína ocultos en el equipaje.",
        "source_name": "El Ancasti / Argentina Customs",
        "confidence": 94,
        "tags": ["weekly:执法查获", "weekly:毒品案件", "china_relevance:强涉华关联"],
    },
]


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def _tag(db, tag_id: str) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag:
        return tag
    namespace, value = tag_id.split(":", 1)
    tag = Tag(id=tag_id, namespace=namespace, value=value, label=value)
    db.add(tag)
    db.flush()
    return tag


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
                keywords_used=["Codex Web Search", "涉华执法案件", "多语种深度检索"],
                started_at=now,
                window_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
                window_end=now,
                metadata_json={
                    "provider": "codex_web_search",
                    "review_mode": "human_verified_source_evidence",
                },
            )
            db.add(run)
            db.flush()

        inserted = 0
        existing = 0
        inserted_ids: list[str] = []
        for case in CASES:
            item = db.query(CollectedItem).filter(CollectedItem.url == case["url"]).first()
            if item:
                existing += 1
                inserted_ids.append(item.id)
                continue

            content_hash = hashlib.sha256(
                f'{case["url"]}\n{case["content"]}'.encode("utf-8")
            ).hexdigest()
            review = {
                "decision": "approve",
                "confidence": case["confidence"],
                "basis": "已核验发布日期、具体执法行为及案件涉华关联。",
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
                "china_relevance_label": (
                    "强涉华关联" if case["level"] == "strong" else "弱涉华关联"
                ),
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
                "tags": case["tags"],
            }
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
                relevance_score=0.95 if case["level"] == "strong" else 0.82,
                published_at=_parse_datetime(case["published_at"]),
                collected_at=now,
                updated_at=now,
                raw_metadata=metadata,
                authorization_level="public",
            )
            item.tags = [_tag(db, tag_id) for tag_id in case["tags"]]
            db.add(item)
            inserted += 1
            inserted_ids.append(item.id)

        run.status = "completed"
        run.items_found = len(CASES)
        run.items_new = inserted
        run.items_updated = 0
        run.items_failed = 0
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = int((run.completed_at - (run.started_at or now)).total_seconds() * 1000)
        run.metadata_json = {
            **(run.metadata_json or {}),
            "item_ids": inserted_ids,
            "inserted": inserted,
            "existing": existing,
        }
        source.items_collected = int(source.items_collected or 0) + inserted
        source.last_sync_at = run.completed_at
        db.commit()
        print(
            f"run_id={run.id} inserted={inserted} existing={existing} "
            f"total={len(CASES)}"
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
