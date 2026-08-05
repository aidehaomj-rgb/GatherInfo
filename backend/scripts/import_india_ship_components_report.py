"""Import the verified India-integrated ship-components supply-chain report."""
from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

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


REPORT_PATH = Path(r"D:\codex\供应链穿透\涉印关键船配件供应链穿透分析_核实版.docx")
INVESTIGATION_ID = "inv-india-csbc-pump-chain"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", NS):
        text = "".join(
            node.text or "" for node in paragraph.findall(".//w:t", NS)
        ).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def upsert(db, model, row_id: str, **values):
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def main():
    if not REPORT_PATH.exists():
        raise FileNotFoundError(REPORT_PATH)

    report_content = docx_text(REPORT_PATH)
    source_ref = str(REPORT_PATH)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        entities = [
            (
                "ent-sulzer-ltd",
                dict(
                    name="Sulzer Ltd",
                    name_zh="苏尔寿集团",
                    country="Switzerland",
                    entity_type="parent_company",
                    aliases=["Sulzer"],
                    parent_id=None,
                    defense_roles=["中国供应节点与印度集成节点的集团控制主体"],
                    source_url="https://report.sulzer.com/ar24/en/note35-major-subsidiaries",
                    notes="集团年度报告和企业资料确认中国、印度相关主体的集团关系。",
                ),
            ),
            (
                "ent-sulzer-suzhou",
                dict(
                    name="Sulzer Pumps Suzhou Ltd.",
                    name_zh="苏州苏尔寿泵业有限公司",
                    country="China",
                    entity_type="china_exporter",
                    aliases=["苏州苏尔寿"],
                    parent_id="ent-sulzer-ltd",
                    defense_roles=["裸轴泵、泵体及泵备件供应商"],
                    source_url=(
                        "https://www.sulzer.com/zh-cn/products/pumps/"
                        "end-suction-and-overhung-pumps"
                    ),
                    notes="2025年4月至6月向Sulzer Pumps India形成至少9条泵及备件供货记录。",
                ),
            ),
            (
                "ent-wolong-nanyang",
                dict(
                    name="Wolong Electric Nanyang Explosion Protection Group Co., Ltd.",
                    name_zh="卧龙电气南阳防爆集团股份有限公司",
                    country="China",
                    entity_type="china_exporter",
                    aliases=["南防集团", "卧龙南防"],
                    parent_id=None,
                    defense_roles=["工业电机和泵组驱动配套供应商"],
                    source_url="https://www.wolong.com.cn/about-wolong/wolong-brand",
                    notes="2025年向Sulzer Pumps India形成7条工业电机供货记录。",
                ),
            ),
            (
                "ent-sulzer-pumps-india",
                dict(
                    name="Sulzer Pumps India Private Limited",
                    name_zh="苏尔寿泵业印度私人有限公司",
                    country="India",
                    entity_type="integrator",
                    aliases=["Sulzer Pumps India"],
                    parent_id="ent-sulzer-ltd",
                    defense_roles=["离心泵组集成、组装、采购组织及项目交付节点"],
                    source_url=(
                        "https://www.sulzer.com/norway/-/media/files/services/"
                        "service-centers/brochures/"
                        "sulzer_pumps_india_manufacturing_and_service_facilities_e10881.pdf"
                    ),
                    notes="企业公开能力与中国产部件进口及对台船交付贸易链路相匹配。",
                ),
            ),
            (
                "ent-csbc-taiwan",
                dict(
                    name="CSBC Corporation, Taiwan",
                    name_zh="台灣國際造船股份有限公司",
                    country="Taiwan",
                    entity_type="terminal_shipyard",
                    aliases=["CSBC", "台船"],
                    parent_id=None,
                    defense_roles=["船舶建造、军用无人艇研发及项目接收"],
                    source_url="https://www.csbcnet.com.tw/",
                    notes="贸易记录显示2025年从Sulzer Pumps India接收至少6批次、共11台/套离心泵组。",
                ),
            ),
            (
                "ent-endeavor-manta",
                dict(
                    name="Endeavor Manta",
                    name_zh="奮進魔鬼魚號",
                    country="Taiwan",
                    entity_type="terminal_project",
                    aliases=["奋进魔鬼鱼号"],
                    parent_id="ent-csbc-taiwan",
                    defense_roles=["军用级无人水面载具", "轻型鱼雷适配设想"],
                    source_url="https://www.taiwannews.com.tw/news/6202826",
                    notes="公开性能与终端场景相符，但尚无证据证明报告所涉泵组已安装到该艇。",
                ),
            ),
            (
                "ent-lockheed-martin",
                dict(
                    name="Lockheed Martin Corporation",
                    name_zh="洛克希德·马丁公司",
                    country="United States",
                    entity_type="defense_prime",
                    aliases=["Lockheed Martin"],
                    parent_id=None,
                    defense_roles=["潜舰战斗系统及美制鱼雷相关主体的高概率候选"],
                    source_url=None,
                    notes="属于待核线索，不得据此认定印度泵组已进入其战斗系统。",
                ),
            ),
        ]
        entity_ids = []
        for row_id, values in entities:
            upsert(db, SupplyChainEntity, row_id, **values)
            entity_ids.append(row_id)
        db.flush()

        cases = [
            (
                "case-india-sulzer-csbc-pump-delivery",
                dict(
                    country="India",
                    title="Sulzer Pumps India向台船交付离心泵组",
                    procurement_agency="台灣國際造船股份有限公司",
                    procurement_reference="2025年贸易记录（至少6批次）",
                    procurement_date=None,
                    supplier_entity_id="ent-sulzer-pumps-india",
                    product="至少11台/套离心泵组",
                    target_program="台船船舶建造与项目交付",
                    contract_value=None,
                    currency="USD",
                    source_url=None,
                    source_excerpt=(
                        "贸易记录确认印度集成节点向台船多批次交付泵组；"
                        "现有证据不能确定具体安装船号。"
                    ),
                    status="verified",
                ),
            ),
            (
                "case-india-csbc-endeavor-manta",
                dict(
                    country="India",
                    title="台船奮進魔鬼魚號军用无人艇终端关联",
                    procurement_agency="台灣國際造船股份有限公司",
                    procurement_reference="公开项目资料（待与设备资料交叉核验）",
                    procurement_date=None,
                    supplier_entity_id="ent-csbc-taiwan",
                    product="军用级无人水面载具",
                    target_program="奮進魔鬼魚號 / Endeavor Manta",
                    contract_value=None,
                    currency="USD",
                    source_url="https://www.taiwannews.com.tw/news/6202826",
                    source_excerpt=(
                        "公开资料确认项目具备军用级定位和轻型鱼雷适配设想；"
                        "尚不能证明所涉11台/套泵组已安装于该项目。"
                    ),
                    status="needs_review",
                ),
            ),
        ]
        case_ids = []
        for row_id, values in cases:
            upsert(db, SupplyChainCase, row_id, **values)
            case_ids.append(row_id)
        db.flush()

        shipments = [
            (
                "shp-sulzer-suzhou-india-pumps-2025",
                dict(
                    exporter_name="苏州苏尔寿泵业有限公司",
                    exporter_country="China",
                    importer_entity_id="ent-sulzer-pumps-india",
                    importer_name="Sulzer Pumps India Private Limited",
                    product="裸轴泵、泵体及泵备件",
                    hs_code=None,
                    shipment_date=None,
                    weight_kg=None,
                    quantity=9,
                    quantity_unit="条贸易记录",
                    origin_country="China",
                    destination_country="India",
                    bill_no=None,
                    source_name="涉印关键船配件供应链穿透分析（核实版）",
                    source_url=None,
                    raw_record={
                        "date_range": "2025-04至2025-06",
                        "record_count": 9,
                        "source_document": source_ref,
                    },
                ),
            ),
            (
                "shp-wolong-india-motors-2025",
                dict(
                    exporter_name="卧龙电气南阳防爆集团股份有限公司",
                    exporter_country="China",
                    importer_entity_id="ent-sulzer-pumps-india",
                    importer_name="Sulzer Pumps India Private Limited",
                    product="工业电机及泵组驱动配套",
                    hs_code=None,
                    shipment_date=None,
                    weight_kg=None,
                    quantity=7,
                    quantity_unit="条贸易记录",
                    origin_country="China",
                    destination_country="India",
                    bill_no=None,
                    source_name="涉印关键船配件供应链穿透分析（核实版）",
                    source_url=None,
                    raw_record={
                        "date_range": "2025年",
                        "record_count": 7,
                        "source_document": source_ref,
                    },
                ),
            ),
            (
                "shp-india-sulzer-csbc-pumps-2025",
                dict(
                    exporter_name="Sulzer Pumps India Private Limited",
                    exporter_country="India",
                    importer_entity_id="ent-csbc-taiwan",
                    importer_name="CSBC Corporation, Taiwan",
                    product="离心泵组",
                    hs_code=None,
                    shipment_date=None,
                    weight_kg=None,
                    quantity=11,
                    quantity_unit="台/套",
                    origin_country="India",
                    destination_country="Taiwan",
                    bill_no=None,
                    source_name="涉印关键船配件供应链穿透分析（核实版）",
                    source_url=None,
                    raw_record={
                        "date_range": "2025年",
                        "shipment_batches": "至少6批次",
                        "source_document": source_ref,
                    },
                ),
            ),
        ]
        shipment_ids = []
        for row_id, values in shipments:
            upsert(db, SupplyChainShipment, row_id, **values)
            shipment_ids.append(row_id)
        db.flush()

        evidence_rows = [
            (
                "evd-india-suzhou-pump-input",
                "case-india-sulzer-csbc-pump-delivery",
                "shp-sulzer-suzhou-india-pumps-2025",
                "upstream_component",
                "B",
                88,
                "approved",
                True,
                "9条贸易记录与苏州苏尔寿泵产品能力相互印证，构成泵体、裸轴泵和备件供给线。",
            ),
            (
                "evd-india-wolong-motor-input",
                "case-india-sulzer-csbc-pump-delivery",
                "shp-wolong-india-motors-2025",
                "upstream_component",
                "B",
                86,
                "approved",
                True,
                "7条工业电机贸易记录与南防集团产品能力匹配，构成泵组驱动配套线。",
            ),
            (
                "evd-india-csbc-pump-delivery",
                "case-india-sulzer-csbc-pump-delivery",
                "shp-india-sulzer-csbc-pumps-2025",
                "integrated_delivery",
                "B",
                90,
                "approved",
                True,
                "至少6批次、11台/套离心泵组由印度集成节点向台船交付，项目交付特征明显。",
            ),
            (
                "evd-india-endeavor-manta-link",
                "case-india-csbc-endeavor-manta",
                "shp-india-sulzer-csbc-pumps-2025",
                "possible_end_use",
                "C",
                45,
                "needs_review",
                False,
                "终端企业与无人艇项目主体一致，但缺少船号、序列号、装箱单或验收文件，不能确认具体安装。",
            ),
        ]
        evidence_ids = []
        for (
            row_id, case_id, shipment_id, relation_type, grade, score,
            status, reportable, reasoning,
        ) in evidence_rows:
            upsert(
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
                verified_facts={
                    "trade_record_reported": True,
                    "specific_platform_installation_verified": False,
                    "source_document": source_ref,
                },
                model_review={
                    "method": "verified_report_import",
                    "boundary": "供应链关系已核实，具体装备安装待核",
                },
                is_reportable=reportable,
            )
            evidence_ids.append(row_id)
        db.flush()

        source_rows = [
            (
                "ose-india-sulzer-facilities",
                "case-india-sulzer-csbc-pump-delivery",
                "Sulzer Pumps India制造与服务设施资料",
                "企业官方资料",
                "Sulzer",
                (
                    "https://www.sulzer.com/norway/-/media/files/services/"
                    "service-centers/brochures/"
                    "sulzer_pumps_india_manufacturing_and_service_facilities_e10881.pdf"
                ),
                "确认印度主体具备离心泵制造、采购、包装和项目交付能力。",
                "B",
                [],
            ),
            (
                "ose-india-sulzer-iso",
                "case-india-sulzer-csbc-pump-delivery",
                "Sulzer Pumps India质量体系证书",
                "企业认证文件",
                "Sulzer",
                (
                    "https://www.sulzer.com/-/media/files/about-us/"
                    "certified_management_systems/pe/"
                    "pumps_equipment_navimumbai_iso_9001.pdf"
                ),
                "证书范围覆盖离心泵设计制造、相关附件采购与包装。",
                "A",
                [],
            ),
            (
                "ose-india-sulzer-china-products",
                "case-india-sulzer-csbc-pump-delivery",
                "Sulzer中国泵产品及苏州主体资料",
                "企业官方资料",
                "Sulzer",
                (
                    "https://www.sulzer.com/zh-cn/products/pumps/"
                    "end-suction-and-overhung-pumps"
                ),
                "产品线与贸易记录中的裸轴泵、泵体及备件字段相匹配。",
                "B",
                [],
            ),
            (
                "ose-india-wolong-capability",
                "case-india-sulzer-csbc-pump-delivery",
                "卧龙官方品牌与南防集团介绍",
                "企业官方资料",
                "卧龙电气",
                "https://www.wolong.com.cn/about-wolong/wolong-brand",
                "确认南防集团为防爆电机科研生产和机电产品出口基地。",
                "B",
                [],
            ),
            (
                "ose-india-csbc-manta",
                "case-india-csbc-endeavor-manta",
                "CSBC无人艇性能与轻型鱼雷适配信息",
                "新闻公开资料",
                "Taiwan News",
                "https://www.taiwannews.com.tw/news/6202826",
                "确认奮進魔鬼魚號的军用级性能及轻型鱼雷适配设想。",
                "B",
                ["未披露报告所涉泵组的设备序列号或安装记录"],
            ),
            (
                "ose-india-csbc-cna",
                "case-india-csbc-endeavor-manta",
                "奮進魔鬼魚號与玉山舰搭载、轻型鱼雷用途",
                "新闻公开资料",
                "中央社",
                "https://www.cna.com.tw/news/aipl/202509170376.aspx",
                "补充无人艇展示、搭载及潜在用途信息。",
                "B",
                ["不能用于证明具体泵组安装位置"],
            ),
        ]
        source_ids = []
        for (
            row_id, case_id, title, source_type, publisher, url,
            excerpt, grade, limitations,
        ) in source_rows:
            upsert(
                db,
                SupplyChainOpenSourceEvidence,
                row_id,
                case_id=case_id,
                title=title,
                source_type=source_type,
                source_publisher=publisher,
                source_url=url,
                source_excerpt=excerpt,
                verified_facts={"source_document": source_ref},
                evidence_grade=grade,
                status="verified",
                limitations=limitations,
            )
            source_ids.append(row_id)

        report_id = "scr-india-csbc-pump-chain-verified"
        upsert(
            db,
            SupplyChainReport,
            report_id,
            country="India",
            title="涉印关键船配件供应链穿透分析（核实版）",
            case_ids=case_ids,
            evidence_ids=evidence_ids,
            model_id=None,
            status="completed",
            content=report_content,
            summary=(
                "苏州苏尔寿提供裸轴泵、泵体及备件，卧龙电气南阳防爆集团提供工业电机，"
                "Sulzer Pumps India在印度完成泵组集成、组装和项目交付，并向台船交付"
                "至少6批次、11台/套离心泵组。现有证据能够确认中国产部件经印度集成后"
                "进入台船供应链，但尚不能确认具体泵组安装于某艘军用无人艇。"
            ),
            error_log=None,
            generated_at=datetime.now(timezone.utc),
        )

        upsert(
            db,
            SupplyChainInvestigation,
            INVESTIGATION_ID,
            country="India",
            name="涉印关键船配件供应链",
            description=(
                "中国产裸轴泵、泵体、备件和工业电机经Sulzer Pumps India集成为"
                "离心泵组，再向台灣國際造船股份有限公司交付的跨境供应链"
            ),
            status="active",
            entity_ids=entity_ids,
            case_ids=case_ids,
            shipment_ids=shipment_ids,
            evidence_ids=evidence_ids,
            open_source_evidence_ids=source_ids,
            report_ids=[report_id],
        )
        db.commit()
        print(
            "Imported India ship-components chain: "
            f"{len(entity_ids)} entities, {len(case_ids)} cases, "
            f"{len(shipment_ids)} shipments, {len(evidence_ids)} evidence links."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
