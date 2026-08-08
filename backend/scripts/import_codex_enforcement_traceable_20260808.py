"""Import traceable China-related enforcement cases verified by Codex web search."""
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
BATCH_ID = "codex-enforcement-traceable-20260808"
WINDOW_START = datetime(2026, 2, 8, tzinfo=timezone.utc)


CASES = [
    {
        "key": "in-kash-big-tex-container-20260409",
        "url": "https://gujaratcustoms.gov.in/juridictional_commissionerate/public/storage/pdfs/hh8BnFlZnBz21Wyh5bj1ppxkdeHBqMd6QVhmIYDD.pdf",
        "published_at": "2026-04-09T12:00:00+05:30",
        "language": "en",
        "title": "Indian Customs order on Kash International's fabric shipment from Big Tex Impex, China",
        "content": (
            "Indian Customs Order-in-Original MCH/ADC/ZDC/19/2026-27 concerns Kash International "
            "Trade Co.'s import from Big Tex Impex Limited, China. Container EITU9296026 entered under "
            "Bill of Entry Z-6816390 dated January 10, 2026 and invoice NS-12. Examination found 1,296 "
            "rolls; laboratory testing identified dyed woven polyester fabric with polyurethane lamination "
            "rather than the declared polyester laminated fabric. Customs reclassified and revalued the "
            "goods and imposed redemption fines and penalties."
        ),
        "title_zh": "印度海关查处Big Tex Impex对Kash International聚酯层压织物申报不实案",
        "summary_zh": "印度海关裁定，中国供应商Big Tex Impex Limited发往Kash International的货柜EITU9296026存在织物品名、归类和价格申报问题。",
        "content_zh": (
            "印度蒙德拉海关2026年4月9日作出原裁定MCH/ADC/ZDC/19/2026-27。进口商为Kash International Trade Co.，"
            "中国供应商为Big Tex Impex Limited。涉案货柜号EITU9296026，报关单号Z-6816390，报关日期为2026年1月10日，"
            "商业发票号NS-12。海关于2月17日查验1296卷货物，实验室检测认定为聚氨酯层压染色聚酯机织物，与申报品名及归类不符。"
            "海关对货物重新归类、核价并作出没收后缴纳赎回金放行及处罚决定。"
        ),
        "category": "纺织品申报与归类执法",
        "authority": "Indian Customs, Mundra Custom House",
        "jurisdiction": "India",
        "subjects": ["Kash International Trade Co.", "Big Tex Impex Limited"],
        "case_type": "customs misdeclaration, classification and valuation",
        "action": "查验、实验室检测、重新归类核价、没收后准予赎回并处罚",
        "procedural_status": "final_administrative_order",
        "evidence": "The official order identifies container EITU9296026, Bill of Entry Z-6816390 and supplier Big Tex Impex Limited, China.",
        "source_name": "印度蒙德拉海关",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": ["EITU9296026"],
            "bill_of_entry_numbers": ["Z-6816390"],
            "bill_of_lading_numbers": [],
            "invoice_numbers": ["NS-12"],
            "mainland_entities": ["Big Tex Impex Limited"],
            "evidence_types": ["container_number", "bill_of_entry", "mainland_supplier"],
        },
    },
    {
        "key": "in-shri-ji-tianjin-jlhy-20260217",
        "url": "https://gujaratcustoms.gov.in/juridictional_commissionerate/public/storage/pdfs/UANk0HiDroUC0cRQqjULISbuCAhENg8zxJ4UljnX.pdf",
        "published_at": "2026-02-17T12:00:00+05:30",
        "language": "en",
        "title": "Indian Customs order on Shri Ji shipment from Tianjin JLHY Import and Export",
        "content": (
            "Indian Customs Order-in-Original MCH/ADC/ZDC/654/2025-26 concerns Shri Ji Import and "
            "Exports Private Limited and supplier Tianjin JLHY Import & Export Co. Ltd. Container "
            "DPWU2049296 was declared under Bill of Entry 3609905 as 1,284 packages of anchor nuts. "
            "Examination found undeclared zinc-coated and black-phosphate drywall screws in addition to "
            "anchor nuts. Customs confiscated the goods subject to redemption fines and imposed penalties."
        ),
        "title_zh": "印度海关查处天津JLHY向Shri Ji出口货柜夹带未申报干壁螺钉案",
        "summary_zh": "印度海关在货柜DPWU2049296中发现除申报锚固螺母外还夹带镀锌及黑色磷化干壁螺钉，中国供应商为Tianjin JLHY。",
        "content_zh": (
            "印度蒙德拉海关2026年2月17日作出原裁定MCH/ADC/ZDC/654/2025-26。进口商为Shri Ji Import and Exports Private Limited，"
            "中国供应商为Tianjin JLHY Import & Export Co. Ltd.。货柜号DPWU2049296，报关单号3609905，申报为1284件、27500千克锚固螺母。"
            "实货查验发现未申报的镀锌干壁螺钉和黑色磷化干壁螺钉，实际总重27588千克。海关对申报货物和未申报货物分别核价、没收，"
            "允许缴纳赎回金后处置，并对进口商实施处罚。"
        ),
        "category": "五金商品瞒报执法",
        "authority": "Indian Customs, Mundra Custom House",
        "jurisdiction": "India",
        "subjects": ["Shri Ji Import and Exports Private Limited", "Tianjin JLHY Import & Export Co. Ltd."],
        "case_type": "undeclared goods concealed in a declared commercial shipment",
        "action": "实货查验、重新核价、没收后准予赎回并处罚",
        "procedural_status": "final_administrative_order",
        "evidence": "The order identifies container DPWU2049296, Bill of Entry 3609905 and Tianjin JLHY Import & Export Co. Ltd.",
        "source_name": "印度蒙德拉海关",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": ["DPWU2049296"],
            "bill_of_entry_numbers": ["3609905"],
            "bill_of_lading_numbers": [],
            "invoice_numbers": [],
            "mainland_entities": ["Tianjin JLHY Import & Export Co. Ltd."],
            "evidence_types": ["container_number", "bill_of_entry", "mainland_supplier"],
        },
    },
    {
        "key": "in-mnr-two-containers-scn-20260313",
        "url": "https://gujaratcustoms.gov.in/juridictional_commissionerate/public/storage/pdfs/Um6cByp1sGVJCX8PKkGYkbX88UoNxIi5k9BVJgyO.pdf",
        "published_at": "2026-03-13T12:00:00+05:30",
        "language": "en",
        "title": "Indian DRI show-cause notice on two China-origin fabric containers imported by M N R Enterprises",
        "content": (
            "A 2026 Indian customs show-cause notice concerns M N R Enterprises and two China-origin "
            "containers, KMTU9295467 and UETU7364726. Bills of Entry 2962594 and 3091762 and Bills of "
            "Lading KMTCNBO8853676 and WSZ25060490 declared cotton woven fabrics. Laboratory tests found "
            "polyester filament yarn fabrics. The notice proposes revaluation, confiscation and penalties; "
            "it is an allegation-stage proceeding rather than a final adjudication."
        ),
        "title_zh": "印度税收情报局就M N R Enterprises两个中国来源织物货柜发出拟处罚通知",
        "summary_zh": "印度执法文件披露货柜KMTU9295467、UETU7364726及对应提单、报关单，实验室检测结果与申报棉织物不符。",
        "content_zh": (
            "印度税收情报局、蒙德拉海关2026年3月13日形成拟处罚通知，涉及M N R Enterprises自中国进口的两个货柜。"
            "货柜号分别为KMTU9295467、UETU7364726，报关单号2962594、3091762，提单号KMTCNBO8853676、WSZ25060490。"
            "货物申报为棉机织物，实验室检测显示聚酯长丝织物占比约94.70%和95.68%。执法机关拟对货物重新核价、没收并处罚。"
            "目前公开文件属于调查及告知程序，不能视为最终违法裁定。"
        ),
        "category": "纺织品申报与归类执法",
        "authority": "Directorate of Revenue Intelligence and Indian Customs, Mundra",
        "jurisdiction": "India",
        "subjects": ["M N R Enterprises", "China-origin fabric suppliers not named in the public notice"],
        "case_type": "customs misdeclaration and laboratory classification dispute",
        "action": "扣押、实验室检测、重新估价并发出拟没收和处罚通知",
        "procedural_status": "show_cause_notice_pending",
        "evidence": "The notice lists containers KMTU9295467 and UETU7364726, two Bills of Entry and two Bills of Lading for imports from China.",
        "source_name": "印度税收情报局及蒙德拉海关",
        "confidence": 98,
        "traceable_evidence": {
            "container_numbers": ["KMTU9295467", "UETU7364726"],
            "bill_of_entry_numbers": ["2962594", "3091762"],
            "bill_of_lading_numbers": ["KMTCNBO8853676", "WSZ25060490"],
            "invoice_numbers": [],
            "mainland_entities": [],
            "evidence_types": ["container_number", "bill_of_entry", "bill_of_lading", "china_origin"],
        },
    },
    {
        "key": "in-supreme-shaoxing-airfly-12-containers-20260415",
        "url": "https://gujaratcustoms.gov.in/juridictional_commissionerate/public/storage/pdfs/IMoywzLFD9vgixx6iNfaIQTJfCWPkYJWARkm5MVW.pdf",
        "published_at": "2026-04-15T12:00:00+05:30",
        "language": "en",
        "title": "Indian Customs order on twelve fabric containers imported by Supreme International",
        "content": (
            "An Indian Customs order covers twelve fabric containers imported by Supreme International. "
            "The order lists each container and Bill of Entry. For container MSMU5383845, Bill of Entry "
            "5916911, it identifies supplier Shaoxing Airfly Import and Export Co. Ltd., China, which said "
            "PU-coated fabric had been shipped in error. Customs found classification and valuation issues, "
            "ordered confiscation subject to redemption and allowed re-export of the identified shipment."
        ),
        "title_zh": "印度海关查处Supreme International进口12个中国来源织物货柜申报不实案",
        "summary_zh": "印度海关裁定涉及12个织物货柜，其中MSMU5383845由中国绍兴Airfly公司发运，官方文件逐一披露货柜号和报关单号。",
        "content_zh": (
            "印度蒙德拉海关2026年4月15日签发裁定，涉及Supreme International进口的12个织物货柜。公开裁定逐一列明货柜号和报关单号。"
            "其中货柜MSMU5383845对应报关单5916911，中国供应商为Shaoxing Airfly Import and Export Co. Ltd.，供应商称聚氨酯涂层织物系误发。"
            "海关查验后认定部分货物存在品名、归类及估价问题，决定没收后准予缴纳赎回金处置，并允许该票已确认误发货物按条件再出口。"
        ),
        "category": "纺织品申报与归类执法",
        "authority": "Indian Customs, Mundra Custom House",
        "jurisdiction": "India",
        "subjects": ["Supreme International", "Shaoxing Airfly Import and Export Co. Ltd."],
        "case_type": "multi-container customs classification and valuation case",
        "action": "逐柜查验、重新归类核价、没收后准予赎回，部分货物准予再出口",
        "procedural_status": "final_administrative_order",
        "evidence": "The order lists twelve container/entry pairs and names Shaoxing Airfly Import and Export Co. Ltd. for container MSMU5383845.",
        "source_name": "印度蒙德拉海关",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": [
                "OCGU8035659", "MSDU7789879", "MSMU8106952", "EITU1352740",
                "TGBU6616724", "MSCU5259351", "EGSU9364524", "CAIU4751697",
                "MSMU6724294", "MSDU6326910", "CXDU2148338", "MSMU5383845",
            ],
            "bill_of_entry_numbers": [
                "5614052", "5743133", "5743135", "5814473", "5917065", "5917409",
                "5917853", "5916909", "5916910", "5916913", "5916914", "5916911",
            ],
            "bill_of_lading_numbers": [],
            "invoice_numbers": [],
            "mainland_entities": ["Shaoxing Airfly Import and Export Co. Ltd."],
            "evidence_types": ["container_number", "bill_of_entry", "mainland_supplier"],
        },
    },
    {
        "key": "us-shandong-fentanyl-entities-20260325",
        "url": "https://www.justice.gov/usao-sdoh/pr/grand-jury-charges-additional-chinese-nationals-pharmaceutical-companies-drug",
        "published_at": "2026-03-25T12:00:00-04:00",
        "language": "en",
        "title": "Grand jury charges Chinese nationals and Shandong chemical companies in drug trafficking case",
        "content": (
            "A U.S. federal grand jury charged six Chinese nationals and two China-based companies, "
            "Shandong Believe Chemical Company Pte Ltd. and Shandong Ranhang Biotechnology Co. Ltd., "
            "in alleged conspiracies involving chemicals used to manufacture or adulterate fentanyl. "
            "Three defendants were also charged with attempting to provide material support to the Gulf "
            "Cartel. These are allegations, and the defendants are presumed innocent unless proven guilty."
        ),
        "title_zh": "美国联邦大陪审团起诉山东两家化工企业及6名中国籍人员涉芬太尼化学品案",
        "summary_zh": "美国司法部披露山东Believe Chemical、山东Ranhang Biotechnology两家企业及6名中国籍人员被起诉，案件仍处指控阶段。",
        "content_zh": (
            "美国司法部2026年3月25日通报，联邦大陪审团起诉6名中国籍人员以及Shandong Believe Chemical Company Pte Ltd.、"
            "Shandong Ranhang Biotechnology Co. Ltd.两家中国境内企业，指控其参与与芬太尼制造或掺混所用化学品有关的毒品和洗钱共谋。"
            "其中3人还被指控企图向墨西哥湾卡特尔提供实质支持。公开材料称中国公安机关曾提供相关情报。案件尚处起诉阶段，"
            "所有被告在法院最终判决前依法推定无罪。"
        ),
        "category": "毒品前体与跨境司法执法",
        "authority": "U.S. Department of Justice",
        "jurisdiction": "United States",
        "subjects": [
            "Shandong Believe Chemical Company Pte Ltd.",
            "Shandong Ranhang Biotechnology Co. Ltd.",
            "Hanson Zhao", "Gao Yanpeng", "Xia Yi", "Zhang Jian", "Wang Zhoalan", "Zhang Chunhai",
        ],
        "case_type": "criminal indictment concerning fentanyl-related chemicals",
        "action": "联邦刑事起诉并追诉相关企业和人员",
        "procedural_status": "criminal_indictment_pending",
        "evidence": "The DOJ release names two Shandong companies and six Chinese nationals as defendants in the indictment.",
        "source_name": "美国司法部",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": [],
            "bill_of_entry_numbers": [],
            "bill_of_lading_numbers": [],
            "invoice_numbers": [],
            "mainland_entities": [
                "Shandong Believe Chemical Company Pte Ltd.",
                "Shandong Ranhang Biotechnology Co. Ltd.",
            ],
            "evidence_types": ["mainland_enterprise", "named_defendants"],
        },
    },
    {
        "key": "us-container-makers-antitrust-20260519",
        "url": "https://www.justice.gov/opa/pr/four-worlds-largest-container-manufacturing-companies-and-seven-their-executives-indicted",
        "published_at": "2026-05-19T12:00:00-04:00",
        "language": "en",
        "title": "Four container manufacturers and seven executives indicted in U.S. antitrust case",
        "content": (
            "The U.S. Department of Justice indicted four major container manufacturers and seven "
            "executives for an alleged conspiracy to restrict output and fix prices for standard dry "
            "shipping containers from November 2019 through January 2024. Mainland defendants include "
            "China International Marine Containers (Group) Co. Ltd., Shanghai Universal Logistics "
            "Equipment Co. Ltd. and CXIC Group Containers Co. Ltd. The charges are allegations."
        ),
        "title_zh": "美国司法部起诉中集集团、上海寰宇物流装备、新华昌集团等涉嫌集装箱价格垄断",
        "summary_zh": "美国司法部对4家集装箱制造商和7名高管提起反垄断刑事诉讼，其中3家为中国大陆企业，案件仍处起诉阶段。",
        "content_zh": (
            "美国司法部2026年5月19日通报，4家大型集装箱制造企业及7名高管被起诉，涉嫌在2019年11月至2024年1月期间限制标准干货集装箱产量并操纵价格。"
            "被点名的中国大陆企业包括中国国际海运集装箱（集团）股份有限公司、上海寰宇物流装备有限公司和新华昌集团有限公司，另有香港胜狮货柜企业。"
            "司法部称相关时期集装箱价格大幅上涨、企业利润显著增加。案件目前属于刑事起诉，尚未经法院最终裁判。"
        ),
        "category": "国际贸易竞争执法",
        "authority": "U.S. Department of Justice Antitrust Division",
        "jurisdiction": "United States",
        "subjects": [
            "中国国际海运集装箱（集团）股份有限公司",
            "上海寰宇物流装备有限公司",
            "新华昌集团有限公司",
            "Singamas Container Holdings Ltd.",
        ],
        "case_type": "criminal antitrust indictment",
        "action": "反垄断刑事起诉并开展跨境追诉",
        "procedural_status": "criminal_indictment_pending",
        "evidence": "The official indictment announcement names three mainland Chinese container manufacturers and their executives.",
        "source_name": "美国司法部反垄断局",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": [],
            "bill_of_entry_numbers": [],
            "bill_of_lading_numbers": [],
            "invoice_numbers": [],
            "mainland_entities": [
                "中国国际海运集装箱（集团）股份有限公司",
                "上海寰宇物流装备有限公司",
                "新华昌集团有限公司",
            ],
            "evidence_types": ["mainland_enterprise", "named_defendants"],
        },
    },
    {
        "key": "us-bis-coastal-pva-smic-20260414",
        "url": "https://www.bis.gov/press-release/bis-reaches-administrative-enforcement-settlement-coastal-pva-technology-inc.",
        "evidence_url": "https://www.bis.gov/media/documents/coastal-pva-technology-inc-4-13-2026-rev.pdf",
        "published_at": "2026-04-14T12:00:00-04:00",
        "language": "en",
        "title": "BIS reaches enforcement settlement with Coastal PVA over exports to SMIC entities",
        "content": (
            "The U.S. Bureau of Industry and Security settled 18 alleged EAR violations by Coastal PVA "
            "Technology Inc. involving PVA brushes used in semiconductor manufacturing. From May 2021 to "
            "May 2024, products valued at approximately USD400,088 were shipped without required licenses "
            "to Semiconductor Manufacturing International (Beijing) Corporation and Semiconductor "
            "Manufacturing North China (Beijing) Corporation, directly or through two China distributors."
        ),
        "title_zh": "美国BIS处罚Coastal PVA向中芯国际北京实体无证出口半导体制造用刷具案",
        "summary_zh": "美国BIS认定Coastal PVA在18次交易中向中芯国际北京、北方集成电路制造实体直接或经中国经销商无证出口PVA刷具。",
        "content_zh": (
            "美国商务部工业与安全局2026年4月14日公布与Coastal PVA Technology Inc.达成的行政执法和解。"
            "案件涉及2021年5月至2024年5月间18次出口，产品为半导体制造使用的PVA刷具，总值约40.0088万美元。"
            "收货或最终使用实体为Semiconductor Manufacturing International (Beijing) Corporation和"
            "Semiconductor Manufacturing North China (Beijing) Corporation，部分货物直接发运，部分经两家未公开名称的中国经销商转运。"
            "BIS认定相关交易未取得所需出口许可证，并据此作出行政处罚。"
        ),
        "category": "出口管制执法",
        "authority": "U.S. Bureau of Industry and Security",
        "jurisdiction": "United States",
        "subjects": [
            "Coastal PVA Technology Inc.",
            "Semiconductor Manufacturing International (Beijing) Corporation",
            "Semiconductor Manufacturing North China (Beijing) Corporation",
        ],
        "case_type": "EAR administrative enforcement settlement",
        "action": "行政调查、认定18项违规并达成执法和解",
        "procedural_status": "final_administrative_settlement",
        "evidence": "The BIS order names two Beijing SMIC entities and states that 18 unlicensed shipments were made directly or through China distributors.",
        "source_name": "美国商务部工业与安全局",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": [],
            "bill_of_entry_numbers": [],
            "bill_of_lading_numbers": [],
            "invoice_numbers": [],
            "mainland_entities": [
                "Semiconductor Manufacturing International (Beijing) Corporation",
                "Semiconductor Manufacturing North China (Beijing) Corporation",
            ],
            "evidence_types": ["mainland_enterprise", "named_recipient", "documented_transaction_route"],
        },
    },
    {
        "key": "us-bis-applied-materials-smic-20260212",
        "url": "https://www.bis.gov/press-release/applied-materials-pay-252-million-penalty-bis-illegally-exporting-semiconductor-manufacturing-equipment",
        "published_at": "2026-02-12T12:00:00-05:00",
        "language": "en",
        "title": "Applied Materials pays USD252 million BIS penalty over semiconductor equipment exports to SMIC",
        "content": (
            "Applied Materials agreed to pay approximately USD252 million to settle BIS allegations covering "
            "54 unauthorized reexports and two attempted reexports of ion implanters valued at about USD126 "
            "million. Equipment was routed from Gloucester, Massachusetts to South Korea for assembly and "
            "then to SMIC and multiple mainland subsidiaries in Beijing, Tianjin, Shanghai, Shenzhen and South China."
        ),
        "title_zh": "美国BIS处罚应用材料经韩国向中芯国际多家大陆实体无证转运离子注入机案",
        "summary_zh": "应用材料因54次无证再出口及2次未遂交易向BIS支付约2.52亿美元，设备经韩国组装后流向中芯国际多家中国大陆实体。",
        "content_zh": (
            "美国商务部工业与安全局2026年2月12日宣布，Applied Materials就54次未经许可再出口和2次未遂再出口支付约2.52亿美元罚款。"
            "涉案货物为受EAR管辖的离子注入机，货值约1.26亿美元，交易路径为美国马萨诸塞州格洛斯特发往韩国组装，再转运中国大陆。"
            "公开执法文件点名的中芯国际关联实体分布于北京、天津、上海、深圳及华南，包括SMIC Beijing、SMIC North、SMIC Tianjin、"
            "SMIC Shanghai、SMIC Shenzhen和Semiconductor Manufacturing South China Corporation。"
        ),
        "category": "出口管制执法",
        "authority": "U.S. Bureau of Industry and Security",
        "jurisdiction": "United States",
        "subjects": [
            "Applied Materials Inc.", "Applied Materials Korea",
            "SMIC Beijing", "SMIC North", "SMIC Tianjin", "SMIC Shanghai", "SMIC Shenzhen",
            "Semiconductor Manufacturing South China Corporation",
        ],
        "case_type": "EAR administrative enforcement settlement",
        "action": "行政调查、和解并支付约2.52亿美元罚款",
        "procedural_status": "final_administrative_settlement",
        "evidence": "BIS identifies 56 transactions, a U.S.-Korea-China route and six mainland SMIC recipient entities.",
        "source_name": "美国商务部工业与安全局",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": [],
            "bill_of_entry_numbers": [],
            "bill_of_lading_numbers": [],
            "invoice_numbers": [],
            "mainland_entities": [
                "Semiconductor Manufacturing International (Beijing) Corporation",
                "Semiconductor Manufacturing North China (Beijing) Corporation",
                "Semiconductor Manufacturing International (Tianjin) Corporation",
                "Semiconductor Manufacturing International (Shanghai) Corporation",
                "Semiconductor Manufacturing International (Shenzhen) Corporation",
                "Semiconductor Manufacturing South China Corporation",
            ],
            "evidence_types": ["mainland_enterprise", "named_recipient", "documented_transaction_route"],
        },
    },
    {
        "key": "us-bis-teledyne-flir-shanghai-20260226",
        "url": "https://www.bis.gov/press-release/bis-reaches-administrative-enforcement-settlement-teledyne-flir-llc-its-affiliates-flir-optoelectronic",
        "evidence_url": "https://www.bis.gov/media/2593",
        "published_at": "2026-02-26T12:00:00-05:00",
        "language": "en",
        "title": "BIS settles with Teledyne FLIR and Shanghai affiliate over thermal imaging export violations",
        "content": (
            "BIS reached a USD1 million settlement with Teledyne FLIR, FLIR Commercial Systems and FLIR "
            "Optoelectronic Technology (Shanghai) Co. Ltd. The matter included unauthorized exports of "
            "thermal imaging cameras, cores and kits from Sweden to China, evasion involving a collaboration "
            "with an unnamed Chinese drone manufacturer, recordkeeping violations by the Shanghai affiliate, "
            "and shipments to an Entity List address in Hong Kong."
        ),
        "title_zh": "美国BIS处罚Teledyne FLIR及其上海子公司热成像设备出口违规案",
        "summary_zh": "BIS与Teledyne FLIR等达成100万美元和解，案件包括向中国出口热成像设备、上海子公司记录保存违规及香港实体清单地址交易。",
        "content_zh": (
            "美国商务部工业与安全局2026年2月26日宣布，与Teledyne FLIR LLC、FLIR Commercial Systems Inc.及"
            "FLIR Optoelectronic Technology (Shanghai) Co. Ltd.达成100万美元行政执法和解。案件共涉及19项违规，"
            "包括2017至2018年从瑞典向中国无证出口热成像相机、核心和套件；围绕与一家未公开名称的中国无人机制造商合作规避限制；"
            "上海关联公司未按要求保存记录；以及向香港实体清单地址发运货物。官方文件未公开中国无人机制造商名称，不作进一步推定。"
        ),
        "category": "出口管制执法",
        "authority": "U.S. Bureau of Industry and Security",
        "jurisdiction": "United States",
        "subjects": [
            "Teledyne FLIR LLC", "FLIR Commercial Systems Inc.",
            "FLIR Optoelectronic Technology (Shanghai) Co. Ltd.",
        ],
        "case_type": "EAR administrative enforcement settlement",
        "action": "行政调查、认定19项违规并达成100万美元和解",
        "procedural_status": "final_administrative_settlement",
        "evidence": "The BIS settlement names FLIR Optoelectronic Technology (Shanghai) Co. Ltd. and documents the China shipment and recordkeeping conduct.",
        "source_name": "美国商务部工业与安全局",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": [],
            "bill_of_entry_numbers": [],
            "bill_of_lading_numbers": [],
            "invoice_numbers": [],
            "mainland_entities": ["FLIR Optoelectronic Technology (Shanghai) Co. Ltd."],
            "evidence_types": ["mainland_enterprise", "named_affiliate", "documented_transaction_route"],
        },
    },
    {
        "key": "us-bis-bosch-huawei-20260617",
        "url": "https://www.bis.gov/press-release/robert-bosch-gmbh-bosch-pay-36-million-penalty-bis-violations-pertaining-shipments-huawei",
        "published_at": "2026-06-17T12:00:00-04:00",
        "language": "en",
        "title": "Bosch pays USD36 million BIS penalty over shipments to Huawei",
        "content": (
            "Robert Bosch GmbH agreed to pay USD36,184,680 to settle BIS allegations involving shipments "
            "to Huawei Technologies Co. Ltd. and affiliates. From 2020 through 2024, Bosch exported MEMS "
            "sensors and automotive software worth approximately USD72.37 million without required licenses. "
            "The settlement identifies Huawei and its listed affiliates as mainland China recipients."
        ),
        "title_zh": "美国BIS处罚博世向华为及关联企业无证出口MEMS传感器和汽车软件案",
        "summary_zh": "博世因2020至2024年向华为及关联企业无证出口约7237万美元MEMS传感器和汽车软件，支付约3618万美元罚款。",
        "content_zh": (
            "美国商务部工业与安全局2026年6月17日宣布，Robert Bosch GmbH同意支付3618.468万美元罚款，解决涉及向华为技术有限公司及其关联实体发运货物的行政执法事项。"
            "公开文件显示，2020至2024年间，博世在未取得所需许可证的情况下出口微机电系统传感器和汽车软件，交易总值约7236.9361万美元。"
            "案件以华为及其实体清单关联企业为中国大陆收货和最终用户线索，已通过行政和解结案。"
        ),
        "category": "出口管制执法",
        "authority": "U.S. Bureau of Industry and Security",
        "jurisdiction": "United States",
        "subjects": ["Robert Bosch GmbH", "华为技术有限公司及实体清单关联企业"],
        "case_type": "EAR administrative enforcement settlement",
        "action": "行政调查、和解并支付约3618万美元罚款",
        "procedural_status": "final_administrative_settlement",
        "evidence": "The BIS release identifies Huawei Technologies Co. Ltd. and affiliates as recipients of approximately USD72.37 million in shipments.",
        "source_name": "美国商务部工业与安全局",
        "confidence": 99,
        "traceable_evidence": {
            "container_numbers": [],
            "bill_of_entry_numbers": [],
            "bill_of_lading_numbers": [],
            "invoice_numbers": [],
            "mainland_entities": ["华为技术有限公司及实体清单关联企业"],
            "evidence_types": ["mainland_enterprise", "named_recipient", "documented_transaction_value"],
        },
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
                    "site:customs.gov.cn OR site:gov.in China container customs order 2026",
                    "site:justice.gov Chinese company indictment export import 2026",
                    "site:bis.gov enforcement China company shipment 2026",
                    "container number Bill of Lading China customs seizure 2026",
                ],
                started_at=now,
                window_start=WINDOW_START,
                window_end=now,
                metadata_json={
                    "provider": "codex_deep_web_search",
                    "review_mode": "official_source_traceable_evidence",
                    "hard_evidence_requirement": "specific_container_or_mainland_entity",
                    "languages": ["zh", "en"],
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

            tag_ids = [
                "weekly:执法查获",
                "weekly:贸易合规",
                "weekly:涉华执法",
                "china_relevance:强涉华关联",
                "evidence:可追溯单证或企业",
            ]
            traceable = case["traceable_evidence"]
            review = {
                "decision": "approve",
                "confidence": case["confidence"],
                "basis": "已核验官方发布日期、执法行为、案件程序状态及可追溯涉华证据。",
                "inclusion_basis": "specific_container_or_mainland_entity",
                "evidence_quote": case["evidence"],
                "enforcement_action": case["action"],
                "procedural_status": case["procedural_status"],
                "jurisdiction": case["jurisdiction"],
                "authority": case["authority"],
                "case_type": case["case_type"],
                "subjects": case["subjects"],
                "source_name": case["source_name"],
                "source_tier": "official",
                "source_domain": urlparse(case["url"]).netloc.casefold(),
                "china_relevance_level": "strong",
                "china_relevance_label": "强涉华关联",
                "reviewer": "codex_deep_web_search",
            }
            metadata = {
                "provider": "codex_deep_web_search",
                "import_batch": BATCH_ID,
                "source_name": case["source_name"],
                "source_tier": "official",
                "original_language": case["language"],
                "translation_zh": {
                    "title_zh": case["title_zh"],
                    "summary_zh": case["summary_zh"],
                    "content_zh": case["content_zh"],
                    "status": "translated",
                },
                "enforcement_review": review,
                "traceable_evidence": traceable,
                "evidence_url": case.get("evidence_url", case["url"]),
                "date_verified": True,
                "date_source": case["url"],
                "publication_basis": "official_order_notice_or_press_release",
                "tags": tag_ids,
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
                    "subjects": case["subjects"],
                    "mainland_entities": traceable["mainland_entities"],
                    "container_numbers": traceable["container_numbers"],
                },
                status="enriched",
                quality_score=case["confidence"] / 100,
                relevance_score=0.98,
                published_at=parse_datetime(case["published_at"]),
                collected_at=now,
                updated_at=now,
                raw_metadata=metadata,
                authorization_level="public",
            )
            item.tags = [get_tag(db, tag_id) for tag_id in tag_ids]
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
            "container_evidence_cases": sum(bool(case["traceable_evidence"]["container_numbers"]) for case in CASES),
            "mainland_entity_cases": sum(bool(case["traceable_evidence"]["mainland_entities"]) for case in CASES),
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
