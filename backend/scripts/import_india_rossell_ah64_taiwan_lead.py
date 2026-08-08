"""Import and disposition the Rossell AH-64/Taiwan lead.

The China-to-Rossell shipments are real, but part-family research now points
toward Rossell's Lam Research semiconductor-equipment business rather than its
AH-64 line.  The two cross-layer hypotheses are therefore rejected and remain
non-reportable unless an exact customer drawing or BOM later contradicts this
screening.  The script is idempotent.
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


INV_ID = "inv-india-rossell-china-cables-ah64-taiwan"
TRADE_URL = "https://en.52wmb.com/supplier/28027374"
ROSSELL_INVESTOR_2025 = (
    "https://rosselltechsys.com/wp-content/uploads/2025/05/"
    "Investor-Presentation.pdf"
)
NBD_KABLETEX = "https://en.nbd.ltd/trader/info/NBDD3Y527049598"
UL_3271 = "https://iq.ul.com/awm/stylepage.aspx?style=3271"
SEMIMARKET_681_090076 = (
    "https://www.semimarket.com/item/"
    "lam-research-681090076054-etch/178417"
)
BOEING_ROSSELL = (
    "https://www.boeing.co.in/news/2019/"
    "boeing-and-rossell-techsys-celebrate-dual-milestones-for-v-22-os"
)
DOD_TAIWAN_SUPPORT = (
    "https://www.defense.gov/News/Contracts/Contract/Article/1481376/"
    "source/GovDelivery/"
)
USA_AWARD_PAGE = (
    "https://www.usaspending.gov/award/"
    "CONT_AWD_W58RGZ23F0241_9700_W58RGZ20D0005_9700"
)
USA_AWARD_API = (
    "https://api.usaspending.gov/api/v2/awards/"
    "CONT_AWD_W58RGZ23F0241_9700_W58RGZ20D0005_9700/"
)
USA_SUBAWARDS_API = "https://api.usaspending.gov/api/v2/subawards/"
AIT_TAIWAN_APACHE = "https://web-archive-2017.ait.org.tw/en/pressrelease-pr1012.html"
IHI_ENGINES = (
    "https://www.ihi.co.jp/en/products/aeroengine_space_defense/"
    "aircraft_engines/index.html"
)
TAIWAN_F16 = "https://www.dsca.mil/sites/default/files/mas/tecro_19-50.pdf"
IHI_INV_ID = "inv-japan-lead-ihi-aerospace-materials"
IHI_MARKER = "【2026-08-08 F110型号筛查】"


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


def attach(row, field: str, *row_ids: str) -> None:
    values = list(getattr(row, field) or [])
    for row_id in row_ids:
        if row_id not in values:
            values.append(row_id)
    setattr(row, field, values)


def entity(db, row_id: str, name: str, name_zh: str, country: str,
           entity_type: str, roles: list[str], source_url: str, notes: str):
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
        source_url=source_url,
        notes=notes,
    )


def open_source(db, row_id: str, case_id: str, title: str, source_type: str,
                publisher: str, url: str, excerpt: str, facts: list[str],
                grade: str, status: str, limitations: list[str]):
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


def relation(db, row_id: str, case_id: str, shipment_id: str,
             relation_type: str, grade: str, score: int, status: str,
             reasoning: str, facts: list[str]):
    return upsert(
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
        verified_facts=facts,
        model_review={"review": "manual OSINT; BOM and award-subcontract closure pending"},
        is_reportable=False,
    )


def add_rossell_entities(db, inv: SupplyChainInvestigation) -> None:
    rows = [
        entity(db, "ent-india-rossell-kabletex", "Shaoxing Kabletex Import & Export Co., Ltd.", "绍兴Kabletex进出口公司", "China", "china_exporter", ["insulated cable", "aerospace wire", "HS 85441990"], TRADE_URL, "Trade-intelligence records identify direct China-to-India cable shipments to Rossell Techsys."),
        entity(db, "ent-india-rossell-techsys", "Rossell Techsys Limited", "Rossell Techsys有限公司", "India", "defense_supplier", ["AH-64 wire harnesses", "AH-64 electrical panels", "electrical wiring interconnect systems"], BOEING_ROSSELL, "Boeing identifies Rossell as an AH-64 harness and electrical-panel supplier."),
        entity(db, "ent-india-rossell-boeing", "The Boeing Company", "波音公司", "United States", "defense_prime", ["AH-64 Apache prime contractor", "Taiwan AH-64E post-production support"], USA_AWARD_PAGE, "USAspending identifies Boeing as recipient of the Taiwan Apache support task order."),
        entity(db, "ent-india-rossell-taiwan-army", "Taiwan Armed Forces AH-64E Fleet", "台湾武装部队AH-64E机队", "Taiwan", "military_end_user", ["AH-64E Apache operator", "U.S. FMS support recipient"], DOD_TAIWAN_SUPPORT, "The U.S. Department of Defense identifies the Taiwan Armed Forces AH-64E fleet as the support customer."),
    ]
    db.flush()
    inv.entity_ids = [row.id for row in rows]


def add_rossell_cases(db, inv: SupplyChainInvestigation) -> list[SupplyChainCase]:
    cases = [
        upsert(db, SupplyChainCase, "case-india-rossell-china-cables", country="India", title="绍兴Kabletex向Rossell Techsys出口带零件号线缆", procurement_agency="Rossell Techsys", procurement_reference="52wmb customs/trade data", procurement_date=dt("2025-12-12"), supplier_entity_id="ent-india-rossell-kabletex", product="绝缘线缆：P/N 681-090076-025、681-097143-005、681-096871-070", target_program="Rossell多业务线制造体系；现有料号反证更指向Lam Research半导体设备业务", contract_value=None, currency="USD", source_url=TRADE_URL, source_excerpt="公开贸易页显示中国供应商、印度买方Rossell、HS 85441990、提单号及多个681系列零件号。", status="verified"),
        upsert(db, SupplyChainCase, "case-india-rossell-boeing-ah64", country="India", title="Rossell向波音交付AH-64线束与电气面板", procurement_agency="The Boeing Company", procurement_reference="Boeing release, 2019-06-10", procurement_date=dt("2019-06-10"), supplier_entity_id="ent-india-rossell-techsys", product="AH-64 wire harnesses and electrical panels", target_program="Boeing AH-64 Apache worldwide supply chain", contract_value=None, currency="USD", source_url=BOEING_ROSSELL, source_excerpt="Boeing称Rossell已交付第15,000套AH-64线束和第1,000块AH-64电气面板，AH-64合同授予于2017年3月。", status="verified"),
        upsert(db, SupplyChainCase, "case-india-rossell-taiwan-ah64-support", country="India", title="波音执行台湾AH-64E机队后生产支持任务单", procurement_agency="U.S. Army / Taiwan FMS", procurement_reference="W58RGZ23F0241 under W58RGZ20D0005", procurement_date=dt("2023-03-31"), supplier_entity_id="ent-india-rossell-boeing", product="Taiwan Apache airframe post-production support services", target_program="Taiwan Armed Forces AH-64E fleet", contract_value=26356697.98, currency="USD", source_url=USA_AWARD_PAGE, source_excerpt="USAspending将任务单描述为台湾阿帕奇机体后生产支持，执行期2023-04-01至2026-12-31。", status="verified"),
    ]
    db.flush()
    inv.case_ids = [row.id for row in cases]
    return cases


def add_shipments(db, inv: SupplyChainInvestigation) -> list[SupplyChainShipment]:
    records = [
        ("0400521", "681-090076-025", 47.67),
        ("6847125", "681-097143-005", 15.89),
        ("5706163", "681-096871-070", 83.43),
    ]
    rows = []
    for bill_no, part_no, displayed_amount in records:
        row = upsert(
            db,
            SupplyChainShipment,
            f"shp-india-rossell-{bill_no}",
            exporter_name="Shaoxing Kabletex Import & Export Co., Ltd.",
            exporter_country="China",
            importer_entity_id="ent-india-rossell-techsys",
            importer_name="Rossell Techsys",
            product=f"Cable/wire P/N {part_no}",
            hs_code="85441990",
            shipment_date=dt("2025-12-12"),
            weight_kg=None,
            quantity=None,
            quantity_unit=None,
            origin_country="China",
            destination_country="India",
            bill_no=bill_no,
            source_name="52wmb customs/trade data",
            source_url=TRADE_URL,
            raw_record={
                "part_number": part_no,
                "displayed_amount": displayed_amount,
                "amount_unit_not_disclosed": True,
                "dynamic_trade_page": True,
            },
        )
        rows.append(row)
    db.flush()
    inv.shipment_ids = [row.id for row in rows]
    return rows


def add_rossell_evidence(db, inv: SupplyChainInvestigation,
                         cases: list[SupplyChainCase],
                         shipments: list[SupplyChainShipment]) -> None:
    relations = []
    for shipment in shipments:
        relations.append(relation(db, f"ev-{shipment.id}", cases[0].id, shipment.id, "direct_trade_record", "B", 76, "verified", "The public trade record directly names the Chinese supplier, Indian buyer, bill number and cable part number; it does not disclose military end use.", [shipment.product, f"B/L {shipment.bill_no}", "China to India", "HS 85441990"]))
    relations.append(relation(db, "ev-india-rossell-cable-to-ah64-candidate", cases[1].id, shipments[0].id, "candidate_component", "C", 18, "rejected", "The AH-64 hypothesis is not supported. Public listings identify other 681-090076 suffixes as Lam Research etch parts; NBD identifies another 681-096871 suffix as UL3271 appliance/internal wire; and Rossell's own 2025 presentation identifies a Lam Research semiconductor-equipment production line. The imported exact suffixes remain unmapped, so this is a disposition of the military hypothesis rather than proof of the final civil assembly.", ["Rossell's AH-64 role is separate from its semiconductor business", "681-090076 base family is publicly associated with Lam Research etch equipment", "681-096871 base family includes UL3271 internal-equipment wire", "No exact-suffix-to-AH-64 drawing or BOM exists"]))
    relations.append(relation(db, "ev-india-rossell-ah64-to-taiwan-candidate", cases[2].id, shipments[0].id, "candidate_end_use", "C", 12, "rejected", "The Taiwan link is not supported: Taiwan's 30-aircraft Apache sale predates Rossell's disclosed 2017 AH-64 contract, the later support task order is for post-production services, and Rossell is absent from its 16 disclosed first-tier subawards.", ["Taiwan original Apache acquisition predates Rossell's disclosed AH-64 award", "The current Boeing award is post-production support rather than aircraft production", "Rossell is absent from 16 disclosed first-tier subawards", "No aircraft serial or lower-tier record links the shipment to Taiwan"]))
    inv.evidence_ids = [row.id for row in relations]

    sources = [
        open_source(db, "ose-india-rossell-kabletex-trade", cases[0].id, "中国绍兴Kabletex向Rossell出口681系列线缆", "trade_intelligence", "52wmb", TRADE_URL, "动态贸易页显示2025年102笔交易，并披露Rossell买方、HS 85441990、提单号和681系列线缆零件号。", ["直接买方为Rossell Techsys", "供应地中国、采购地印度", "P/N 681-090076-025、681-097143-005、681-096871-070", "提单号0400521、6847125、5706163"], "B", "verified", ["商业贸易数据库，仍应补印度海关原始记录", "页面动态更新", "金额字段单位未披露", "不披露最终用途"]),
        open_source(db, "ose-india-rossell-boeing-ah64", cases[1].id, "波音确认Rossell为AH-64线束和电气面板供应商", "company_disclosure", "Boeing", BOEING_ROSSELL, "波音公告记录Rossell第15,000套AH-64线束、第1,000块AH-64电气面板，并称其属于波音全球供应链。", ["AH-64组件合同授予于2017年3月", "2019年已交付15,000套线束", "2019年已交付1,000块电气面板"], "A", "verified", ["公告未披露中国线缆供应商或BOM", "未区分AH-64客户批次"]),
        open_source(db, "ose-india-rossell-taiwan-dod-support", cases[2].id, "美国国防部确认波音支持台湾AH-64E机队", "official_contract", "U.S. Department of Defense", DOD_TAIWAN_SUPPORT, "国防部合同公告将W58RGZ-18-C-0008描述为台湾武装部队AH-64E机队后生产支持服务。", ["承包商为波音", "客户为台湾武装部队AH-64E机队", "属于FMS后生产支持"], "A", "verified", ["原公告不列Rossell或具体线缆"]),
        open_source(db, "ose-india-rossell-taiwan-usaspending", cases[2].id, "USAspending：台湾阿帕奇支持任务单延续至2026年底", "official_contract_database", "USAspending.gov", USA_AWARD_API, "官方API记录W58RGZ23F0241金额26,356,697.98美元，描述为台湾阿帕奇机体后生产支持，执行期至2026-12-31。", ["任务单W58RGZ23F0241", "主合同W58RGZ20D0005", "承包商波音", "执行期2023-04-01至2026-12-31", "金额26,356,697.98美元"], "A", "verified", ["支持合同不等于新机生产合同", "API未披露资产序列号或材料BOM"]),
        open_source(db, "ose-india-rossell-taiwan-subaward-negative", cases[2].id, "USAspending分包筛查：16个一级分包记录未出现Rossell", "official_contract_database", "USAspending.gov", USA_SUBAWARDS_API, "对W58RGZ23F0241的官方分包接口核对显示16条记录，未出现Rossell Techsys。", ["已核对16条公开一级分包记录", "未发现Rossell Techsys", "不能把Rossell认定为该台湾任务单的直接分包商"], "A", "verified", ["未披露的低于一级分包、供应商采购或其他波音合同仍可能存在", "否定结果只适用于当前公开任务单分包数据"]),
        open_source(db, "ose-india-rossell-taiwan-apache-sale", cases[2].id, "美国在台协会：台湾获售30架AH-64D Block III阿帕奇", "official_fact_sheet", "American Institute in Taiwan", AIT_TAIWAN_APACHE, "军售概要列明30架新造AH-64D Block III Apache Longbow攻击直升机，案值25.32亿美元。", ["台湾采购30架阿帕奇", "新造出口型飞机", "案值25.32亿美元"], "A", "verified", ["原始军售早于Rossell 2017年AH-64合同", "不证明Rossell部件进入台湾原始交付机"]),
        open_source(db, "ose-india-rossell-semiconductor-lam-business", cases[0].id, "Rossell官方：半导体设备业务客户包括Lam Research", "company_disclosure", "Rossell Techsys", ROSSELL_INVESTOR_2025, "Rossell 2025年投资者演示将AH-64等航空项目与半导体业务分列；半导体板块明确列出Gas Boxes/Vapor Deposition Equipment的样机和量产，客户包括LAM Research、Jabil、ICHOR和TCM。", ["Rossell同时经营航空防务与半导体设备业务", "Lam Research为其半导体业务客户", "半导体业务包括气体箱及气相沉积设备样机/量产", "AH-64项目与半导体客户在披露中分栏列示"], "A", "verified", ["公司演示未披露本次三个精确后缀的领料记录"]),
        open_source(db, "ose-india-rossell-681096871-ul3271-family", cases[0].id, "NBD：681-096871同基号线缆为UL3271设备内配线", "trade_intelligence", "NBD Trade Data", NBD_KABLETEX, "Kabletex另一票对印出口记录披露P/N 681-096871-210，规格为UL3271、18AWG、125°C、600V；与本案进口的681-096871-070共享基号，但后缀不同。", ["公开货描给出681-096871-210完整规格", "线规18AWG", "UL3271、125°C、600V", "与本案681-096871-070共享基号"], "B", "verified", ["后缀-210并非本案精确后缀-070", "共享基号只能用于业务线排歧，不能证明同一成品"]),
        open_source(db, "ose-india-rossell-ul3271-standard", cases[0].id, "UL官方：Style 3271用于电机引线或电器内部布线", "standards_document", "UL Solutions", UL_3271, "UL Style 3271为挤出XLPE绝缘单芯线，额定125°C、600Vac，典型用途为电机引线或电器内部布线。", ["单芯挤出XLPE绝缘", "额定125°C、600Vac", "用途为电机引线或电器内部布线", "依据UL 758"], "A", "verified", ["UL标准是通用规格，不单独证明半导体设备最终用途", "页面为UL历史参考样式页"]),
        open_source(db, "ose-india-rossell-681090076-lam-family", cases[0].id, "二级市场索引：681-090076同基号多个后缀列为Lam Research蚀刻设备零件", "secondary_parts_market", "SemiMarket", SEMIMARKET_681_090076, "二级零件市场将681-090076-012、-054、-070、-072列作Lam Research etch零件；本案后缀-025未在公开索引中命中。", ["多个681-090076后缀被索引为Lam Research零件", "用途标签为etch", "本案进口后缀-025共享基号但未被精确命中"], "C", "follow_up", ["卖方自填的二级市场信息，不是Lam Research官方BOM", "精确后缀不同", "只可作为强排歧线索，不可单独认定最终用途"]),
    ]
    inv.open_source_evidence_ids = [row.id for row in sources]


def add_report(db, inv: SupplyChainInvestigation) -> None:
    report = upsert(
        db,
        SupplyChainReport,
        "scr-india-rossell-china-cables-ah64-taiwan",
        country="India",
        title="中国线缆—Rossell—AH-64/台湾候选排歧报告",
        case_ids=list(inv.case_ids or []),
        evidence_ids=list(inv.evidence_ids or []),
        model_id="manual-osint-import",
        status="completed",
        content=(
            "排歧结论：已核实中国绍兴供应商向印度Rossell Techsys出口带明确零件号的线缆，但新增料号家族证据更指向Rossell的Lam Research半导体设备业务，而不是AH-64。681-090076同基号多个后缀被列为Lam Research蚀刻设备零件；681-096871同基号公开规格为UL3271设备内配线；Rossell官方又明确披露Lam Research半导体设备量产业务。\n\n"
            "台湾边界：台湾30架阿帕奇原始军售早于Rossell公开的2017年AH-64合同；后续波音任务单属于机体后生产支持，Rossell未出现在16条公开一级分包中。由于三个进口精确后缀仍无客户图号/BOM，不能绝对确认其最终民用装配，但现有证据不支持中国线缆进入AH-64或台湾机队。两段跨层关系均已标记rejected，图谱不得绘成已连接链路。"
        ),
        summary="贸易记录真实，但料号家族与Rossell官方业务披露共同指向Lam Research半导体设备；AH-64及台湾链已排除。",
        generated_at=datetime.now(timezone.utc),
    )
    inv.report_ids = [report.id]


def enrich_ihi_f110_screening(db) -> None:
    inv = db.get(SupplyChainInvestigation, IHI_INV_ID)
    if inv is None:
        raise RuntimeError(f"missing investigation: {IHI_INV_ID}")
    case_id = "case-japan-ihi-f110-taiwan-screening"
    upsert(db, SupplyChainCase, case_id, country="Japan", title="F110同型号筛查：IHI日本F-2发动机与台湾F-16 Block 70发动机", procurement_agency="IHI / DSCA / TECRO", procurement_reference="IHI product page; DSCA 19-50", procurement_date=dt("2019-08-20"), supplier_entity_id="ent-japan-ihi-corporation", product="F110 turbofan / 75 F110 General Electric engines", target_program="日本F-2与台湾F-16C/D Block 70型号边界筛查", contract_value=8000000000.0, currency="USD", source_url=TAIWAN_F16, source_excerpt="IHI确认其按GE许可为日本F-2量产F110；DSCA确认台湾F-16案含75台GE F110。没有来源将台湾发动机归为IHI产。", status="researching")
    db.flush()
    sources = [
        open_source(db, "ose-japan-ihi-f110-f2-license", case_id, "IHI官方：按GE许可为日本F-2量产F110", "company_disclosure", "IHI Corporation", IHI_ENGINES, "IHI称该F110为日美联合研制F-2战斗机动力，并由IHI按GE许可作为主承包商量产。", ["平台明确为日本F-2", "IHI为许可生产主承包商", "许可方为美国GE"], "A", "verified", ["页面没有说明IHI参与GE面向第三国的F110出口发动机"]),
        open_source(db, "ose-japan-ihi-f110-taiwan-dsca", case_id, "DSCA：台湾F-16 Block 70案含75台GE F110发动机", "official_document", "Defense Security Cooperation Agency", TAIWAN_F16, "DSCA 19-50列明66架F-16C/D Block 70及75台F110 General Electric发动机（含9台备份）。", ["66架F-16C/D Block 70", "75台F110 General Electric发动机", "其中9台为备份", "估值80亿美元"], "A", "verified", ["DSCA未提IHI或日本制造内容"]),
        open_source(db, "ose-japan-ihi-f110-taiwan-boundary", case_id, "型号相同不等于供应链相同：未发现IHI进入台湾F110", "analyst_boundary", "Manual OSINT review", IHI_ENGINES, "公开证据分别确认IHI的日本F-2许可生产和台湾采购GE F110，但没有制造号、合同、BOM或出口记录将二者连接。", ["只能确认同属F110系列", "不能据型号名推定IHI供货", "当前未形成日本—台湾军售链"], "A", "verified", ["需GE发动机序列号、分包清单或IHI出口文件才能升级"]),
    ]
    attach(inv, "case_ids", case_id)
    attach(inv, "open_source_evidence_ids", *(row.id for row in sources))
    description = inv.description or ""
    if IHI_MARKER in description:
        description = description.split(IHI_MARKER, 1)[0].rstrip()
    inv.description = (
        f"{description}\n\n{IHI_MARKER}IHI按GE许可量产的F110官方用途为日本F-2；"
        "台湾F-16 Block 70军售虽含75台GE F110，但没有证据表明由IHI生产或含IHI部件。"
        "该项仅作同型号排歧，不构成日本对台军售链。"
    )
    inv.updated_at = datetime.now(timezone.utc)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        inv = upsert(db, SupplyChainInvestigation, INV_ID, country="India", name="中国绍兴线缆—Rossell业务线排歧（AH-64/台湾链未成立）", description="中国绍兴Kabletex向印度Rossell Techsys出口带明确零件号的线缆，直接贸易事实保留。但681-090076同基号公开索引指向Lam Research蚀刻设备，681-096871同基号记录对应UL3271设备内配线，Rossell官方又披露面向Lam Research的半导体设备量产业务。台湾原始阿帕奇军售早于Rossell公开AH-64合同，后续支持任务单的16条一级分包也没有Rossell。现有证据不支持把中国线缆连接到AH-64或台湾机队，两段跨层关系均标记rejected；仅因三个精确后缀尚无客户图号而保留researching。", status="researching", entity_ids=[], case_ids=[], shipment_ids=[], evidence_ids=[], open_source_evidence_ids=[], report_ids=[])
        add_rossell_entities(db, inv)
        cases = add_rossell_cases(db, inv)
        shipments = add_shipments(db, inv)
        add_rossell_evidence(db, inv, cases, shipments)
        add_report(db, inv)
        enrich_ihi_f110_screening(db)
        inv.updated_at = datetime.now(timezone.utc)
        db.commit()
        print(f"imported {INV_ID}: 4 entities, 3 cases, 3 shipments, 10 OSE")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
