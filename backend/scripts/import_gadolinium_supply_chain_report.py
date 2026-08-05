"""Import the gadolinium oxide end-use assessment into supply-chain projects."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

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


REPORT_PATH = Path(r"D:\codex\供应链穿透\氧化钆出口最终用途风险研判报告.md")
SOURCE_REF = str(REPORT_PATH)
INVESTIGATION_ID = "inv-us-gadolinium-oxide"


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
    if not REPORT_PATH.exists():
        raise FileNotFoundError(REPORT_PATH)
    content = REPORT_PATH.read_text(encoding="utf-8")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        entities = [
            (
                "ent-gadolinium-china-exporter-pending",
                dict(
                    name="Domestic exporter (identity pending verification)",
                    name_zh="境内出口企业（待核）",
                    country="China",
                    entity_type="china_exporter",
                    aliases=["本案境内出口企业"],
                    parent_id=None,
                    defense_roles=["30吨高纯氧化钆出口申报主体", "最终用户和最终用途审查前端责任主体"],
                    source_url=None,
                    notes=(
                        "更新稿未披露企业名称和统一社会信用代码。需核查企业属性、货源来源、"
                        "历史高纯稀土出口记录、与G.E. Chaplin交易历史、客户尽调材料及许可证"
                        "申报一致性；取得真实身份后替换本占位主体。"
                    ),
                ),
            ),
            (
                "ent-ge-chaplin",
                dict(
                    name="G.E. Chaplin Inc.",
                    name_zh="G.E. Chaplin特种化学品与金属公司",
                    country="United States",
                    entity_type="importer",
                    aliases=["GE Chaplin", "GEC"],
                    parent_id=None,
                    defense_roles=["DLA稀土氧化物合同供应商", "高纯重稀土氧化物进口商"],
                    source_url="https://www.gechaplin.com/contact_us.html",
                    notes="曾承接DLA稀土氧化物采购，官网经营包括氧化钆在内的高纯重稀土氧化物。",
                ),
            ),
            (
                "ent-national-magnetics-group",
                dict(
                    name="National Magnetics Group, Inc.",
                    name_zh="美国国家磁性材料集团",
                    country="United States",
                    entity_type="defense_supplier",
                    aliases=["NMG", "National Magnetics Group"],
                    parent_id=None,
                    defense_roles=["美国海军水下通信材料供应商", "潜艇天线材料供应链节点"],
                    source_url="https://www.magneticsgroup.com/about/",
                    notes="TCI、Ferronics和Ceramic Magnetics处于同一集团制造体系。",
                ),
            ),
            (
                "ent-tci-ceramics",
                dict(
                    name="TCI Ceramics, Inc.",
                    name_zh="TCI陶瓷公司",
                    country="United States",
                    entity_type="subsidiary",
                    aliases=["TCI", "CAGE 3NBT2"],
                    parent_id="ent-national-magnetics-group",
                    defense_roles=["含钆微波陶瓷制造", "军民两用先进陶瓷材料"],
                    source_url="https://www.magneticsgroup.com/about/",
                    notes="公开目录列有GD/GA系列含钆石榴石材料，具备消耗氧化钆的技术和产品基础。",
                ),
            ),
            (
                "ent-lockheed-sippican",
                dict(
                    name="Lockheed Martin Sippican, Inc.",
                    name_zh="洛克希德·马丁Sippican公司",
                    country="United States",
                    entity_type="defense_prime",
                    aliases=["Lockheed Martin Sippican"],
                    parent_id=None,
                    defense_roles=["美国海军多功能桅杆天线主承包商"],
                    source_url=(
                        "https://www.defense.gov/News/Contracts/Contract/Article/2365695/"
                    ),
                    notes="N00039-20-C-0013合同涉及潜艇多功能桅杆天线组。",
                ),
            ),
        ]
        for row_id, values in entities:
            upsert(db, SupplyChainEntity, row_id, **values)
        db.flush()

        cases = [
            (
                "case-ge-chaplin-dla-rare-earth",
                dict(
                    country="United States",
                    title="G.E. Chaplin承接DLA高纯稀土氧化物采购",
                    procurement_agency="美国国防后勤局",
                    procurement_reference="SP8000-23-C-0013",
                    procurement_date=dt("2023-09-26"),
                    supplier_entity_id="ent-ge-chaplin",
                    product="磁体级氧化钕和氧化镨",
                    target_program="美国国防稀土储备供应链",
                    contract_value=8188490,
                    currency="USD",
                    source_url=None,
                    source_excerpt=(
                        "合同最高值818.849万美元；公开记录显示实际义务金额约17.77万美元，"
                        "后因政府便利原因提前终止。合同物项不是氧化钆。"
                    ),
                    status="monitoring",
                ),
            ),
            (
                "case-nmg-nuwc-ferrite-bar",
                dict(
                    country="United States",
                    title="NMG向美国海军水下通信项目供应军方图纸铁氧体棒",
                    procurement_agency="美国海军水下作战中心纽波特分部",
                    procurement_reference="N66604-24-P-0005",
                    procurement_date=dt("2024-01-01"),
                    supplier_entity_id="ent-national-magnetics-group",
                    product="图纸8628194铁氧体棒",
                    target_program="NAVWAR PMW 770水下通信与集成项目",
                    contract_value=None,
                    currency="USD",
                    source_url=None,
                    source_excerpt=(
                        "该项目构成NMG进入海军供应链的强证据，但公开材料指向MN60锰锌"
                        "铁氧体，不能据此认定使用氧化钆。"
                    ),
                    status="monitoring",
                ),
            ),
            (
                "case-lockheed-sippican-mast-antenna",
                dict(
                    country="United States",
                    title="洛克希德·马丁Sippican潜艇多功能桅杆天线合同",
                    procurement_agency="美国海军",
                    procurement_reference="N00039-20-C-0013",
                    procurement_date=dt("2020-09-29"),
                    supplier_entity_id="ent-lockheed-sippican",
                    product="OE-538/OE-592多功能桅杆天线组及升级保障",
                    target_program="美国海军潜艇通信与天线系统",
                    contract_value=79986940,
                    currency="USD",
                    source_url=(
                        "https://www.defense.gov/News/Contracts/Contract/Article/2365695/"
                    ),
                    source_excerpt=(
                        "NMG旗下Ceramic Magnetics曾向该项目供应DISC FERRITE；"
                        "公开资料未显示产品含钆或由TCI分部供应。"
                    ),
                    status="monitoring",
                ),
            ),
        ]
        for row_id, values in cases:
            upsert(db, SupplyChainCase, row_id, **values)
        db.flush()

        upsert(
            db,
            SupplyChainShipment,
            "shp-gadolinium-gec-tci-30t",
            exporter_name="境内出口企业（待核）",
            exporter_country="China",
            importer_entity_id="ent-ge-chaplin",
            importer_name="G.E. Chaplin Inc.",
            product="4N/5N高纯氧化钆",
            hs_code=None,
            shipment_date=None,
            weight_kg=30000,
            quantity=30,
            quantity_unit="吨",
            origin_country="China",
            destination_country="United States",
            bill_no=None,
            source_name="氧化钆出口最终用途风险研判报告",
            source_url=None,
            raw_record={
                "final_user": "TCI Ceramics/National Magnetics Group",
                "transaction_status": "待企业材料核验",
                "source_document": SOURCE_REF,
            },
        )
        db.flush()

        evidence_rows = [
            (
                "evd-gadolinium-gec-dla",
                "case-ge-chaplin-dla-rare-earth",
                "B",
                72,
                True,
                "G.E. Chaplin既是本案进口商，又曾承接DLA高纯稀土氧化物合同，主体关联明确；但DLA合同物项为氧化钕、氧化镨，并非本案氧化钆。",
            ),
            (
                "evd-gadolinium-nmg-navy",
                "case-nmg-nuwc-ferrite-bar",
                "C",
                48,
                False,
                "最终用户所属NMG集团已进入美国海军水下通信供应链，但已知图纸材料为MN60锰锌铁氧体，不能证明本案氧化钆进入该项目。",
            ),
            (
                "evd-gadolinium-submarine-antenna",
                "case-lockheed-sippican-mast-antenna",
                "C",
                42,
                False,
                "NMG集团分部向潜艇桅杆天线项目供应铁氧体部件，构成集团层面国防背景证据；尚无TCI含钆牌号、投料批次或军方订单对应关系。",
            ),
        ]
        for row_id, case_id, grade, score, reportable, reasoning in evidence_rows:
            upsert(
                db,
                SupplyChainEvidence,
                row_id,
                case_id=case_id,
                shipment_id="shp-gadolinium-gec-tci-30t",
                relation_type="possible_supply",
                evidence_grade=grade,
                score=score,
                status="needs_review" if grade == "C" else "approved",
                reasoning=reasoning,
                verified_facts={
                    "china_origin": True,
                    "shipment_quantity_kg": 30000,
                    "importer_defense_supply_background": True,
                    "final_user_gadolinium_processing_capability": True,
                    "specific_military_end_use_verified": False,
                    "source_document": SOURCE_REF,
                },
                model_review={
                    "method": "verified_report_import",
                    "risk_level": "high",
                    "conclusion": "高风险、强关联、未闭环",
                },
                is_reportable=reportable,
            )

        source_rows = [
            (
                "ose-gadolinium-ge-chaplin",
                "case-ge-chaplin-dla-rare-earth",
                "G.E. Chaplin企业与高纯稀土经营主体信息",
                "企业官网",
                "G.E. Chaplin Inc.",
                "https://www.gechaplin.com/contact_us.html",
                "企业公开信息显示其为特种化学品与金属供应商。",
                "B",
            ),
            (
                "ose-gadolinium-tci-capability",
                "case-nmg-nuwc-ferrite-bar",
                "TCI/NMG先进陶瓷与磁性材料制造能力",
                "企业官网",
                "National Magnetics Group",
                "https://www.magneticsgroup.com/about/",
                "NMG官网确认TCI具备微波铁氧体、石榴石、定制化学组成及规模化生产能力。",
                "B",
            ),
            (
                "ose-gadolinium-sippican-contract",
                "case-lockheed-sippican-mast-antenna",
                "美国海军多功能桅杆天线合同公告",
                "美国国防部合同公告",
                "U.S. Department of Defense",
                "https://www.defense.gov/News/Contracts/Contract/Article/2365695/",
                "官方公告确认N00039-20-C-0013合同及OE-538/OE-592多功能桅杆天线项目。",
                "A",
            ),
        ]
        for row in source_rows:
            row_id, case_id, title, source_type, publisher, url, excerpt, grade = row
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
                verified_facts={"source_document": SOURCE_REF},
                evidence_grade=grade,
                status="verified",
                limitations=[],
            )

        upsert(
            db,
            SupplyChainReport,
            "scr-us-gadolinium-end-use-risk",
            country="United States",
            title="美国高纯氧化钆出口最终用途风险研判报告",
            case_ids=[row[0] for row in cases],
            evidence_ids=[row[0] for row in evidence_rows],
            model_id=None,
            status="completed",
            content=content,
            summary=(
                "境内出口企业是货物流、单证流及最终用途审查的前端责任主体；进口商"
                "与最终用户集团均具有美国国防供应链背景，氧化钆具备军民两用属性。"
                "建议按高风险事项开展穿透核查，但现有证据尚不能直接认定本批30吨"
                "氧化钆已进入具体美国军事项目。"
            ),
            error_log=None,
            generated_at=datetime.now(timezone.utc),
        )

        upsert(
            db,
            SupplyChainInvestigation,
            INVESTIGATION_ID,
            country="United States",
            name="美国高纯氧化钆供应链",
            description=(
                "境内出口企业出口30吨高纯氧化钆，经G.E. Chaplin流向TCI/NMG，"
                "并与美国海军水下通信及潜艇天线供应链形成主体和技术关联"
            ),
            status="active",
            entity_ids=[row[0] for row in entities],
            case_ids=[row[0] for row in cases],
            shipment_ids=["shp-gadolinium-gec-tci-30t"],
            evidence_ids=[row[0] for row in evidence_rows],
            open_source_evidence_ids=[row[0] for row in source_rows],
            report_ids=["scr-us-gadolinium-end-use-risk"],
        )
        db.commit()
        print(
            "Imported gadolinium investigation: "
            f"{len(entities)} entities, {len(cases)} cases, "
            f"{len(evidence_rows)} evidence links, 1 report."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
