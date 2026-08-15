"""Import two Taiwan-facing, platform-level rare-earth supply-chain leads.

The sources close the China-to-U.S.-weapon-platform segment and the separate
U.S.-platform-to-Taiwan sale segment.  They do not identify a shared material
lot, serial number, configuration record, or bill of materials, so both
investigations remain ``researching`` and are not reportable as batch-level
Taiwan deliveries.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainCase,
    SupplyChainEntity,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
    SupplyChainReport,
)


DOJ_QUADRANT_INDICTMENT = "https://www.justice.gov/opa/media/1379441/dl"
DOJ_QUADRANT_RELEASE = (
    "https://www.justice.gov/archives/opa/pr/"
    "three-arrested-illegal-scheme-export-controlled-data-and-defraud-department-defense"
)
GAO_RARE_EARTH = "https://www.gao.gov/assets/a96655.html"
ARMY_PORTFOLIO = (
    "https://api.army.mil/e2/c/downloads/2024/07/19/ab2038a9/"
    "u-s-army-portfolio-2024.pdf"
)
DSCA_F16_TAIWAN = "https://www.dsca.mil/sites/default/files/mas/tecro_19-50.pdf"
DSCA_M1A2T_TAIWAN = "https://www.dsca.mil/sites/default/files/mas/tecro_19-22_0.pdf"

F16_INV_ID = "inv-taiwan-quadrant-china-magnets-f16"
M1A2_INV_ID = "inv-taiwan-m1a2-china-samarium"


def upsert(db, model, row_id: str, **values):
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def entity(db, row_id, name, name_zh, country, entity_type, roles, url, notes):
    return upsert(
        db,
        SupplyChainEntity,
        row_id,
        name=name,
        name_zh=name_zh,
        country=country,
        entity_type=entity_type,
        aliases=[],
        defense_roles=roles,
        source_url=url,
        notes=notes,
    )


def evidence(
    db,
    row_id,
    case_id,
    title,
    publisher,
    url,
    excerpt,
    facts,
    grade="A",
    status="verified",
    limitations=None,
    source_type="official_document",
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
        limitations=limitations or [],
    )


def import_f16_chain(db) -> None:
    entity(
        db,
        "ent-quadrant-china-magnet-anon",
        "Chinese Company 1 (Hangzhou; undisclosed)",
        "中国磁体企业1（杭州，未披露名称）",
        "China",
        "china_exporter",
        ["SmCo magnets", "NdFeB magnets", "sintering and magnetization"],
        DOJ_QUADRANT_INDICTMENT,
        "2023年联邦大陪审团替代起诉书称该杭州企业向Quadrant供应在中国烧结、充磁的稀土磁体；起诉书没有披露企业名称，不应与杭州X-Mag或成都银河磁体混同。",
    )
    entity(
        db,
        "ent-us-lead-quadrant-fighter-magnets",
        "Quadrant Magnetics LLC",
        "Quadrant Magnetics",
        "United States",
        "defense_supplier",
        ["SmCo magnets", "NdFeB magnets", "aviation and military supply"],
        DOJ_QUADRANT_INDICTMENT,
        "司法文件称Quadrant接收、重新包装中国磁体，再交付美方两家国防零部件企业。",
    )
    for suffix in ("1", "2"):
        entity(
            db,
            f"ent-quadrant-us-component-{suffix}",
            f"U.S. Component Company {suffix} (undisclosed)",
            f"美国零部件企业{suffix}（未披露）",
            "United States",
            "tier_supplier",
            ["military end-use components", "F-16/F-18 component supply"],
            DOJ_QUADRANT_INDICTMENT,
            "司法文件以U.S. Company 1/2代称；不可据公开材料推断其真实名称。",
        )
    entity(
        db,
        "ent-taiwan-lockheed-martin",
        "Lockheed Martin Corporation",
        "洛克希德·马丁公司",
        "United States",
        "defense_prime",
        [
            "PAC-3 MSE prime contractor",
            "missile defense",
            "F-16 prime contractor",
            "F-16 Block 70",
        ],
        DSCA_F16_TAIWAN,
        "Moog/PAC-3公开材料及DSCA 19-50分别确认其PAC-3 MSE和台湾66架F-16C/D Block 70军售案主承包角色。",
    )
    entity(
        db,
        "ent-taiwan-f16-recipient",
        "Taiwan Air Force / TECRO",
        "台湾空军／驻美台北经济文化代表处",
        "Taiwan",
        "military_end_user",
        ["66 F-16C/D Block 70 recipient"],
        DSCA_F16_TAIWAN,
        "DSCA 19-50确认TECRO申请采购66架F-16C/D Block 70及配套设备。",
    )
    db.flush()

    upstream_case = upsert(
        db,
        SupplyChainCase,
        "case-taiwan-quadrant-f16-china-magnets",
        country="Taiwan",
        title="杭州匿名企业经Quadrant向F-16国防用途供应中国稀土磁体",
        procurement_agency="U.S. Department of Defense supply chain",
        procurement_reference="W.D. Ky. No. 3:23-cr-00120-DJH, Document 9",
        procurement_date=dt("2023-12-05"),
        supplier_entity_id="ent-us-lead-quadrant-fighter-magnets",
        product="中国烧结并充磁的钐钴／钕铁硼永磁体",
        target_program="F-16、F-18及其他美国国防装备",
        contract_value=None,
        currency="USD",
        source_url=DOJ_QUADRANT_INDICTMENT,
        source_excerpt=(
            "替代起诉书称Quadrant从杭州匿名企业进口在中国烧结、充磁的磁体，"
            "再售予美方两家企业并装入供美国国防部使用的F-16、F-18等装备部件。"
        ),
        status="verified_lead",
    )
    sale_case = upsert(
        db,
        SupplyChainCase,
        "case-taiwan-f16-block70-fms",
        country="Taiwan",
        title="台湾66架F-16C/D Block 70对外军售案",
        procurement_agency="U.S. Department of State / DSCA; TECRO",
        procurement_reference="DSCA Transmittal No. 19-50",
        procurement_date=dt("2019-08-20"),
        supplier_entity_id="ent-taiwan-lockheed-martin",
        product="66架F-16C/D Block 70及相关设备与保障",
        target_program="Taiwan F-16 Block 70 Foreign Military Sale",
        contract_value=8_000_000_000.0,
        currency="USD",
        source_url=DSCA_F16_TAIWAN,
        source_excerpt="DSCA批准可能向TECRO出售66架F-16C/D Block 70，估值80亿美元，主承包商为Lockheed Martin。",
        status="verified",
    )
    db.flush()

    sources = [
        evidence(
            db,
            "ose-taiwan-quadrant-2023-indictment",
            upstream_case.id,
            "美国联邦法院替代起诉书：杭州中国磁体经Quadrant进入F-16/F-18部件",
            "U.S. District Court, Western District of Kentucky",
            DOJ_QUADRANT_INDICTMENT,
            "文件第1—3页描述杭州Chinese Company 1、Quadrant、美方企业1/2及F-16/F-18国防用途；后文列出多个零件号和中国发货数量。",
            [
                "Chinese Company 1位于杭州并制造钐钴或钕铁硼磁体",
                "磁体在中国烧结、充磁并发运至Quadrant",
                "Quadrant重新包装后交给美方企业1和2",
                "起诉书称磁体进入美国国防部F-16、F-18等装备部件",
                "文件列出PN 10500B-1022、6000U-1002、100101、3730D-1012等具体零件号与中国发货记录",
            ],
            status="verified_lead",
            limitations=[
                "该文件是替代起诉书，相关陈述属于检方指控，不等同于法院终局事实认定",
                "F-16具体批次、构型及承接零部件企业名称未披露",
            ],
        ),
        evidence(
            db,
            "ose-taiwan-quadrant-doj-release",
            upstream_case.id,
            "美国司法部公告：Quadrant中国磁体进入F-16/F-18国防部部件",
            "U.S. Department of Justice",
            DOJ_QUADRANT_RELEASE,
            "司法部公告概述Quadrant进口中国冶炼、充磁磁体，再经两家美国企业进入F-16、F-18等国防装备。",
            ["司法部公开确认案件、涉案企业和装备平台范围"],
            status="verified_lead",
            limitations=["公告同样依据起诉指控，未披露F-16型号、生产批次或台湾终端"],
            source_type="government_release",
        ),
        evidence(
            db,
            "ose-taiwan-f16-block70-dsca",
            sale_case.id,
            "DSCA 19-50：台湾66架F-16C/D Block 70军售",
            "Defense Security Cooperation Agency",
            DSCA_F16_TAIWAN,
            "2019年8月20日公告列明66架F-16C/D Block 70、75台F110发动机等，估值80亿美元。",
            [
                "采购方为TECRO",
                "数量为66架F-16C/D Block 70",
                "估值80亿美元",
                "Lockheed Martin为主承包商",
            ],
            limitations=["DSCA公告不披露飞机物料清单或Quadrant／中国磁体供应商"],
        ),
        evidence(
            db,
            "ose-taiwan-quadrant-f16-evidence-boundary",
            sale_case.id,
            "证据边界：F-16平台相同不等于中国磁体批次进入台湾Block 70",
            "GatherInfo evidence review",
            DOJ_QUADRANT_INDICTMENT,
            "司法文件覆盖2012—2018年前后的泛F-16国防用途，台湾Block 70军售在2019年通知；两份材料之间没有同一零件号、批次、序列号或构型记录。",
            ["可形成平台级候选链", "不能形成批次级或构型级闭环"],
            status="follow_up",
            limitations=[
                "需补F-16 Block 70具体BOM、分包商身份、Quadrant订单与台湾机号/生产批次对应关系",
            ],
            source_type="analytical_boundary",
        ),
    ]

    report = upsert(
        db,
        SupplyChainReport,
        "scr-taiwan-quadrant-f16-platform-chain",
        country="Taiwan",
        title="中国稀土磁体—Quadrant—F-16—台湾军售平台级供应链核验",
        case_ids=[upstream_case.id, sale_case.id],
        evidence_ids=[],
        model_id="manual-open-source-review",
        status="completed",
        content=(
            "已核实的前段：杭州匿名中国企业在中国烧结、充磁SmCo/NdFeB磁体，"
            "经Quadrant重新包装后交给两家匿名美国零部件企业；联邦替代起诉书称相关部件用于F-16、F-18等美国国防装备。\n\n"
            "已核实的后段：DSCA 19-50确认台湾通过TECRO采购66架F-16C/D Block 70，Lockheed Martin为主承包商。\n\n"
            "证据边界：司法材料所述F-16用途与台湾Block 70军售只有平台重合，未发现同一零件号、批次、构型或BOM贯通证据，故保持研究中。"
        ),
        summary="F-16平台两端均有A级官方材料，但缺少中国磁体批次到台湾Block 70构型的直接映射。",
        generated_at=datetime.now(timezone.utc),
    )
    upsert(
        db,
        SupplyChainInvestigation,
        F16_INV_ID,
        country="Taiwan",
        name="中国稀土磁体—Quadrant—F-16—台湾军售候选链",
        description=(
            "联邦替代起诉书称杭州匿名企业生产的中国SmCo/NdFeB磁体经Quadrant和两家匿名美国零部件企业进入F-16等国防装备；"
            "DSCA另行确认台湾采购66架F-16C/D Block 70。平台层链路成立，但缺少具体批次、构型和BOM闭环，不能认定涉案磁体进入台湾飞机。"
        ),
        status="researching",
        entity_ids=[
            "ent-quadrant-china-magnet-anon",
            "ent-us-lead-quadrant-fighter-magnets",
            "ent-quadrant-us-component-1",
            "ent-quadrant-us-component-2",
            "ent-taiwan-lockheed-martin",
            "ent-taiwan-f16-recipient",
        ],
        case_ids=[upstream_case.id, sale_case.id],
        shipment_ids=[],
        evidence_ids=[],
        open_source_evidence_ids=[row.id for row in sources],
        report_ids=[report.id],
        updated_at=datetime.now(timezone.utc),
    )


def import_m1a2_chain(db) -> None:
    entity(
        db,
        "ent-taiwan-m1a2-china-samarium-source",
        "Chinese Samarium Source (undisclosed)",
        "中国钐金属来源企业（未披露）",
        "China",
        "china_exporter",
        ["samarium metal"],
        GAO_RARE_EARTH,
        "GAO确认M1A2钐钴磁体使用的钐金属来自中国，但未披露企业名称。",
    )
    entity(
        db,
        "ent-taiwan-m1a2-us-smco-maker",
        "U.S. SmCo Magnet Manufacturer (undisclosed)",
        "美国钐钴磁体制造商（未披露）",
        "United States",
        "defense_supplier",
        ["SmCo permanent magnets"],
        GAO_RARE_EARTH,
        "GAO图5称该企业从中国采购钐并制造SmCo永磁体，企业名称未披露。",
    )
    entity(
        db,
        "ent-taiwan-m1a2-navigation-subcontractor",
        "M1A2 Reference/Navigation Unit Subcontractor (undisclosed)",
        "M1A2参考／导航装置分包商（未披露）",
        "United States",
        "tier_supplier",
        ["M1A2 reference/navigation unit", "SmCo magnet integration"],
        GAO_RARE_EARTH,
        "GAO图5确认分包商将SmCo磁体装入M1A2参考/导航装置，名称未披露。",
    )
    entity(
        db,
        "ent-m1a2-gdls",
        "General Dynamics Land Systems",
        "通用动力地面系统公司",
        "United States",
        "prime_contractor",
        ["M1A2 Abrams prime contractor", "tank systems integration"],
        ARMY_PORTFOLIO,
        "美国陆军项目资料确认General Dynamics Land Systems承担Abrams主承包/系统集成角色。",
    )
    entity(
        db,
        "ent-taiwan-m1a2t-recipient",
        "Taiwan Army / TECRO",
        "台湾陆军／驻美台北经济文化代表处",
        "Taiwan",
        "military_end_user",
        ["108 M1A2T Abrams recipient"],
        DSCA_M1A2T_TAIWAN,
        "DSCA 19-22确认TECRO申请采购108辆M1A2T Abrams。",
    )
    db.flush()

    upstream_case = upsert(
        db,
        SupplyChainCase,
        "case-taiwan-m1a2-china-smco-navigation",
        country="Taiwan",
        title="中国钐金属经SmCo磁体和参考／导航装置进入M1A2",
        procurement_agency="U.S. Department of Defense supply chain",
        procurement_reference="GAO-10-617R, Figure 5",
        procurement_date=dt("2010-04-14"),
        supplier_entity_id="ent-taiwan-m1a2-us-smco-maker",
        product="钐金属、SmCo永磁体及M1A2参考／导航装置",
        target_program="M1A2 Abrams tank",
        contract_value=None,
        currency="USD",
        source_url=GAO_RARE_EARTH,
        source_excerpt="GAO称M1A2参考/导航系统使用SmCo永磁体，其中钐金属来自中国，并给出四级供应链图。",
        status="verified_lead",
    )
    sale_case = upsert(
        db,
        SupplyChainCase,
        "case-taiwan-m1a2t-fms",
        country="Taiwan",
        title="台湾108辆M1A2T Abrams对外军售案",
        procurement_agency="U.S. Department of State / DSCA; TECRO",
        procurement_reference="DSCA Transmittal No. 19-22",
        procurement_date=dt("2019-07-08"),
        supplier_entity_id="ent-m1a2-gdls",
        product="108辆M1A2T Abrams及相关装备与保障",
        target_program="Taiwan M1A2T Abrams Foreign Military Sale",
        contract_value=2_000_000_000.0,
        currency="USD",
        source_url=DSCA_M1A2T_TAIWAN,
        source_excerpt="DSCA批准可能向TECRO出售108辆M1A2T Abrams及相关装备与保障，估值20亿美元。",
        status="verified",
    )
    db.flush()

    sources = [
        evidence(
            db,
            "ose-taiwan-m1a2-gao-smco-chain",
            upstream_case.id,
            "GAO-10-617R：M1A2钐钴导航系统的中国钐供应链",
            "U.S. Government Accountability Office",
            GAO_RARE_EARTH,
            "GAO图5给出中国钐→SmCo磁体制造商→参考/导航装置分包商→坦克主承包商→美国陆军M1A2的链路。",
            [
                "M1A2参考/导航系统使用SmCo永磁体",
                "磁体所用钐金属来自中国",
                "磁体制造商、装置分包商、坦克主承包商和美国陆军构成四级供应链",
            ],
            limitations=["GAO没有披露钐供应商、磁体制造商和导航装置分包商名称，也未给出零件号"],
        ),
        evidence(
            db,
            "ose-taiwan-m1a2t-dsca",
            sale_case.id,
            "DSCA 19-22：台湾108辆M1A2T Abrams军售",
            "Defense Security Cooperation Agency",
            DSCA_M1A2T_TAIWAN,
            "2019年7月8日公告列明108辆M1A2T Abrams及配套装备，估值20亿美元。",
            ["采购方为TECRO", "数量为108辆M1A2T Abrams", "估值20亿美元"],
            limitations=["DSCA公告不披露M1A2T参考/导航装置BOM或稀土材料来源"],
        ),
        evidence(
            db,
            "ose-taiwan-m1a2-gdls-prime",
            sale_case.id,
            "美国陆军项目资料：General Dynamics Land Systems承担Abrams主承包角色",
            "U.S. Army",
            ARMY_PORTFOLIO,
            "美国陆军项目组合资料将Abrams项目与General Dynamics Land Systems主承包/系统集成角色对应。",
            ["General Dynamics Land Systems为M1A2 Abrams主承包与集成节点"],
            limitations=["该资料不披露台湾M1A2T批次的导航装置分包商或SmCo磁体来源"],
        ),
        evidence(
            db,
            "ose-taiwan-m1a2-evidence-boundary",
            sale_case.id,
            "证据边界：2010年泛M1A2材料链不能直接等同于2019年台湾M1A2T构型",
            "GatherInfo evidence review",
            GAO_RARE_EARTH,
            "GAO材料链与DSCA台湾军售相隔九年，且未披露M1A2T构型控制、零件号或供应商沿用记录。",
            ["可形成平台级候选链", "不能形成M1A2T构型级或批次级闭环"],
            status="follow_up",
            limitations=["需补M1A2T参考/导航单元零件号、供应商沿用证明、BOM和台湾车号/生产批次对应关系"],
            source_type="analytical_boundary",
        ),
    ]

    report = upsert(
        db,
        SupplyChainReport,
        "scr-taiwan-m1a2-china-smco-platform-chain",
        country="Taiwan",
        title="中国钐金属—SmCo导航系统—M1A2T—台湾军售平台级供应链核验",
        case_ids=[upstream_case.id, sale_case.id],
        evidence_ids=[],
        model_id="manual-open-source-review",
        status="completed",
        content=(
            "已核实的前段：GAO确认M1A2参考/导航系统使用SmCo永磁体，钐金属来自中国；"
            "磁体制造商、导航装置分包商及坦克主承包商构成逐级供应关系。\n\n"
            "已核实的后段：DSCA 19-22确认台湾通过TECRO采购108辆M1A2T Abrams，估值20亿美元。\n\n"
            "证据边界：GAO为2010年泛M1A2供应链，未发现M1A2T构型、零件号或供应商沿用文件，故只能作为平台级候选链。"
        ),
        summary="M1A2平台两端均有A级官方材料，但缺少中国钐/SmCo磁体进入台湾M1A2T具体构型的直接映射。",
        generated_at=datetime.now(timezone.utc),
    )
    upsert(
        db,
        SupplyChainInvestigation,
        M1A2_INV_ID,
        country="Taiwan",
        name="中国钐金属—SmCo导航系统—M1A2T—台湾军售候选链",
        description=(
            "GAO确认中国钐金属经美国SmCo磁体制造商、参考/导航装置分包商和坦克主承包商进入M1A2；"
            "DSCA另行确认台湾采购108辆M1A2T。平台层链路成立，但缺少M1A2T具体零件号、供应商沿用、构型和批次闭环。"
        ),
        status="researching",
        entity_ids=[
            "ent-taiwan-m1a2-china-samarium-source",
            "ent-taiwan-m1a2-us-smco-maker",
            "ent-taiwan-m1a2-navigation-subcontractor",
            "ent-m1a2-gdls",
            "ent-taiwan-m1a2t-recipient",
        ],
        case_ids=[upstream_case.id, sale_case.id],
        shipment_ids=[],
        evidence_ids=[],
        open_source_evidence_ids=[row.id for row in sources],
        report_ids=[report.id],
        updated_at=datetime.now(timezone.utc),
    )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        import_f16_chain(db)
        import_m1a2_chain(db)
        db.commit()
        print(f"imported {F16_INV_ID} and {M1A2_INV_ID}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
