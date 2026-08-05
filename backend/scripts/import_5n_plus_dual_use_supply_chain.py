"""Import the 5N Plus China-Canada-U.S. dual-use materials investigation.

The source report contains verified corporate, trade and program-level facts,
but explicitly stops short of proving that a specific Chinese-origin shipment
entered a specific U.S. military production batch.  This import preserves that
boundary by separating verified group/trade relationships from follow-up
end-use hypotheses.
"""
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


REPORT_PATH = Path(
    r"D:\codex\供应链穿透\美拟借加拿大5N Plus集团2家在华子公司构建“两用物项”供应链通道，推动关键材料经加进入美光伏与军工领域.docx"
)
INVESTIGATION_ID = "inv-us-5n-plus-dual-use-materials"
REPORT_URI = REPORT_PATH.as_uri()
ANNUAL_REPORT = "https://www.5nplus.com/media/uploads/documents/b5n_plus_inc._-_2025_annual_report.pdf"
FIRST_SOLAR_RELEASE = "https://www.5nplus.com/en/news/5n-plus-inc-scales-up-and-expands-critical-materia/"
DOD_GERMANIUM_RELEASE = "https://www.defense.gov/News/Releases/Release/Article/3743467/dod-awards-144-million-to-sustain-and-enhance-the-space-qualified-solar-cell-su/"
GERMANIUM_EXPANSION_RELEASE = "https://www.5nplus.com/en/news/5n-awarded-us181-million/"
TELEDYNE_T3_RELEASE = "https://www.teledyne.com/en-us/news/Pages/teledyne-advances-us-national-defense-with-multiple-awards-for-sdas-tranche-3-tracking-layer-program.aspx"
USITC_1494_RELEASE = "https://www.usitc.gov/press_room/news_release/2026/er0326_68358.htm"
MOFCOM_CONTROL = "https://exportcontrol.mofcom.gov.cn/article/hgfw/lywxcx/gzqd/202502/1102.html"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    rows = []
    for paragraph in root.findall(".//w:p", NS):
        text = "".join(
            node.text or "" for node in paragraph.findall(".//w:t", NS)
        ).strip()
        if text:
            rows.append(text)
    return "\n\n".join(rows)


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
        entities = {
            "ent-ca-5n-plus": dict(
                name="5N Plus Inc.",
                name_zh="加拿大5N Plus集团",
                country="Canada",
                entity_type="integrator",
                aliases=["5N+", "TSX: VNP"],
                parent_id=None,
                defense_roles=[
                    "高纯碲、硒、铋、锗及特种半导体材料整合加工",
                    "连接中国原料节点与美国光伏、航天和红外应用",
                ],
                source_url=REPORT_URI,
                notes="集团总部位于加拿大蒙特利尔。报告识别出中国生产、香港贸易协调、加拿大加工及美国应用的跨境链路。",
            ),
            "ent-cn-5n-plus-shangyu": dict(
                name="5N Plus Shangyu Co., Ltd.",
                name_zh="5N Plus上虞有限公司",
                country="China",
                entity_type="component_supplier",
                aliases=["5N Plus Shangyu"],
                parent_id="ent-ca-5n-plus",
                defense_roles=["浙江上虞生产与出口节点", "金属碲、硒及铋材料供应"],
                source_url=ANNUAL_REPORT,
                notes="报告将其识别为5N Plus在华生产/发货主体；逐票出口主体仍应以原始提单复核。",
            ),
            "ent-hk-5n-plus-asia": dict(
                name="5N Plus Asia Limited",
                name_zh="5N Plus亚洲有限公司",
                country="Hong Kong",
                entity_type="trading_company",
                aliases=["5N Plus Asia"],
                parent_id="ent-ca-5n-plus",
                defense_roles=["合同、结算与贸易协调", "连接中国内地生产节点与北美收货体系"],
                source_url=ANNUAL_REPORT,
                notes="报告识别的香港交易组织节点；并不等同于每一票货物均以其为提单发货人。",
            ),
            "ent-us-5n-plus-wisconsin": dict(
                name="5N Plus Wisconsin Inc.",
                name_zh="5N Plus Wisconsin公司",
                country="United States",
                entity_type="downstream_processor",
                aliases=["5N Plus Wisconsin"],
                parent_id="ent-ca-5n-plus",
                defense_roles=["美国康涅狄格州布里奇波特铋材料加工", "低熔点合金及工业固定材料"],
                source_url=ANNUAL_REPORT,
                notes="报告记载2026年3批中国来源氧化铋进入该布里奇波特基地。具体军工终端用途未闭环。",
            ),
            "ent-us-5n-plus-semiconductors": dict(
                name="5N Plus Semiconductors LLC",
                name_zh="5N Plus半导体有限责任公司",
                country="United States",
                entity_type="defense_supplier",
                aliases=["5N+ Semiconductors", "5N Semi"],
                parent_id="ent-ca-5n-plus",
                defense_roles=[
                    "犹他州圣乔治高纯锗与空间级锗衬底",
                    "CZT红外探测与空间、国防关键材料",
                ],
                source_url=DOD_GERMANIUM_RELEASE,
                notes="美国国防部2024年投资支持空间级锗衬底能力；集团材料同时覆盖红外、夜视、监视与国家安全卫星应用。",
            ),
            "ent-us-first-solar": dict(
                name="First Solar, Inc.",
                name_zh="第一太阳能公司",
                country="United States",
                entity_type="industrial_end_user",
                aliases=["First Solar", "NASDAQ: FSLR"],
                parent_id=None,
                defense_roles=["CdTe/CdSe薄膜光伏组件制造", "美国本土光伏产能扩张"],
                source_url=FIRST_SOLAR_RELEASE,
                notes="5N Plus已公开扩大2025—2028年CdTe供应，并自2026年开始供应CdSe。",
            ),
            "ent-us-teledyne": dict(
                name="Teledyne Technologies Incorporated",
                name_zh="美国Teledyne技术公司",
                country="United States",
                entity_type="defense_contractor",
                aliases=["Teledyne", "NYSE: TDY"],
                parent_id=None,
                defense_roles=["红外焦平面模块与HgCdTe探测器", "SDA跟踪层第3批次项目承包商"],
                source_url=TELEDYNE_T3_RELEASE,
                notes="报告记载其与5N Plus存在CZT衬底采购和产能投资关系；公开项目材料可确认其承担SDA T3红外焦平面模块生产。",
            ),
            "ent-us-sda": dict(
                name="Space Development Agency",
                name_zh="美国太空发展局",
                country="United States",
                entity_type="government_agency",
                aliases=["SDA"],
                parent_id=None,
                defense_roles=["PWSA跟踪层", "低轨导弹预警、跟踪与防御"],
                source_url=TELEDYNE_T3_RELEASE,
                notes="Teledyne于2026年2月启动跟踪层第3批次红外焦平面模块生产。",
            ),
            "ent-us-dod": dict(
                name="U.S. Department of Defense",
                name_zh="美国国防部",
                country="United States",
                entity_type="government_agency",
                aliases=["DoD", "DOD"],
                parent_id=None,
                defense_roles=["国防工业基础投资", "空间级锗衬底供应链保障"],
                source_url=DOD_GERMANIUM_RELEASE,
                notes="2024年通过国防生产法投资项目向5N Plus Semiconductors提供1,440万美元。",
            ),
        }
        for entity_id, values in entities.items():
            upsert(db, SupplyChainEntity, entity_id, **values)
        db.flush()

        cases = {
            "case-us-5n-first-solar-critical-materials": dict(
                country="United States",
                title="5N Plus扩大向First Solar供应CdTe并新增CdSe",
                procurement_agency="First Solar, Inc.",
                procurement_reference="5N Plus supply agreement release 2025-08-05",
                procurement_date=dt("2025-08-05T00:00:00"),
                supplier_entity_id="ent-ca-5n-plus",
                product="碲化镉（CdTe）与硒化镉（CdSe）半导体材料",
                target_program="First Solar美国薄膜光伏组件产能扩张",
                contract_value=None,
                currency="USD",
                source_url=FIRST_SOLAR_RELEASE,
                source_excerpt="5N Plus将2025—2026年CdTe交付量提高33%，2027—2028年再提高25%，并自2026年开始交付CdSe。",
                status="verified",
            ),
            "case-us-5n-germanium-dpai": dict(
                country="United States",
                title="美国国防部投资5N Plus空间级锗衬底供应链",
                procurement_agency="U.S. Department of Defense",
                procurement_reference="Defense Production Act Investment, 2024-04-16",
                procurement_date=dt("2024-04-16T00:00:00"),
                supplier_entity_id="ent-us-5n-plus-semiconductors",
                product="空间级锗晶圆、锗衬底及回收精炼能力",
                target_program="商业与国家安全卫星太阳能电池供应链",
                contract_value=14_400_000,
                currency="USD",
                source_url=DOD_GERMANIUM_RELEASE,
                source_excerpt="美国国防部通过DPAI向5N Plus Semiconductors投资1,440万美元，扩建犹他州圣乔治空间级锗衬底能力。",
                status="verified",
            ),
            "case-us-5n-teledyne-sda-tranche3": dict(
                country="United States",
                title="Teledyne启动SDA跟踪层第3批次红外焦平面模块生产",
                procurement_agency="Space Development Agency",
                procurement_reference="SDA Tracking Layer Tranche 3 awards",
                procurement_date=dt("2026-02-09T00:00:00"),
                supplier_entity_id="ent-us-teledyne",
                product="红外焦平面模块；上游CZT/HgCdTe材料链",
                target_program="PWSA Tracking Layer Tranche 3导弹预警、跟踪与防御",
                contract_value=None,
                currency="USD",
                source_url=TELEDYNE_T3_RELEASE,
                source_excerpt="Teledyne宣布开始生产多项SDA T3红外焦平面模块，用于低轨导弹预警、跟踪和防御卫星。",
                status="verified",
            ),
            "case-us-5n-bismuth-processing": dict(
                country="United States",
                title="中国氧化铋进入5N Plus美国布里奇波特材料加工基地",
                procurement_agency="5N Plus集团内部供应链（非政府采购）",
                procurement_reference="2026年3批公开提单汇总（逐票编号待补）",
                procurement_date=None,
                supplier_entity_id="ent-us-5n-plus-wisconsin",
                product="氧化铋及低熔点铋合金材料",
                target_program="低熔点合金、涡轮叶片/光学镜片固定及温控安全装置等两用应用",
                contract_value=None,
                currency="USD",
                source_url=REPORT_URI,
                source_excerpt="报告汇总3批、59,430千克中国来源氧化铋进入5N Plus Wisconsin位于康涅狄格州布里奇波特的基地。",
                status="follow_up",
            ),
        }
        for case_id, values in cases.items():
            upsert(db, SupplyChainCase, case_id, **values)
        db.flush()

        shipments = {
            "shp-5n-shangyu-tellurium-2026-aggregate": dict(
                exporter_name="5N Plus Shangyu Co., Ltd.",
                exporter_country="China",
                importer_entity_id="ent-ca-5n-plus",
                importer_name="5N Plus Inc. North American system",
                product="金属碲（3批汇总，经美国港口留船/中转后进入加拿大）",
                hs_code="2804500001",
                shipment_date=None,
                weight_kg=60_904,
                quantity=3,
                quantity_unit="批",
                origin_country="China",
                destination_country="Canada",
                bill_no=None,
                source_name="研究报告汇总的公开提单记录",
                source_url=REPORT_URI,
                raw_record={
                    "period": "2026年近5个月，报告未逐票披露日期",
                    "transit": "美国港口留船/中转后进入加拿大",
                    "trade_coordinator": "5N Plus Asia Limited",
                    "source_report": str(REPORT_PATH),
                    "batch_end_use_verified": False,
                },
            ),
            "shp-5n-shangyu-bismuth-oxide-2026-aggregate": dict(
                exporter_name="5N Plus Shangyu Co., Ltd.",
                exporter_country="China",
                importer_entity_id="ent-us-5n-plus-wisconsin",
                importer_name="5N Plus Wisconsin Inc.",
                product="氧化铋（3批汇总）",
                hs_code=None,
                shipment_date=None,
                weight_kg=59_430,
                quantity=3,
                quantity_unit="批",
                origin_country="China",
                destination_country="United States",
                bill_no=None,
                source_name="研究报告汇总的公开提单记录",
                source_url=REPORT_URI,
                raw_record={
                    "destination": "Bridgeport, Connecticut",
                    "period": "2026年近5个月，报告未逐票披露日期",
                    "trade_coordinator": "5N Plus Asia Limited",
                    "source_report": str(REPORT_PATH),
                    "batch_end_use_verified": False,
                },
            ),
            "shp-5n-shangyu-selenium-2026-aggregate": dict(
                exporter_name="5N Plus Shangyu Co., Ltd.",
                exporter_country="China",
                importer_entity_id="ent-ca-5n-plus",
                importer_name="5N Plus Inc. North American system",
                product="金属硒（1批）",
                hs_code=None,
                shipment_date=None,
                weight_kg=600,
                quantity=1,
                quantity_unit="批",
                origin_country="China",
                destination_country="Canada",
                bill_no=None,
                source_name="研究报告汇总的公开提单记录",
                source_url=REPORT_URI,
                raw_record={
                    "period": "2026年近5个月，报告未逐票披露日期",
                    "trade_coordinator": "5N Plus Asia Limited",
                    "source_report": str(REPORT_PATH),
                    "batch_end_use_verified": False,
                },
            ),
        }
        for shipment_id, values in shipments.items():
            upsert(db, SupplyChainShipment, shipment_id, **values)
        db.flush()

        evidence_rows = {
            "ev-5n-tellurium-first-solar": dict(
                case_id="case-us-5n-first-solar-critical-materials",
                shipment_id="shp-5n-shangyu-tellurium-2026-aggregate",
                relation_type="possible_material_feed",
                evidence_grade="B",
                score=74,
                status="follow_up",
                reasoning="贸易记录确认3批中国金属碲进入5N Plus北美体系；公司公告确认同期扩大对First Solar的CdTe供应，报告据业务规模判断多数碲更可能进入光伏链。尚无批号、转化记录或交付单证明这3批碲具体进入First Solar。",
                verified_facts={"china_origin": True, "group_import_verified": True, "first_solar_supply_agreement_verified": True, "batch_end_use_verified": False},
                model_review={"decision": "follow_up", "boundary": "group-level overlap; no batch closure"},
                is_reportable=True,
            ),
            "ev-5n-selenium-first-solar": dict(
                case_id="case-us-5n-first-solar-critical-materials",
                shipment_id="shp-5n-shangyu-selenium-2026-aggregate",
                relation_type="possible_material_feed",
                evidence_grade="B",
                score=78,
                status="follow_up",
                reasoning="1批中国金属硒进入5N Plus北美体系，时间与5N Plus自2026年向First Solar供应CdSe的公开安排重合；但未取得该批硒的生产批次、CdSe转化或客户交付记录。",
                verified_facts={"china_origin": True, "group_import_verified": True, "cdse_supply_start_verified": True, "batch_end_use_verified": False},
                model_review={"decision": "follow_up", "boundary": "timing and material match; no batch closure"},
                is_reportable=True,
            ),
            "ev-5n-tellurium-teledyne-sda": dict(
                case_id="case-us-5n-teledyne-sda-tranche3",
                shipment_id="shp-5n-shangyu-tellurium-2026-aggregate",
                relation_type="possible_defense_supply",
                evidence_grade="C",
                score=58,
                status="follow_up",
                reasoning="报告核实5N Plus具备CZT材料业务，并记载与Teledyne存在CZT衬底采购/产能投资关系；Teledyne又于2026年2月启动SDA T3红外焦平面模块生产。首批中国碲在项目启动后13天进入集团北美体系，形成材料、企业和时间上的现实可能性，但不能证明特定碲批次进入CZT、HgCdTe探测器或SDA项目。",
                verified_facts={"china_origin": True, "group_import_verified": True, "teledyne_t3_production_verified": True, "czt_batch_conversion_verified": False, "military_program_batch_use_verified": False},
                model_review={"decision": "follow_up", "boundary": "risk hypothesis, not confirmed military end use"},
                is_reportable=True,
            ),
            "ev-5n-bismuth-bridgeport": dict(
                case_id="case-us-5n-bismuth-processing",
                shipment_id="shp-5n-shangyu-bismuth-oxide-2026-aggregate",
                relation_type="processed_supply",
                evidence_grade="B",
                score=82,
                status="verified",
                reasoning="报告汇总的公开提单可确认3批、59,430千克中国来源氧化铋进入5N Plus Wisconsin的布里奇波特基地。该基地加工铋材料及低熔点合金，但没有证据将具体批次闭环到涡轮叶片、光学镜片或其他军工终端。",
                verified_facts={"china_origin": True, "named_group_importer_verified": True, "bridgeport_destination_verified": True, "specific_end_use_verified": False},
                model_review={"decision": "verified_trade_follow_up_end_use", "boundary": "facility receipt verified; military end use not verified"},
                is_reportable=True,
            ),
        }
        for evidence_id, values in evidence_rows.items():
            upsert(db, SupplyChainEvidence, evidence_id, **values)

        open_source_rows = {
            "ose-5n-group-structure-2025": dict(
                case_id="case-us-5n-first-solar-critical-materials",
                title="5N Plus 2025年报披露集团业务与全球制造节点",
                source_type="company_disclosure",
                source_publisher="5N Plus Inc.",
                source_url=REPORT_URI,
                source_excerpt="年报用于核验集团主体、北美与亚洲运营节点，以及碲、硒、铋、锗和特种半导体材料业务。",
                verified_facts=["5N Plus为加拿大总部的特种半导体和高性能材料集团", "集团业务覆盖碲、硒、铋、锗及美国国家安全相关应用"],
                evidence_grade="A",
                status="verified",
                limitations=["年报不能替代逐票提单和客户批次流向记录"],
            ),
            "ose-5n-mofcom-tellurium-control": dict(
                case_id="case-us-5n-first-solar-critical-materials",
                title="中国对金属碲及相关碲化物实施两用物项出口管制",
                source_type="official_document",
                source_publisher="中国商务部安全与管制局",
                source_url=MOFCOM_CONTROL,
                source_excerpt="商务部2025年第10号公告将金属碲列为6C002.a，并覆盖CdTe、CZT和HgCdTe等碲化物制品。",
                verified_facts=["金属碲管制编码为6C002.a", "CdTe、CZT和HgCdTe制品纳入6C002.b"],
                evidence_grade="A",
                status="verified",
                limitations=["管制属性说明材料敏感性，不自动证明每批货物的军事最终用途"],
            ),
            "ose-5n-first-solar-agreement": dict(
                case_id="case-us-5n-first-solar-critical-materials",
                title="5N Plus扩大First Solar关键材料供应协议",
                source_type="company_disclosure",
                source_publisher="5N Plus Inc.",
                source_url=FIRST_SOLAR_RELEASE,
                source_excerpt="2025—2026年CdTe交付较初始水平增加33%，2027—2028年再增加25%，并自2026年开始交付CdSe。",
                verified_facts=["5N Plus与First Solar存在长期供应关系", "CdTe增量和CdSe起供时间可核验", "First Solar美国制造扩张为协议背景"],
                evidence_grade="A",
                status="verified",
                limitations=["公告未披露上游原料产地和批次映射"],
            ),
            "ose-5n-dod-germanium-2024": dict(
                case_id="case-us-5n-germanium-dpai",
                title="美国国防部向5N Plus Semiconductors投资1,440万美元",
                source_type="official_document",
                source_publisher="U.S. Department of Defense",
                source_url=DOD_GERMANIUM_RELEASE,
                source_excerpt="DPAI投资用于维持和扩大圣乔治空间级锗衬底制造能力，服务商业和国家安全卫星太阳能电池。",
                verified_facts=["投资金额1,440万美元", "执行地点为犹他州圣乔治", "应用包括国家安全卫星"],
                evidence_grade="A",
                status="verified",
                limitations=["项目材料为锗，不直接证明中国碲进入该项目"],
            ),
            "ose-5n-germanium-expansion-2026": dict(
                case_id="case-us-5n-germanium-dpai",
                title="5N Plus获1,810万美元扩建圣乔治锗回收精炼能力",
                source_type="company_disclosure",
                source_publisher="5N Plus Inc.",
                source_url=GERMANIUM_EXPANSION_RELEASE,
                source_excerpt="2026年美国政府资助将支持圣乔治锗回收和精炼能力，规划最终每年处理最多20吨高纯锗。",
                verified_facts=["资助金额1,810万美元", "48个月扩建周期", "目标能力最高20吨/年高纯锗"],
                evidence_grade="A",
                status="verified",
                limitations=["公开稿未披露全部客户、合同编号和具体项目分配"],
            ),
            "ose-5n-teledyne-t3-2026": dict(
                case_id="case-us-5n-teledyne-sda-tranche3",
                title="Teledyne启动SDA跟踪层第3批次红外焦平面模块生产",
                source_type="company_disclosure",
                source_publisher="Teledyne Technologies Incorporated",
                source_url=TELEDYNE_T3_RELEASE,
                source_excerpt="Teledyne于2026年2月9日宣布开始生产多项T3红外焦平面模块，服务低轨导弹预警、跟踪和防御卫星。",
                verified_facts=["项目为SDA Tracking Layer Tranche 3", "产品为红外焦平面模块", "任务包括导弹预警、跟踪和防御"],
                evidence_grade="A",
                status="verified",
                limitations=["公告没有披露5N Plus、CZT或中国碲批次"],
            ),
            "ose-5n-usitc-1494": dict(
                case_id="case-us-5n-first-solar-critical-materials",
                title="USITC对First Solar投诉启动337-TA-1494调查",
                source_type="official_document",
                source_publisher="U.S. International Trade Commission",
                source_url=USITC_1494_RELEASE,
                source_excerpt="USITC于2026年3月对TOPCon太阳能电池、组件及相关产品启动337调查，投诉人为First Solar。",
                verified_facts=["调查编号337-TA-1494", "投诉人为First Solar", "立案不代表已对实体争议作出裁决"],
                evidence_grade="A",
                status="verified",
                limitations=["贸易救济程序与5N Plus原料流向是并列背景，不能直接证明供应链分配"],
            ),
            "ose-5n-trade-aggregate-report": dict(
                case_id="case-us-5n-bismuth-processing",
                title="2026年中国来源碲、铋、硒进入5N Plus北美体系的提单汇总",
                source_type="research_report",
                source_publisher="供应链穿透研究",
                source_url=REPORT_URI,
                source_excerpt="报告汇总7批、120,934千克：3批金属碲60,904千克、3批氧化铋59,430千克、1批金属硒600千克。",
                verified_facts=["三类材料合计7批、120,934千克", "碲经美国港口中转进入加拿大", "氧化铋进入布里奇波特基地"],
                evidence_grade="B",
                status="follow_up",
                limitations=["报告未逐票披露日期、提单号和可回链数据库URL", "终端客户批次和最终用途尚未闭环"],
            ),
        }
        for evidence_id, values in open_source_rows.items():
            upsert(db, SupplyChainOpenSourceEvidence, evidence_id, **values)

        report_id = "report-us-5n-plus-dual-use-materials"
        summary = (
            "报告识别出5N Plus上虞生产、香港贸易协调、加拿大整合加工及美国光伏/军工应用的跨境链路。"
            "2026年近5个月公开提单汇总为7批、120,934千克，其中金属碲60,904千克、氧化铋59,430千克、"
            "金属硒600千克。First Solar的CdTe/CdSe供应协议、5N Plus美国锗材料国防投资及Teledyne的SDA T3"
            "红外项目均可由公开材料核验；但现有证据只能确认集团、材料、时间和项目层面的交叉，尚不能证明"
            "任一中国来源批次实际进入特定美国军工型号或项目。"
        )
        upsert(
            db,
            SupplyChainReport,
            report_id,
            country="United States",
            title="5N Plus中国—加拿大—美国两用关键材料供应链穿透报告",
            case_ids=list(cases),
            evidence_ids=list(evidence_rows),
            model_id="manual-verified-import",
            status="completed",
            content=docx_text(REPORT_PATH),
            summary=summary,
            error_log=None,
            generated_at=datetime.now(timezone.utc),
        )
        upsert(
            db,
            SupplyChainInvestigation,
            INVESTIGATION_ID,
            country="United States",
            name="5N Plus两用关键材料经加赴美供应链",
            description=(
                "5N Plus在华生产和香港贸易节点将碲、硒、铋材料导入加拿大及美国集团体系，"
                "下游连接First Solar薄膜光伏、布里奇波特铋材料加工、圣乔治空间级半导体材料和"
                "Teledyne/SDA红外导弹预警项目。已核实集团关系、7批贸易汇总和公开项目，"
                "具体中国批次进入美国军工用途仍待提单、订单、生产批号和最终用途文件闭环。"
            ),
            status="researching",
            entity_ids=list(entities),
            case_ids=list(cases),
            shipment_ids=list(shipments),
            evidence_ids=list(evidence_rows),
            open_source_evidence_ids=list(open_source_rows),
            report_ids=[report_id],
        )

        db.commit()
        print(
            {
                "investigation": INVESTIGATION_ID,
                "entities": len(entities),
                "cases": len(cases),
                "shipment_groups": len(shipments),
                "shipment_events": sum(int(row["quantity"]) for row in shipments.values()),
                "shipment_weight_kg": sum(float(row["weight_kg"]) for row in shipments.values()),
                "evidence_links": len(evidence_rows),
                "open_source_evidence": len(open_source_rows),
                "reports": 1,
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
