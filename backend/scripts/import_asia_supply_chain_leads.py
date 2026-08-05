"""Import preliminary India, Japan and Taiwan defense supply-chain leads."""
from __future__ import annotations

from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainCase,
    SupplyChainEntity,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
)


def upsert(db, model, row_id, **values):
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


LEADS = [
    # India: specific procurement or weapon-system cases.
    ("India", "dhanush-china-bearing", "Dhanush火炮中国轴承供应链",
     "印度军械工厂为Dhanush 155毫米火炮采购的线轨滚柱轴承被指由中国制造并冒充德国原产，涉Sidh Sales Syndicate及CRB Antriebstechnik。",
     "Sidh Sales Syndicate", "印度国防部 / Gun Carriage Factory Jabalpur",
     "线轨滚柱轴承", "Dhanush 155毫米火炮", "2018-03-07",
     "https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=176946", "印度政府新闻信息局",
     "A", "verified", ["印度国防部确认案件涉及Dhanush火炮轴承采购", "争议轴承被指为中国制造并冒充德国原产"],
     ["需继续取得CBI案卷、进口记录及中国实际制造商"]),
    ("India", "dhaksha-logistics-drone", "Dhaksha陆军物流无人机供应链",
     "Dhaksha Unmanned Systems获得印度陆军200架中空物流无人机合同，后因中国来源部件疑虑被暂停并纳入军方供应链审查。",
     "Dhaksha Unmanned Systems Pvt. Ltd.", "印度陆军",
     "中空物流无人机及电子部件", "200架物流无人机紧急采购", "2023-08-07",
     "https://www.drdo.gov.in/drdo/sites/default/files/drdo-news-documents/NPC29Aug2024.pdf", "印度国防研究与发展组织新闻汇编",
     "B", "follow_up", ["Dhaksha取得印度陆军200架物流无人机订单", "采购因疑似中国部件问题受到审查"],
     ["企业否认军用交付产品使用中国部件", "需核验被质疑的飞控、电机、通信和电池厂商"]),
    ("India", "army-400-drone-cancelled", "印度陆军400架无人机中国部件审查链",
     "印度军方取消三份合计400架、约23亿卢比的物流无人机合同，公开报道将取消原因指向中国部件及供应链安全风险。",
     "Indian Army Drone Vendors (under review)", "印度陆军",
     "轻型、中型和重型物流无人机", "400架物流无人机紧急采购", "2025-02-10",
     "https://aviationweek.com/defense/aircraft-propulsion/india-scraps-orders-400-military-drones-chinese-components", "Aviation Week",
     "B", "follow_up", ["三份合同合计400架无人机被取消", "公开报道明确指向中国制造部件风险"],
     ["除Dhaksha外的承包企业、具体部件和中国供应商待识别"]),
    ("India", "newspace-drone-components", "NewSpace军用无人机部件供应链",
     "印度军用小型无人机供应商NewSpace Research曾公开表示行业供应链中大量商品由中国制造，适合作为飞控、电机、电池和通信模块穿透入口。",
     "NewSpace Research & Technologies Pvt. Ltd.", "印度军方",
     "小型军用无人机、飞控、电机、电池及通信模块", "印度军用小型无人机项目", "2023-08-08",
     "https://indianexpress.com/article/india/india-bars-makers-military-drones-using-chinese-parts-8881963/", "The Indian Express",
     "B", "follow_up", ["NewSpace是印度军用小型无人机供应商", "企业负责人称无人机行业供应链约70%商品由中国制造"],
     ["表述反映行业总体依赖，尚不能直接证明某批军用交付使用中国部件"]),

    # Japan: named defense-industry nodes under export controls; actual shipments remain unproven.
    ("Japan", "mhi-aeroengine-critical-materials", "三菱重工航空发动机关键材料供应链",
     "三菱重工航空发动机承担日本防卫航空动力业务，被列入中国两用物项出口管制名单；重稀土、耐高温磁材等具体来源和装备项目待穿透。",
     "Mitsubishi Heavy Industries Aero Engines, Ltd.", "日本防卫省 / 防卫装备厅",
     "航空发动机、重稀土及耐高温材料", "日本自卫队航空发动机供应链", "2026-02-24",
     "https://interview.mofcom.gov.cn/mofcom_interview/front/opdata/downlodePdfNew?id=e83f69deed3a446288808643ddb2d0cf", "中国商务部",
     "A", "follow_up", ["企业被列入商务部2026年第11号出口管制管控名单", "公告禁止向其提供中国原产两用物项"],
     ["管制公告不等同于已证明存在具体进口", "需匹配日本防卫合同及历史贸易记录"]),
    ("Japan", "khi-aerospace-materials", "川崎重工航空航天关键材料供应链",
     "川崎重工航空航天系统承担日本军机和航空装备业务，被纳入中国两用物项管控对象，关键矿产、电子和加工设备节点待核验。",
     "Kawasaki Heavy Industries Aerospace Systems Company", "日本防卫省 / 防卫装备厅",
     "军用航空装备、关键矿产及电子部件", "日本自卫队航空装备供应链", "2026-02-24",
     "https://www.mofcom.gov.cn/cms_files/filemanager/policySummary/art_f344bbdbfaef487dad12a45bed1c8722.html", "中国商务部",
     "A", "follow_up", ["川崎重工航空航天系统公司列入管控名单"],
     ["尚未取得中国供应商、产品和批次级证据"]),
    ("Japan", "ihi-aerospace-materials", "IHI航空航天关键材料供应链",
     "IHI航空制造、宇航、喷气机服务等多个防务节点被纳入中国两用物项出口管制，航空发动机合金、磁材和电子器件链条待穿透。",
     "IHI Aerospace Co., Ltd.", "日本防卫省 / 防卫装备厅",
     "航空发动机、宇航装备及关键材料", "日本防卫航空与宇航项目", "2026-02-24",
     "https://www.mofcom.gov.cn/cms_files/filemanager/policySummary/art_f344bbdbfaef487dad12a45bed1c8722.html", "中国商务部",
     "A", "follow_up", ["IHI系多家航空航天实体列入管控名单"],
     ["尚不能由管制名单反推实际采购关系", "需核验合同、进口商和材料供应商"]),
    ("Japan", "nec-defense-electronics", "NEC防务电子与传感器供应链",
     "NEC网络传感器和航空宇宙系统实体进入两用物项管控名单，雷达、通信、传感器所涉半导体和磁性材料来源待排查。",
     "NEC Aerospace Systems, Ltd.", "日本防卫省 / 防卫装备厅",
     "雷达、通信、传感器及电子元件", "日本防卫电子信息系统", "2026-02-24",
     "https://www.mofcom.gov.cn/cms_files/filemanager/policySummary/art_f344bbdbfaef487dad12a45bed1c8722.html", "中国商务部",
     "A", "follow_up", ["NEC航空宇宙系统及网络传感器实体列入管控名单"],
     ["具体中国来源电子元件和防卫合同尚待穿透"]),

    # Taiwan: concrete drone investigations and procurement programs.
    ("Taiwan", "albatross-china-components", "锐鸢无人机中国部件供应链",
     "台湾地区防务主管部门确认中山科学研究院研制的锐鸢无人机被发现中国大陆制造部件，并要求承包商更换为本地供应链产品。",
     "National Chung-Shan Institute of Science and Technology", "台湾地区防务主管部门",
     "无人机电子及非关键部件", "锐鸢无人机（Albatross UAV）", "2025-05-14",
     "https://www.taipeitimes.com/News/taiwan/archives/2025/05/14/2003836878", "Taipei Times",
     "B", "verified", ["锐鸢无人机内发现中国大陆制造部件", "主管部门要求承包商更换有关部件"],
     ["具体部件、制造商、承包商和采购批次未公开"]),
    ("Taiwan", "thunder-tiger-army-drone", "雷虎陆军训练无人机供应链",
     "雷虎科技陆军训练无人机接受零部件原产地和非红供应链调查，企业已提交完整来源证明，适合作为持续核验项目。",
     "Thunder Tiger Corporation", "台湾地区陆军",
     "训练无人机及全套零部件", "陆军训练无人机采购", "2026-05-27",
     "https://www.taiwannews.com.tw/news/6370854", "Taiwan News",
     "B", "follow_up", ["企业确认正配合陆军调查并提交零部件来源文件", "项目要求排除中国大陆来源部件"],
     ["目前公开材料未确认发现违规中国部件"]),
    ("Taiwan", "military-commercial-drones", "军用商规无人机非红供应链",
     "台湾地区通过军用商规无人机采购建立非红供应链，涉及多型无人机和本地整机企业，可继续按中标企业逐一穿透飞控、电机、电池、图传和光电载荷。",
     "Taiwan Excellence Drone International Business Opportunities Alliance", "台湾地区防务主管部门",
     "军用商规无人机、飞控、电机、电池、图传和光电载荷", "军用商规无人机采购计划", "2024-12-31",
     "https://gazette.nat.gov.tw/EG_FileManager/eguploadpub/eg032082/ch09/type9/gov01/num58/Eg.pdf", "台湾地区行政机构公报",
     "A", "follow_up", ["官方规划通过国防采购形成非红供应链", "2025至2030年规划持续投入无人机产业与供应链韧性"],
     ["需补充各型无人机中标公告、企业清单及部件原产地"]),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for country, slug, name, desc, entity_name, agency, product, program, date, url, publisher, grade, status, facts, limits in LEADS:
            ent_id, case_id, ose_id, inv_id = (
                f"ent-{country.lower()}-lead-{slug}",
                f"case-{country.lower()}-lead-{slug}",
                f"ose-{country.lower()}-lead-{slug}",
                f"inv-{country.lower()}-lead-{slug}",
            )
            upsert(db, SupplyChainEntity, ent_id, name=entity_name, name_zh=None,
                   country=country, entity_type="defense_supplier", aliases=[],
                   parent_id=None, defense_roles=[program, product], source_url=url,
                   notes=f"公开源线索；状态：{status}。后续补充合同、贸易和最终用途证据。")
            db.flush()
            upsert(db, SupplyChainCase, case_id, country=country, title=name,
                   procurement_agency=agency, procurement_reference="公开源供应链调查",
                   procurement_date=datetime.fromisoformat(date).replace(tzinfo=timezone.utc),
                   supplier_entity_id=ent_id, product=product, target_program=program,
                   contract_value=None, currency="USD", source_url=url,
                   source_excerpt=desc, status="verified_lead" if status == "verified" else "researching")
            db.flush()
            upsert(db, SupplyChainOpenSourceEvidence, ose_id, case_id=case_id,
                   title=f"{name}公开源核验材料",
                   source_type="official_document" if grade == "A" else "investigative_report",
                   source_publisher=publisher, source_url=url, source_excerpt=desc,
                   verified_facts=facts, evidence_grade=grade,
                   status="verified" if status == "verified" else "follow_up",
                   limitations=limits)
            upsert(db, SupplyChainInvestigation, inv_id, country=country, name=name,
                   description=desc, status="active" if status == "verified" else "researching",
                   entity_ids=[ent_id], case_ids=[case_id], shipment_ids=[], evidence_ids=[],
                   open_source_evidence_ids=[ose_id], report_ids=[])
        db.commit()
        print(f"Imported {len(LEADS)} Asia supply-chain leads.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
