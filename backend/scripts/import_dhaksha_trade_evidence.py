"""Import verified China-to-Dhaksha shipment evidence from Tradesparq."""
from __future__ import annotations

from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainEntity,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
    SupplyChainShipment,
)


INVESTIGATION_ID = "inv-india-lead-dhaksha-logistics-drone"
CASE_ID = "case-india-lead-dhaksha-logistics-drone"
SOURCE_URL = "https://data.tradesparq.com/shipments/search"


def upsert(db, model, row_id, **values):
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def attach(row, field, *ids):
    values = list(getattr(row, field) or [])
    for row_id in ids:
        if row_id not in values:
            values.append(row_id)
    setattr(row, field, values)


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        investigation = db.get(SupplyChainInvestigation, INVESTIGATION_ID)
        if investigation is None:
            raise RuntimeError(f"Missing investigation: {INVESTIGATION_ID}")

        supplier_id = "ent-dhaksha-new-wing-tianjin"
        upsert(
            db,
            SupplyChainEntity,
            supplier_id,
            name="New Wing Advanced Tianjin Technology Co., Ltd.",
            name_zh="天津新翼先进科技有限公司（中文名称待工商核验）",
            country="China",
            entity_type="china_exporter",
            aliases=[
                "NEW WING ADVANCED TIANJIN TECHNOLOGY CO. LTD",
                "NEW WING ADVANCED TIANJIN TECHNOLOGY CO., LTD",
            ],
            parent_id=None,
            defense_roles=["无人机推力测试及光学检测设备供应商"],
            source_url=SOURCE_URL,
            notes=(
                "外贸公社印度进口数据将其列为Dhaksha的中国供应商；平台展示的中文名称"
                "根据英文名称暂译，正式工商登记名称仍需核验。"
            ),
        )

        importer_id = "ent-india-lead-dhaksha-logistics-drone"
        shipments = [
            (
                "shp-dhaksha-new-wing-thrust-stand-20260214",
                "LY-70KGF无人机推力测试台及EKT-VT-980离线AOI检测设备",
                5435.44,
            ),
            (
                "shp-dhaksha-new-wing-calibration-20260214",
                "推力测试台校准工具及EKT-VT-980离线AOI检测设备",
                1698.58,
            ),
        ]
        shipment_ids = []
        for shipment_id, product, amount_usd in shipments:
            upsert(
                db,
                SupplyChainShipment,
                shipment_id,
                exporter_name="New Wing Advanced Tianjin Technology Co., Ltd.",
                exporter_country="China",
                importer_entity_id=importer_id,
                importer_name="Dhaksha Unmanned Systems Private Limited",
                product=product,
                hs_code="90314900",
                shipment_date=datetime(2026, 2, 14, tzinfo=timezone.utc),
                weight_kg=None,
                quantity=1,
                quantity_unit="unit",
                origin_country="China",
                destination_country="India",
                bill_no="LQ6DBGURERWY4",
                source_name="外贸公社印度高级月更新（进口）",
                source_url=SOURCE_URL,
                raw_record={
                    "declared_amount_usd": amount_usd,
                    "supplier_address": (
                        "Room G390, 7th Floor, B2# Animation Building, "
                        "Sino-Singapore Tianjin Eco-City, China"
                    ),
                    "buyer_address": (
                        "No.7, Venkatakrishna Nagar, 1st Street, "
                        "Arumbakkam, Chennai, Tamil Nadu"
                    ),
                    "query_time_beijing": "2026-07-31",
                    "deduplication": (
                        "The standard India import dataset and advanced monthly update "
                        "show duplicate representations of the same two product lines."
                    ),
                },
            )
            shipment_ids.append(shipment_id)

        evidence_id = "ose-dhaksha-new-wing-tradesparq-20260214"
        upsert(
            db,
            SupplyChainOpenSourceEvidence,
            evidence_id,
            case_id=CASE_ID,
            title="天津供应商向Dhaksha出口无人机测试与检测设备",
            source_type="trade_database",
            source_publisher="外贸公社（Tradesparq）",
            source_url=SOURCE_URL,
            source_excerpt=(
                "印度进口记录显示，2026年2月14日，New Wing Advanced Tianjin "
                "Technology Co., Ltd.向Dhaksha Unmanned Systems Private Limited"
                "出口LY-70KGF推力测试台、校准工具及EKT-VT-980离线AOI检测设备，"
                "HS编码90314900，运单号LQ6DBGURERWY4。"
            ),
            verified_facts=[
                "中国供应商和印度采购商均为具名主体",
                "原产地为中国、目的地为印度",
                "两项产品记录日期均为2026年2月14日",
                "产品用于无人机推力校准和制造检测环节",
                "两项申报金额合计7,134.02美元",
            ],
            evidence_grade="A",
            status="verified",
            limitations=[
                "记录证明设备进入Dhaksha一般生产供应链",
                "尚无装箱单或序列号证明设备专用于印度陆军200架物流无人机合同",
                "供应商中文工商登记名称仍需核验",
            ],
        )

        attach(investigation, "entity_ids", supplier_id)
        attach(investigation, "shipment_ids", *shipment_ids)
        attach(investigation, "open_source_evidence_ids", evidence_id)
        investigation.description = (
            "天津New Wing Advanced供应无人机推力测试台、校准工具和AOI检测设备"
            "→Dhaksha Unmanned Systems生产与检测环节→印度陆军200架中空物流无人机"
            "采购项目。自华进口事实已经逐票核实，具体设备是否专用于该军用合同仍需"
            "通过设备序列号、产线资料或合同附件进一步确认。"
        )
        db.commit()
        print("Imported two deduplicated Dhaksha trade records and one verified evidence item.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
