"""Import the verified Ultralife report into the supply-chain module."""
from __future__ import annotations

import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainCase,
    SupplyChainEntity,
    SupplyChainEvidence,
    SupplyChainOpenSourceEvidence,
    SupplyChainReport,
    SupplyChainShipment,
)


DOCX_PATH = Path(
    r"D:\codex\供应链穿透\美军电池供应商Ultralife向中国企业采购锂电池_开源核验增补报告.docx"
)
SOURCE_REF = str(DOCX_PATH)
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def upsert(db, model, row_id: str, **values):
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def evidence(
    db,
    row_id: str,
    case_id: str,
    shipment_id: str,
    score: int,
    reasoning: str,
    limitations: list[str],
    *,
    grade: str = "B",
    relation_type: str = "processed_supply",
    status: str = "approved",
    reportable: bool = True,
    verified_facts_extra: dict | None = None,
):
    verified_facts = {
        "china_origin": True,
        "same_or_related_importer": True,
        "contract_supplier_verified": True,
        "shipment_to_supplier_verified": True,
        "final_program_use_verified": False,
        "source_document": SOURCE_REF,
    }
    verified_facts.update(verified_facts_extra or {})
    return upsert(
        db,
        SupplyChainEvidence,
        row_id,
        case_id=case_id,
        shipment_id=shipment_id,
        relation_type=relation_type,
        evidence_grade=grade,
        score=score,
        status=status,
        reasoning=reasoning,
        verified_facts=verified_facts,
        model_review={
            "method": "open_source_verified_report_import",
            "grade": grade,
            "status": status,
            "reportable": reportable,
            "limitations": limitations,
        },
        is_reportable=reportable,
    )


def main():
    if not DOCX_PATH.exists():
        raise FileNotFoundError(DOCX_PATH)
    content = docx_text(DOCX_PATH)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        upsert(
            db,
            SupplyChainEntity,
            "ent-ultralife",
            name="Ultralife Corporation",
            name_zh="奥特莱夫公司",
            country="United States",
            entity_type="defense_supplier",
            aliases=["Ultralife", "NASDAQ: ULBI"],
            parent_id=None,
            defense_roles=[
                "MK 68水雷系统电池唯一开发商和原始设备制造商",
                "BA-5390军用一次电池供应商",
                "CWB贴合式可穿戴电池承包商",
            ],
            source_url="https://www.ultralifecorp.com/",
            notes=(
                f"依据开源核验增补报告录入。U9VL-J-P对应NSN 6135-01-554-4281，"
                f"已进入美国国防物资编码和采购体系。原始文档：{SOURCE_REF}"
            ),
        )
        db.flush()
        upsert(
            db,
            SupplyChainEntity,
            "ent-able-new-energy",
            name="ABLE New Energy Co., Ltd.",
            name_zh="深圳市艾博尔新能源有限公司",
            country="China",
            entity_type="subsidiary",
            aliases=["Ultralife China", "ABLE"],
            parent_id="ent-ultralife",
            defense_roles=["Ultralife在华全资制造节点", "一次锂电池及锂离子电池生产"],
            source_url=None,
            notes=(
                "Ultralife于2006年收购，经香港控股公司100%控制。ABLE供应的CR123A相关部件"
                "与Ultralife军用一次电池产品存在技术和制造链关联，但尚无批次级军用合同证据。"
            ),
        )
        upsert(
            db,
            SupplyChainEntity,
            "ent-shandong-goldencell",
            name="Shandong Goldencell Power Technology Co., Ltd.",
            name_zh="山东精工电源科技有限公司",
            country="China",
            entity_type="china_exporter",
            aliases=["Shandong Goldencell"],
            parent_id=None,
            defense_roles=["Ultralife锂离子电池供应节点"],
            source_url=None,
            notes="企业身份依据提单发货人名称、山东枣庄地址和企业官网核验。",
        )
        upsert(
            db,
            SupplyChainEntity,
            "ent-tianjin-lishen",
            name="Tianjin Lishen Battery Joint-Stock Co., Ltd.",
            name_zh="天津力神电池股份有限公司",
            country="China",
            entity_type="china_exporter",
            aliases=["Tianjin Lishen", "Lishen Battery"],
            parent_id=None,
            defense_roles=["Ultralife锂离子电芯供应节点"],
            source_url=None,
            notes="企业身份依据提单英文法定名称和企业官网核验。",
        )
        db.flush()

        upsert(
            db,
            SupplyChainCase,
            "case-ultralife-mk68",
            country="United States",
            title="美国海军MK 68水雷系统BA-5390A/U锂电池独家采购",
            procurement_agency="美国海军海上系统司令部",
            procurement_reference="N61331-26-Q-KS18",
            procurement_date=dt("2026-01-01"),
            supplier_entity_id="ent-ultralife",
            product="2000块BA-5390A/U 13Ah锂电池，零件号UB0048，MIL-PRF-32271",
            target_program="MK 68（全型号）水雷系统研发试验、环境鉴定、安全测试及初始能力生产",
            contract_value=None,
            currency="USD",
            source_url="https://sam.gov/workspace/contract/opp/8fd9aa3ca51e42179ba14b191056a785/view",
            source_excerpt="公告将Ultralife列为该型电池唯一开发商和原始设备制造商。",
            status="monitoring",
        )
        upsert(
            db,
            SupplyChainCase,
            "case-ultralife-ba5390-dla",
            country="United States",
            title="美国国防后勤局BA-5390军用一次电池订单",
            procurement_agency="美国国防后勤局",
            procurement_reference="BA-5390 DLA order (2025-09)",
            procurement_date=dt("2025-09-01"),
            supplier_entity_id="ent-ultralife",
            product="BA-5390非充电式锂二氧化锰军用电池",
            target_program="美国国防后勤保障，多数产品于2026年交付",
            contract_value=5200000,
            currency="USD",
            source_url="https://investor.ultralifecorporation.com/node/17071/pdf",
            source_excerpt="公开报道显示订单金额约520万美元，主要安排在2026年交付。",
            status="monitoring",
        )
        upsert(
            db,
            SupplyChainCase,
            "case-ultralife-cwb",
            country="United States",
            title="Ultralife贴合式可穿戴电池（CWB）美军合同",
            procurement_agency="美国国防部",
            procurement_reference="W91CRB21D0016",
            procurement_date=dt("2021-05-01"),
            supplier_entity_id="ent-ultralife",
            product="Conformal Wearable Battery，MIL-PRF-32383/4A",
            target_program="Nett Warrior单兵态势感知系统，合同履约期至2030年",
            contract_value=518000000,
            currency="USD",
            source_url="https://investor.ultralifecorporation.com/news-releases/news-release-details/ultralife-corporation-awarded-idiq-contract-under-us-armys-125b",
            source_excerpt=(
                "多承包商项目总上限12.5亿美元；Ultralife三年基础合同上限1.68亿美元，"
                "六个一年期选项合计最高追加3.5亿美元，公司合同潜在上限5.18亿美元。"
            ),
            status="monitoring",
        )
        db.flush()

        upsert(
            db,
            SupplyChainShipment,
            "shp-able-ultralife-202603-06",
            exporter_name="ABLE New Energy Co., Ltd.",
            exporter_country="China",
            importer_entity_id="ent-ultralife",
            importer_name="Ultralife Corporation",
            product="锂离子电池及锂金属一次电池",
            hs_code=None,
            shipment_date=dt("2026-06-19"),
            weight_kg=19612,
            quantity=5,
            quantity_unit="发运事件",
            origin_country="China",
            destination_country="United States",
            bill_no=None,
            source_name="ImportGenius公开贸易页面及核验报告",
            source_url=None,
            raw_record={
                "period": "2026-03-12/2026-06-19",
                "breakdown": "4票锂离子电池、1票锂金属电池",
                "known_shipment": {"date": "2026-03-18", "weight_kg": 2738},
                "source_document": SOURCE_REF,
            },
        )
        upsert(
            db,
            SupplyChainShipment,
            "shp-goldencell-ultralife-202606-07",
            exporter_name="Shandong Goldencell Power Technology Co., Ltd.",
            exporter_country="China",
            importer_entity_id="ent-ultralife",
            importer_name="Ultralife Corporation",
            product="锂离子电池",
            hs_code=None,
            shipment_date=dt("2026-07-06"),
            weight_kg=7454,
            quantity=2,
            quantity_unit="发运事件",
            origin_country="China",
            destination_country="United States",
            bill_no=None,
            source_name="ImportGenius公开贸易页面及核验报告",
            source_url=None,
            raw_record={
                "period": "2026-06/2026-07",
                "note": "第二批规模接近第一批两倍",
                "source_document": SOURCE_REF,
            },
        )
        upsert(
            db,
            SupplyChainShipment,
            "shp-lishen-ultralife-202603-05",
            exporter_name="Tianjin Lishen Battery Joint-Stock Co., Ltd.",
            exporter_country="China",
            importer_entity_id="ent-ultralife",
            importer_name="Ultralife Corporation",
            product="锂离子电芯",
            hs_code=None,
            shipment_date=dt("2026-05-10"),
            weight_kg=5055,
            quantity=3,
            quantity_unit="发运事件",
            origin_country="China",
            destination_country="United States",
            bill_no=None,
            source_name="ImportGenius公开贸易页面及核验报告",
            source_url=None,
            raw_record={
                "dates": ["2026-03-04", "2026-03-28", "2026-05-10"],
                "reported_total_kg": 5055,
                "alternative_total_kg": 5207,
                "difference_note": "公开贸易页面另列一条2026-03-04、152公斤记录；本条保留原报告口径。",
                "source_document": SOURCE_REF,
            },
        )
        db.flush()

        common_limitations = [
            "公开提单不能单独证明具体货票最终用于某一军工项目或型号",
            "需以订单、生产记录或可追溯批次资料进一步核实最终用途",
        ]
        evidence(
            db, "evd-mk68-able", "case-ultralife-mk68",
            "shp-able-ultralife-202603-06", 78,
            "Ultralife为MK 68电池唯一开发商，ABLE为其在华全资制造节点；中国原产一次锂电池在项目备料窗口到港，构成较强供应链关联。",
            common_limitations,
            verified_facts_extra={
                "mk68_contract_verified": True,
                "ba5390a_product_verified": True,
                "same_battery_category": True,
            },
        )
        evidence(
            db, "evd-ba5390-able", "case-ultralife-ba5390-dla",
            "shp-able-ultralife-202603-06", 82,
            "ABLE一次锂电池制造能力、到港品类和时间均与BA-5390订单2026年生产交付周期高度重合。",
            common_limitations,
            verified_facts_extra={
                "dla_order_verified": True,
                "u9vljp_nsn": "6135-01-554-4281",
                "u9vljp_in_defense_procurement_system": True,
                "cr123a_miles_use_verified": True,
            },
        )
        for suffix, shipment_id, score, supplier in [
            ("able", "shp-able-ultralife-202603-06", 78, "ABLE"),
            ("goldencell", "shp-goldencell-ultralife-202606-07", 74, "山东精工"),
            ("lishen", "shp-lishen-ultralife-202603-05", 76, "天津力神"),
        ]:
            evidence(
                db, f"evd-cwb-{suffix}", "case-ultralife-cwb", shipment_id, score - 18,
                f"{supplier}向Ultralife供应锂电池或电芯，能够确认其进入Ultralife总体供应链；"
                "现有型号、容量和时间证据不足以证明该批货物用于CWB，仅作为待核线索。",
                [
                    *common_limitations,
                    "CWB公开资料未披露与18NC、26FC、600155、LP653450SA、INR21700-45E等电芯的对应关系",
                    "不能仅凭容量、形状或到港时间认定货物用于CWB",
                ],
                grade="C",
                relation_type="possible_supply",
                status="needs_review",
                reportable=True,
                verified_facts_extra={
                    "cwb_contract_verified": True,
                    "cwb_specific_cell_match_verified": False,
                    "shipment_enters_ultralife_general_supply_chain": True,
                },
            )
        db.flush()

        open_source_rows = [
            {
                "id": "ose-ultralife-u9vljp",
                "case_id": "case-ultralife-ba5390-dla",
                "title": "Ultralife U9VL-J-P官方规格书与国防物资编码",
                "source_type": "manufacturer_datasheet",
                "source_publisher": "Ultralife Corporation",
                "source_url": "https://www.ulbi.com/Go/5-336-U9VLJP%2BTechnical%2BDatasheet.aspx",
                "source_excerpt": "U9VL-J-P官方规格书对应NSN 6135-01-554-4281。",
                "verified_facts": {
                    "product": "U9VL-J-P",
                    "nsn": "6135-01-554-4281",
                    "defense_catalogue_link_verified": True,
                    "specific_china_shipment_to_us_military_verified": False,
                },
                "evidence_grade": "B",
                "status": "verified",
                "limitations": ["同一NSN可能由多个合格来源供货", "不能证明特定中国批次直接转供美军"],
            },
            {
                "id": "ose-federal-register-nsn",
                "case_id": "case-ultralife-ba5390-dla",
                "title": "美国联邦公报确认NSN 6135-01-554-4281纳入国防采购需求",
                "source_type": "official_gazette",
                "source_publisher": "U.S. Federal Register",
                "source_url": "https://www.govinfo.gov/content/pkg/FR-2021-12-23/pdf/FR-2021-12-23.pdf",
                "source_excerpt": "联邦公报将该NSN列为9.0V不可充电锂电池，并纳入DLA陆地与海事部门管理的国防部采购需求。",
                "verified_facts": {
                    "nsn": "6135-01-554-4281",
                    "voltage": "9.0V",
                    "battery_type": "不可充电锂电池",
                    "dla_procurement_system_verified": True,
                },
                "evidence_grade": "B",
                "status": "verified",
                "limitations": ["证明产品编码进入采购体系，不证明某票进口货物最终用途"],
            },
            {
                "id": "ose-army-miles-cr123a",
                "case_id": "case-ultralife-ba5390-dla",
                "title": "美国陆军MILES训练系统使用CR123A电池",
                "source_type": "official_equipment_document",
                "source_publisher": "U.S. Army",
                "source_url": "https://home.army.mil/bragg/8217/7074/2018/Cleaning_instructions_for_issue_equipment.pdf",
                "source_excerpt": "美国陆军装备交还文件显示，MILES激光交战训练系统每套配发2只CR123A电池。",
                "verified_facts": {
                    "battery_model": "CR123A",
                    "military_equipment": "MILES激光交战训练系统",
                    "quantity_per_set": 2,
                    "military_use_verified": True,
                },
                "evidence_grade": "B",
                "status": "verified",
                "limitations": ["尚无批次文件证明ABLE部件进入特定MILES装备或合同"],
            },
            {
                "id": "ose-army-cr123a-safety",
                "case_id": "case-ultralife-ba5390-dla",
                "title": "美国陆军军用CR123A假冒电池安全通报",
                "source_type": "official_safety_notice",
                "source_publisher": "U.S. Army",
                "source_url": "https://battery.army.mil/safety/safety-and-maintenance-messages/",
                "source_excerpt": "美国陆军发布过军用CR123A假冒电池安全信息，确认该规格存在军用保障和安全监管场景。",
                "verified_facts": {"battery_model": "CR123A", "army_safety_context_verified": True},
                "evidence_grade": "B",
                "status": "verified",
                "limitations": ["安全通报不等同于Ultralife采购合同或具体供应关系"],
            },
            {
                "id": "ose-ultralife-ubbl72",
                "case_id": "case-ultralife-cwb",
                "title": "Ultralife UBBL72贴合式可穿戴电池规格",
                "source_type": "manufacturer_datasheet",
                "source_publisher": "Ultralife Corporation",
                "source_url": "https://www.ultralifecorp.com/ECommerce/product/ubbl72/rechargeable-conformal-battery",
                "source_excerpt": "UBBL72/BB-2525规格为14.8V、10.75Ah、159Wh，由20个可弯折矩形单元构成，面向Nett Warrior等设备。",
                "verified_facts": {
                    "voltage": "14.8V", "capacity": "10.75Ah", "energy": "159Wh",
                    "cell_count": 20, "target_system": "Nett Warrior",
                    "china_cell_model_match_verified": False,
                },
                "evidence_grade": "C",
                "status": "verified",
                "limitations": ["未披露内部电芯型号，不能与力神、山东精工批次直接对应"],
            },
            {
                "id": "ose-accutronics-ub123a",
                "case_id": "case-ultralife-ba5390-dla",
                "title": "Ultralife关联公司UB123A产品用途说明",
                "source_type": "manufacturer_datasheet",
                "source_publisher": "Accutronics / Ultralife",
                "source_url": "https://accutronics.co.uk/product/ub123a/",
                "source_excerpt": "UB123A被列为可用于军用、外科或工业照明的电池，支持ABLE CR123A相关部件进入Ultralife产品制造链的判断。",
                "verified_facts": {
                    "product": "UB123A", "military_application_listed": True,
                    "able_component_chain_likely": True, "specific_contract_batch_verified": False,
                },
                "evidence_grade": "B",
                "status": "verified",
                "limitations": ["产品用途说明不能证明中方部件进入特定美军合同"],
            },
        ]
        for row in open_source_rows:
            row_id = row.pop("id")
            upsert(db, SupplyChainOpenSourceEvidence, row_id, **row)
        db.flush()

        summary = (
            "报告核验Ultralife作为美军MK 68水雷系统、BA-5390一次电池及CWB可穿戴电池供应商的采购关系，"
            "并梳理ABLE、山东精工和天津力神于2026年3月至7月向其供应中国原产锂电池、电芯共32121公斤的贸易链条。"
            "开源增补核验确认U9VL-J-P进入美国国防物资采购体系、CR123A实际用于美军MILES训练装备；"
            "力神和山东精工的可充电电芯目前只能确认进入Ultralife总体供应链，尚不能直接指向CWB。"
        )
        upsert(
            db,
            SupplyChainReport,
            "scr-ultralife-verified-20260719",
            country="United States",
            title="美军电池供应商Ultralife自华采购锂电池供应链穿透报告",
            case_ids=[
                "case-ultralife-mk68",
                "case-ultralife-ba5390-dla",
                "case-ultralife-cwb",
            ],
            evidence_ids=[
                "evd-mk68-able",
                "evd-ba5390-able",
                "evd-cwb-able",
                "evd-cwb-goldencell",
                "evd-cwb-lishen",
            ],
            model_id=None,
            status="completed",
            content=content,
            summary=summary,
            error_log=None,
            generated_at=datetime.now(timezone.utc),
        )
        db.commit()
        print({
            "entities": 4,
            "cases": 3,
            "shipments": 3,
            "evidence": 5,
            "open_source_evidence": len(open_source_rows),
            "reports": 1,
            "document_chars": len(re.sub(r"\s+", "", content)),
        })
    finally:
        db.close()


if __name__ == "__main__":
    main()
