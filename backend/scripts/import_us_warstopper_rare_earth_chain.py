"""Import the identified eight-company US warstopper rare-earth chain."""
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
    SupplyChainReport,
    SupplyChainShipment,
)


DOCX_SIZE = 222946
INVESTIGATION_ID = "inv-us-warstopper-rare-earth"
TARGET_INVESTIGATION_ID = "inv-us-gadolinium-oxide"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def find_report() -> Path:
    candidates = [p for p in Path(r"D:\codex").rglob("*.docx") if p.stat().st_size == DOCX_SIZE]
    if not candidates:
        raise FileNotFoundError("Warstopper rare-earth report was not found")
    return next((p for p in candidates if p.parent.name == "供应链穿透"), candidates[0])


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.findall(".//w:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


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


def main():
    report_path = find_report()
    content = docx_text(report_path)
    source_ref = str(report_path)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        entities = [
            ("ent-ge-chaplin", "G.E. Chaplin, Inc.", "G.E. Chaplin公司", "United States", "importer",
             ["DLA国家国防储备合同供应商", "CREaTe稀土技术联盟成员"],
             "企业性质、DLA储备合同、CREaTe成员身份及2026年进口记录相互吻合。"),
            ("ent-sichuan-wonaixi", "Sichuan Wo Nai Xi New Materials Technology Co., Ltd.",
             "四川沃耐稀新材料科技有限公司", "China", "china_exporter",
             ["高纯稀土产品出口商"], "2026年4月21日向G.E. Chaplin发运20,060千克氯化镧。"),
            ("ent-jiangsu-nonferrous-ie", "Jiangsu Nonferrous Metals I/E Corp.",
             "江苏省有色金属进出口有限公司", "China", "china_exporter",
             ["稀土及有色金属出口商"], "2026年6月28日向G.E. Chaplin发运10,050千克氧化镱。"),
            ("ent-baotou-steel-rare-earth-export", "Inner Mongolia Baotou Steel Rare Earth",
             "内蒙古包钢稀土相关出口主体", "China", "china_exporter",
             ["稀土产品出口节点"], "提单名称为Inner Mongolia Baotou Steel Rare Earth；2026年7月1日到港60,240千克氧化镧。"),
            ("ent-fujian-golden-dragon", "Fujian Golden Dragon Rare-Earth Co., Ltd.",
             "福建省金龙稀土股份有限公司", "China", "china_exporter",
             ["受控氧化钆出口商"], "22,340千克氧化钆提单发货人，主体对应可信度很高。"),
            ("ent-c5-warehousing", "C5 Warehousing and Logistics LLC",
             "C5仓储与物流公司", "United States", "warehouse",
             ["受控氧化钆美国收货仓储节点"], "地址、G.E. Chaplin荷兰子公司发货记录和氧化钆收货记录一致。"),
            ("ent-changsha-fengyuan", "Changsha Fengyuan Import and Export Trading Co., Ltd.",
             "长沙丰园进出口贸易有限公司", "China", "china_exporter",
             ["氧化钇出口许可证违规案件当事人"], "厦门海关公布的氧化钇违法出口案当事人。"),
            ("ent-rare-earth-salts", "Rare Earth Salts Separations & Refining LLC",
             "Rare Earth Salts公司", "United States", "defense_supplier",
             ["美国国防生产法关键稀土项目承接方"], "2024年获美国国防部422万美元资金扩大氧化铽产能；管理人员与G.E. Chaplin存在交叉关联。"),
        ]
        entity_ids = []
        for row_id, name, name_zh, country, entity_type, roles, notes in entities:
            parent_id = None
            upsert(
                db, SupplyChainEntity, row_id, name=name, name_zh=name_zh,
                country=country, entity_type=entity_type, aliases=[],
                parent_id=parent_id, defense_roles=roles, source_url=None,
                notes=f"主体识别可信度：很高。{notes} 来源报告：{source_ref}",
            )
            entity_ids.append(row_id)
        db.flush()

        cases = [
            (
                "case-dla-warstopper-samarium-gadolinium",
                "美国DLA钐钆战时保障项目信息征询",
                "美国国防后勤局",
                "Samarium and Gadolinium RFI—Warstopper",
                "2026-07-14",
                None,
                "钐、钆需求、库存、交付周期及氧化物还原和合金化能力",
                "美国战时关键稀土供应保障评估",
                "信息征询不是授予合同，但表明美国正将钐、钆纳入战时供应保障评估。",
            ),
            (
                "case-ge-chaplin-dla-stockpile",
                "G.E. Chaplin承接美国国家国防储备稀土合同",
                "美国国防后勤局",
                "DLA Strategic Materials contracts",
                "2023-09-26",
                "ent-ge-chaplin",
                "碳酸铈、氧化钕和氧化镨等稀土产品",
                "美国国家国防储备供应链",
                "历史合同已结束，但证明该企业曾直接进入DLA国家国防储备采购体系。",
            ),
            (
                "case-rare-earth-salts-dpa-terbium",
                "美国国防部支持Rare Earth Salts扩大氧化铽产能",
                "美国国防部",
                "Defense Production Act investment",
                "2024-01-01",
                "ent-rare-earth-salts",
                "氧化铽分离与精炼产能",
                "美国本土关键稀土供应链建设",
                "美国国防部提供422万美元资金；管理人员交叉关联强化了G.E. Chaplin与美国防务稀土网络的联系。",
            ),
        ]
        case_ids = []
        for row in cases:
            row_id, title, agency, ref, date, supplier, product, program, excerpt = row
            upsert(
                db, SupplyChainCase, row_id, country="United States", title=title,
                procurement_agency=agency, procurement_reference=ref,
                procurement_date=dt(date), supplier_entity_id=supplier,
                product=product, target_program=program, contract_value=None,
                currency="USD", source_url=None, source_excerpt=excerpt,
                status="monitoring",
            )
            case_ids.append(row_id)
        db.flush()

        shipments = [
            ("shp-wonaixi-gec-lacl3-20260421", "Sichuan Wo Nai Xi New Materials Technology Co., Ltd.",
             "ent-ge-chaplin", "G.E. Chaplin, Inc.", "氯化镧", "2026-04-21", 20060, None),
            ("shp-jiangsu-gec-yb2o3-20260628", "Jiangsu Nonferrous Metals I/E Corp.",
             "ent-ge-chaplin", "G.E. Chaplin, Inc.", "氧化镱", "2026-06-28", 10050, None),
            ("shp-baotou-gec-la2o3-20260701", "Inner Mongolia Baotou Steel Rare Earth",
             "ent-ge-chaplin", "G.E. Chaplin, Inc.", "氧化镧", "2026-07-01", 60240, "经韩国釜山装船或中转"),
            ("shp-golden-dragon-c5-gd2o3-202603", "Fujian Golden Dragon Rare-Earth Co., Ltd.",
             "ent-c5-warehousing", "C5 Warehousing and Logistics LLC", "受控氧化钆", "2026-03-01", 22340, "40件，原产国中国"),
            ("shp-gec-nl-c5-rare-earth-20260215", "G.E. Chaplin B.V.",
             "ent-c5-warehousing", "C5 Warehousing and Logistics LLC", "稀土氧化物", "2026-02-15", None, "G.E. Chaplin海外子公司发运"),
            ("shp-golden-dragon-gec-y2o3-202510", "Fujian Golden Dragon Rare-Earth Co., Ltd.",
             "ent-ge-chaplin", "G.E. Chaplin, Inc.", "氧化钇", "2025-10-01", 3351, None),
        ]
        shipment_ids = []
        for row in shipments:
            row_id, exporter, importer_id, importer, product, date, weight, note = row
            upsert(
                db, SupplyChainShipment, row_id, exporter_name=exporter,
                exporter_country="China" if "G.E. Chaplin B.V." not in exporter else "Netherlands",
                importer_entity_id=importer_id, importer_name=importer,
                product=product, hs_code=None, shipment_date=dt(date),
                weight_kg=weight, quantity=None, quantity_unit=None,
                origin_country="China" if "G.E. Chaplin B.V." not in exporter else "Netherlands",
                destination_country="United States", bill_no=None,
                source_name="报告所载公开贸易/提单记录", source_url=None,
                raw_record={"note": note, "source_document": source_ref},
            )
            shipment_ids.append(row_id)
        db.flush()

        evidence_ids = []
        for index, shipment_id in enumerate(shipment_ids):
            gadolinium = shipment_id == "shp-golden-dragon-c5-gd2o3-202603"
            case_id = (
                "case-dla-warstopper-samarium-gadolinium"
                if gadolinium else "case-ge-chaplin-dla-stockpile"
            )
            evidence_id = f"evd-warstopper-{index + 1:02d}"
            upsert(
                db, SupplyChainEvidence, evidence_id, case_id=case_id,
                shipment_id=shipment_id, relation_type="possible_supply",
                evidence_grade="B" if gadolinium else "B",
                score=76 if gadolinium else 68, status="approved",
                reasoning=(
                    "22,340千克受控氧化钆由福建金龙稀土发运并由C5仓储收货，"
                    "收货节点与G.E. Chaplin存在人员和历史货物流联系；能够证明货物"
                    "进入美国防务稀土关联商业网络，但后续最终用途仍未闭环。"
                    if gadolinium else
                    "中国稀土企业向曾承接DLA国防储备合同的G.E. Chaplin持续供货，"
                    "证明中国供应渠道仍在其现实采购体系中发挥作用。"
                ),
                verified_facts={
                    "identified_entities_confidence": "very_high",
                    "trade_record_reported": True,
                    "specific_defense_end_use_verified": False,
                    "source_document": source_ref,
                },
                model_review={"method": "identified_entity_report_import"},
                is_reportable=True,
            )
            evidence_ids.append(evidence_id)

        report_id = "scr-us-warstopper-rare-earth-network"
        upsert(
            db, SupplyChainReport, report_id, country="United States",
            title="美国战时稀土保障体系及自华采购网络穿透报告",
            case_ids=case_ids, evidence_ids=evidence_ids, model_id=None,
            status="completed", content=content,
            summary=(
                "美国正通过DLA战时保障评估和《国防生产法》投资补齐钐、钆等关键稀土"
                "能力，但G.E. Chaplin等防务稀土关联主体仍持续采购中国企业产品。"
                "福建金龙稀土发运的22,340千克受控氧化钆由C5仓储收货，相关节点与"
                "G.E. Chaplin存在人员及历史货物流联系，真实买方和最终用途需继续核查。"
            ),
            error_log=None, generated_at=datetime.now(timezone.utc),
        )
        investigation = db.get(SupplyChainInvestigation, TARGET_INVESTIGATION_ID)
        if investigation is None:
            raise RuntimeError("美国高纯氧化钆供应链不存在，请先导入氧化钆报告")
        investigation.description = (
            "境内稀土企业向G.E. Chaplin及C5仓储网络供应高纯氧化钆等稀土产品，"
            "经TCI/NMG先进材料体系与DLA战时保障、美国海军通信和潜艇天线供应链"
            "形成主体、货物流及技术关联"
        )
        investigation.entity_ids = sorted(set(investigation.entity_ids or []) | set(entity_ids))
        investigation.case_ids = sorted(set(investigation.case_ids or []) | set(case_ids))
        investigation.shipment_ids = sorted(
            set(investigation.shipment_ids or []) | set(shipment_ids)
        )
        investigation.evidence_ids = sorted(
            set(investigation.evidence_ids or []) | set(evidence_ids)
        )
        investigation.report_ids = list(dict.fromkeys(
            [report_id, *(investigation.report_ids or [])]
        ))
        obsolete = db.get(SupplyChainInvestigation, INVESTIGATION_ID)
        if obsolete is not None:
            db.delete(obsolete)
        db.commit()
        print(
            f"Imported warstopper rare-earth chain: {len(entity_ids)} entities, "
            f"{len(shipment_ids)} shipments, {len(evidence_ids)} evidence links."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
