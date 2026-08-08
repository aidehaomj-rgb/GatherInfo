"""Deepen India and Japan supply-chain evidence and record Taiwan screening.

The import is idempotent.  It keeps corporate/import evidence separate from
military end-use evidence and explicitly records negative-screening limits.
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
)


PIB_DHANUSH_PARTS = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1522500"
PIB_DHANUSH_ARMY = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1570184&lang=2&reg=3"
COROMANDEL_DHAKSHA = (
    "https://www.coromandel.biz/press-release/coromandel-internationals-subsidiary-"
    "dhaksha-unmanned-systems-bags-rs-165-crores-order-for-defence-and-agri-drones/"
)
DHAKSHA_TAIWAN = (
    "https://www.indiatoday.in/india-today-insight/story/chinese-components-why-indian-"
    "military-drones-are-under-defence-ministry-scanner-2623392-2024-10-26"
)
DRDO_DHAKSHA = (
    "https://www.drdo.gov.in/drdo/sites/default/files/drdo-news-documents/NPC29Aug2024.pdf"
)
DRONE_400 = (
    "https://www.indiatoday.in/india/story/army-cancels-rs-230-crore-drone-contracts-"
    "over-alleged-use-of-chinese-components-2676137-2025-02-07"
)
PIB_DRONE_POLICY = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2242398&lang=1&reg=1"
PIB_NEWSPACE_ULPGM = "https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2148320&lang=2&reg=48"
PIB_NEWSPACE_TDF = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2030445&lang=2&reg=3"
GARUDA_DEFENCE = (
    "https://www.garudaaerospace.com/company/case-studies/"
    "drone-based-defence-surveillance-solutions"
)
PARAS_DISCLOSURE = (
    "https://parasdefence.com/uploads/disclosures/"
    "1773121217receipt-of-order-from-drdo-ministry-of-defence.pdf"
)
PIB_ACCORD = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2271094&lang=1&reg=1"
ACE_RELEASE = "https://www.ace-cranes.com/public/front/pdf/20.02.2025.pdf"
CSBC_CPC = "https://www.csbcnet.com.tw/FileDownLoad/FileUpload/2025111316034972196.pdf"

MHI_NOTICE = "https://www.mhi.com/notice/"
MHI_DEFENCE = "https://www.mhi.com/inquiry/inquiry_defense.html"
MHI_SHIMONOSEKI = "https://www.mhi.com/jp/company/location/shimonosekiw/history"
NIDS_TAIWAN_BOATS = "https://www.nids.mod.go.jp/publication/senshi/pdf/202403/03-2.pdf"
KHI_AEROSPACE = "https://global.kawasaki.com/en/history/business/aero.html"
JAPAN_DEFENCE_INDUSTRY = (
    "https://www.mod.go.jp/j/policy/agenda/meeting/drastic-reinforcement/pdf/siryo03_02.pdf"
)
IHI_ENGINES = (
    "https://www.ihi.co.jp/en/products/aeroengine_space_defense/aircraft_engines/index.html"
)
IHI_HGV = "https://www.mod.go.jp/j/press/news/2024/03/12a.html"
NEC_DEFENCE = "https://jpn.nec.com/recruit/dept/ans/index.html"
NEC_UNICORN = "https://www.mod.go.jp/j/press/news/2024/11/15d.html"
NEC_TRANSFER_FUND = "https://www.mod.go.jp/j/press/news/2026/01/16b.html"
TAIWAN_PROCUREMENT = "https://web.pcc.gov.tw/prkms/tender/common/updated/readTenderUpdated"

RESEARCH_MARKER = "【2026-08-05深检补充】"


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


def set_note(inv: SupplyChainInvestigation, text: str) -> None:
    description = inv.description or ""
    if RESEARCH_MARKER in description:
        description = description.split(RESEARCH_MARKER, 1)[0].rstrip()
    inv.description = f"{description}\n\n{RESEARCH_MARKER}{text}"


def add_entity(
    db,
    row_id: str,
    name: str,
    name_zh: str,
    country: str,
    entity_type: str,
    roles: list[str],
    source_url: str,
    notes: str,
    *,
    parent_id: str | None = None,
    aliases: list[str] | None = None,
):
    return upsert(
        db,
        SupplyChainEntity,
        row_id,
        name=name,
        name_zh=name_zh,
        country=country,
        entity_type=entity_type,
        aliases=aliases or [],
        parent_id=parent_id,
        defense_roles=roles,
        source_url=source_url,
        notes=notes,
    )


def add_open(
    db,
    row_id: str,
    case_id: str,
    title: str,
    source_type: str,
    publisher: str,
    url: str,
    excerpt: str,
    facts: list[str],
    grade: str,
    status: str,
    limitations: list[str],
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
        limitations=limitations,
    )


def add_screening(
    db,
    inv: SupplyChainInvestigation,
    case_id: str,
    slug: str,
    names: list[str],
    result: str | None = None,
    *,
    url: str = TAIWAN_PROCUREMENT,
    publisher: str = "台湾政府电子采购网/国防部公开信息",
    facts: list[str] | None = None,
    limitations: list[str] | None = None,
):
    row_id = f"ose-20260805-{slug}-taiwan-screening"
    add_open(
        db,
        row_id,
        case_id,
        "对台军售与台湾军方采购公开信息筛查",
        "screening_note",
        publisher,
        url,
        result
        or "截至2026-08-05，本轮按企业名称、产品名称和台湾军方采购关键词交叉检索，未发现可直接闭环的对台军售记录。",
        facts
        or [
            f"按企业中英文名及别名检索：{'、'.join(names)}",
            "截至2026-08-05，未发现可把该链直接闭环至台湾军方采购或对台装备转移的公开记录",
        ],
        "C",
        "follow_up",
        limitations
        or [
            "公开采购库未命中不等于不存在非公开、代理商或政府间采购",
            "本记录只说明本轮公开源检索结果，不能作为排他性证明",
        ],
    )
    attach(inv, "open_source_evidence_ids", row_id)


def add_relation(
    db,
    row_id: str,
    case_id: str,
    shipment_id: str,
    relation_type: str,
    grade: str,
    score: int,
    reasoning: str,
    facts: list[str],
    boundary: str,
):
    return upsert(
        db,
        SupplyChainEvidence,
        row_id,
        case_id=case_id,
        shipment_id=shipment_id,
        relation_type=relation_type,
        evidence_grade=grade,
        score=score,
        status="follow_up",
        reasoning=reasoning,
        verified_facts=facts,
        model_review={
            "reviewed": True,
            "decision": "follow_up",
            "boundary": boundary,
            "reviewed_at": "2026-08-05",
        },
        is_reportable=True,
    )


def enrich_dhanush(db) -> None:
    inv = db.get(SupplyChainInvestigation, "inv-india-lead-dhanush-china-bearing")
    case_id = "case-india-lead-dhanush-china-bearing"
    entities = [
        (
            "ent-india-dhanush-gcf",
            "Gun Carriage Factory, Jabalpur",
            "印度贾巴尔普尔炮车工厂",
            "India",
            "defense_factory",
            ["Dhanush 155毫米/45倍径火炮生产与装配"],
            PIB_DHANUSH_PARTS,
            "印度政府通报确认涉事轴承由该厂为Dhanush项目采购。",
        ),
        (
            "ent-india-army-dhanush",
            "Indian Army",
            "印度陆军",
            "India",
            "military_end_user",
            ["Dhanush火炮接装与使用"],
            PIB_DHANUSH_ARMY,
            "印度政府确认首批6门Dhanush于2019年移交陆军，初始订单114门。",
        ),
        (
            "ent-china-dhanush-bearing-undisclosed",
            "Chinese Wire Race Roller Bearing Manufacturer (undisclosed)",
            "中国线轨滚柱轴承制造商（未披露）",
            "China",
            "component_manufacturer",
            ["Dhanush项目6只涉事轴承的实际制造商"],
            PIB_DHANUSH_PARTS,
            "官方文件未公开中国制造企业名称，不得以候选企业替代。",
        ),
    ]
    for row in entities:
        add_entity(db, *row)
    add_open(
        db,
        "ose-20260805-dhanush-official-parts",
        case_id,
        "印度政府确认Dhanush火炮6只轴承实际由中国企业制造",
        "official_document",
        "印度新闻信息局/国防部",
        PIB_DHANUSH_PARTS,
        "官方答复称，炮车工厂从Sidh Sales Syndicate采购6只线轨滚柱轴承，文件标示德国CRB，实际由一家中国企业制造；轴承拟装于Dhanush火炮。",
        [
            "数量为6只线轨滚柱轴承",
            "实际制造国为中国，供应文件将其标示为德国CRB产品",
            "最终项目为贾巴尔普尔炮车工厂生产的Dhanush火炮",
            "案件已移交印度中央调查局，涉事供应商业务被暂停",
        ],
        "A",
        "verified",
        ["官方未披露中国制造商名称、进口报关单及轴承序列号"],
    )
    add_open(
        db,
        "ose-20260805-dhanush-army-induction",
        case_id,
        "印度政府确认Dhanush首批交付及114门初始订单",
        "official_document",
        "印度新闻信息局/国防部",
        PIB_DHANUSH_ARMY,
        "2019年4月8日首批6门Dhanush移交印度陆军，初始订单总量114门。",
        ["首批6门于2019-04-08移交印度陆军", "初始订单为114门"],
        "A",
        "verified",
        ["文件没有逐门列示是否安装上述6只涉事轴承"],
    )
    attach(inv, "entity_ids", *(row[0] for row in entities))
    attach(
        inv,
        "open_source_evidence_ids",
        "ose-20260805-dhanush-official-parts",
        "ose-20260805-dhanush-army-induction",
    )
    add_screening(db, inv, case_id, "dhanush", ["Sidh Sales Syndicate", "Dhanush", "Gun Carriage Factory"])
    set_note(inv, "官方文件已把6只中国制造轴承、印度中间商、炮车工厂和Dhanush项目闭环；但没有逐门装机序列号。未发现该火炮或涉事轴承对台军售记录。")


def enrich_dhaksha(db) -> None:
    inv = db.get(SupplyChainInvestigation, "inv-india-lead-dhaksha-logistics-drone")
    case_id = "case-india-lead-dhaksha-logistics-drone"
    add_open(
        db,
        "ose-20260805-dhaksha-contract",
        case_id,
        "Coromandel确认Dhaksha获印度陆军200架中空物流无人机订单",
        "company_disclosure",
        "Coromandel International",
        COROMANDEL_DHAKSHA,
        "母公司公告确认Dhaksha获200架中空物流无人机及附件订单，最终用户为印度陆军。",
        ["数量200架", "产品为中空物流无人机及附件", "最终用户为印度陆军", "公告日期为2023-08-07"],
        "A",
        "verified",
        ["16.5亿卢比（165 crore）口径同时包含农业无人机订单，不能全部归入陆军合同"],
    )
    add_open(
        db,
        "ose-20260805-dhaksha-taiwan-alternative",
        case_id,
        "Dhaksha称替代飞控部件来自美国和台湾",
        "media_report",
        "India Today",
        DHAKSHA_TAIWAN,
        "Dhaksha否认军用合同使用中国部件，并称为飞控找到来自美国和台湾的替代制造商。",
        ["企业称尚未向印度军方交付合同无人机", "企业称替代飞控部件制造地包括美国和台湾"],
        "B",
        "follow_up",
        ["报道未披露台湾制造商、料号、数量、提单或装机批次", "这是台湾到印度的零部件方向，不是印度对台军售"],
    )
    relation_ids = []
    for suffix, shipment_id, product in [
        ("thrust-stand", "shp-dhaksha-new-wing-thrust-stand-20260214", "LY-70KGF推力测试台"),
        ("calibration", "shp-dhaksha-new-wing-calibration-20260214", "EKT-VT-980 AOI/校准设备"),
    ]:
        relation_id = f"ev-20260805-dhaksha-{suffix}"
        add_relation(
            db,
            relation_id,
            case_id,
            shipment_id,
            "manufacturing_equipment_overlap",
            "C",
            42,
            f"{product}由中国企业运往Dhaksha，可证明企业制造/测试体系存在中国来源设备，但不能证明设备或其测试对象进入200架陆军无人机合同。",
            ["收货企业为Dhaksha", "发货企业为天津New Wing Advanced", f"货物为{product}", "到货日期为2026-02-14"],
            "enterprise_manufacturing_equipment_only",
        )
        relation_ids.append(relation_id)
    attach(inv, "open_source_evidence_ids", "ose-20260805-dhaksha-contract", "ose-20260805-dhaksha-taiwan-alternative")
    attach(inv, "evidence_ids", *relation_ids)
    add_screening(
        db,
        inv,
        case_id,
        "dhaksha",
        ["Dhaksha", "Dhaksha Unmanned Systems"],
        "检索到的涉台关系仅为Dhaksha声称飞控替代件制造地包括台湾；未发现Dhaksha向台湾军方销售无人机的公开记录。",
        url=DHAKSHA_TAIWAN,
        publisher="India Today/台湾政府电子采购网",
        facts=["公开报道记载的方向为台湾零部件流入印度Dhaksha", "未发现反向的印度对台无人机军售闭环"],
        limitations=["台湾供应商和料号未披露", "公开库未命中不能排除代理商或非公开政府间交易"],
    )
    set_note(inv, "200架印度陆军订单由母公司公告确认；2026年中国来源测试/校准设备只到企业制造体系层面，尚不能归入合同BOM。涉台信息为台湾部件替代来源，方向不是对台军售。")


def enrich_drone_400(db) -> None:
    inv = db.get(SupplyChainInvestigation, "inv-india-lead-army-400-drone-cancelled")
    case_id = "case-india-lead-army-400-drone-cancelled"
    add_open(
        db,
        "ose-20260805-india-400-drone-cancellation",
        case_id,
        "印度陆军约23亿卢比、400架物流无人机合同取消报道",
        "media_report",
        "India Today",
        DRONE_400,
        "报道将400架拆分为200架中型、100架重型和100架轻型物流无人机，并称合同因疑似中国部件被取消。",
        ["合计400架", "构成为200架中型、100架重型、100架轻型物流无人机", "报道金额约23亿卢比（230 crore）", "Dhaksha为受影响企业之一"],
        "B",
        "follow_up",
        ["未取得印度国防部逐合同取消决定", "不能把三家风险提示企业自动等同于全部400架合同中标方"],
    )
    add_open(
        db,
        "ose-20260805-india-drone-component-policy",
        case_id,
        "印度政府确认无人机关键部件仍广泛依赖中国进口",
        "official_document",
        "印度新闻信息局/国防部",
        PIB_DRONE_POLICY,
        "印度政府的无人机自主化说明指出，多类关键部件仍广泛从中国进口，支持行业层面的供应链风险判断。",
        ["官方承认无人机关键部件存在中国进口依赖", "该材料属于行业政策背景而非400架合同的逐票证据"],
        "A",
        "verified",
        ["宏观政策材料不能证明某一家企业或某一批无人机使用中国部件"],
    )
    attach(inv, "open_source_evidence_ids", "ose-20260805-india-400-drone-cancellation", "ose-20260805-india-drone-component-policy")
    add_screening(db, inv, case_id, "india-400-drone", ["Indian Army logistics drone", "Dhaksha", "Sky Industries", "Garuda Aerospace"])
    set_note(inv, "400架数量、类型和约23亿卢比（230 crore）金额来自媒体，印度政府公开材料只支持行业层面的中国部件依赖；未取得逐合同取消文件或对台销售证据。")


def enrich_newspace(db) -> None:
    inv = db.get(SupplyChainInvestigation, "inv-india-lead-newspace-drone-components")
    base_case = "case-india-lead-newspace-drone-components"
    new_case = "case-india-newspace-ulpgm-v3"
    add_entity(
        db,
        "ent-india-drdo-newspace",
        "Defence Research and Development Organisation",
        "印度国防研究与发展组织",
        "India",
        "defense_agency",
        ["ULPGM-V3无人机发射精确制导武器研发与试验"],
        PIB_NEWSPACE_ULPGM,
        "印度国防部官方发布明确点名NewSpace提供国产无人机平台。",
    )
    db.flush()
    upsert(
        db,
        SupplyChainCase,
        new_case,
        country="India",
        title="NewSpace国产无人机参与ULPGM-V3精确制导武器飞行试验",
        procurement_agency="DRDO / 印度国防部",
        procurement_reference="PIB PRID 2148320",
        procurement_date=dt("2025-07-25T00:00:00"),
        supplier_entity_id="ent-india-lead-newspace-drone-components",
        product="NewSpace国产无人机平台及ULPGM-V3试验集成",
        target_program="印度无人机发射精确制导武器ULPGM-V3",
        contract_value=None,
        currency="INR",
        source_url=PIB_NEWSPACE_ULPGM,
        source_excerpt="印度国防部确认ULPGM-V3由NewSpace Research Technologies研制的国产无人机发射并完成飞行试验。",
        status="verified",
    )
    db.flush()
    add_open(
        db,
        "ose-20260805-newspace-ulpgm",
        new_case,
        "印度国防部点名NewSpace无人机参与ULPGM-V3试验",
        "official_document",
        "印度新闻信息局/国防部",
        PIB_NEWSPACE_ULPGM,
        "官方发布确认NewSpace Research Technologies研制的国产无人机用于发射ULPGM-V3。",
        ["企业为NewSpace Research Technologies", "平台为印度国产无人机", "用途为ULPGM-V3精确制导武器飞行试验"],
        "A",
        "verified",
        ["未公开无人机型号、BOM或本案两批进口件的装机归属"],
    )
    add_open(
        db,
        "ose-20260805-newspace-tdf",
        base_case,
        "DRDO技术发展基金项目确认NewSpace军民两用自主无人机能力",
        "official_document",
        "印度新闻信息局/DRDO",
        PIB_NEWSPACE_TDF,
        "官方材料列明NewSpace承担室内第一响应自主无人机项目，集成自主导航、目标检测、定位回退和飞控固件。",
        ["项目承担方为NewSpace", "技术模块包括自主导航、目标检测、定位回退和飞控固件", "项目由DRDO技术发展基金支持"],
        "A",
        "verified",
        ["该项目与陆军蜂群无人机或ULPGM-V3并非同一装备批次"],
    )
    relation_ids = []
    for slug, shipment_id, fact in [
        ("aerium", "shp-newspace-aerium-20260225", "以色列Aerium USB线缆组件"),
        ("iqinetics", "shp-newspace-iqinetics-20260223", "美国IQinetics电机"),
    ]:
        relation_id = f"ev-20260805-newspace-{slug}-replacement"
        add_relation(
            db,
            relation_id,
            base_case,
            shipment_id,
            "non_china_replacement_supply",
            "B",
            58,
            f"贸易记录证明NewSpace在2026年取得{fact}，可作为非中国来源替代供应监测；缺少BOM，不能归入具体军用型号。",
            ["进口商为NewSpace Research & Technologies", f"产品为{fact}", "原产方向不是中国"],
            "company_level_replacement_only",
        )
        relation_ids.append(relation_id)
    attach(inv, "entity_ids", "ent-india-drdo-newspace")
    attach(inv, "case_ids", new_case)
    attach(inv, "open_source_evidence_ids", "ose-20260805-newspace-ulpgm", "ose-20260805-newspace-tdf")
    attach(inv, "evidence_ids", *relation_ids)
    add_screening(db, inv, base_case, "newspace", ["NewSpace Research & Technologies", "Beluga", "Nimbus", "ULPGM"])
    set_note(inv, "印度国防部已直接确认NewSpace国产无人机用于ULPGM-V3试验；2026年以色列线缆与美国电机只能证明企业级替代来源，尚无具体型号装机闭环，也未发现对台军售。")


def enrich_remaining_india(db) -> None:
    rows = [
        (
            "inv-india-garuda-defense-drone",
            "case-india-garuda-defense-drones",
            "garuda",
            "ose-20260805-garuda-defence-case-study",
            "Garuda官网称其防务监视无人机为100%印度制造",
            "company_disclosure",
            "Garuda Aerospace",
            GARUDA_DEFENCE,
            "公司案例页称防务导向模块化监视无人机为印度设计制造并用于昼夜ISR；这与贸易记录中的中国部件形成需核验的口径冲突。",
            ["产品任务包括持续监视、周界巡逻、昼夜ISR", "企业宣称100%印度设计制造和支持"],
            "B",
            "follow_up",
            ["企业自述未披露客户、合同、型号、BOM和交付批次", "不能据此否定现有中国来源部件进口记录"],
            ["Garuda Aerospace", "Jatayu", "SkyPod"],
            "企业级中国部件贸易记录与公司100%印度制造表述需要按具体型号、料号和生产批次核对；未发现对台军售。",
        ),
        (
            "inv-india-paras-defense-optics",
            "case-india-paras-air-defense-optics",
            "paras",
            "ose-20260805-paras-drdo-disclosure",
            "Paras正式披露DRDO防空高精度光学系统订单",
            "company_disclosure",
            "Paras Defence and Space Technologies",
            PARAS_DISCLOSURE,
            "公司正式披露收到DRDO高精度防空光学系统订单，含税金额8.028亿卢比（80.28 crore），18个月内执行。",
            ["客户为DRDO", "用途为防空应用高精度光学系统", "合同金额8.028亿卢比（80.28 crore，含税）", "执行期18个月"],
            "A",
            "verified",
            ["披露未公开光学系统BOM，不能将2026-02-02进口镜头组件直接归入该订单"],
            ["Paras Defence", "Paras Defence and Space Technologies"],
            "合同对象、金额和周期已由公司正式披露；中国镜头组件到达Paras在合同前，但仍缺料号/BOM闭环。未发现对台军售。",
        ),
        (
            "inv-india-accord-navy-ew",
            "case-india-accord-ecgnss-jammer",
            "accord",
            "ose-20260805-accord-official-contract",
            "印度国防部确认20套ECGNSS干扰机合同及技术用途",
            "official_document",
            "印度新闻信息局/国防部",
            PIB_ACCORD,
            "印度国防部与Accord签署20套ECGNSS干扰机合同，总额44.9亿卢比，最低75%国产化，用于印度海军舰艇。",
            ["数量20套", "合同金额44.9亿卢比", "最低国产化率75%", "最终用户为印度海军", "功能包括GNSS压制和欺骗干扰"],
            "A",
            "verified",
            ["官方合同未公开散热器、频谱仪或其他分系统BOM"],
            ["Accord Software and Systems", "ECGNSS"],
            "20套、44.9亿卢比、75%国产化和舰载用途均由印度国防部确认；中国来源散热器/仪器仍只有企业级时间重合。未发现对台军售。",
        ),
        (
            "inv-india-ace-rtflt-china-sourcing",
            "case-india-ace-1121-rtflt",
            "ace",
            "ose-20260805-ace-contract-boundary",
            "ACE军用RTFLT合同与中国叉车型号边界复核",
            "company_disclosure",
            "Action Construction Equipment",
            ACE_RELEASE,
            "ACE公告确认1121台军用RTFLT合同；结合公司后续电话会，军方RTFLT属于telehandler，而中国AF80D等记录多为传统平衡重叉车或仓储设备。",
            ["ACE合同数量为1121台", "合同金额42亿卢比", "最终用户覆盖印度陆海空三军", "中国进口型号与军方telehandler存在产品形态差异"],
            "A",
            "verified",
            ["没有军方RTFLT具体型号、吨位、BOM及生产领料记录"],
            ["Action Construction Equipment", "ACE", "RTFLT"],
            "合同本身已确认，但现有中国进口型号多数不能直接匹配军方telehandler；未发现ACE向台湾军方销售RTFLT。",
        ),
        (
            "inv-india-csbc-pump-chain",
            "case-india-sulzer-csbc-pump-delivery",
            "csbc-pump",
            "ose-20260805-csbc-cpc-enduse-boundary",
            "台船收货泵组的台湾中油石化EPC最终用途复核",
            "official_document",
            "台湾国际造船股份有限公司",
            CSBC_CPC,
            "台船官方文件将相关工程对应台湾中油大林石化油品储运中心槽车装卸工场及储槽项目；泵名也与甲苯、混合二甲苯装卸及含油废水相符。",
            ["项目业主为台湾中油", "工程场景为大林石化油品储运中心", "泵组名称与石化装卸和废水工况相符"],
            "A",
            "verified_non_defense",
            ["台船本身具有军民两用造船业务，但主体重合不能推翻该批泵组的民用EPC证据"],
            ["CSBC", "台湾国际造船", "Sulzer Pumps India"],
            "该链确实流入台湾企业，但官方项目和货描均闭环至台湾中油石化EPC，不属于对台军售或军舰设备供应。",
        ),
    ]
    for (
        inv_id,
        case_id,
        slug,
        ose_id,
        title,
        source_type,
        publisher,
        url,
        excerpt,
        facts,
        grade,
        status,
        limits,
        names,
        note,
    ) in rows:
        inv = db.get(SupplyChainInvestigation, inv_id)
        add_open(db, ose_id, case_id, title, source_type, publisher, url, excerpt, facts, grade, status, limits)
        attach(inv, "open_source_evidence_ids", ose_id)
        if inv_id == "inv-india-csbc-pump-chain":
            add_screening(
                db,
                inv,
                case_id,
                slug,
                names,
                "收货方为台湾国际造船，但本案官方EPC文件和泵组货描均指向台湾中油大林石化项目；未发现进入台湾军方装备的证据。",
                url=CSBC_CPC,
                publisher="台湾国际造船股份有限公司/台湾政府电子采购网",
                facts=["台湾收货主体为台船", "具体最终用途为台湾中油大林石化EPC", "不能将台船军工身份等同于该批泵组军用"],
                limitations=["结论仅适用于当前已识别的11台/套泵组及其项目资料"],
            )
        else:
            add_screening(db, inv, case_id, slug, names)
        set_note(inv, note)


def enrich_japan_mhi(db) -> None:
    inv = db.get(SupplyChainInvestigation, "inv-japan-lead-mhi-aeroengine-critical-materials")
    base_case = "case-japan-lead-mhi-aeroengine-critical-materials"
    current_case = "case-japan-mhi-defense-aeroengine-succession"
    taiwan_case = "case-japan-mhi-taiwan-torpedo-boats-1958"
    add_entity(
        db,
        "ent-japan-mhi-current",
        "Mitsubishi Heavy Industries, Ltd.",
        "三菱重工业株式会社",
        "Japan",
        "defense_prime",
        ["日本防卫航空发动机业务", "防卫飞机、导弹和舰艇系统"],
        MHI_NOTICE,
        "2025年三菱重工从集团公司承接防卫航空发动机业务；应与民用航空发动机业务主体区分。",
    )
    add_entity(
        db,
        "ent-japan-mitsubishi-shipbuilding-historical",
        "Mitsubishi Shipbuilding Co., Ltd. (1950s)",
        "三菱造船株式会社（1950年代历史主体）",
        "Japan",
        "historical_defense_shipbuilder",
        ["1950年代台湾海军复仇级鱼雷艇建造与转移"],
        NIDS_TAIWAN_BOATS,
        "该历史主体于1964年与另外两家企业合并为现三菱重工；不得把历史交易写成当代航空发动机销售。",
    )
    add_entity(
        db,
        "ent-taiwan-roc-navy-historical",
        "Republic of China Navy",
        "台湾海军（历史最终用户）",
        "Taiwan",
        "military_end_user",
        ["复仇级鱼雷艇接装与运用"],
        NIDS_TAIWAN_BOATS,
        "日本防卫研究所战史研究年报记载两艇服役至1982年。",
    )
    db.flush()
    upsert(
        db,
        SupplyChainCase,
        current_case,
        country="Japan",
        title="三菱重工承接集团防卫航空发动机业务",
        procurement_agency="日本防卫省/自卫队",
        procurement_reference="MHI business succession notice 2024-2025",
        procurement_date=dt("2025-01-31T00:00:00"),
        supplier_entity_id="ent-japan-mhi-current",
        product="TS1、TJM3等防卫航空发动机业务",
        target_program="日本自卫队防卫航空发动机",
        contract_value=None,
        currency="JPY",
        source_url=MHI_NOTICE,
        source_excerpt="三菱重工公告其从集团航空发动机公司承接防卫航空发动机业务。",
        status="verified",
    )
    upsert(
        db,
        SupplyChainCase,
        taiwan_case,
        country="Japan",
        title="三菱造船下关造船所向台湾海军转移2艘复仇级鱼雷艇（历史案例）",
        procurement_agency="台湾海军（历史）",
        procurement_reference="防卫研究所《战史研究年报》第27号",
        procurement_date=dt("1958-05-01T00:00:00"),
        supplier_entity_id="ent-japan-mitsubishi-shipbuilding-historical",
        product="2艘复仇级40吨级全轻合金鱼雷艇",
        target_program="台湾海军鱼雷艇队",
        contract_value=None,
        currency="JPY",
        source_url=NIDS_TAIWAN_BOATS,
        source_excerpt="日本防卫研究所研究确认三菱下关建造并向台湾海军转移2艘复仇级鱼雷艇。",
        status="verified",
    )
    db.flush()
    add_open(
        db,
        "ose-20260805-mhi-defense-business-succession",
        current_case,
        "三菱重工防卫航空发动机业务主体纠偏",
        "company_disclosure",
        "Mitsubishi Heavy Industries",
        MHI_NOTICE,
        "三菱重工集团公告显示，防卫航空发动机业务由集团航空发动机公司转回三菱重工本体。",
        ["当前防卫航空发动机责任主体为三菱重工本体", "原航空发动机公司节点不能继续笼统代表当前防务发动机业务"],
        "A",
        "verified",
        ["公告不涉及中国来源关键材料或具体进口批次"],
    )
    add_open(
        db,
        "ose-20260805-mhi-defense-products",
        current_case,
        "三菱重工官方防卫产品目录列示防卫航空发动机",
        "company_disclosure",
        "Mitsubishi Heavy Industries",
        MHI_DEFENCE,
        "三菱重工官方防卫业务页面列示TS1、TJM3等防卫航空发动机。",
        ["三菱重工本体经营防卫航空发动机业务", "官方页面列示TS1和TJM3"],
        "A",
        "verified",
        ["产品目录不是采购合同，也不披露材料供应商"],
    )
    add_open(
        db,
        "ose-20260805-mhi-taiwan-torpedo-boats",
        taiwan_case,
        "日本防卫研究所确认1950年代三菱造船对台鱼雷艇转移",
        "official_research",
        "日本防卫省防卫研究所",
        NIDS_TAIWAN_BOATS,
        "研究确认1954至1958年三菱下关建造的7艘轻合金小艇中包含2艘复仇级；1958年三菱人员赴台参加试航和交付，两艇在台湾海军服役至1982年。",
        ["建造方为三菱造船下关造船所", "数量为2艘", "接收方为台湾海军", "两艇服役至1982年"],
        "A",
        "verified",
        ["这是1950年代历史装备转移，与当前航空发动机关键材料链不存在已证明的物料或合同连续性"],
    )
    add_open(
        db,
        "ose-20260805-mhi-shimonoseki-continuity",
        taiwan_case,
        "三菱重工官方沿革确认下关造船所主体演变",
        "company_disclosure",
        "Mitsubishi Heavy Industries",
        MHI_SHIMONOSEKI,
        "官方沿革显示1952年为三菱造船下关造船所，1964年三社合并后改称三菱重工下关造船所。",
        ["1952年主体名称为三菱造船株式会社下关造船所", "1964年三社合并后纳入三菱重工"],
        "A",
        "verified",
        ["企业继承关系不意味着历史交易在当代持续"],
    )
    attach(inv, "entity_ids", "ent-japan-mhi-current", "ent-japan-mitsubishi-shipbuilding-historical", "ent-taiwan-roc-navy-historical")
    attach(inv, "case_ids", current_case, taiwan_case)
    attach(
        inv,
        "open_source_evidence_ids",
        "ose-20260805-mhi-defense-business-succession",
        "ose-20260805-mhi-defense-products",
        "ose-20260805-mhi-taiwan-torpedo-boats",
        "ose-20260805-mhi-shimonoseki-continuity",
    )
    add_screening(
        db,
        inv,
        base_case,
        "mhi",
        ["Mitsubishi Heavy Industries", "Mitsubishi Shipbuilding", "三菱重工", "三菱造船"],
        "确认一项历史直接对台装备转移：三菱造船下关造船所在1950年代向台湾海军转移2艘复仇级鱼雷艇；本轮未发现当代三菱重工航空发动机链对台军售闭环。",
        url=NIDS_TAIWAN_BOATS,
        publisher="日本防卫省防卫研究所/台湾政府电子采购网",
        facts=["历史对台装备转移数量为2艘", "建造主体是现三菱重工的历史合并前主体", "未发现与当前航空发动机关键材料链相连的当代台湾合同"],
        limitations=["必须把1950年代历史造船主体与当前航空发动机业务分开呈现", "未命中当代公开采购不等于不存在非公开交易"],
    )
    set_note(inv, "主体已纠偏：当前防卫航空发动机业务由三菱重工本体承接。对台方向确认1950年代历史前身向台湾海军转移2艘复仇级鱼雷艇，但不能延伸成当代航空发动机链对台军售；仍无企业级中国材料进口批次。")


def enrich_japan_others(db) -> None:
    # Kawasaki Heavy Industries
    inv = db.get(SupplyChainInvestigation, "inv-japan-lead-khi-aerospace-materials")
    case_id = "case-japan-lead-khi-aerospace-materials"
    add_open(
        db,
        "ose-20260805-khi-p1-c2-official",
        case_id,
        "川崎重工官方确认P-1、C-2和CH-47J防务航空项目",
        "company_disclosure",
        "Kawasaki Heavy Industries",
        KHI_AEROSPACE,
        "川崎重工官方沿革确认其为日本防卫省开发制造P-1巡逻机、C-2运输机，并许可生产CH-47J。",
        ["P-1最终用户为海上自卫队", "C-2最终用户为航空自卫队", "川崎重工许可生产CH-47J"],
        "A",
        "verified",
        ["官方产品沿革未披露中国来源材料、供应商或进口批次"],
    )
    add_open(
        db,
        "ose-20260805-khi-mod-contract-ranking",
        case_id,
        "日本防卫省列示川崎重工2023年度155件、3886亿日元中央采购",
        "official_document",
        "日本防卫省",
        JAPAN_DEFENCE_INDUSTRY,
        "日本防卫省材料列川崎重工为中央采购金额第二位，155件、3886亿日元，主要项目包括P-1、C-2及新型反舰导弹技术研究。",
        ["合同件数155件", "合同金额3886亿日元", "主要装备包括P-1、C-2及反舰导弹技术研究"],
        "A",
        "verified",
        ["汇总表未披露单份合同、BOM或进口材料来源"],
    )
    attach(inv, "open_source_evidence_ids", "ose-20260805-khi-p1-c2-official", "ose-20260805-khi-mod-contract-ranking")
    add_screening(db, inv, case_id, "khi", ["Kawasaki Heavy Industries", "川崎重工", "P-1", "C-2", "CH-47J"])
    set_note(inv, "P-1、C-2、CH-47J及日本防卫省采购规模已由官方材料确认；仍无可归属川崎重工的中国关键材料逐批贸易记录，也未发现对台军售。")

    # IHI Corporation and IHI Aerospace are separate relevant nodes.
    inv = db.get(SupplyChainInvestigation, "inv-japan-lead-ihi-aerospace-materials")
    base_case = "case-japan-lead-ihi-aerospace-materials"
    engine_case = "case-japan-ihi-f7-10-p1"
    hgv_case = "case-japan-ihi-hgv-space-demo"
    add_entity(
        db,
        "ent-japan-ihi-corporation",
        "IHI Corporation",
        "IHI株式会社",
        "Japan",
        "defense_supplier",
        ["P-1用F7-10发动机主承包和量产", "下一代战斗机发动机系统"],
        IHI_ENGINES,
        "航空发动机业务主体为IHI株式会社；应与IHI Aerospace宇航/火箭业务节点区分。",
    )
    add_entity(
        db,
        "ent-japan-mod-ihi",
        "Japan Ministry of Defense",
        "日本防卫省",
        "Japan",
        "military_end_user",
        ["P-1发动机采购", "高超声速滑翔体探测跟踪技术验证"],
        JAPAN_DEFENCE_INDUSTRY,
        "日本防卫省为相关项目采购与试验主管机构。",
    )
    db.flush()
    upsert(
        db,
        SupplyChainCase,
        engine_case,
        country="Japan",
        title="IHI为P-1巡逻机量产F7-10发动机",
        procurement_agency="日本防卫省/海上自卫队",
        procurement_reference="IHI official aircraft engine portfolio",
        procurement_date=None,
        supplier_entity_id="ent-japan-ihi-corporation",
        product="F7-10涡扇发动机",
        target_program="P-1固定翼反潜巡逻机",
        contract_value=None,
        currency="JPY",
        source_url=IHI_ENGINES,
        source_excerpt="IHI官方页面确认F7-10为P-1动力，并由IHI作为主承包商量产。",
        status="verified",
    )
    upsert(
        db,
        SupplyChainCase,
        hgv_case,
        country="Japan",
        title="IHI Aerospace承接高超声速滑翔体天基探测跟踪技术验证",
        procurement_agency="日本防卫省",
        procurement_reference="防卫省2024-03-12公告",
        procurement_date=dt("2024-03-06T00:00:00"),
        supplier_entity_id="ent-japan-lead-ihi-aerospace-materials",
        product="HTV-X搭载红外传感器与HGV探测跟踪技术验证",
        target_program="高超声速滑翔体探测与跟踪",
        contract_value=None,
        currency="JPY",
        source_url=IHI_HGV,
        source_excerpt="日本防卫省确认2024年3月6日与IHI Aerospace签署HTV-X搭载HGV探测跟踪技术验证合同。",
        status="verified",
    )
    db.flush()
    add_open(
        db,
        "ose-20260805-ihi-f7-engine",
        engine_case,
        "IHI官方确认F7-10为P-1发动机并由其主承包量产",
        "company_disclosure",
        "IHI Corporation",
        IHI_ENGINES,
        "IHI官方航空发动机页面列明F7-10为P-1巡逻机动力，由IHI作为主承包商量产。",
        ["发动机型号F7-10", "搭载平台P-1", "IHI为主承包商和量产方"],
        "A",
        "verified",
        ["未披露合金、磁材和电子材料供应商"],
    )
    add_open(
        db,
        "ose-20260805-ihi-hgv-contract",
        hgv_case,
        "日本防卫省确认IHI Aerospace高超声速滑翔体探测合同",
        "official_document",
        "日本防卫省",
        IHI_HGV,
        "合同于2024年3月6日成立，承包方为IHI Aerospace，内容为利用HTV-X和红外传感器开展HGV探测跟踪技术验证。",
        ["承包方为IHI Aerospace", "合同日期为2024-03-06", "用途为高超声速滑翔体探测跟踪技术验证"],
        "A",
        "verified",
        ["公告未披露合同金额、BOM或中国来源材料"],
    )
    add_open(
        db,
        "ose-20260805-ihi-mod-contract-ranking",
        base_case,
        "日本防卫省列示IHI主要防务合同与年度规模",
        "official_document",
        "日本防卫省",
        JAPAN_DEFENCE_INDUSTRY,
        "日本防卫省材料列IHI 2023年度中央采购31件、1257亿日元，主要项目包括OZZ-100水下无人机、下一代战斗机发动机系统和P-1备用F7-10。",
        ["合同件数31件", "合同金额1257亿日元", "主要项目包括OZZ-100、下一代战斗机发动机系统及F7-10"],
        "A",
        "verified",
        ["年度汇总不能替代逐合同和逐物料证据"],
    )
    attach(inv, "entity_ids", "ent-japan-ihi-corporation", "ent-japan-mod-ihi")
    attach(inv, "case_ids", engine_case, hgv_case)
    attach(inv, "open_source_evidence_ids", "ose-20260805-ihi-f7-engine", "ose-20260805-ihi-hgv-contract", "ose-20260805-ihi-mod-contract-ranking")
    add_screening(db, inv, base_case, "ihi", ["IHI Corporation", "IHI Aerospace", "IHI株式会社"])
    set_note(inv, "主体已拆分：IHI株式会社负责F7-10等航空发动机，IHI Aerospace另有HGV天基探测验证合同。两条军用终端均已由官方来源确认，但无中国材料逐批记录，也未发现对台军售。")

    # NEC: add a named overseas military transfer to India.
    inv = db.get(SupplyChainInvestigation, "inv-japan-lead-nec-defense-electronics")
    base_case = "case-japan-lead-nec-defense-electronics"
    unicorn_case = "case-japan-nec-unicorn-india-transfer"
    add_entity(
        db,
        "ent-japan-nec-corporation",
        "NEC Corporation",
        "日本电气株式会社",
        "Japan",
        "defense_supplier",
        ["雷达、JADGE、防空通信、舰艇网络和复合通信天线"],
        NEC_DEFENCE,
        "NEC本体为日本防卫电子主要承包方；应与NEC Aerospace Systems子公司节点区分。",
    )
    add_entity(
        db,
        "ent-india-navy-nec-unicorn",
        "Indian Navy",
        "印度海军",
        "India",
        "military_end_user",
        ["UNICORN舰载复合通信天线接收方"],
        NEC_UNICORN,
        "日本防卫省确认日印已签署对印度海军转移UNICORN的细目安排。",
    )
    db.flush()
    upsert(
        db,
        SupplyChainCase,
        unicorn_case,
        country="Japan",
        title="NEC向印度海军转移UNICORN舰载复合通信天线",
        procurement_agency="印度海军/日本防卫省",
        procurement_reference="日印防卫装备转移细目安排",
        procurement_date=dt("2024-11-15T00:00:00"),
        supplier_entity_id="ent-japan-nec-corporation",
        product="UNICORN舰载复合通信天线",
        target_program="印度海军舰艇隐身通信系统",
        contract_value=None,
        currency="JPY",
        source_url=NEC_UNICORN,
        source_excerpt="日本防卫省确认签署向印度海军转移UNICORN的细目安排；后续公开规格调整计划申请企业为NEC、认定额约15亿日元。",
        status="verified",
    )
    db.flush()
    add_open(
        db,
        "ose-20260805-nec-unicorn-transfer",
        unicorn_case,
        "日本防卫省确认向印度海军转移UNICORN",
        "official_document",
        "日本防卫省",
        NEC_UNICORN,
        "日印双方签署向印度海军转移UNICORN的细目安排；该系统把多副天线集成为一体以提升舰艇隐身性，并已用于日本海自最上级护卫舰。",
        ["最终用户为印度海军", "产品为UNICORN舰载复合通信天线", "系统用于提升舰艇隐身性", "日本海自最上级护卫舰已采用"],
        "A",
        "verified",
        ["公告未披露具体印度舰型、交付数量、合同总价和电子元器件BOM"],
    )
    add_open(
        db,
        "ose-20260805-nec-unicorn-fund",
        unicorn_case,
        "日本防卫省列明NEC为印度UNICORN转移申请企业",
        "official_document",
        "日本防卫省",
        NEC_TRANSFER_FUND,
        "防卫装备转移规格调整计划的历史认定表列明印度UNICORN项目申请企业为NEC，2024年7月认定额约15亿日元。",
        ["项目名称为印度舰载复合通信天线UNICORN", "申请企业为NEC", "认定时间为2024年7月", "认定额约15亿日元"],
        "A",
        "verified",
        ["15亿日元是规格调整计划认定额，不应等同于最终装备销售合同总价"],
    )
    add_open(
        db,
        "ose-20260805-nec-defense-capabilities",
        base_case,
        "NEC官方列示防空、舰艇网络、雷达和水下声学防务能力",
        "company_disclosure",
        "NEC Corporation",
        NEC_DEFENCE,
        "NEC官方业务介绍列示JADGE、防空通信、舰艇网络、雷达、水下声学、红外传感器和卫星系统。",
        ["NEC防务业务涵盖雷达和防空通信", "涵盖舰艇网络、水下声学和红外传感器", "涵盖卫星和空间态势相关系统"],
        "A",
        "verified",
        ["业务能力介绍不披露中国来源电子材料供应商"],
    )
    attach(inv, "entity_ids", "ent-japan-nec-corporation", "ent-india-navy-nec-unicorn")
    attach(inv, "case_ids", unicorn_case)
    attach(inv, "open_source_evidence_ids", "ose-20260805-nec-unicorn-transfer", "ose-20260805-nec-unicorn-fund", "ose-20260805-nec-defense-capabilities")
    add_screening(db, inv, base_case, "nec", ["NEC Corporation", "NEC Aerospace Systems", "日本電気", "UNICORN"])
    set_note(inv, "新增NEC向印度海军转移UNICORN的官方闭环，且日本防卫省明确NEC为申请企业、规格调整认定额约15亿日元；该金额不是销售合同总价。未发现NEC对台军售，也无中国电子材料逐批记录。")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        enrich_dhanush(db)
        enrich_dhaksha(db)
        enrich_drone_400(db)
        enrich_newspace(db)
        enrich_remaining_india(db)
        enrich_japan_mhi(db)
        enrich_japan_others(db)
        db.commit()
        print("Enriched 9 India and 4 Japan supply-chain investigations.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
