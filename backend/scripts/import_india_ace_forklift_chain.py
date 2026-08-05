"""Import the India ACE forklift and Chinese sourcing investigation.

The import is idempotent and keeps the verified corporate-level overlap
separate from the still-unverified claim that Chinese parts entered RTFLTs.
"""
from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainCase, SupplyChainEntity, SupplyChainEvidence,
    SupplyChainInvestigation, SupplyChainOpenSourceEvidence,
    SupplyChainReport, SupplyChainShipment,
)

REPORT_PATH = Path(r"D:\codex\供应链穿透\印度ACE进口叉车及零部件供应链分析.docx")
INVESTIGATION_ID = "inv-india-ace-rtflt-china-sourcing"
ACE_RELEASE = "https://www.ace-cranes.com/public/front/pdf/Press%20Release_20.02.2025.pdf"
MOD_RELEASE = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2104951"
MOD_AON_RELEASE = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1831550&lang=2&reg=3"
ACE_TRANSCRIPT = "https://www.ace-cranes.com/public/front/pdf/TRANSCRIPT%20CONCALL%20_27.05.2025.pdf"
ACE_AF80D_BROCHURE = "https://www.ace-cranes.com/images/productimage/ebrochure/175327248520250723.pdf"
NBD_ACE_TRADE = "https://en.nbd.ltd/trader/info/NBDD3Y529728152"
TRADE_SOURCE = "https://data.tradesparq.com/shipments/search"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    rows = []
    for paragraph in root.findall(".//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
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


def main():
    if not REPORT_PATH.exists():
        raise FileNotFoundError(REPORT_PATH)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        entities = {
            "ent-india-ace": dict(name="Action Construction Equipment Limited", name_zh="印度ACE工程机械公司", country="India", entity_type="defense_supplier", aliases=["ACE", "ACE Limited"], parent_id=None, defense_roles=["粗糙地形叉车制造商", "印度三军后勤装备承包商"], source_url=ACE_RELEASE, notes="获得印度国防部1121台粗糙地形叉车合同，同时持续采购中国来源叉车整机、传动总成和仓储搬运设备。"),
            "ent-india-mod-rtflt": dict(name="Ministry of Defence, Government of India", name_zh="印度国防部", country="India", entity_type="military_end_user", aliases=["Indian MoD"], parent_id=None, defense_roles=["1868台粗糙地形叉车采购机关", "印度陆海空三军后勤保障"], source_url=ACE_RELEASE, notes="ACE承担其中60%份额，即1121台及其属具和附件。"),
            "ent-china-ace-forklift-parts": dict(name="Undisclosed Chinese Forklift Component Suppliers", name_zh="中国叉车零部件供应商（待识别）", country="China", entity_type="component_supplier", aliases=[], parent_id=None, defense_roles=["变速箱、驱动桥及叉车配套总成供应"], source_url=TRADE_SOURCE, notes="公开贸易记录未完整披露企业名称，需通过提单和ACE采购料号继续识别。"),
            "ent-china-jac-heavy-duty-export": dict(name="JAC Heavy Duty Import and Export Co., Ltd.", name_zh="江淮重型进出口有限公司", country="China", entity_type="china_exporter", aliases=["JAC Heavy Duty"], parent_id=None, defense_roles=["AF80D型8吨级叉车出口商"], source_url=TRADE_SOURCE, notes="2025年7月向ACE出口1台AF80D型叉车；该产品与军方RTFLT不是同一已核实型号。"),
            "ent-china-ace-warehouse-equipment": dict(name="Undisclosed Chinese Material Handling Equipment Supplier", name_zh="中国仓储搬运设备供应商（待识别）", country="China", entity_type="component_supplier", aliases=[], parent_id=None, defense_roles=["电动托盘搬运车和电动堆垛车供应"], source_url=TRADE_SOURCE, notes="公开页面仅显示C***，相关设备用于仓储物流，不能直接认定为军用叉车部件。"),
        }
        for entity_id, values in entities.items():
            upsert(db, SupplyChainEntity, entity_id, **values)
        db.flush()

        case_id = "case-india-ace-1121-rtflt"
        upsert(db, SupplyChainCase, case_id, country="India", title="印度国防部采购ACE 1121台粗糙地形叉车", procurement_agency="印度国防部", procurement_reference="ACE Press Release 20.02.2025", procurement_date=dt("2025-02-20T00:00:00"), supplier_entity_id="ent-india-ace", product="1121台粗糙地形叉车、属具及配套附件", target_program="印度陆军、空军和海军后勤装备保障", contract_value=4200000000.0, currency="INR", source_url=ACE_RELEASE, source_excerpt="印度国防部采购1868台RTFLT，ACE取得60%份额并交付1121台，合同价值42亿卢比。", status="verified")
        db.flush()

        shipment_specs = [
            ("shp-ace-af80d-china-20250212", "Undisclosed Chinese Forklift Supplier", "AF80D型8吨级集装箱叉车，液压系统、充气轮胎、1220毫米货叉", "84272090", "2025-02-12", 1, "台", "complete_equipment"),
            ("shp-ace-transmissions-china-20250228", "Undisclosed Chinese Forklift Component Suppliers", "YQX30A、JDS30II-3、YQX45IIH、DCS25H5型叉车变速箱", "84312010", "2025-02-28", None, None, "candidate_component"),
            ("shp-ace-drive-axle-china-20250228", "Undisclosed Chinese Forklift Component Suppliers", "100000L型叉车驱动桥", "84312010", "2025-02-28", None, None, "candidate_component"),
            ("shp-ace-jac-af80d-20250710", "JAC Heavy Duty Import and Export Co., Ltd.", "AF80D型8吨级集装箱叉车，实心轮胎、1220毫米货叉", "84272090", "2025-07-10", 1, "台", "complete_equipment"),
            ("shp-ace-pallet-truck-20260227", "Undisclosed Chinese Material Handling Equipment Supplier", "SL25GA/RPT25W及SL20GA/RPT20N、RPT20W电动托盘搬运车", "84279000", "2026-02-27", 9, "套", "factory_logistics"),
            ("shp-ace-stacker-20260227", "Undisclosed Chinese Material Handling Equipment Supplier", "CL1545GA/ES15型1.5吨电动堆垛车", "84279000", "2026-02-27", 3, "套", "factory_logistics"),
        ]
        shipment_ids, evidence_ids = [], []
        for shipment_id, exporter, product, hs_code, date, quantity, unit, relation in shipment_specs:
            exporter_id = "ent-china-jac-heavy-duty-export" if "JAC" in exporter else "ent-china-ace-warehouse-equipment" if relation == "factory_logistics" else "ent-china-ace-forklift-parts"
            upsert(db, SupplyChainShipment, shipment_id, exporter_name=exporter, exporter_country="China", importer_entity_id="ent-india-ace", importer_name="Action Construction Equipment Limited", product=product, hs_code=hs_code, shipment_date=dt(f"{date}T00:00:00"), weight_kg=None, quantity=quantity, quantity_unit=unit, origin_country="China", destination_country="India", bill_no=None, source_name="公开贸易记录（报告汇总）", source_url=TRADE_SOURCE, raw_record={"exporter_entity_id": exporter_id, "source_report": str(REPORT_PATH)})
            # Evidence rows reference shipments by foreign key, so persist each
            # shipment before creating its evidence link.
            db.flush()
            evidence_id = f"ev-{shipment_id.removeprefix('shp-')}"
            score = 52 if relation == "candidate_component" else 42 if relation == "complete_equipment" else 30
            reasoning = "变速箱和驱动桥属于叉车关键总成，且进口发生在军方合同签订后；但ACE管理层明确将军方RTFLT称为telehandler，YQX30A/JDS30系列公开适配信息又主要指向约3吨级传统叉车，存在产品形态和吨位错配，尚无BOM、料号或领用记录证明装机。" if relation == "candidate_component" else "记录证明ACE在军方合同期内持续采购中国叉车产业链产品，但AF80D为8吨平衡重叉车，仓储搬运设备则用于厂内物流，均与ACE管理层所称军方telehandler不是同一已核实产品。"
            upsert(db, SupplyChainEvidence, evidence_id, case_id=case_id, shipment_id=shipment_id, relation_type=relation, evidence_grade="B" if relation == "candidate_component" else "C", score=score, status="follow_up", reasoning=reasoning, verified_facts=["ACE为进口商", f"原产国为中国，进口日期为{date}", product], model_review={"reviewed": True, "decision": "follow_up", "boundary": "corporate_level_overlap"}, is_reportable=True)
            shipment_ids.append(shipment_id)
            evidence_ids.append(evidence_id)

        open_ids = [
            "ose-india-ace-rtflt-contract", "ose-india-ace-china-trade-report",
            "ose-india-ace-mod-buy-indian", "ose-india-ace-mod-aon",
            "ose-india-ace-telehandler-transcript", "ose-india-ace-af80d-spec",
            "ose-india-ace-nbd-trade",
        ]
        upsert(db, SupplyChainOpenSourceEvidence, open_ids[0], case_id=case_id, title="ACE获印度国防部1121台粗糙地形叉车合同", source_type="company_disclosure", source_publisher="Action Construction Equipment Limited", source_url=ACE_RELEASE, source_excerpt="ACE获得印度国防部42亿卢比合同，为印度陆海空三军交付1121台RTFLT及附件。", verified_facts=["合同日期、金额、数量和三军最终用户可核验", "ACE明确称RTFLT为关键任务资产"], evidence_grade="A", status="verified", limitations=["公告未公开具体物料清单和零部件来源"])
        upsert(db, SupplyChainOpenSourceEvidence, open_ids[1], case_id=case_id, title="ACE中国来源叉车及零部件贸易记录汇总", source_type="research_report", source_publisher="供应链穿透研究", source_url=TRADE_SOURCE, source_excerpt="报告汇总2025至2026年ACE进口中国来源叉车整机、变速箱、驱动桥及仓储搬运设备的记录。", verified_facts=["进口商、日期、产品型号、HS编码和原产国可核验"], evidence_grade="B", status="follow_up", limitations=["部分中国供应商名称被脱敏", "缺少军用RTFLT物料清单、生产领料和验收记录"])
        upsert(db, SupplyChainOpenSourceEvidence, open_ids[2], case_id=case_id, title="印度国防部确认RTFLT为Buy (Indian)采购", source_type="official_document", source_publisher="印度新闻信息局/印度国防部", source_url=MOD_RELEASE, source_excerpt="印度国防部确认采购1868台RTFLT，总额69.735亿卢比，用于陆海空三军，并明确该项目属于Buy (Indian)类别。", verified_facts=["合同总量1868台", "合同总额69.735亿卢比", "最终用户为印度陆军、空军和海军", "采购类别为Buy (Indian)"], evidence_grade="A", status="verified", limitations=["公告未披露国产化比例、分系统供应商和BOM"])
        upsert(db, SupplyChainOpenSourceEvidence, open_ids[3], case_id=case_id, title="印度国防采办委员会批准从国内来源采购RTFLT", source_type="official_document", source_publisher="印度新闻信息局/印度国防部", source_url=MOD_AON_RELEASE, source_excerpt="2022年采办必要性批准要求RTFLT通过国内来源采购，并强调本土设计与开发。", verified_facts=["RTFLT项目在2022年获得采购必要性批准", "政策方向强调国内来源和本土设计开发"], evidence_grade="A", status="verified", limitations=["政策口径不能单独证明所有零部件均为印度原产"])
        upsert(db, SupplyChainOpenSourceEvidence, open_ids[4], case_id=case_id, title="ACE管理层确认军方RTFLT实为telehandler", source_type="company_disclosure", source_publisher="Action Construction Equipment Limited", source_url=ACE_TRANSCRIPT, source_excerpt="ACE管理层在2025年5月业绩电话会上表示，1121台设备是公司所称的telehandlers，军方称其为RTFLT。", verified_facts=["1121台合同与此前约1800台telehandler招标为同一项目", "军方RTFLT在ACE产品口径中属于telehandler"], evidence_grade="A", status="verified", limitations=["电话会未披露具体型号、吨位、动力总成和零部件清单"])
        upsert(db, SupplyChainOpenSourceEvidence, open_ids[5], case_id=case_id, title="ACE AF80D为8吨平衡重柴油叉车", source_type="company_disclosure", source_publisher="Action Construction Equipment Limited", source_url=ACE_AF80D_BROCHURE, source_excerpt="ACE官方样本显示AF80D额定载荷8吨、标准门架3米、2前进/2后退档，属于传统平衡重柴油叉车。", verified_facts=["AF80D额定载荷8吨", "AF80D采用门架和货叉结构", "官方样本未将AF80D标为telehandler或RTFLT"], evidence_grade="A", status="verified", limitations=["不能仅凭产品名称排除军方采购存在定制变型"])
        upsert(db, SupplyChainOpenSourceEvidence, open_ids[6], case_id=case_id, title="第三方海关数据库确认ACE持续进口中国仓储搬运设备", source_type="trade_database", source_publisher="NBD Trade Data", source_url=NBD_ACE_TRADE, source_excerpt="公开页面列示ACE于2026年2月27日从中国进口RPT25W、RPT20N、RPT20W托盘车及ES15堆垛车。", verified_facts=["进口日期为2026-02-27", "原产/贸易地区为中国", "公开列示型号和数量与研究报告相互印证"], evidence_grade="B", status="verified", limitations=["供应商名称被脱敏", "设备属于仓储搬运类别，不能证明进入军用RTFLT"])

        report_id = "report-india-ace-rtflt-china-sourcing"
        summary = "ACE获得印度国防部1121台RTFLT合同后，仍持续从中国进口叉车变速箱、驱动桥、AF80D整机和仓储搬运设备。深度核验同时发现，ACE管理层将军方RTFLT称为telehandler，而YQX30A/JDS30系列主要适配约3吨级传统叉车，AF80D也属于8吨平衡重叉车。现阶段可确认中国供应链进入ACE企业生产经营体系，但具体中国部件装入印度三军RTFLT的判断缺少BOM、料号、生产领用和军方验收记录。"
        research_update = """\n\n深度核验补充（2026年8月）\n\n一、强关联证据\n1. 印度国防部确认采购1868台RTFLT，用于陆军、空军和海军，项目属于Buy (Indian)采购；ACE确认获得其中1121台、金额42亿卢比。\n2. 海关贸易记录显示，ACE在合同签订后继续从中国进口叉车变速箱、驱动桥、AF80D整机及仓储搬运设备。\n\n二、重要反向证据\n1. ACE管理层明确称1121台军方设备实为telehandlers，军方口径称RTFLT。\n2. YQX30A/JDS30系列公开适配信息主要指向约3吨级传统平衡重叉车；ACE官方AF80D则为8吨门架式平衡重叉车。两类产品与telehandler存在结构和应用差异。\n3. Buy (Indian)及国内来源要求提高了直接使用进口成套关键系统的合规门槛，但不等同于绝对禁止使用所有进口零部件。\n\n三、当前结论\n现有证据支持“ACE军方合同期内仍存在中国叉车产业链依赖”的企业层面关联，不足以支持“已确认中国变速箱、驱动桥或AF80D整机进入1121台军用RTFLT”的装机结论。后续应优先获取RTFLT具体型号与吨位、BOM/AVL、零件号映射、产线领料记录、分批交付序列号及军方验收资料。\n"""
        upsert(db, SupplyChainReport, report_id, country="India", title="印度ACE军用粗糙地形叉车供应链分析", case_ids=[case_id], evidence_ids=evidence_ids, model_id="manual-verified-import", status="completed", content=docx_text(REPORT_PATH) + research_update, summary=summary, error_log=None, generated_at=datetime.now(timezone.utc))
        upsert(db, SupplyChainInvestigation, INVESTIGATION_ID, country="India", name="ACE军用粗糙地形叉车供应链", description="印度国防部以Buy (Indian)方式采购1868台RTFLT，ACE承担1121台；ACE管理层称该装备实为telehandler。合同期内ACE仍自华采购传统叉车整机、变速箱、驱动桥和仓储搬运设备，但现有型号存在产品形态或吨位错配，只能确认企业生产体系层面的中国供应链交叉，具体装机仍待BOM、料号、领用和验收记录核验。", status="researching", entity_ids=list(entities), case_ids=[case_id], shipment_ids=shipment_ids, evidence_ids=evidence_ids, open_source_evidence_ids=open_ids, report_ids=[report_id])
        db.commit()
        print("Imported ACE RTFLT investigation with 1 case, 6 shipment groups and 6 evidence links.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
