"""Correct the India-CSBC pump chain after product and project-level verification."""
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


INVESTIGATION_ID = "inv-india-csbc-pump-chain"


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
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        investigation = db.get(SupplyChainInvestigation, INVESTIGATION_ID)
        if not investigation:
            raise RuntimeError("India-CSBC pump investigation is missing")

        cpc_id = "ent-cpc-dalin-petrochemical-center"
        upsert(
            db,
            SupplyChainEntity,
            cpc_id,
            name="CPC Corporation, Taiwan - Dalin Petrochemical Storage Center",
            name_zh="台湾中油大林石化油品储运中心",
            country="Taiwan",
            entity_type="industrial_end_user",
            aliases=["大林石化油品储运中心"],
            parent_id=None,
            defense_roles=["26座石化品储槽及槽车装卸工场项目最终业主"],
            source_url=(
                "https://www.csbcnet.com.tw/monthly_pub/files/"
                "003%E5%8F%B0%E8%88%B9%E5%85%AC%E5%8F%B8%E5%BB%BA%E9%80%A0"
                "%E4%B8%AD%E6%B2%B9%E5%85%AC%E5%8F%B826%E5%BA%A7%E7%9F%B3"
                "%E5%8C%96%E5%93%81%E5%84%B2%E6%A7%BD%20%E8%88%89%E8%A1%8C"
                "%E5%84%B2%E6%A7%BD%E9%8B%BC%E6%9D%BF%E5%89%B2%E5%88%87"
                "%E9%96%8B%E5%B7%A5%E5%85%B8%E7%A6%AE%282%29.pdf"
            ),
            notes="台船以EPC方式承揽该石化储运项目，项目范围包括设计、采购、建造、安装和试车。",
        )
        db.flush()

        delivery_case = db.get(SupplyChainCase, "case-india-sulzer-csbc-pump-delivery")
        delivery_case.title = "Sulzer Pumps India向台船石化EPC项目交付工艺泵组"
        delivery_case.procurement_agency = "台灣國際造船股份有限公司（EPC承包方）"
        delivery_case.procurement_reference = "2025-06-24等贸易记录 / 大林石化储运中心EPC项目"
        delivery_case.procurement_date = datetime(2025, 6, 24, tzinfo=timezone.utc)
        delivery_case.product = "甲苯、混合二甲苯装卸泵及含油废水集水坑泵等11台/套"
        delivery_case.target_program = "台湾中油大林石化油品储运中心槽车装卸工场及储槽项目"
        delivery_case.source_url = "https://www.csbcnet.com.tw/FileDownLoad/FileUpload/2025111316034972196.pdf"
        delivery_case.source_excerpt = (
            "提单品名及设备标签指向甲苯、混合二甲苯槽车/码头装卸和含油废水处理；"
            "台船同期承揽中油大林石化储运中心储槽及槽车装卸工场EPC项目。"
        )
        delivery_case.status = "verified_non_defense"

        excluded_case = db.get(SupplyChainCase, "case-india-csbc-endeavor-manta")
        if excluded_case:
            excluded_case.title = "奋进魔鬼鱼无人艇关联排除核验"
            excluded_case.procurement_reference = "产品用途与项目时间线交叉核验"
            excluded_case.product = "军用级无人水面载具（与本批工艺泵无直接证据关联）"
            excluded_case.source_excerpt = (
                "奋进魔鬼鱼确属台船军用级无人艇，但涉案泵组的型号、标签和用途均指向石化装卸工程，"
                "且没有船号、BOM、安装或验收文件，因此不得纳入该无人艇供应链。"
            )
            excluded_case.status = "excluded"

        shipment = db.get(SupplyChainShipment, "shp-india-sulzer-csbc-pumps-2025")
        shipment.product = (
            "OHH/PRE/OCV系列石化工艺离心泵：甲苯及混合二甲苯槽车/码头装卸泵、"
            "含油废水集水坑泵"
        )
        shipment.hs_code = "84137091"
        shipment.shipment_date = datetime(2025, 6, 24, tzinfo=timezone.utc)
        shipment.source_name = "Volza公开提单摘要 / 台船官方财务报告"
        shipment.source_url = "https://www.volza.com/company-profile/csbc-corporation-taiwan-2967055/import/"
        shipment.raw_record = {
            "shipment_batches": "至少6批次",
            "quantity_total": 11,
            "verified_products": [
                "P-3643A/B oily waste water sump pumps, OCV 1x2x7.5-1, 2 PCS",
                "P-3411/P-3412 marine loading pump, OHH 6x8x21B-2, 2 PCS",
                "P-3314A/B mix xylene truck loading pump, OHH 3x6x11.5B-1, 2 PCS",
                "P-3318A/B mix xylene high-EB truck loading pump, OHH 3x6x11.5B-1, 2 PCS",
                "P-3309A/B toluene truck loading pump, OHH 3x4x9-1, 2 PCS",
                "P-3315B mix xylene marine loading pump, PRE Z200-450, 1 PCS",
            ],
            "assessment": "石化储运工程用途；不支持军用无人艇或潜艇最终用途",
        }

        for evidence_id in (
            "evd-india-suzhou-pump-input",
            "evd-india-wolong-motor-input",
            "evd-india-csbc-pump-delivery",
        ):
            evidence = db.get(SupplyChainEvidence, evidence_id)
            if evidence:
                evidence.relation_type = "industrial_process_equipment_supply"
                evidence.status = "verified_non_defense"
                evidence.is_reportable = True
                evidence.reasoning = (
                    "中国部件经印度集成为石化装卸工艺泵组并交付台船EPC项目；"
                    "该关系可用于产业供应链分析，但不能作为军工最终用途证据。"
                )
        manta_evidence = db.get(SupplyChainEvidence, "evd-india-endeavor-manta-link")
        if manta_evidence:
            manta_evidence.evidence_grade = "C"
            manta_evidence.score = 5
            manta_evidence.status = "rejected"
            manta_evidence.is_reportable = False
            manta_evidence.reasoning = (
                "同一收货企业不能证明同一最终项目。泵型、设备标签及公开EPC项目均指向石化储运，"
                "与8.6米双舷外机无人艇的设备需求不匹配，军用关联予以排除。"
            )

        project_url = "https://www.csbcnet.com.tw/FileDownLoad/FileUpload/2025111316034972196.pdf"
        upsert(
            db,
            SupplyChainOpenSourceEvidence,
            "ose-india-csbc-cpc-epc-project",
            case_id=delivery_case.id,
            title="台船承揽中油大林石化储运中心EPC项目",
            source_type="official_financial_report",
            source_publisher="台灣國際造船股份有限公司",
            source_url=project_url,
            source_excerpt=(
                "台船于2022年12月及2023年7月分别签约承揽26座石化品储槽和槽车装卸工场，"
                "累计金额约116亿元新台币，预计2026年陆续完工。"
            ),
            verified_facts=["项目业主为台湾中油", "台船为EPC承包方", "项目涵盖石化储槽和槽车装卸工场"],
            evidence_grade="A",
            status="verified",
            limitations=[],
        )
        upsert(
            db,
            SupplyChainOpenSourceEvidence,
            "ose-india-csbc-pump-product-details",
            case_id=delivery_case.id,
            title="Sulzer Pumps India向台船交付泵组的产品用途明细",
            source_type="trade_database",
            source_publisher="Volza公开提单摘要",
            source_url="https://www.volza.com/company-profile/csbc-corporation-taiwan-2967055/import/",
            source_excerpt=(
                "产品明细包括甲苯、混合二甲苯槽车/码头装卸泵及含油废水集水坑泵，"
                "型号为OHH、PRE和OCV系列。"
            ),
            verified_facts=["11台/套泵组用途均为石化装卸或废水处理", "收货人为台船", "供应商为Sulzer Pumps India"],
            evidence_grade="B",
            status="verified",
            limitations=["公开摘要未展示全部提单字段；数量与产品描述可交叉核验"],
        )

        report = db.get(SupplyChainReport, "scr-india-csbc-pump-chain-verified")
        report.title = "涉印—台船石化工程泵供应链深度核验报告"
        report.summary = (
            "中国泵体、电机等部件经Sulzer Pumps India集成为11台/套石化工艺离心泵，"
            "由台船作为EPC承包方接收，较大概率用于台湾中油大林石化油品储运中心项目。"
            "产品标签明确对应甲苯、混合二甲苯装卸和含油废水处理，不支持进入奋进魔鬼鱼无人艇"
            "或海鲲潜艇。原军工供应链判断属于同一收货企业导致的错误关联，应予排除。"
        )
        report.content = """一、核验结论
本链条能够确认中国部件经印度集成后进入台船承揽的工程项目，但不能认定其进入军用无人艇或潜艇。现有产品用途、设备标签、项目时间线和台船官方披露共同指向台湾中油大林石化油品储运中心的储槽及装卸工场EPC项目。

二、已核验贸易链路
苏州苏尔寿向Sulzer Pumps India供应裸轴泵、泵体及备件，卧龙电气南阳防爆集团供应工业电机。Sulzer Pumps India完成泵组集成后，于2025年向台船交付至少6批次、11台/套离心泵组。公开产品明细包括甲苯槽车装卸泵、混合二甲苯槽车及码头装卸泵、含油废水集水坑泵。

三、项目归属判断
台船官方财务资料确认，其以EPC方式承揽台湾中油大林石化油品储运中心26座石化品储槽及槽车装卸工场项目，项目实施期覆盖2025年泵组进口时点。OHH、PRE等型号属于API 610石油、石化和天然气工艺泵，产品名称与该EPC项目高度吻合。

四、军工关联排除
奋进魔鬼鱼由台船研制，具备军用、鱼雷适配和无人作战用途；海鲲潜艇也由台船承造并采用美制战斗系统和鱼雷。但上述事实仅证明台船同时承担军民项目。没有船号、采购项目号、BOM、设备安装或验收记录证明本批石化泵进入任何军用平台。以共同收货人为依据将三条链路连接，属于实体层面的错误归因。

五、风险判断
该链条的现实价值主要是境内泵、电机部件经跨国集团内部贸易和印度集成后进入台湾重大石化基础设施，涉及关键工业设备来源依赖、集团内部供应替代和石化设施供应链安全，不宜作为军工供应链成果上报。后续仅在获得军舰项目号、船用级规格、安装船号或最终用途文件后，方可重新评估军工关联。"""
        report.generated_at = datetime.now(timezone.utc)

        investigation.name = "涉印—台船石化工程泵供应链"
        investigation.description = (
            "中国产泵体、备件和工业电机经Sulzer Pumps India集成为石化工艺离心泵，"
            "由台船作为EPC承包方接收并较大概率用于台湾中油大林石化储运中心项目。"
            "经深度核验，奋进魔鬼鱼及海鲲潜艇军工关联不成立。"
        )
        investigation.status = "verified_non_defense"
        investigation.entity_ids = [
            "ent-sulzer-ltd",
            "ent-sulzer-suzhou",
            "ent-wolong-nanyang",
            "ent-sulzer-pumps-india",
            "ent-csbc-taiwan",
            cpc_id,
        ]
        investigation.case_ids = [delivery_case.id]
        investigation.open_source_evidence_ids = list(dict.fromkeys([
            *(investigation.open_source_evidence_ids or []),
            "ose-india-csbc-cpc-epc-project",
            "ose-india-csbc-pump-product-details",
        ]))
        db.commit()
        print("Corrected India-CSBC pump chain as a petrochemical EPC supply chain.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
