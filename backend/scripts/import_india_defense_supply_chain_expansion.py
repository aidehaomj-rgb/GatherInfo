"""Import the July 2026 India defence supply-chain expansion findings.

The script is idempotent. It records trade facts and defence-program facts
separately so the UI does not imply that a specific shipment entered a
specific military product without bill-of-material or end-use evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainCase,
    SupplyChainEntity,
    SupplyChainEvidence,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
    SupplyChainReport,
    SupplyChainShipment,
)


TRADESPARQ_SEARCH_URL = "https://data.tradesparq.com/shipments/search"


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


def add_entity(
    db,
    row_id: str,
    name: str,
    country: str,
    entity_type: str,
    roles: list[str],
    source_url: str,
    notes: str,
    name_zh: str | None = None,
):
    row = upsert(
        db,
        SupplyChainEntity,
        row_id,
        name=name,
        name_zh=name_zh,
        country=country,
        entity_type=entity_type,
        aliases=[],
        parent_id=None,
        defense_roles=roles,
        source_url=source_url,
        notes=notes,
    )
    db.flush()
    return row


def add_open_evidence(
    db,
    row_id: str,
    case_id: str,
    title: str,
    publisher: str,
    url: str,
    excerpt: str,
    facts: list[str],
    grade: str,
    status: str,
    limitations: list[str],
    source_type: str = "official_document",
):
    return upsert(
        db,
        SupplyChainOpenSourceEvidence,
        row_id,
        case_id=case_id,
        title=title,
        source_type=source_type,
        source_publisher=publisher,
        source_url=url,
        source_excerpt=excerpt,
        verified_facts=facts,
        evidence_grade=grade,
        status=status,
        limitations=limitations,
    )


def add_investigation(
    db,
    row_id: str,
    name: str,
    description: str,
    status: str,
    entity_ids: list[str],
    case_ids: list[str],
    shipment_ids: list[str],
    evidence_ids: list[str],
    open_source_ids: list[str],
    report_id: str,
    report_summary: str,
    report_content: str,
):
    upsert(
        db,
        SupplyChainReport,
        report_id,
        country="India",
        title=f"{name}初步核验报告",
        case_ids=case_ids,
        evidence_ids=evidence_ids,
        model_id=None,
        status="completed",
        content=report_content,
        summary=report_summary,
        error_log=None,
        generated_at=dt("2026-07-31T12:00:00"),
    )
    upsert(
        db,
        SupplyChainInvestigation,
        row_id,
        country="India",
        name=name,
        description=description,
        status=status,
        entity_ids=entity_ids,
        case_ids=case_ids,
        shipment_ids=shipment_ids,
        evidence_ids=evidence_ids,
        open_source_evidence_ids=open_source_ids,
        report_ids=[report_id],
    )


def import_garuda(db):
    garuda_id = "ent-india-garuda-aerospace"
    walkera_id = "ent-china-walkera-garuda"
    trader_id = "ent-china-chevron-garuda"
    army_id = "ent-india-armed-forces-garuda"
    case_id = "case-india-garuda-defense-drones"

    add_entity(
        db, garuda_id, "Garuda Aerospace Private Limited", "India",
        "defense_supplier", ["军用无人机研发、集成与供应"],
        "https://www.garudaaerospace.com/products/defense-drones",
        "印度无人机企业，官网设有军用无人机产品线。外贸公社检索显示其在2025至2026年持续进口中国来源无人机部件。",
    )
    add_entity(
        db, walkera_id, "WALKERA TECHNOLOGY CICI LAU", "China",
        "component_supplier", ["无人机电源板、中央框架和电池充电集线器"],
        TRADESPARQ_SEARCH_URL,
        "外贸公社提单显示名称，准确工商主体仍待进一步核验。",
        "华科尔相关无人机部件供应主体",
    )
    add_entity(
        db, trader_id, "CHEVRON UNITED CO FOR GENERAL TRADING", "China",
        "trading_company", ["无人机电池充电集线器贸易供应"],
        TRADESPARQ_SEARCH_URL,
        "外贸公社记录显示原产国为中国；贸易商名称及实际制造商仍待核验。",
    )
    add_entity(
        db, army_id, "Indian Armed Forces", "India", "military_end_user",
        ["军用无人机采购与使用"],
        "https://www.drdo.gov.in/drdo/sites/default/files/drdo-news-documents/NPC29Aug2024.pdf",
        "印度国防生产部门风险提示涉及向印度国防力量供应无人机的企业。",
        "印度武装力量",
    )
    upsert(
        db, SupplyChainCase, case_id,
        country="India",
        title="Garuda Aerospace军用无人机供应与中国部件风险审查",
        procurement_agency="印度国防生产部门 / 印度武装力量",
        procurement_reference="DPP advisory dated 25 June 2024",
        procurement_date=dt("2024-06-25T00:00:00"),
        supplier_entity_id=garuda_id,
        product="军用无人机及无人机部件",
        target_program="印度军用无人机采购与供应链安全审查",
        contract_value=None,
        currency="INR",
        source_url="https://www.drdo.gov.in/drdo/sites/default/files/drdo-news-documents/NPC29Aug2024.pdf",
        source_excerpt="印度国防生产部门文件点名Garuda Aerospace等企业，提示其向国防力量供应的无人机存在组装或集成中国部件风险。",
        status="verified_lead",
    )
    db.flush()

    shipment_specs = [
        ("shp-garuda-walkera-20260316", walkera_id, "WALKERA TECHNOLOGY CICI LAU",
         "无人机电源板及C1无人机电池充电集线器", "88071000", "2026-03-16T00:00:00",
         "R6VDW3QGNIGKH", None),
        ("shp-garuda-walkera-20260124", walkera_id, "WALKERA TECHNOLOGY CICI LAU",
         "无人机塑料中央框架及C1无人机电池充电集线器", "88071000", "2026-01-24T00:00:00",
         "C9NRUMKAUFQNN", None),
        ("shp-garuda-walkera-20251222", walkera_id, "WALKERA TECHNOLOGY CICI LAU",
         "无人机塑料中央框架", "88071000", "2025-12-22T00:00:00",
         "LB92ALUYH806B", 100.0),
        ("shp-garuda-chevron-20251103", trader_id, "CHEVRON UNITED CO FOR GENERAL TRADING",
         "C1无人机电池充电集线器", "88071000", "2025-11-03T00:00:00",
         "KOOJ7S8P604L2", None),
        ("shp-garuda-chevron-20251004", trader_id, "CHEVRON UNITED CO FOR GENERAL TRADING",
         "C1无人机电池充电集线器", "88071000", "2025-10-04T00:00:00",
         "F36RTES0RIMGD", None),
    ]
    shipment_ids = []
    evidence_ids = []
    for shipment_id, exporter_id, exporter_name, product, hs_code, date, bill_no, quantity in shipment_specs:
        shipment_ids.append(shipment_id)
        upsert(
            db, SupplyChainShipment, shipment_id,
            exporter_name=exporter_name,
            exporter_country="China",
            importer_entity_id=garuda_id,
            importer_name="Garuda Aerospace Private Limited",
            product=product,
            hs_code=hs_code,
            shipment_date=dt(date),
            weight_kg=None,
            quantity=quantity,
            quantity_unit="PCS" if quantity else None,
            origin_country="China",
            destination_country="India",
            bill_no=bill_no,
            source_name="外贸公社 / Tradesparq",
            source_url=TRADESPARQ_SEARCH_URL,
            raw_record={
                "verification_date": "2026-07-31",
                "exporter_entity_id": exporter_id,
                "deduplicated": True,
                "scope": "企业层面的进口记录，未与具体军方交付批次建立一一对应",
            },
        )
        db.flush()
        evidence_id = f"ev-{shipment_id.removeprefix('shp-')}"
        evidence_ids.append(evidence_id)
        upsert(
            db, SupplyChainEvidence, evidence_id,
            case_id=case_id,
            shipment_id=shipment_id,
            relation_type="corporate_supply_chain_import",
            evidence_grade="B",
            score=86,
            status="verified",
            reasoning="贸易记录确认Garuda Aerospace自中国进口无人机部件；国防文件确认该企业属于军用无人机供应链风险审查对象。尚无物料清单证明该批部件进入某一具体军方交付产品。",
            verified_facts=["进口商、产品、日期和提单号可核验", "中国来源无人机部件进入Garuda企业供应链"],
            model_review={"reviewed": True, "decision": "bounded_match"},
            is_reportable=True,
        )

    open_ids = ["ose-india-garuda-ddp-warning", "ose-india-garuda-defense-products"]
    add_open_evidence(
        db, open_ids[0], case_id,
        "印度国防生产部门关于军用无人机中国部件风险的提示",
        "印度国防生产部门 / DRDO新闻汇编",
        "https://www.drdo.gov.in/drdo/sites/default/files/drdo-news-documents/NPC29Aug2024.pdf",
        "文件点名Dhaksha、Sky Industries（Gandhinagar）和Garuda Aerospace，涉及向印度国防力量供应无人机时使用中国部件的风险。",
        ["Garuda Aerospace被官方风险提示点名", "风险事项涉及军用无人机中的中国部件"],
        "A", "verified",
        ["文件证明风险提示与企业军方供应关系，不证明本次录入的每一批贸易记录均进入军用产品。"],
    )
    add_open_evidence(
        db, open_ids[1], case_id,
        "Garuda Aerospace军用无人机产品页面",
        "Garuda Aerospace",
        "https://www.garudaaerospace.com/products/defense-drones",
        "企业官网展示面向国防和军事应用的无人机产品。",
        ["Garuda Aerospace公开开展军用无人机业务"],
        "A", "verified",
        ["官网未披露具体产品的完整物料清单和批次来源。"],
        "company_disclosure",
    )
    add_investigation(
        db,
        "inv-india-garuda-defense-drone",
        "Garuda军用无人机中国部件供应链",
        "外贸公社记录确认Garuda Aerospace在2025至2026年从中国进口无人机电源板、中央框架和电池充电集线器；印度国防生产部门又将其列为军用无人机中国部件风险审查对象。现有证据确认中国部件进入企业供应链，但尚不能逐批对应具体军方交付。",
        "active",
        [garuda_id, walkera_id, trader_id, army_id],
        [case_id], shipment_ids, evidence_ids, open_ids,
        "report-india-garuda-defense-drone",
        "Garuda Aerospace具有明确军用无人机业务，并存在连续、可核验的中国来源无人机部件进口。官方风险提示与贸易记录相互印证，构成较强企业级供应链关联；具体军方产品批次仍需物料清单、序列号或验收文件闭合。",
        "已核验企业业务、官方风险提示及5组去重贸易记录。建议持续跟踪Garuda军方合同、产品BOM、进口部件用途及供应商工商主体，防止将企业一般进口直接等同于特定军品最终用途。",
    )


def import_paras(db):
    paras_id = "ent-india-paras-defence"
    supplier_id = "ent-china-paras-optics-undisclosed"
    drdo_id = "ent-india-drdo-paras"
    case_id = "case-india-paras-air-defense-optics"
    shipment_id = "shp-paras-china-optics-20260202"
    evidence_id = "ev-paras-china-optics-air-defense"

    add_entity(
        db, paras_id, "Paras Defence and Space Technologies Limited", "India",
        "defense_supplier", ["军用光学、光电、夜视及防空系统"],
        "https://parasdefence.com/investors",
        "印度军用光学与光电设备供应商，承担DRDO及BEL相关项目。",
    )
    add_entity(
        db, supplier_id, "Undisclosed Chinese Optical Components Supplier", "China",
        "component_supplier", ["无焦变焦镜头及光学组件"],
        "https://nbd.ltd/trader/info/NBDD3Y524350267",
        "公开贸易页面对供应商名称作了掩码处理，需通过完整提单进一步识别。",
        "待识别中国光学组件供应商",
    )
    add_entity(
        db, drdo_id, "Defence Research and Development Organisation", "India",
        "government_end_user", ["防空应用高精度光学系统研发采购"],
        "https://parasdefence.com/uploads/disclosures/1773121217receipt-of-order-from-drdo-ministry-of-defence.pdf",
        "印度国防研究与发展组织。",
        "印度国防研究与发展组织",
    )
    upsert(
        db, SupplyChainCase, case_id,
        country="India",
        title="DRDO防空应用高精度光学系统项目",
        procurement_agency="Defence Research and Development Organisation",
        procurement_reference="Paras Defence disclosure dated 9 March 2026",
        procurement_date=dt("2026-03-09T00:00:00"),
        supplier_entity_id=paras_id,
        product="防空应用高精度光学系统",
        target_program="DRDO High Precision Optical System for Air Defence Applications",
        contract_value=802800000.0,
        currency="INR",
        source_url="https://parasdefence.com/uploads/disclosures/1773121217receipt-of-order-from-drdo-ministry-of-defence.pdf",
        source_excerpt="Paras Defence披露获得DRDO约8.028亿卢比高精度防空光学系统研发订单。",
        status="researching",
    )
    db.flush()
    upsert(
        db, SupplyChainShipment, shipment_id,
        exporter_name="Undisclosed Chinese Optical Components Supplier",
        exporter_country="China",
        importer_entity_id=paras_id,
        importer_name="Paras Defence and Space Technologies Limited",
        product="S2 VIS无焦变焦镜头等光学组件",
        hs_code="90029000",
        shipment_date=dt("2026-02-02T00:00:00"),
        weight_kg=None,
        quantity=None,
        quantity_unit=None,
        origin_country="China",
        destination_country="India",
        bill_no=None,
        source_name="NBD Trade Data",
        source_url="https://nbd.ltd/trader/info/NBDD3Y524350267",
        raw_record={"product_text": "OPTICAL COMPONENTS S2 VIS AFOCAL ZOOM LENS", "scope": "公开摘要记录"},
    )
    db.flush()
    upsert(
        db, SupplyChainEvidence, evidence_id,
        case_id=case_id,
        shipment_id=shipment_id,
        relation_type="candidate_component_match",
        evidence_grade="B",
        score=74,
        status="follow_up",
        reasoning="进口产品与企业军用光学业务具有技术相关性，但尚无料号、BOM或领用记录将该镜头对应至DRDO防空项目。",
        verified_facts=["Paras Defence在2026年2月进口中国来源光学组件", "企业于2026年3月披露DRDO防空光学系统订单"],
        model_review={"reviewed": True, "decision": "follow_up"},
        is_reportable=True,
    )
    open_ids = ["ose-india-paras-drdo-order", "ose-india-paras-china-optics"]
    add_open_evidence(
        db, open_ids[0], case_id,
        "Paras Defence获得DRDO高精度防空光学系统订单",
        "Paras Defence证券披露",
        "https://parasdefence.com/uploads/disclosures/1773121217receipt-of-order-from-drdo-ministry-of-defence.pdf",
        "公司披露DRDO订单金额约8.028亿卢比。",
        ["DRDO采购机关、项目方向、合同金额和披露日期可核验"],
        "A", "verified",
        ["合同未公开完整物料清单。"],
        "company_disclosure",
    )
    add_open_evidence(
        db, open_ids[1], case_id,
        "Paras Defence中国来源光学组件进口记录",
        "NBD Trade Data",
        "https://nbd.ltd/trader/info/NBDD3Y524350267",
        "公开记录显示2026年2月2日从中国进口HS 90029000光学组件和无焦变焦镜头。",
        ["进口商、日期、原产国、HS编码和产品描述可核验"],
        "B", "follow_up",
        ["供应商名称被掩码", "尚未证明该批镜头用于DRDO防空项目。"],
        "trade_database",
    )
    add_investigation(
        db,
        "inv-india-paras-defense-optics",
        "Paras Defence军用光电系统供应链",
        "Paras Defence于2026年2月进口中国来源无焦变焦镜头等光学组件，并于同年3月披露DRDO防空应用高精度光学系统订单。时间和技术方向具有较强关联，但具体物料用途尚待料号与BOM核验。",
        "researching",
        [paras_id, supplier_id, drdo_id],
        [case_id], [shipment_id], [evidence_id], open_ids,
        "report-india-paras-defense-optics",
        "已确认Paras Defence的中国光学组件进口和DRDO防空光学系统订单，两类证据在时间与产品方向上相邻。尚不能确认该批无焦镜头进入具体防空系统，应列为重点待核链条。",
        "下一步应获取完整提单以识别中国供应商，并比对镜头料号、Paras采购订单、生产领料记录及DRDO项目BOM。",
    )


def import_accord(db):
    accord_id = "ent-india-accord-software"
    supplier_id = "ent-china-accord-electronics-undisclosed"
    navy_id = "ent-india-navy-accord"
    case_id = "case-india-accord-ecgnss-jammer"
    shipment_ids = ["shp-accord-heatsink-20260127", "shp-accord-spectrum-20260123"]
    evidence_ids = ["ev-accord-heatsink-ecgnss", "ev-accord-spectrum-ecgnss"]

    add_entity(
        db, accord_id, "Accord Software and Systems Private Limited", "India",
        "defense_supplier", ["GNSS、导航与电子对抗系统"],
        "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2271094&lang=1&reg=1",
        "印度导航和电子战系统企业，2026年获得印度海军ECGNSS干扰设备合同。",
    )
    add_entity(
        db, supplier_id, "Undisclosed Chinese Electronics Suppliers", "China",
        "component_supplier", ["铝制散热器、频谱分析仪"],
        "https://en.nbd.ltd/trader/info/NBDD3Y524380556",
        "NBD公开页面显示中国来源记录，供应商完整名称待核。",
        "待识别中国电子设备供应商",
    )
    add_entity(
        db, navy_id, "Indian Navy", "India", "military_end_user",
        ["ECGNSS电子对抗型卫星导航干扰系统"],
        "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2271094&lang=1&reg=1",
        "印度海军。",
        "印度海军",
    )
    upsert(
        db, SupplyChainCase, case_id,
        country="India",
        title="印度海军20套ECGNSS干扰设备采购项目",
        procurement_agency="印度国防部 / 印度海军",
        procurement_reference="PIB PRID 2271094",
        procurement_date=dt("2026-06-10T00:00:00"),
        supplier_entity_id=accord_id,
        product="20套电子对抗型全球导航卫星系统干扰设备",
        target_program="Indian Navy ECGNSS Jammers",
        contract_value=4490000000.0,
        currency="INR",
        source_url="https://www.pib.gov.in/PressReleasePage.aspx?PRID=2271094&lang=1&reg=1",
        source_excerpt="印度国防部与Accord签订约44.9亿卢比合同，采购20套ECGNSS干扰设备，最低本土化比例为75%。",
        status="researching",
    )
    db.flush()
    products = [
        ("铝制散热器", "76169990", "2026-01-27T00:00:00"),
        ("OWON HSA1075-TG手持式频谱分析仪", "90304000", "2026-01-23T00:00:00"),
    ]
    for index, (product, hs_code, date) in enumerate(products):
        upsert(
            db, SupplyChainShipment, shipment_ids[index],
            exporter_name="Undisclosed Chinese Electronics Supplier",
            exporter_country="China",
            importer_entity_id=accord_id,
            importer_name="Accord Software and Systems Private Limited",
            product=product,
            hs_code=hs_code,
            shipment_date=dt(date),
            weight_kg=None,
            quantity=None,
            quantity_unit=None,
            origin_country="China",
            destination_country="India",
            bill_no=None,
            source_name="NBD Trade Data",
            source_url="https://en.nbd.ltd/trader/info/NBDD3Y524380556",
            raw_record={"scope": "公开摘要记录；具体供应商和提单号待获取"},
        )
        db.flush()
        upsert(
            db, SupplyChainEvidence, evidence_ids[index],
            case_id=case_id,
            shipment_id=shipment_ids[index],
            relation_type="production_support" if index else "candidate_component_match",
            evidence_grade="C",
            score=62 if index else 68,
            status="follow_up",
            reasoning=(
                "频谱分析仪更可能是研发测试设备，不能视为装备嵌入部件。"
                if index else
                "散热器可能用于电子设备生产，但尚无BOM证明其进入ECGNSS干扰设备。"
            ),
            verified_facts=["Accord于2026年1月存在中国来源进口", "2026年6月获得印度海军ECGNSS合同"],
            model_review={"reviewed": True, "decision": "follow_up"},
            is_reportable=True,
        )
    open_ids = ["ose-india-accord-navy-contract", "ose-india-accord-china-imports"]
    add_open_evidence(
        db, open_ids[0], case_id,
        "印度国防部采购20套ECGNSS干扰设备",
        "印度政府新闻信息局",
        "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2271094&lang=1&reg=1",
        "印度国防部与Accord签署约44.9亿卢比合同，最低本土化比例为75%。",
        ["供应商、采购机关、数量、金额和本土化要求可核验"],
        "A", "verified",
        ["合同未公开完整部件清单。"],
    )
    add_open_evidence(
        db, open_ids[1], case_id,
        "Accord中国来源电子设备进口记录",
        "NBD Trade Data",
        "https://en.nbd.ltd/trader/info/NBDD3Y524380556",
        "公开记录显示2026年1月进口中国来源铝制散热器和手持式频谱分析仪。",
        ["进口商、日期、原产国和产品描述可核验"],
        "B", "follow_up",
        ["频谱分析仪更可能属于测试设备", "散热器最终用途未核实", "供应商名称和提单号待补。"],
        "trade_database",
    )
    add_investigation(
        db,
        "inv-india-accord-navy-ew",
        "Accord印度海军电子战供应链",
        "Accord在获得印度海军20套ECGNSS干扰设备合同前，从中国进口铝制散热器和频谱分析仪。记录能够证明中国设备进入企业研发生产体系，但现阶段只能将其界定为候选组件或生产支撑设备。",
        "researching",
        [accord_id, supplier_id, navy_id],
        [case_id], shipment_ids, evidence_ids, open_ids,
        "report-india-accord-navy-ew",
        "Accord具有明确的印度海军电子战合同及同期中国来源进口。散热器可能具有产品组件属性，频谱分析仪更可能用于研发测试；两者均缺少与ECGNSS设备的BOM或领用记录。",
        "建议进一步获取完整提单、供应商身份和Accord采购料号，并区分嵌入式部件、通用生产耗材与研发测试设备。",
    )


def update_newspace(db):
    inv = db.get(SupplyChainInvestigation, "inv-india-lead-newspace-drone-components")
    if not inv:
        return
    inv.name = "NewSpace军用无人机供应链替代监测"
    inv.description = (
        "NewSpace负责人曾公开表示印度无人机行业供应链中大量商品由中国制造；"
        "当前可见的2026年贸易记录主要转向以色列和美国的线缆、电机等部件。"
        "该项目用于监测其由中国部件依赖向多国供应商替代的变化，不将历史行业性表述视为当前具体批次证据。"
    )
    current_entities = list(inv.entity_ids or [])
    current_shipments = list(inv.shipment_ids or [])
    newspace_id = "ent-india-lead-newspace-drone-components"
    supplier_specs = [
        ("ent-israel-aerium-newspace", "Aerium Systems Ltd", "Israel", "USB线缆及无人机电子连接部件"),
        ("ent-us-iqinetics-newspace", "IQinetics Technologies Inc", "United States", "无人机电机"),
    ]
    for entity_id, name, country, role in supplier_specs:
        add_entity(
            db, entity_id, name, country, "component_supplier", [role],
            TRADESPARQ_SEARCH_URL,
            "外贸公社2026年可见供应记录；用于反映NewSpace供应链替代方向。",
        )
        if entity_id not in current_entities:
            current_entities.append(entity_id)
    shipment_specs = [
        ("shp-newspace-aerium-20260225", "Aerium Systems Ltd", "Israel", "USB线缆及连接部件", "2026-02-25T00:00:00"),
        ("shp-newspace-iqinetics-20260223", "IQinetics Technologies Inc", "United States", "无人机电机", "2026-02-23T00:00:00"),
    ]
    for shipment_id, exporter, origin, product, date in shipment_specs:
        upsert(
            db, SupplyChainShipment, shipment_id,
            exporter_name=exporter,
            exporter_country=origin,
            importer_entity_id=newspace_id,
            importer_name="NewSpace Research & Technologies Pvt. Ltd.",
            product=product,
            hs_code=None,
            shipment_date=dt(date),
            weight_kg=None,
            quantity=None,
            quantity_unit=None,
            origin_country=origin,
            destination_country="India",
            bill_no=None,
            source_name="外贸公社 / Tradesparq",
            source_url=TRADESPARQ_SEARCH_URL,
            raw_record={"verification_date": "2026-07-31", "scope": "供应链替代趋势记录"},
        )
        if shipment_id not in current_shipments:
            current_shipments.append(shipment_id)
    inv.entity_ids = current_entities
    inv.shipment_ids = current_shipments


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        import_garuda(db)
        import_paras(db)
        import_accord(db)
        update_newspace(db)
        db.commit()
        print("Imported 3 India supply chains and updated the NewSpace monitoring chain.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
