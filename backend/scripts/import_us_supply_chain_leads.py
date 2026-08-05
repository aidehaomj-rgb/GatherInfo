"""Import verified and follow-up US defense supply-chain leads."""
from __future__ import annotations

from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainCase,
    SupplyChainEntity,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
)


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


LEADS = [
    {
        "slug": "f35-china-smco",
        "name": "F-35中国钐钴合金供应链",
        "description": "中国制造钐钴合金经磁体、润滑泵和Honeywell涡轮机械等多级供应商进入Lockheed Martin F-35项目；具体中国合金企业仍待识别。",
        "entity": ("Honeywell International Inc.", "Honeywell", "defense_supplier"),
        "agency": "美国国防部 / F-35联合项目办公室",
        "product": "中国制造钐钴合金、磁体及涡轮机械润滑泵组件",
        "program": "F-35 Lightning II",
        "date": "2022-09-07",
        "source": "https://www.pogo.org/commentaries/use-of-chinese-material-in-f-35-highlights-pentagons-complexity-problem",
        "publisher": "Project On Government Oversight",
        "grade": "A",
        "status": "verified",
        "facts": ["F-35涡轮机械磁性组件含中国制造钐钴合金", "供应链至少经过五级企业", "美国国防部曾暂停飞机交付并签发国家安全豁免"],
        "limits": ["中国合金制造商、磁体供应商和润滑泵供应商名称尚未公开"],
    },
    {
        "slug": "quadrant-fighter-magnets",
        "name": "Quadrant战机稀土磁体供应链",
        "description": "中国企业完成稀土磁体冶炼和充磁后由Quadrant Magnetics进口，经两家美国零部件企业进入F-16、F/A-18等国防装备。",
        "entity": ("Quadrant Magnetics LLC", "Quadrant Magnetics", "defense_supplier"),
        "agency": "美国国防部",
        "product": "在中国冶炼和充磁的稀土磁体",
        "program": "F-16、F/A-18及其他国防装备",
        "date": "2024-09-20",
        "source": "https://www.justice.gov/archives/opa/pr/three-arrested-illegal-scheme-export-controlled-data-and-defraud-department-defense",
        "publisher": "美国司法部",
        "grade": "A",
        "status": "verified",
        "facts": ["Quadrant从中国进口稀土磁体", "相关组件进入F-16和F/A-18等国防装备"],
        "limits": ["中国制造商及两家美国中间企业在司法文件中匿名"],
    },
    {
        "slug": "skydio-china-battery",
        "name": "Skydio军用无人机电池供应链",
        "description": "Skydio向美国军方和公共安全部门供应无人机，其锂电池供应曾依赖中国节点并因出口限制出现配给；具体电芯和电池企业待穿透。",
        "entity": ("Skydio, Inc.", "Skydio", "defense_supplier"),
        "agency": "美国陆军及美国政府机构",
        "product": "锂离子无人机电池",
        "program": "短程侦察无人机及政府无人机项目",
        "date": "2024-10-30",
        "source": "https://techcrunch.com/2024/10/31/chinese-sanctions-hit-us-drone-maker-skydio/",
        "publisher": "TechCrunch",
        "grade": "B",
        "status": "follow_up",
        "facts": ["Skydio受到中国制裁后对电池实施配给", "Skydio产品进入美国国防和公共安全市场"],
        "limits": ["中国电池供应商名称及具体军用批次尚待核验"],
    },
    {
        "slug": "aventura-surveillance",
        "name": "Aventura军用安防设备供应链",
        "description": "中国监控与安防设备由Aventura进口并重新标识为美国制造，随后销售至美国军事基地、舰艇和政府机构。",
        "entity": ("Aventura Technologies, Inc.", "Aventura Technologies", "defense_supplier"),
        "agency": "美国海军及其他联邦机构",
        "product": "网络监控设备、夜视摄像机及安防系统",
        "program": "美国军事基地、舰艇及新伦敦海军潜艇基地安防系统",
        "date": "2019-11-07",
        "source": "https://www.justice.gov/usao-edny/pr/aventura-technologies-inc-and-its-senior-management-charged-fraud-money-laundering-and",
        "publisher": "美国司法部",
        "grade": "A",
        "status": "verified",
        "facts": ["Aventura从中国制造商进口安防设备", "有关设备安装于美国军事和政府设施"],
        "limits": ["多家中国原始设备制造商名称未在通报中披露"],
    },
    {
        "slug": "ddg51-nefeb-motor",
        "name": "DDG-51驱逐舰永磁电机供应链",
        "description": "中国钕铁硼磁体经美国材料加工商和电机分包商进入DDG-51驱逐舰混合电力推进系统。",
        "entity": ("DDG-51 Hybrid Electric Drive Prime Contractor", "DDG-51混合电力推进主承包商（待识别）", "defense_supplier"),
        "agency": "美国海军",
        "product": "中国来源钕铁硼磁体及永磁电机",
        "program": "DDG-51 Hybrid Electric Drive Ship Program",
        "date": "2010-04-01",
        "source": "https://www.gao.gov/assets/a96655.html",
        "publisher": "美国政府问责局",
        "grade": "A",
        "status": "follow_up",
        "facts": ["供应商从中国企业采购钕铁硼磁体", "磁体经加工并制成电机后用于DDG-51混合电力推进系统"],
        "limits": ["GAO公开版本未披露中国企业、加工商、电机分包商和主承包商名称"],
    },
    {
        "slug": "m1a2-smco-navigation",
        "name": "M1A2坦克钐钴导航系统供应链",
        "description": "中国钐金属经美国磁体企业和导航装置分包商进入M1A2 Abrams坦克参考与导航系统。",
        "entity": ("M1A2 Abrams Prime Contractor", "M1A2主承包商（待识别）", "defense_supplier"),
        "agency": "美国陆军",
        "product": "中国来源钐金属、钐钴磁体及参考导航装置",
        "program": "M1A2 Abrams主战坦克",
        "date": "2010-04-01",
        "source": "https://www.gao.gov/assets/a96655.html",
        "publisher": "美国政府问责局",
        "grade": "A",
        "status": "follow_up",
        "facts": ["M1A2参考与导航系统使用钐钴永磁体", "制造磁体所用钐金属来自中国"],
        "limits": ["磁体企业、导航装置分包商和具体采购批次尚未公开"],
    },
    {
        "slug": "hong-dark-electronics",
        "name": "深圳鸿达军用电子元件供应链",
        "description": "深圳鸿达电子贸易供应的大量疑似假冒电子元件经美国渠道进入全球鹰、C-5、P-3、斯崔克、神剑炮弹及潜艇成像系统等装备。",
        "entity": ("Hong Dark Electronic Trade", "深圳鸿达电子贸易", "china_exporter"),
        "agency": "美国国防部及各军种",
        "product": "疑似假冒军用电子元件",
        "program": "全球鹰、C-5、C-12、P-3、A/MH-6M、神剑炮弹、斯崔克及潜艇成像系统",
        "date": "2012-05-21",
        "source": "https://www.armed-services.senate.gov/download/2012/05/21/senate-armed-services-committee-releases-report-on-counterfeit-electronic-parts",
        "publisher": "美国参议院军事委员会",
        "grade": "A",
        "status": "verified",
        "facts": ["约8.4万件疑似假冒零件由深圳鸿达供应", "零件进入或拟用于多型美国关键军事装备"],
        "limits": ["各型装备对应的完整美国中间商链路仍需逐案还原"],
    },
    {
        "slug": "staff-gasket-helicopter-parts",
        "name": "Staff Gasket军用直升机零件供应链",
        "description": "Staff Gasket将部分美国国防合同零件外包至中国等境外制造商，向美国国防部供应包括军用直升机锁销在内的关键零件。",
        "entity": ("Staff Gasket Manufacturing Corporation", "Staff Gasket", "defense_supplier"),
        "agency": "美国国防部",
        "product": "军用直升机锁销及其他关键应用零件",
        "program": "美国国防部军用替换零件采购",
        "date": "2011-09-13",
        "source": "https://www.justice.gov/sites/default/files/pages/attachments/2014/10/22/export-case-fact-sheet-201410.pdf",
        "publisher": "美国司法部",
        "grade": "A",
        "status": "verified",
        "facts": ["Staff Gasket承接美国国防部替换零件合同", "部分关键零件由中国等境外制造商生产并出现质量问题"],
        "limits": ["中国制造商名称、合同编号和具体直升机型号待进一步核查"],
    },
    {
        "slug": "f35-china-robotics",
        "name": "F-35中国制造装配机械臂供应链",
        "description": "F-35装配线使用由中国企业控股的德国制造商提供的中国制造机械臂，属于生产设施层面的供应链风险。",
        "entity": ("F-35 German Robotics Manufacturer", "F-35德国机械臂制造商（中资控股，待核名）", "equipment_supplier"),
        "agency": "美国国防部 / F-35联合项目办公室",
        "product": "中国制造工业机械臂",
        "program": "F-35生产装配线",
        "date": "2025-07-01",
        "source": "https://files.gao.gov/reports/GAO-25-107283/index.html",
        "publisher": "美国政府问责局",
        "grade": "A",
        "status": "follow_up",
        "facts": ["美国国防部现场检查发现F-35装配线使用中国制造机械臂", "制造商为一家被中国企业收购的德国公司"],
        "limits": ["GAO未公开制造商及其中国母公司名称", "设备不属于装机部件"],
    },
    {
        "slug": "f35-exception-pcb",
        "name": "F-35中资控股印刷电路板供应链",
        "description": "英国Exception PCB向F-35供应印刷电路板，其母公司为中国企业；该线索属于中资所有权与控制风险，不等同于中国原产产品。",
        "entity": ("Exception PCB Ltd.", "Exception PCB", "component_supplier"),
        "agency": "英国国防部 / F-35项目",
        "product": "印刷电路板",
        "program": "F-35 Lightning II",
        "date": "2019-06-14",
        "source": "https://www.forbes.com/sites/zakdoffman/2019/06/14/chinese-owned-company-makes-circuit-boards-for-top-secret-u-s-f-35-fighter-jets/",
        "publisher": "Forbes",
        "grade": "B",
        "status": "follow_up",
        "facts": ["Exception PCB为F-35供应电路板", "Exception PCB由中国企业控股"],
        "limits": ["电路板在英国制造，不能表述为中国原产", "需补充母公司股权和具体分系统合同证据"],
    },
    {
        "slug": "mq9-china-subtier",
        "name": "MQ-9无人机中国底层供应节点",
        "description": "美国国防部专项穿透分析确认MQ-9 Reaper底层供应层存在中国集成节点，但公开材料尚未披露企业和部件。",
        "entity": ("MQ-9 Reaper Prime Contractor", "MQ-9主承包商", "defense_supplier"),
        "agency": "美国国防部",
        "product": "底层中国来源原材料或部件（待识别）",
        "program": "MQ-9 Reaper无人机",
        "date": "2025-03-01",
        "source": "https://files.gao.gov/reports/GAO-25-107283/index.html",
        "publisher": "美国政府问责局",
        "grade": "A",
        "status": "follow_up",
        "facts": ["DOD深度分析识别出MQ-9较低供应层级存在中国集成"],
        "limits": ["具体中国企业、产品、流向和采购批次均未公开"],
    },
    {
        "slug": "bulletproof-it-china-armor",
        "name": "BulletProof-IT中国防弹装备供应链",
        "description": "BulletProof-IT从中国企业进口头盔、防弹衣和盾牌等装备，并以美国制造名义向政府机构和政府承包商销售。",
        "entity": ("BulletProof-IT, LLC", "BulletProof-IT", "defense_supplier"),
        "agency": "美国联邦、州和地方政府机构",
        "product": "头盔、防弹衣和防弹盾牌",
        "program": "美国政府及政府承包商防护装备采购",
        "date": "2024-05-31",
        "source": "https://oig.justice.gov/news/press-release/former-doj-contractor-ordered-pay-restitution-pursuant-amended-judgement-wire",
        "publisher": "美国司法部监察长办公室",
        "grade": "A",
        "status": "follow_up",
        "facts": ["多类防弹装备从中国企业进口", "产品直接或经政府承包商销售至多级政府机构"],
        "limits": ["具体中国制造商及明确的美国国防部终端合同仍待匹配"],
    },
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for lead in LEADS:
            slug = lead["slug"]
            entity_id = f"ent-us-lead-{slug}"
            case_id = f"case-us-lead-{slug}"
            evidence_id = f"ose-us-lead-{slug}"
            investigation_id = f"inv-us-lead-{slug}"
            entity_name, entity_name_zh, entity_type = lead["entity"]

            upsert(
                db,
                SupplyChainEntity,
                entity_id,
                name=entity_name,
                name_zh=entity_name_zh,
                country="China" if entity_type == "china_exporter" else "United States",
                entity_type=entity_type,
                aliases=[],
                parent_id=None,
                defense_roles=[lead["program"], lead["product"]],
                source_url=lead["source"],
                notes=f"线索状态：{lead['status']}。后续应继续穿透匿名供应商、合同和贸易记录。",
            )
            db.flush()
            upsert(
                db,
                SupplyChainCase,
                case_id,
                country="United States",
                title=lead["name"],
                procurement_agency=lead["agency"],
                procurement_reference="公开源供应链调查",
                procurement_date=dt(lead["date"]),
                supplier_entity_id=entity_id,
                product=lead["product"],
                target_program=lead["program"],
                contract_value=None,
                currency="USD",
                source_url=lead["source"],
                source_excerpt=lead["description"],
                status="verified_lead" if lead["status"] == "verified" else "researching",
            )
            db.flush()
            upsert(
                db,
                SupplyChainOpenSourceEvidence,
                evidence_id,
                case_id=case_id,
                title=f"{lead['name']}公开源核验材料",
                source_type="official_document" if lead["grade"] == "A" else "investigative_report",
                source_publisher=lead["publisher"],
                source_url=lead["source"],
                source_excerpt=lead["description"],
                verified_facts=lead["facts"],
                evidence_grade=lead["grade"],
                status="verified" if lead["status"] == "verified" else "follow_up",
                limitations=lead["limits"],
            )
            upsert(
                db,
                SupplyChainInvestigation,
                investigation_id,
                country="United States",
                name=lead["name"],
                description=lead["description"],
                status="active" if lead["status"] == "verified" else "researching",
                entity_ids=[entity_id],
                case_ids=[case_id],
                shipment_ids=[],
                evidence_ids=[],
                open_source_evidence_ids=[evidence_id],
                report_ids=[],
            )
        db.commit()
        print(f"Imported {len(LEADS)} US supply-chain investigations.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
