"""Add newly verified nodes to incomplete defence supply-chain investigations."""
from __future__ import annotations

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainEntity,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
)


def upsert(db, model, row_id: str, **values):
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def attach(row, field: str, *row_ids: str):
    values = list(getattr(row, field) or [])
    for row_id in row_ids:
        if row_id not in values:
            values.append(row_id)
    setattr(row, field, values)


def entity(
    db,
    row_id: str,
    name: str,
    name_zh: str | None,
    country: str,
    entity_type: str,
    roles: list[str],
    source_url: str,
    notes: str,
    parent_id: str | None = None,
):
    return upsert(
        db,
        SupplyChainEntity,
        row_id,
        name=name,
        name_zh=name_zh,
        country=country,
        entity_type=entity_type,
        aliases=[],
        parent_id=parent_id,
        defense_roles=roles,
        source_url=source_url,
        notes=notes,
    )


def evidence(
    db,
    row_id: str,
    case_id: str,
    title: str,
    publisher: str,
    source_url: str,
    excerpt: str,
    facts: list[str],
    grade: str,
    limitations: list[str],
    source_type: str = "official_document",
    status: str = "verified",
):
    return upsert(
        db,
        SupplyChainOpenSourceEvidence,
        row_id,
        case_id=case_id,
        title=title,
        source_type=source_type,
        source_publisher=publisher,
        source_url=source_url,
        source_excerpt=excerpt,
        verified_facts=facts,
        evidence_grade=grade,
        status=status,
        limitations=limitations,
    )


def add_entities(db, investigation_id: str, rows: list[tuple]):
    inv = db.get(SupplyChainInvestigation, investigation_id)
    if inv is None:
        return None
    for row in rows:
        entity(db, *row)
    db.flush()
    attach(inv, "entity_ids", *(row[0] for row in rows))
    return inv


def add_evidence(db, inv, rows: list[tuple]):
    if inv is None:
        return
    for row in rows:
        evidence(db, *row)
    attach(inv, "open_source_evidence_ids", *(row[0] for row in rows))


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Quadrant: keep the DOJ's anonymous China manufacturer separate from
        # Hangzhou X-Mag, whose direct public shipment is independently dated 2024.
        quadrant_url = (
            "https://www.justice.gov/archives/opa/pr/"
            "three-arrested-illegal-scheme-export-controlled-data-and-defraud-department-defense"
        )
        inv = add_entities(
            db,
            "inv-us-lead-quadrant-fighter-magnets",
            [
                (
                    "ent-quadrant-china-magnet-anon",
                    "PRC Magnet Manufacturer (undisclosed)",
                    "中国稀土磁体冶炼及充磁企业（未披露）",
                    "China",
                    "china_exporter",
                    ["按Quadrant技术数据在中国完成稀土磁体冶炼和充磁"],
                    quadrant_url,
                    "美国司法部确认该节点存在，但未披露企业名称；不得与杭州X-Mag直接等同。",
                    None,
                ),
                (
                    "ent-quadrant-us-dod",
                    "U.S. Department of Defense",
                    "美国国防部",
                    "United States",
                    "military_end_user",
                    ["F-16、F/A-18及其他国防资产终端采购体系"],
                    quadrant_url,
                    "司法材料确认两家美国零部件企业向美国国防部供应相关组件。",
                    None,
                ),
            ],
        )
        if inv:
            inv.description = (
                "中国稀土磁体企业（司法材料未披露）按技术数据完成冶炼和充磁，"
                "经Quadrant Magnetics LLC及两家匿名美国零部件企业进入美国国防部F-16、"
                "F/A-18等装备。另有杭州X-Mag于2024年向Quadrant发运3,050千克稀土磁体的"
                "直接贸易记录；2026年杭州X-Mag虽仍有对美出口，但尚不能确认买方为Quadrant。"
            )

        # DDG-51: identify the permanent-magnet motor supplier from DRS product material.
        drs_url = "https://www.leonardodrs.com/wp-content/uploads/2023/08/drs-catalog-2013-final-online.pdf"
        inv = add_entities(
            db,
            "inv-us-lead-ddg51-nefeb-motor",
            [
                (
                    "ent-ddg51-leonardo-drs",
                    "Leonardo DRS, Inc.",
                    "Leonardo DRS公司",
                    "United States",
                    "tier_supplier",
                    ["DDG-51混合电力驱动1.5MW永磁电机供应商"],
                    drs_url,
                    "DRS产品资料明确将其永磁电机用于DDG-51主减速齿轮混合推进场景。",
                    None,
                ),
            ],
        )
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-ddg51-drs-pm-motor",
                    "case-us-lead-ddg51-nefeb-motor",
                    "DRS DDG-51混合电力驱动永磁电机产品资料",
                    "Leonardo DRS",
                    drs_url,
                    "DRS资料确认其1.5MW永磁电机适配DDG-51主减速齿轮混合电力驱动系统。",
                    ["DRS为DDG-51混合电力驱动提供永磁电机节点", "电机额定功率1.5MW"],
                    "A",
                    ["资料未披露磁体加工商和中国钕铁硼制造商名称"],
                ),
            ],
        )
        if inv:
            inv.description = (
                "中国来源钕铁硼磁体经未披露材料加工商进入DRS/Leonardo DRS的1.5MW永磁电机，"
                "用于DDG-51驱逐舰主减速齿轮混合电力驱动系统。电机供应商已确认，"
                "中国磁体企业和中间加工商仍待穿透。"
            )

        # M1A2: the tank prime is public even though GAO anonymized the magnet
        # and reference/navigation-unit suppliers.
        army_abrams_url = (
            "https://api.army.mil/e2/c/downloads/2024/07/19/ab2038a9/"
            "u-s-army-portfolio-2024.pdf"
        )
        inv = add_entities(
            db,
            "inv-us-lead-m1a2-smco-navigation",
            [
                (
                    "ent-m1a2-gdls",
                    "General Dynamics Land Systems",
                    "通用动力地面系统公司",
                    "United States",
                    "prime_contractor",
                    ["M1A2 Abrams主承包商及系统集成商"],
                    army_abrams_url,
                    "美国陆军项目组合资料将General Dynamics Land Systems列为Abrams主承包商。",
                    None,
                ),
                (
                    "ent-m1a2-us-army",
                    "U.S. Army",
                    "美国陆军",
                    "United States",
                    "military_end_user",
                    ["M1A2 Abrams采购与使用部门"],
                    army_abrams_url,
                    "美国陆军为M1A2 Abrams项目采购和使用部门。",
                    None,
                ),
            ],
        )
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-m1a2-gdls-prime",
                    "case-us-lead-m1a2-smco-navigation",
                    "M1A2 Abrams主承包商核验",
                    "美国陆军",
                    army_abrams_url,
                    "美国陆军2024项目组合将General Dynamics Land Systems列为Abrams主承包商。",
                    ["General Dynamics Land Systems为M1A2主承包商", "美国陆军为终端采购使用部门"],
                    "A",
                    ["未披露钐钴磁体企业和参考导航装置分包商"],
                ),
            ],
        )
        if inv:
            inv.description = (
                "中国钐金属→美国磁体企业（未披露）→参考/导航装置分包商（未披露）"
                "→General Dynamics Land Systems→美国陆军M1A2 Abrams坦克。"
                "主承包商和终端已确认，磁体及导航装置两级仍待穿透。"
            )

        # Hong Dark: restore the disclosed U.S. broker and major contractor tiers.
        senate_url = (
            "https://www.armed-services.senate.gov/download/"
            "inquiry-into-counterfeit-electronic-parts-in-the-department-of-defense-supply-chain"
        )
        inv = add_entities(
            db,
            "inv-us-lead-hong-dark-electronics",
            [
                (
                    "ent-hongdark-global-ic",
                    "Global IC Trading Group",
                    "Global IC贸易集团",
                    "United States",
                    "distributor",
                    ["深圳鸿达疑似假冒电子元件的美国中间供应商"],
                    senate_url,
                    "参议院调查材料确认Global IC接收深圳鸿达元件并向国防承包体系供货。",
                    None,
                ),
                (
                    "ent-hongdark-l3",
                    "L-3 Communications",
                    "L-3通信公司",
                    "United States",
                    "defense_supplier",
                    ["军用航空和电子系统承包商"],
                    senate_url,
                    "属于调查材料披露的下游国防承包商。",
                    None,
                ),
                (
                    "ent-hongdark-boeing",
                    "The Boeing Company",
                    "波音公司",
                    "United States",
                    "prime_contractor",
                    ["军用航空装备总承包商"],
                    senate_url,
                    "属于调查材料披露的下游国防承包商。",
                    None,
                ),
                (
                    "ent-hongdark-lockheed",
                    "Lockheed Martin Corporation",
                    "洛克希德·马丁",
                    "United States",
                    "prime_contractor",
                    ["军用航空与武器系统总承包商"],
                    senate_url,
                    "属于调查材料披露的下游国防承包商。",
                    None,
                ),
                (
                    "ent-hongdark-raytheon",
                    "Raytheon Company",
                    "雷神公司",
                    "United States",
                    "prime_contractor",
                    ["导弹与军用电子系统承包商"],
                    senate_url,
                    "属于调查材料披露的下游国防承包商。",
                    None,
                ),
            ],
        )
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-hongdark-us-intermediaries",
                    "case-us-lead-hong-dark-electronics",
                    "深圳鸿达疑似假冒元件美国中间链路",
                    "美国参议院军事委员会",
                    senate_url,
                    "调查确认约8.4万件疑似假冒元件来自深圳鸿达，并经Global IC等渠道进入多家国防承包商。",
                    [
                        "深圳鸿达供应约8.4万件疑似假冒电子元件",
                        "Global IC为已披露美国中间商",
                        "下游涉及L-3、Boeing、Lockheed Martin和Raytheon等承包商",
                    ],
                    "A",
                    ["各承包商对应的具体批次和装备仍需逐案匹配"],
                ),
            ],
        )
        if inv:
            inv.description = (
                "深圳鸿达电子贸易→Global IC等美国中间商→L-3、Boeing、Lockheed Martin、"
                "Raytheon等国防承包商→全球鹰、C-5、P-3、A/MH-6M、神剑炮弹、斯崔克及"
                "潜艇成像系统。已补出主要中间层，具体批次对应关系仍待逐案还原。"
            )

        # Exception PCB: the Chinese parent is confirmed by FastPrint's own history.
        fastprint_url = "https://en.chinafastprint.com/about"
        inv = add_entities(
            db,
            "inv-us-lead-f35-exception-pcb",
            [
                (
                    "ent-exception-fastprint",
                    "Shenzhen FastPrint Circuit Tech Co., Ltd.",
                    "深圳市兴森快捷电路科技股份有限公司",
                    "China",
                    "parent_company",
                    ["Exception PCB的中国母公司"],
                    fastprint_url,
                    "兴森科技官网确认其香港子公司于2013年收购Exception PCB 100%股权。",
                    None,
                ),
            ],
        )
        exception = db.get(SupplyChainEntity, "ent-us-lead-f35-exception-pcb")
        if exception:
            exception.country = "United Kingdom"
            exception.parent_id = "ent-exception-fastprint"
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-exception-fastprint-ownership",
                    "case-us-lead-f35-exception-pcb",
                    "Exception PCB中国母公司股权核验",
                    "深圳市兴森快捷电路科技股份有限公司",
                    fastprint_url,
                    "兴森科技官网记载FastPrint Hong Kong于2013年收购Exception PCB Solutions Limited 100%股权。",
                    ["Exception PCB由兴森科技体系100%控股", "收购发生于2013年"],
                    "A",
                    ["该证据证明所有权关系，不证明电路板在中国制造或含中国原产材料"],
                ),
            ],
        )
        if inv:
            inv.description = (
                "深圳市兴森快捷电路科技股份有限公司→FastPrint Hong Kong→英国Exception PCB"
                "→F-35印刷电路板供应链。中国母公司股权已由企业官网确认；产品在英国制造，"
                "该链条属于中资所有权和治理风险，不得表述为中国原产部件。"
            )

        # Aventura: the criminal complaint provides aggregate customs counts and end users.
        aventura_complaint = (
            "https://www.justice.gov/d9/press-releases/attachments/2019/11/07/"
            "aventura_et_al._complaint_0.pdf"
        )
        inv = add_entities(
            db,
            "inv-us-lead-aventura-surveillance",
            [
                (
                    "ent-aventura-prc-manufacturer-1",
                    "PRC Surveillance Manufacturer 1 (undisclosed)",
                    "中国监控设备制造商1（未披露）",
                    "China",
                    "china_exporter",
                    ["2010至2018年向Aventura发运约274批监控设备"],
                    aventura_complaint,
                    "司法材料匿名节点，不得推测为海康、大华或其他具体企业。",
                    None,
                ),
                (
                    "ent-aventura-us-government",
                    "U.S. Military and Federal Government Customers",
                    "美国军方及联邦政府客户",
                    "United States",
                    "military_end_user",
                    ["陆军、空军、海军、能源部等终端"],
                    aventura_complaint,
                    "司法材料确认设备进入军事基地、海军设施和联邦机构。",
                    None,
                ),
            ],
        )
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-aventura-import-counts",
                    "case-us-lead-aventura-surveillance",
                    "Aventura中国进口规模及政府销售核验",
                    "美国司法部",
                    aventura_complaint,
                    "起诉材料披露Aventura从40余家中国制造商收货；其中制造商1约274批，并向中国企业支付至少1,240万美元。",
                    [
                        "Aventura从40余家中国监控设备制造商进口",
                        "中国制造商1在2010至2018年间约274批",
                        "Aventura向中国企业支付至少1,240万美元",
                        "相关产品进入美国陆海空军和联邦机构",
                    ],
                    "A",
                    ["中国制造商在公开司法材料中匿名，不能进行推测性核名"],
                ),
            ],
        )
        if inv:
            inv.description = (
                "40余家中国监控设备制造商（司法材料匿名）→Aventura Technologies→美国陆军、"
                "空军、海军及能源部等客户。司法材料可确认进口规模、货物类型和政府终端，"
                "但中国原厂名称未公开。"
            )

        # BulletProof-IT: add the disclosed GSA distributor channel.
        bulletproof_url = (
            "https://www.justice.gov/usao-or/pr/washington-state-man-sentenced-federal-prison-"
            "marketing-and-selling-low-quality"
        )
        inv = add_entities(
            db,
            "inv-us-lead-bulletproof-it-china-armor",
            [
                (
                    "ent-bulletproof-us-tactical-supply",
                    "U.S. Tactical Supply",
                    "U.S. Tactical Supply公司",
                    "United States",
                    "government_contractor",
                    ["通过GSA合同向政府客户供应BulletProof-IT产品"],
                    bulletproof_url,
                    "美国司法部确认BulletProof-IT于2016年成为该公司GSA合同项下供应商。",
                    None,
                ),
                (
                    "ent-bulletproof-government-customers",
                    "U.S. Federal, State and Local Government Customers",
                    "美国联邦、州及地方政府客户",
                    "United States",
                    "government_end_user",
                    ["执法、消防及美国军方防护装备用户"],
                    bulletproof_url,
                    "司法材料确认产品直接或间接销售至多级政府机构和美国军方。",
                    None,
                ),
            ],
        )
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-bulletproof-gsa-channel",
                    "case-us-lead-bulletproof-it-china-armor",
                    "BulletProof-IT政府合同销售渠道",
                    "美国司法部",
                    bulletproof_url,
                    "BulletProof-IT销售的头盔、防弹衣和盾牌多数产自中国，并通过U.S. Tactical Supply的GSA合同进入政府采购渠道。",
                    [
                        "多数涉案防护装备产自中国",
                        "2016年成为U.S. Tactical Supply的GSA合同供应商",
                        "终端包括政府机构和美国军方",
                    ],
                    "A",
                    ["具体中国制造商和逐笔政府订单未在公开材料中披露"],
                ),
            ],
        )
        if inv:
            inv.description = (
                "中国防护装备制造商（未披露）→BulletProof-IT→U.S. Tactical Supply GSA合同渠道"
                "→美国联邦、州、地方政府机构及军方。政府销售渠道已经确认，"
                "中国原厂和逐笔订单仍待穿透。"
            )

        # Staff Gasket: add the confirmed DOD end user and quantified case facts.
        staff_url = (
            "https://www.justice.gov/sites/default/files/pages/attachments/2014/10/22/"
            "export-case-fact-sheet-201410.pdf"
        )
        inv = add_entities(
            db,
            "inv-us-lead-staff-gasket-helicopter-parts",
            [
                (
                    "ent-staff-gasket-dod",
                    "U.S. Department of Defense",
                    "美国国防部",
                    "United States",
                    "military_end_user",
                    ["2004至2006年替换零件合同采购方"],
                    staff_url,
                    "司法部事实清单确认合同采购方及损失金额。",
                    None,
                ),
            ],
        )
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-staff-gasket-quantified-case",
                    "case-us-lead-staff-gasket-helicopter-parts",
                    "Staff Gasket国防合同时间与损失核验",
                    "美国司法部",
                    staff_url,
                    "Staff Gasket在2004年8月至2006年3月承接国防部替换零件合同，并将包括直升机锁销在内的关键零件交由中国等境外制造。",
                    [
                        "合同执行期为2004年8月至2006年3月",
                        "涉案零件包括直升机锁销",
                        "国防部损失约751,091美元",
                    ],
                    "A",
                    ["中国制造商名称、合同编号和直升机型号仍未公开"],
                ),
            ],
        )

        # India drone review: add all three firms named in the 2024 caution letter.
        india_url = (
            "https://www.drdo.gov.in/drdo/sites/default/files/drdo-news-documents/"
            "NPC29Aug2024.pdf"
        )
        drone_rows = [
            (
                "ent-india-drone-sky-industries",
                "Sky Industries",
                "Sky Industries公司",
                "India",
                "defense_supplier",
                ["印度国防部审查涉及的无人机供应商"],
                india_url,
                "与Dhaksha、Garuda Aerospace一同被2024年6月25日风险提示点名。",
                None,
            ),
            (
                "ent-india-drone-garuda-aerospace",
                "Garuda Aerospace",
                "Garuda Aerospace公司",
                "India",
                "defense_supplier",
                ["印度国防部审查涉及的无人机供应商"],
                india_url,
                "与Dhaksha、Sky Industries一同被2024年6月25日风险提示点名。",
                None,
            ),
        ]
        inv = add_entities(db, "inv-india-lead-dhaksha-logistics-drone", drone_rows)
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-india-drone-three-firms",
                    "case-india-lead-dhaksha-logistics-drone",
                    "印度国防部无人机供应链风险提示涉及企业",
                    "印度国防研究与发展组织新闻汇编",
                    india_url,
                    "公开汇编披露国防生产部门提示谨慎采购Dhaksha、Sky Industries和Garuda Aerospace产品。",
                    ["风险提示点名三家印度无人机企业", "Dhaksha的200架陆军物流无人机订单被暂停"],
                    "B",
                    ["Dhaksha否认军用产品使用中国部件", "具体中国部件和制造商未披露"],
                    "government_news_compilation",
                ),
            ],
        )
        inv_400 = db.get(SupplyChainInvestigation, "inv-india-lead-army-400-drone-cancelled")
        if inv_400:
            attach(inv_400, "entity_ids", *(row[0] for row in drone_rows))
            attach(inv_400, "open_source_evidence_ids", "ose-india-drone-three-firms")
            inv_400.description = (
                "印度军方取消三份合计400架物流无人机订单，公开材料将风险指向中国制造部件。"
                "Dhaksha、Sky Industries和Garuda Aerospace属于同期被风险提示点名企业，"
                "但现有公开证据尚不能把三份取消合同逐一对应到三家企业。"
            )

        # Taiwan Albatross: public reporting identifies the component categories,
        # but not their manufacturers or procurement lots.
        albatross_url = "https://www.taiwannews.com.tw/news/6110096"
        inv = add_entities(
            db,
            "inv-taiwan-lead-albatross-china-components",
            [
                (
                    "ent-albatross-prc-component-makers",
                    "PRC Communications Module and SD Card Manufacturers (undisclosed)",
                    "中国大陆通信模块及SD存储卡制造商（未披露）",
                    "China",
                    "china_exporter",
                    ["锐鸢无人机被发现的中国大陆制造部件来源"],
                    albatross_url,
                    "公开材料只披露部件类别，未披露品牌、型号和制造商。",
                    None,
                ),
                (
                    "ent-albatross-taiwan-defense",
                    "Taiwan Defense Authority",
                    "中国台湾地区防务主管部门",
                    "Taiwan",
                    "military_end_user",
                    ["锐鸢无人机监管和使用体系"],
                    albatross_url,
                    "确认发现中国大陆部件并要求承包商替换。",
                    None,
                ),
            ],
        )
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-albatross-component-types",
                    "case-taiwan-lead-albatross-china-components",
                    "锐鸢无人机中国大陆部件类别核验",
                    "Taiwan News",
                    albatross_url,
                    "公开报道将涉事中国大陆制造部件细化为通信模块和SD存储卡。",
                    ["涉事部件包括通信模块", "涉事部件包括SD存储卡", "主管部门要求更换相关部件"],
                    "B",
                    ["部件品牌、制造商、承包商和采购批次仍未公开"],
                    "news_report",
                ),
            ],
        )
        if inv:
            inv.description = (
                "中国大陆通信模块及SD存储卡制造商（未披露）→承包商（未披露）"
                "→中山科学研究院锐鸢无人机→中国台湾地区防务使用体系。"
                "部件类别已确认，企业和采购批次仍待穿透。"
            )

        # F-35 robotics: KUKA/Midea is a plausible identity match, not a verified
        # identification because GAO intentionally left the manufacturer unnamed.
        gao_url = "https://files.gao.gov/reports/GAO-25-107283/index.html"
        inv = add_entities(
            db,
            "inv-us-lead-f35-china-robotics",
            [
                (
                    "ent-f35-robot-midea-candidate",
                    "Midea Group Co., Ltd. (candidate parent)",
                    "美的集团股份有限公司（候选母公司）",
                    "China",
                    "candidate_parent",
                    ["KUKA控股股东"],
                    gao_url,
                    "与KUKA共同构成身份候选，尚无官方材料将其与涉事F-35机械臂直接对应。",
                    None,
                ),
                (
                    "ent-f35-robot-kuka-candidate",
                    "KUKA AG (candidate match)",
                    "库卡公司（候选匹配）",
                    "Germany",
                    "candidate_supplier",
                    ["符合“被中国企业收购的德国机器人制造商”特征"],
                    gao_url,
                    "仅为基于公开企业特征的候选，不得表述为GAO已确认的F-35机械臂供应商。",
                    "ent-f35-robot-midea-candidate",
                ),
            ],
        )
        add_evidence(
            db,
            inv,
            [
                (
                    "ose-f35-robot-identity-candidate",
                    "case-us-lead-f35-china-robotics",
                    "F-35装配机械臂制造商身份候选研判",
                    "美国政府问责局",
                    gao_url,
                    "GAO仅描述为“中国企业持有的德国制造商所产中国制造机械臂”；KUKA与美的符合该特征，但公开报告未点名。",
                    ["官方确认涉事机械臂为中国制造", "官方确认德国制造商已被中国企业收购"],
                    "C",
                    ["KUKA和美的仅为候选身份，缺少设备铭牌、采购合同或官方点名"],
                    "analyst_assessment",
                    "follow_up",
                ),
            ],
        )

        db.commit()
        print("Enriched incomplete supply-chain investigations.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
