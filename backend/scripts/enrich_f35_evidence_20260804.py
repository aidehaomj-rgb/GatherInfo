"""Add the August 2026 F-35 evidence review to the supply-chain module."""
from __future__ import annotations

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainEntity,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
)


GAO_URL = "https://files.gao.gov/reports/GAO-25-107283/index.html"
NORTHROP_URL = (
    "https://www.northropgrumman.com/what-we-do/digital-transformation/"
    "using-automation-and-robotics-in-advanced-aircraft-production"
)
KUKA_URL = "https://www.kuka.com/en-us/company/press/news/2022/11/squeeze-out-completed"
HONEYWELL_URL = (
    "https://www.honeywellaerospace.com/us/en/insights/articles/"
    "1750th-ptms-turbomachine-f-35-fighter-jets"
)
EXCEPTION_URL = (
    "https://www.exceptionpcb.com/"
    "exception-pcb-brought-back-into-british-ownership-to-strengthen-strategic-uk-manufacturing/"
)
PARLIAMENT_URL = (
    "https://publications.parliament.uk/pa/cm5801/cmselect/cmdfence/699/69905.htm"
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


def attach(investigation, field: str, *row_ids: str):
    values = list(getattr(investigation, field) or [])
    for row_id in row_ids:
        if row_id not in values:
            values.append(row_id)
    setattr(investigation, field, values)


def evidence(
    db,
    row_id: str,
    case_id: str,
    title: str,
    publisher: str,
    url: str,
    excerpt: str,
    facts: list[str],
    limitations: list[str],
    grade: str = "A",
):
    return upsert(
        db,
        SupplyChainOpenSourceEvidence,
        row_id,
        case_id=case_id,
        title=title,
        source_type="official_document",
        source_publisher=publisher,
        source_url=url,
        source_excerpt=excerpt,
        verified_facts=facts,
        evidence_grade=grade,
        status="verified",
        limitations=limitations,
    )


def enrich_magnet_chain(db):
    inv = db.get(SupplyChainInvestigation, "inv-us-lead-f35-china-smco")
    if inv is None:
        return

    gao = evidence(
        db,
        "ose-f35-gao-2025-magnets-waivers",
        "case-us-lead-f35-china-smco",
        "GAO确认F-35中国磁体发现、停产及国家安全豁免",
        "美国政府问责局（GAO）",
        GAO_URL,
        "GAO确认洛克希德·马丁发现F-35供应链中的禁用中国磁体并通知国防部；国防部暂停生产、寻找替代供应商，并签发国家安全豁免。",
        [
            "洛克希德·马丁通过供应商自报发现中国制造磁体",
            "国防部曾暂停生产数月以识别替代供应商",
            "国防部签发国家安全豁免并认定磁体不构成飞行安全风险",
            "SCREEn工具被用于验证替代磁体供应商",
            "截至2025年4月，F-35约4万种零件中3万种已有一、二级供应商原产国数据",
            "国防部掌握的零部件和原材料下级供应商原产国信息仍不足10%",
        ],
        [
            "GAO未公开中国磁体制造商、磁体型号、润滑泵供应商或批次信息",
            "GAO对2023、2024年通知和豁免的表述不能单独证明均属于2022年钐钴合金同一批次",
        ],
    )
    honeywell = evidence(
        db,
        "ose-f35-honeywell-2025-ptms",
        "case-us-lead-f35-china-smco",
        "Honeywell确认持续生产F-35 PTMS涡轮机械",
        "Honeywell Aerospace",
        HONEYWELL_URL,
        "Honeywell披露第1750台F-35 PTMS涡轮机械交付计划，并说明该设备集辅助动力、应急动力、环境控制和热管理功能于一体。",
        [
            "Honeywell仍是F-35 PTMS涡轮机械制造商",
            "该涡轮机械已应用于近1200架F-35并累计运行超过100万飞行小时",
            "PTMS零部件当前在英国、加拿大、墨西哥、法国、荷兰和捷克生产维护",
        ],
        [
            "该官方材料未披露润滑泵、磁体或钐钴合金下级供应商",
            "当前全球生产布局不能证明2022年涉事中国合金链仍在延续",
        ],
    )
    attach(inv, "open_source_evidence_ids", gao.id, honeywell.id)
    inv.description = (
        "中国钐钴合金制造商（未披露）→磁体供应商（未披露）→润滑泵供应商（未披露）"
        "→Honeywell PTMS涡轮机械→Lockheed Martin F-35。2022年事件已确认合金在中国生产、"
        "在美国磁化并进入全部既有F-35；GAO后续确认国防部曾停产、签发国家安全豁免并验证"
        "替代供应商。下三级企业及批次仍未公开，尚无证据证明2026年继续自华采购。"
    )


def enrich_robotics_chain(db):
    inv = db.get(SupplyChainInvestigation, "inv-us-lead-f35-china-robotics")
    if inv is None:
        return

    midea = upsert(
        db,
        SupplyChainEntity,
        "ent-f35-robot-midea-candidate",
        name="Midea Group Co., Ltd.",
        name_zh="美的集团股份有限公司（高可信母公司匹配）",
        country="China",
        entity_type="parent_company",
        aliases=["Midea Group", "美的集团"],
        parent_id=None,
        defense_roles=["KUKA最终控制方", "F-35机械臂厂商身份研判中的中资母公司"],
        source_url=KUKA_URL,
        notes="KUKA官网确认全部少数股权转至美的集团控制公司；GAO未直接公布涉事母公司名称。",
    )
    kuka = upsert(
        db,
        SupplyChainEntity,
        "ent-f35-robot-kuka-candidate",
        name="KUKA SE & Co. KGaA",
        name_zh="库卡公司（高可信身份匹配）",
        country="Germany",
        entity_type="high_confidence_supplier_match",
        aliases=["KUKA AG", "KUKA Systems North America", "库卡"],
        parent_id=midea.id,
        defense_roles=["F-35中央机身集成装配线自动化系统建设方", "涉事机械臂厂商高可信匹配"],
        source_url=NORTHROP_URL,
        notes=(
            "Northrop Grumman官网确认KUKA参与F-35中央机身集成装配线建设；KUKA官网确认其由"
            "美的集团控制。该特征与GAO描述高度一致，但GAO未直接点名，故保留身份匹配边界。"
        ),
    )
    northrop = upsert(
        db,
        SupplyChainEntity,
        "ent-f35-robot-northrop",
        name="Northrop Grumman Corporation",
        name_zh="Northrop Grumman",
        country="United States",
        entity_type="major_subcontractor",
        aliases=["Northrop Grumman"],
        parent_id=None,
        defense_roles=["F-35中央机身制造商", "F-35集成装配线运营方"],
        source_url=NORTHROP_URL,
        notes="官网确认其与KUKA共同建设用于生产F-35中央机身的集成装配线。",
    )
    gao = evidence(
        db,
        "ose-f35-gao-2025-robot-arms",
        "case-us-lead-f35-china-robotics",
        "GAO确认F-35装配线中国制造机械臂及处置措施",
        "美国政府问责局（GAO）",
        GAO_URL,
        "GAO披露国防部在承包商现场发现由一家现属中资的德国厂商生产的中国制造机械臂，并要求采取网络隔离措施。",
        [
            "涉事设备为F-35装配线使用的中国制造机械臂",
            "制造商是现由中国企业持有的德国厂商",
            "国防部调查认为不影响F-35安全或质量",
            "调查发现网络安全问题后，机械臂被要求断开互联网",
        ],
        ["GAO未公开厂商名称、设备型号、数量、序列号和采购合同"],
    )
    northrop_ev = evidence(
        db,
        "ose-f35-northrop-kuka-ial",
        "case-us-lead-f35-china-robotics",
        "Northrop Grumman确认KUKA参与F-35集成装配线建设",
        "Northrop Grumman",
        NORTHROP_URL,
        "Northrop Grumman确认与KUKA Systems North America合作建设F-35中央机身集成装配线。",
        [
            "KUKA Systems North America是F-35中央机身集成装配线合作建设方",
            "该装配线用于生产全部三种F-35型号的中央机身",
        ],
        ["该材料未说明GAO发现的具体中国制造机械臂型号是否由KUKA提供"],
    )
    kuka_ev = evidence(
        db,
        "ose-f35-kuka-midea-ownership",
        "case-us-lead-f35-china-robotics",
        "KUKA确认美的集团实现全部股权控制",
        "KUKA",
        KUKA_URL,
        "KUKA公告确认少数股东股份全部转至广东美的电气，该公司由中国母公司美的集团控制。",
        ["KUKA由美的集团控制", "2022年挤出程序完成后少数股东股份全部转移"],
        ["所有权证据本身不证明具体涉事机械臂的制造地、型号或采购批次"],
    )
    attach(inv, "entity_ids", midea.id, kuka.id, northrop.id)
    attach(inv, "open_source_evidence_ids", gao.id, northrop_ev.id, kuka_ev.id)
    inv.description = (
        "美的集团→KUKA→Northrop Grumman F-35中央机身集成装配线→Lockheed Martin F-35。"
        "GAO确认装配线存在一家中资持有德国厂商生产的中国制造机械臂，并披露断网等缓解措施；"
        "Northrop Grumman和KUKA官方材料使KUKA/美的成为高可信身份匹配，但GAO尚未直接点名。"
    )


def enrich_pcb_chain(db):
    inv = db.get(SupplyChainInvestigation, "inv-us-lead-f35-exception-pcb")
    if inv is None:
        return

    wright = upsert(
        db,
        SupplyChainEntity,
        "ent-f35-pcb-wright-industries",
        name="Wright Industries Ltd",
        name_zh="Wright Industries",
        country="United Kingdom",
        entity_type="current_parent_company",
        aliases=["Connexion Technologies"],
        parent_id=None,
        defense_roles=["Exception PCB自2025年起的英国所有者"],
        source_url=EXCEPTION_URL,
        notes="Exception PCB于2025年8月公告恢复英国所有权。",
    )
    parliament = evidence(
        db,
        "ose-f35-uk-parliament-exception-pcb",
        "case-us-lead-f35-exception-pcb",
        "英国议会确认Exception PCB进入F-35供应链",
        "英国议会下议院国防委员会",
        PARLIAMENT_URL,
        "英国议会材料确认Exception PCB生产F-35裸印刷电路板，经GE Aviation安装电子元件后进入上级供应链。",
        [
            "Exception PCB为F-35制造裸印刷电路板",
            "下游为GE Aviation，再进入Lockheed Martin供应链",
            "英国国防部称其不接触敏感项目资料并将风险评估为较低",
        ],
        ["议会材料反映的是历史中资持有阶段，不代表2025年8月后的当前股权状态"],
    )
    ownership = evidence(
        db,
        "ose-f35-exception-uk-ownership-2025",
        "case-us-lead-f35-exception-pcb",
        "Exception PCB于2025年恢复英国所有权",
        "Exception PCB / Wright Industries",
        EXCEPTION_URL,
        "Exception PCB公告Wright Industries已完成收购，使公司从亚洲所有权恢复为英国所有权。",
        [
            "Wright Industries于2025年8月收购Exception PCB",
            "Exception PCB现已恢复英国所有权",
            "公司继续服务国防、航空航天等行业",
        ],
        ["公告未披露交易价格，也未逐项确认F-35合同在收购后的延续状态"],
    )
    attach(inv, "entity_ids", wright.id)
    attach(inv, "open_source_evidence_ids", parliament.id, ownership.id)
    inv.description = (
        "深圳市兴森快捷电路科技→FastPrint Hong Kong→英国Exception PCB→GE Aviation"
        "→Lockheed Martin F-35。2013年至2025年8月属于历史中资所有权风险，且产品在英国制造；"
        "2025年8月Wright Industries完成收购后，Exception PCB已恢复英国所有权。"
    )


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        enrich_magnet_chain(db)
        enrich_robotics_chain(db)
        enrich_pcb_chain(db)
        db.commit()
        print("Enriched three F-35 investigations with the August 2026 evidence review.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
