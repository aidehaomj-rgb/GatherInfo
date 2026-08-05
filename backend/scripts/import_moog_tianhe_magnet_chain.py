"""Import the Tianhe Magnetics to Moog missile-actuation supply-chain report."""
from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainCase,
    SupplyChainEntity,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
    SupplyChainReport,
    SupplyChainShipment,
)


REPORT_PATH = Path(
    r"D:\codex\供应链穿透\美军工企业M今年打了采购中企T生产的稀土永磁体，正用于洛克西德.马丁、莱多斯等导弹作动系统生产，相关装备对台军售.docx"
)
INVESTIGATION_ID = "inv-us-moog-tianhe-missile-magnets"
REPORT_ID = "scr-us-moog-tianhe-missile-magnets"
REPORT_URI = REPORT_PATH.as_uri()
MOOG_PAC3_URL = (
    "https://www.moog.com/news/operating-group-news/2025/"
    "moog-receives-substantial-lockheed-martin-award-in-support-of-pac-3-mse-contract.html"
)
MOOG_BLACK_ARROW_URL = (
    "https://www.moog.com/news/operating-group-news/2025/"
    "moog-missile-cas-performs-flawlessly-during-successful-test-of-leidos-black-arrow-scm-for-ussocm.html"
)
LEIDOS_BLACK_ARROW_URL = (
    "https://www.leidos.com/insights/leidos-completes-successful-test-launch-small-cruise-missile"
)
LOCKHEED_PAC3_URL = (
    "https://investors.lockheedmartin.com/news-releases/news-release-details/"
    "lockheed-martin-secures-first-contract-pac-3r-mse-accelerated/"
)
TIANHE_REPORT_URL = "https://static.cninfo.com.cn/finalpage/2025-04-26/1223324237.PDF"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
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


def main() -> None:
    if not REPORT_PATH.exists():
        raise FileNotFoundError(REPORT_PATH)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        entities = [
            ("ent-cn-tianhe-magnetics", dict(
                name="Baotou Tianhe Magnetics Technology Co., Ltd.",
                name_zh="包头天和磁材科技股份有限公司",
                country="China",
                entity_type="component_supplier",
                aliases=["天和磁材", "Tianhe Magnetics", "603072.SH"],
                parent_id=None,
                defense_roles=["稀土永磁体上游供应商", "烧结钕铁硼和烧结钐钴制造商"],
                source_url=TIANHE_REPORT_URL,
                notes="上市公司年报确认产品体系；报告所列2026年对Moog贸易记录仍需用原始提单逐票复核。",
            )),
            ("ent-us-moog-inc", dict(
                name="Moog Inc.",
                name_zh="Moog Inc.",
                country="United States",
                entity_type="defense_supplier",
                aliases=["Moog", "穆格公司"],
                parent_id=None,
                defense_roles=["导弹机电作动器制造商", "PAC-3 MSE定制作动器供应商", "黑箭巡航导弹翼面控制作动系统供应商"],
                source_url=MOOG_PAC3_URL,
                notes="军工项目关系由Moog官方材料确认；未公开具体作动器所用磁体供应商、材料牌号和生产批次。",
            )),
            ("ent-us-lockheed-martin", dict(
                name="Lockheed Martin Corporation",
                name_zh="Lockheed Martin",
                country="United States",
                entity_type="prime_contractor",
                aliases=["Lockheed Martin", "洛克希德·马丁"],
                parent_id=None,
                defense_roles=["PAC-3 MSE主承包商", "导弹系统集成商"],
                source_url=LOCKHEED_PAC3_URL,
                notes="2026年获PAC-3 MSE加速生产合同。",
            )),
            ("ent-us-leidos", dict(
                name="Leidos Holdings, Inc.",
                name_zh="Leidos",
                country="United States",
                entity_type="prime_contractor",
                aliases=["Leidos", "莱多斯"],
                parent_id=None,
                defense_roles=["黑箭小型巡航导弹主承包商和系统集成商"],
                source_url=LEIDOS_BLACK_ARROW_URL,
                notes="Leidos官方确认黑箭项目和飞行测试。",
            )),
            ("ent-us-army-pac3", dict(
                name="U.S. Army PAC-3 MSE Program",
                name_zh="美国陆军PAC-3 MSE项目",
                country="United States",
                entity_type="military_end_user",
                aliases=["PAC-3 MSE", "Patriot Advanced Capability-3 MSE"],
                parent_id=None,
                defense_roles=["反导拦截弹采购和应用端"],
                source_url=MOOG_PAC3_URL,
                notes="项目与Moog作动器关系已核验。",
            )),
            ("ent-us-socom-black-arrow", dict(
                name="U.S. Special Operations Command Black Arrow Program",
                name_zh="美国特种作战司令部黑箭项目",
                country="United States",
                entity_type="military_end_user",
                aliases=["USSOCOM", "Black Arrow SCM", "AGM-190A"],
                parent_id=None,
                defense_roles=["小型巡航导弹需求和应用端"],
                source_url=MOOG_BLACK_ARROW_URL,
                notes="Moog和Leidos公开材料确认项目关系。",
            )),
        ]
        for entity_id, values in entities:
            upsert(db, SupplyChainEntity, entity_id, **values)
        db.flush()

        cases = [
            ("case-us-moog-pac3-actuator", dict(
                country="United States",
                title="Moog为PAC-3 MSE提供定制机电作动器",
                procurement_agency="Lockheed Martin / U.S. Army",
                procurement_reference="Moog PAC-3 MSE actuator award",
                procurement_date=dt("2025-01-29"),
                supplier_entity_id="ent-us-moog-inc",
                product="定制机电作动器",
                target_program="PAC-3 MSE",
                contract_value=100_000_000,
                currency="USD",
                source_url=MOOG_PAC3_URL,
                source_excerpt="Moog被Lockheed Martin选中，为PAC-3 MSE提供定制作动器，合同价值超过1亿美元。",
                status="verified",
            )),
            ("case-us-moog-black-arrow-cas", dict(
                country="United States",
                title="Moog向Leidos黑箭巡航导弹交付翼面控制作动系统",
                procurement_agency="Leidos / USSOCOM",
                procurement_reference="Black Arrow SCM CAS",
                procurement_date=dt("2025-05-07"),
                supplier_entity_id="ent-us-moog-inc",
                product="翼面控制作动系统（CAS）",
                target_program="Black Arrow Small Cruise Missile / AGM-190A",
                contract_value=None,
                currency="USD",
                source_url=MOOG_BLACK_ARROW_URL,
                source_excerpt="Moog确认已向Leidos交付定制翼面控制作动系统，用于黑箭小型巡航导弹。",
                status="verified",
            )),
        ]
        for case_id, values in cases:
            upsert(db, SupplyChainCase, case_id, **values)
        db.flush()

        shipments = [
            ("shp-tianhe-moog-20260430", dict(
                exporter_name="包头天和磁材科技股份有限公司",
                exporter_country="China",
                importer_entity_id="ent-us-moog-inc",
                importer_name="Moog Inc.",
                product="稀土永磁体",
                hs_code=None,
                shipment_date=dt("2026-04-30"),
                weight_kg=4803,
                quantity=None,
                quantity_unit="kg",
                origin_country="China",
                destination_country="United States",
                bill_no=None,
                source_name="报告引用的国际海关提单数据",
                source_url=REPORT_URI,
                raw_record={"verification": "待原始提单复核", "report_claim": "中国直发"},
            )),
            ("shp-tianhe-moog-20260504", dict(
                exporter_name="包头天和磁材科技股份有限公司",
                exporter_country="China",
                importer_entity_id="ent-us-moog-inc",
                importer_name="Moog Inc.",
                product="稀土永磁体",
                hs_code=None,
                shipment_date=dt("2026-05-04"),
                weight_kg=2389,
                quantity=None,
                quantity_unit="kg",
                origin_country="South Korea",
                destination_country="United States",
                bill_no=None,
                source_name="报告引用的国际海关提单数据",
                source_url=REPORT_URI,
                raw_record={"verification": "待原始提单复核", "route": "经韩国釜山", "reported_exporter_country": "China"},
            )),
            ("shp-tianhe-moog-20260319-0504-aggregate", dict(
                exporter_name="包头天和磁材科技股份有限公司",
                exporter_country="China",
                importer_entity_id="ent-us-moog-inc",
                importer_name="Moog Inc.",
                product="稀土永磁体（8票期间汇总，包含两票明细）",
                hs_code=None,
                shipment_date=dt("2026-03-19"),
                weight_kg=26500,
                quantity=8,
                quantity_unit="shipments",
                origin_country="China",
                destination_country="United States",
                bill_no=None,
                source_name="报告引用的国际海关提单数据",
                source_url=REPORT_URI,
                raw_record={"period_end": "2026-05-04", "direct_from_china": 7, "via_korea": 1, "verification": "期间汇总，不与明细重复计重"},
            )),
        ]
        for shipment_id, values in shipments:
            upsert(db, SupplyChainShipment, shipment_id, **values)

        evidence_rows = [
            ("ose-moog-tianhe-source-report", dict(
                case_id=None,
                title="天和磁材向Moog出口稀土永磁体供应链研究报告",
                source_type="research_report",
                source_publisher="供应链穿透研究",
                source_url=REPORT_URI,
                source_excerpt="报告汇总2026年3月19日至5月4日天和磁材向Moog发运8票稀土永磁体、总毛重约2.65万千克的记录。",
                verified_facts=["报告列明出口商、进口商、品名、期间和汇总重量", "其中4月30日和5月4日两票具有明确日期和重量"],
                evidence_grade="B",
                status="follow_up",
                limitations=["未附原始提单号和逐票截图", "提单未披露材料元素含量、磁体牌号或最终用途", "不能证明具体批次进入PAC-3或黑箭生产"],
            )),
            ("ose-moog-pac3-official", dict(
                case_id="case-us-moog-pac3-actuator",
                title="Moog确认PAC-3 MSE作动器合同",
                source_type="company_disclosure",
                source_publisher="Moog Inc.",
                source_url=MOOG_PAC3_URL,
                source_excerpt="Moog被Lockheed Martin选中，为美国陆军PAC-3 MSE提供定制机电作动器，合同价值超过1亿美元。",
                verified_facts=["Moog是PAC-3 MSE作动器供应商", "作动器用于导弹精确转向", "生产地点为犹他州盐湖城"],
                evidence_grade="A",
                status="verified",
                limitations=["未披露作动器物料清单和磁体供应商"],
            )),
            ("ose-lockheed-pac3-2026-acceleration", dict(
                case_id="case-us-moog-pac3-actuator",
                title="Lockheed Martin确认2026年PAC-3 MSE加速生产合同",
                source_type="company_disclosure",
                source_publisher="Lockheed Martin",
                source_url=LOCKHEED_PAC3_URL,
                source_excerpt="2026年4月10日，Lockheed Martin宣布获得47亿美元PAC-3 MSE加速生产合同安排。",
                verified_facts=["合同金额47亿美元", "合同用于加速PAC-3 MSE生产", "项目面向美国及盟友"],
                evidence_grade="A",
                status="verified",
                limitations=["不能据此证明天和磁材特定批次被用于该合同"],
            )),
            ("ose-moog-black-arrow-official", dict(
                case_id="case-us-moog-black-arrow-cas",
                title="Moog确认向Leidos黑箭项目交付翼面控制作动系统",
                source_type="company_disclosure",
                source_publisher="Moog Inc.",
                source_url=MOOG_BLACK_ARROW_URL,
                source_excerpt="Moog开发并向Leidos交付黑箭小型巡航导弹定制翼面控制作动系统。",
                verified_facts=["Moog为黑箭提供CAS", "Leidos将CAS集成进黑箭", "项目服务美国特种作战司令部需求"],
                evidence_grade="A",
                status="verified",
                limitations=["未披露CAS电机磁体的材料来源和批次"],
            )),
            ("ose-tianhe-product-system", dict(
                case_id=None,
                title="天和磁材年报确认稀土永磁产品体系",
                source_type="company_disclosure",
                source_publisher="包头天和磁材科技股份有限公司",
                source_url=TIANHE_REPORT_URL,
                source_excerpt="公司年报确认主营烧结钕铁硼和烧结钐钴等高性能稀土永磁材料。",
                verified_facts=["天和磁材生产烧结钕铁硼", "天和磁材生产烧结钐钴", "公司存在较大规模境外销售"],
                evidence_grade="A",
                status="verified",
                limitations=["年报未披露Moog客户名称或相关磁体具体牌号"],
            )),
        ]
        for evidence_id, values in evidence_rows:
            upsert(db, SupplyChainOpenSourceEvidence, evidence_id, **values)

        content = docx_text(REPORT_PATH)
        summary = (
            "报告识别出天和磁材向Moog供应稀土永磁体的贸易关系，以及Moog向Lockheed Martin PAC-3 MSE和"
            "Leidos黑箭巡航导弹提供作动系统的军工关系。现有证据能够分别证明上游贸易和下游项目，但尚缺"
            "物料清单、磁体牌号、生产领料或批次追踪文件，不能认定特定中国来源磁体已经进入具体导弹。"
        )
        upsert(
            db,
            SupplyChainReport,
            REPORT_ID,
            country="United States",
            title="天和磁材—Moog导弹作动系统供应链穿透分析",
            case_ids=[case_id for case_id, _ in cases],
            evidence_ids=[evidence_id for evidence_id, _ in evidence_rows],
            model_id="source-report-import-with-evidence-boundary",
            status="completed",
            content=content,
            summary=summary,
            error_log=None,
            generated_at=datetime.now(timezone.utc),
        )

        upsert(
            db,
            SupplyChainInvestigation,
            INVESTIGATION_ID,
            country="United States",
            name="天和磁材—Moog导弹作动系统供应链",
            description=(
                "包头天和磁材科技股份有限公司向Moog供应稀土永磁体；Moog分别向Lockheed Martin的PAC-3 MSE"
                "和Leidos的黑箭小型巡航导弹提供机电/翼面控制作动系统。贸易端和军工项目端均有证据，"
                "但尚缺批次级材料追踪，当前应定性为高价值关联线索而非最终用途闭环。"
            ),
            status="active",
            entity_ids=[entity_id for entity_id, _ in entities],
            case_ids=[case_id for case_id, _ in cases],
            shipment_ids=[shipment_id for shipment_id, _ in shipments],
            evidence_ids=[],
            open_source_evidence_ids=[evidence_id for evidence_id, _ in evidence_rows],
            report_ids=[REPORT_ID],
        )

        db.commit()
        print(f"Imported {INVESTIGATION_ID}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
