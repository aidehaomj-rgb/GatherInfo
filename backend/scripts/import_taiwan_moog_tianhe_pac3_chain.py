"""Import the user-supplied Moog/Tianhe Taiwan-facing supply-chain lead.

The import is intentionally conservative: trade records are aggregated from a
redacted report, while the Moog PAC-3 contract and Taiwan PAC-3 MSE sale are
stored as separate, independently sourced downstream cases.  The script is
idempotent and preserves the evidence boundary between them.
"""
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


REPORT_PATH = Path(r"D:\codex\供应链穿透\美军工企业M今年打了采购中企T生产的稀土永磁体，正用于洛克西德.马丁、莱多斯等导弹作动系统生产，相关装备对台军售.docx")
REPORT_URL = REPORT_PATH.as_uri()
MOOG_PAC3 = "https://www.moog.com/news/operating-group-news/2025/moog-receives-substantial-lockheed-martin-award-in-support-of-pac-3-mse-contract.html"
MOOG_MISSILES = "https://www.moog.com/markets/defense/missiles.html"
CONGRESS_PAC3 = "https://www.congress.gov/117/crec/2022/12/05/168/188/CREC-2022-12-05.pdf"
LOCKHEED_PAC3_2026 = "https://news.lockheedmartin.com/2026-04-10-Lockheed-Martin-Secures-First-Contract-for-PAC-3-R-MSE-Accelerated-Production%2C-Strengthening-the-Arsenal-of-Freedom"
GALAXY_PROFILE = "https://en.galaxymagnets.com/about.aspx?t=4"
GALAXY_TRADE = "https://www.importgenius.com/suppliers/chengdu-galaxy-magnets-co-ltd"
INV_ID = "inv-taiwan-lead-moog-tianhe-pac3-magnets"
SHIP_ID = "shp-taiwan-moog-tianhe-20260316-20260504-summary"


def upsert(db, model, row_id: str, **values):
    row = db.get(model, row_id)
    if row is None:
        row = model(id=row_id, **values)
        db.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    return row


def attach(row, field: str, *ids: str) -> None:
    current = list(getattr(row, field) or [])
    for row_id in ids:
        if row_id not in current:
            current.append(row_id)
    setattr(row, field, current)


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def entity(db, row_id, name, name_zh, country, entity_type, roles, url, notes, aliases=None):
    return upsert(db, SupplyChainEntity, row_id, name=name, name_zh=name_zh,
                  country=country, entity_type=entity_type, aliases=list(aliases or []),
                  defense_roles=roles, source_url=url, notes=notes)


def ose(db, row_id, case_id, title, source_type, publisher, url, excerpt,
        facts, grade, status, limitations):
    return upsert(db, SupplyChainOpenSourceEvidence, row_id, case_id=case_id,
                  title=title, source_type=source_type, source_publisher=publisher,
                  source_url=url, source_excerpt=excerpt, verified_facts=facts,
                  evidence_grade=grade, status=status, limitations=limitations)


def relation(db, row_id, case_id, shipment_id, relation_type, grade, score,
             status, reasoning, facts, reportable=False):
    return upsert(db, SupplyChainEvidence, row_id, case_id=case_id,
                  shipment_id=shipment_id, relation_type=relation_type,
                  evidence_grade=grade, score=score, status=status,
                  reasoning=reasoning, verified_facts=facts,
                  model_review={"review": "manual import; batch-to-end-use closure pending"},
                  is_reportable=reportable)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        inv = upsert(
            db, SupplyChainInvestigation, INV_ID,
            country="Taiwan",
            name="天和磁材/成都银河磁体—穆格—PAC-3 MSE涉台军售供应链",
            description=(
                "中国供应端包括天和磁材及成都银河磁体两家并列节点。报告称2026-03-16至05-04，Moog自天和磁材采购至少8票、约26.5吨稀土永磁体，"
                "其中7票中国直发、1票经韩国釜山中转。公开证据可独立确认Moog为Lockheed Martin PAC-3 MSE"
                "定制机电作动器供应商，以及台湾曾获批PAC-3 MSE军售；贸易情报另将Moog Components Group/Moog Aspen列为成都银河磁体贸易伙伴。"
                "但两家中国供应商均缺少磁体批次到武器的BOM、序列号或最终用途文件，"
                "因此本调查保持researching，不能把该批磁体直接认定为已进入台湾军售装备。报告中2026年‘102枚’表述未独立核验。"
            ),
            status="researching", entity_ids=[], case_ids=[], shipment_ids=[],
            evidence_ids=[], open_source_evidence_ids=[], report_ids=[],
        )

        # Entities are added and flushed before cases to satisfy FK ordering on SQLite.
        entities = [
            entity(db, "ent-taiwan-moog", "Moog Inc.", "穆格公司", "United States", "defense_supplier", ["missile actuation", "precision motion", "PAC-3 MSE actuators"], MOOG_PAC3, "Official Moog disclosure supports the PAC-3 MSE actuator award."),
            entity(db, "ent-taiwan-tianhe-magnet", "Tianhe Magnetic Materials (report name)", "天和磁材（报告口径）", "China", "china_exporter", ["sintered NdFeB magnets", "sintered SmCo magnets"], REPORT_URL, "Supplier/importer names are redacted in the supplied trade screenshot; legal identity requires verification."),
            entity(db, "ent-taiwan-chengdu-galaxy-magnets", "Chengdu Galaxy Magnets Co., Ltd.", "成都银河磁体股份有限公司", "China", "component_supplier", ["bonded NdFeB magnets", "hot-pressed NdFeB magnets", "SmCo magnets", "reported Moog trade partner"], GALAXY_PROFILE, "Official company profile verifies the magnet product range. Trade-intelligence indexing lists Moog Components Group and Moog Aspen among U.S. trading partners; individual bills and end use remain to be verified.", aliases=["成都银河磁体有限公司", "成都银河磁体", "银河磁体", "Galaxy Magnets"]),
            entity(db, "ent-taiwan-moog-military-aircraft", "Moog Military Aircraft, LLC", "穆格军用飞机公司", "United States", "defense_supplier", ["military aircraft systems", "facility security"], REPORT_URL, "Facility-clearance and AS9100D claims are retained as report-level leads."),
            entity(db, "ent-taiwan-lockheed-martin", "Lockheed Martin Corporation", "洛克希德·马丁公司", "United States", "defense_prime", ["PAC-3 MSE prime contractor", "missile defense"], LOCKHEED_PAC3_2026, "PAC-3 MSE prime/production role."),
            entity(db, "ent-taiwan-leidos", "Leidos, Inc.", "莱多斯公司", "United States", "defense_prime", ["Black Arrow customer/prime", "missile systems"], MOOG_MISSILES, "Black Arrow connection is report-level here; official page supports Moog missile actuation capability."),
            entity(db, "ent-taiwan-us-army", "U.S. Army / U.S. Department of Defense", "美国陆军/国防部", "United States", "military_end_user", ["PAC-3 MSE end user"], MOOG_PAC3, "Official Moog release identifies the U.S. Army contract."),
            entity(db, "ent-taiwan-pac3-enduser", "Taiwan Ministry of National Defense / TECRO", "台湾防务部门/驻美台北经济文化代表处", "Taiwan", "military_end_user", ["Taiwan PAC-3 MSE recipient"], CONGRESS_PAC3, "Congressional Record identifies TECRO as purchaser for the PAC-3 MSE case."),
            entity(db, "ent-taiwan-trivet-industrial", "Trivet Industrial Corporation", "卓域工业", "Taiwan", "agent_distributor", ["Taiwan defense/industrial agent (report claim)"], REPORT_URL, "Agent relationship is reported but not independently validated in this import."),
        ]
        db.flush()
        # The displayed primary chain is intentionally four nodes:
        # Tianhe / Chengdu Galaxy (parallel China suppliers) -> Moog ->
        # Lockheed Martin -> Taiwan. Other
        # actors remain in the database as evidence/context entities but are
        # not allowed to displace Taiwan from the fourth displayed position.
        inv.entity_ids = [
            "ent-taiwan-tianhe-magnet",
            "ent-taiwan-chengdu-galaxy-magnets",
            "ent-taiwan-moog",
            "ent-taiwan-lockheed-martin",
            "ent-taiwan-pac3-enduser",
        ]

        cases = [
            upsert(db, SupplyChainCase, "case-taiwan-moog-tianhe-magnets", country="Taiwan", title="穆格2026年自天和磁材采购稀土永磁体", procurement_agency="Moog Inc.", procurement_reference="用户报告/提单截图汇总", procurement_date=None, supplier_entity_id="ent-taiwan-tianhe-magnet", product="稀土永磁体（烧结钕铁硼/钐钴，具体元素含量待核）", target_program="Moog军用/航空防务作动器和电机生产体系", contract_value=None, currency="USD", source_url=REPORT_URL, source_excerpt="报告称2026-03-16至05-04至少8票、约26.5吨；进口商/供应商在截图中打码。", status="researching"),
            upsert(db, SupplyChainCase, "case-taiwan-moog-lockheed-pac3-mse", country="Taiwan", title="穆格为Lockheed Martin PAC-3 MSE提供定制作动器", procurement_agency="Lockheed Martin / U.S. Army", procurement_reference="Moog official release", procurement_date=dt("2025-01-29"), supplier_entity_id="ent-taiwan-moog", product="PAC-3 MSE custom electromechanical actuators", target_program="Patriot PAC-3 MSE", contract_value=None, currency="USD", source_url=MOOG_PAC3, source_excerpt="Moog states it was selected by Lockheed Martin for custom electromechanical actuators; award exceeds $100 million and provides precision steering.", status="verified"),
            upsert(db, SupplyChainCase, "case-taiwan-moog-leidos-black-arrow", country="Taiwan", title="穆格为莱多斯Black Arrow提供导弹鳍面控制作动系统（报告线索）", procurement_agency="Leidos, Inc.", procurement_reference="用户报告；Moog missile capabilities page", procurement_date=None, supplier_entity_id="ent-taiwan-moog", product="Black Arrow small cruise missile fin-control actuation/CAS shipsets", target_program="Leidos Black Arrow", contract_value=None, currency="USD", source_url=MOOG_MISSILES, source_excerpt="Moog公开资料支持其导弹精密转向/鳍面控制作动能力；具体Black Arrow批次关联仍以报告线索记录。", status="researching"),
            upsert(db, SupplyChainCase, "case-taiwan-pac3-mse-taiwan-fms", country="Taiwan", title="台湾PAC-3 MSE军售官方记录（100枚+2枚测试弹）", procurement_agency="U.S. Department of State / DoD / DSCA; TECRO", procurement_reference="117th Congressional Record, 2022-12-05", procurement_date=dt("2022-12-01"), supplier_entity_id="ent-taiwan-lockheed-martin", product="100 PAC-3 MSE missiles + 2 PAC-3 MSE test missiles", target_program="Taiwan Patriot missile defense", contract_value=2810000000.0, currency="USD", source_url=CONGRESS_PAC3, source_excerpt="Congressional Record records the addition of 100 PAC-3 MSE missiles and 2 test missiles for TECRO; total case value estimated at $2.81 billion.", status="verified"),
            upsert(db, SupplyChainCase, "case-taiwan-galaxy-moog-bonded-magnets", country="Taiwan", title="成都银河磁体向Moog体系供应粘结磁体（贸易情报线索）", procurement_agency="Moog Components Group / Moog Aspen Motion Technologies", procurement_reference="公开贸易情报索引", procurement_date=None, supplier_entity_id="ent-taiwan-chengdu-galaxy-magnets", product="粘结钕铁硼等永磁体（具体牌号、批次待核）", target_program="Moog电机/作动器供应体系（最终项目待核）", contract_value=None, currency="USD", source_url=GALAXY_TRADE, source_excerpt="ImportGenius公开供应商页将MOOG COMPONENTS GROUP、MOOG ASPEN-RADFORD列为成都银河磁体的主要贸易伙伴；逐票记录及最终用途未公开。", status="researching"),
        ]
        db.flush()
        attach(inv, "case_ids", *(row.id for row in cases))

        shipment = upsert(db, SupplyChainShipment, SHIP_ID, exporter_name="Tianhe Magnetic Materials (report name, legal identity undisclosed)", exporter_country="China", importer_entity_id="ent-taiwan-moog", importer_name="Moog Inc.", product="稀土永磁体", hs_code=None, shipment_date=None, weight_kg=26500.0, quantity=8.0, quantity_unit="shipments", origin_country="China", destination_country="United States", bill_no=None, source_name="用户提供报告/提单截图汇总", source_url=REPORT_URL, raw_record={"evidence_boundary": "report_aggregate_not_individual_bills", "reported_min_shipments": 8, "reported_total_weight_kg_approx": 26500, "china_direct_shipments": 7, "south_korea_transit_shipments": 1, "visible_rows": [{"arrival_date": "2026-05-04", "origin_label": "South Korea", "weight_kg": 2389}, {"arrival_date": "2026-04-30", "origin_label": "China", "weight_kg": 4803}, {"arrival_date": "2026-04-18", "origin_label": "China", "weight_kg": 2389}, {"arrival_date": "2026-03-20", "origin_label": "China", "weight_kg": 2389}, {"arrival_date": "2026-03-19", "origin_label": "China", "weight_kg": 2389}, {"arrival_date": "2026-03-19", "origin_label": "China", "weight_kg": 4778}, {"arrival_date": "2026-03-19", "origin_label": "China", "weight_kg": 5024}, {"arrival_date": "2026-03-16", "origin_label": "China", "weight_kg": 2389}], "supplier_name_redacted": True, "importer_name_redacted": True})
        db.flush()
        attach(inv, "shipment_ids", shipment.id)

        ev_trade = relation(db, "ev-taiwan-moog-tianhe-trade-direct", cases[0].id, shipment.id, "direct_trade_record", "B", 72, "follow_up", "Report screenshot shows Moog as importer and the named Chinese supplier, but names are redacted and individual bills were not supplied.", ["At least 8 reported shipments", "Approx. 26.5 tonnes", "7 China-direct and 1 South Korea-transit route", "Elemental composition and final use are undisclosed"])
        ev_pac3 = relation(db, "ev-taiwan-moog-tianhe-pac3-candidate", cases[1].id, shipment.id, "candidate_component", "C", 45, "follow_up", "Moog's official PAC-3 MSE actuator role is verified, but no BOM, lot, serial, or batch-to-actuator record connects this magnet shipment to PAC-3.", ["Moog official release confirms PAC-3 MSE actuator award", "Shipment-to-PAC-3 linkage remains a candidate"])
        ev_black = relation(db, "ev-taiwan-moog-tianhe-black-arrow-candidate", cases[2].id, shipment.id, "candidate_component", "C", 40, "follow_up", "Moog missile actuation capability is public and the report names Black Arrow, but the supplied material does not close the batch-to-weapon chain.", ["Moog missile fin-control capability is public", "Black Arrow batch linkage remains report-level"])
        attach(inv, "evidence_ids", ev_trade.id, ev_pac3.id, ev_black.id)

        opens = [
            ose(db, "ose-taiwan-moog-report-trade-records", cases[0].id, "报告/提单截图：穆格自天和磁材采购稀土永磁体", "user_report", "用户提供报告", REPORT_URL, "截图可见2026-03-16至05-04多票稀土永磁体，来源国标注中国或韩国，供应商和进口商字段打码。", ["报告汇总至少8票", "总毛重约26.5吨", "7票中国直发、1票经韩国中转", "不可据此确认元素成分或最终用途"], "B", "follow_up", ["未提供逐票提单原件", "供应商/进口商名称在截图中打码", "缺少批次、BOM和最终用户"]),
            ose(db, "ose-taiwan-moog-report-military-clearance", cases[0].id, "报告：Moog Military Aircraft设施安全资质与AS9100D", "user_report", "用户提供报告", REPORT_URL, "报告称Moog Military Aircraft, LLC具备设施安全资质并符合AS9100D。", ["属于报告转述"], "C", "follow_up", ["报告未附外部证书或官方查询链接"]),
            ose(db, "ose-taiwan-moog-report-black-arrow", cases[2].id, "报告：Moog向莱多斯Black Arrow交付鳍面控制作动系统", "user_report", "用户提供报告", REPORT_URL, "报告称Moog交付Black Arrow CAS shipsets；具体采购/交付文件未附。", ["属于报告线索", "需要Moog/Leidos项目公告或合同佐证"], "C", "follow_up", ["报告未给出可核验的原始公告链接"]),
            ose(db, "ose-taiwan-moog-report-trivet-agent", cases[0].id, "报告：Moog台湾代理卓域工业", "user_report", "用户提供报告", REPORT_URL, "报告列示Trivet Industrial Corporation为台湾代理/渠道。", ["属于报告线索"], "C", "follow_up", ["未做官网、注册或军售合同独立核验"]),
            ose(db, "ose-taiwan-moog-official-pac3-actuator", cases[1].id, "Moog官方：获Lockheed Martin PAC-3 MSE作动器合同", "company_disclosure", "Moog", MOOG_PAC3, "Moog称被Lockheed Martin选中，为美国陆军PAC-3 MSE合同提供定制机电作动器；合同金额超过1亿美元，作动器用于精密转向。", ["Moog确认PAC-3 MSE作动器供应角色", "合同金额超过1亿美元", "生产地点为盐湖城"], "A", "verified", ["公司公告不披露磁体供应商、批次或BOM"]),
            ose(db, "ose-taiwan-moog-official-missile-capabilities", cases[2].id, "Moog官方导弹业务：精密转向与鳍面控制作动", "company_disclosure", "Moog", MOOG_MISSILES, "Moog公开导弹业务资料说明其提供精密转向控制和鳍面控制作动系统。", ["官方资料支持Moog导弹作动器能力", "不等于该批磁体已进入Black Arrow"], "B", "verified", ["本条不单独证明Black Arrow具体批次"]),
            ose(db, "ose-taiwan-pac3-taiwan-official-fms", cases[3].id, "美国国会记录：台湾PAC-3 MSE军售", "official_document", "U.S. Congress / DSCA", CONGRESS_PAC3, "官方记录列明TECRO为购买方，并增加100枚PAC-3 MSE导弹及2枚测试弹；预计总案值28.1亿美元。", ["100枚PAC-3 MSE + 2枚测试弹", "TECRO为购买方", "总案值估计28.1亿美元", "这是官方涉台军售证据"], "A", "verified", ["该记录不证明本次2026年磁体批次进入上述导弹"]),
            ose(db, "ose-taiwan-lockheed-pac3-2026-production", cases[1].id, "Lockheed Martin官方：PAC-3 MSE加速生产合同", "company_disclosure", "Lockheed Martin", LOCKHEED_PAC3_2026, "Lockheed Martin称获得47亿美元PAC-3 MSE加速生产合同，面向美国及盟友。", ["PAC-3 MSE生产规模和盟友供给得到官方确认"], "A", "verified", ["公告未指向台湾特定批次，也未涉及磁体供应链"]),
            ose(db, "ose-taiwan-moog-material-boundary", cases[0].id, "报告明确限制：提单未披露元素含量和最终用途", "user_report", "用户提供报告", REPORT_URL, "报告自身提示提单没有披露稀土元素组成，无法仅凭货运记录确认材料具体进入何种武器。", ["元素含量未知", "无BOM/批次/序列号闭环", "最终用途未被提单直接证明"], "A", "verified", ["这是对证据边界的记录，不是独立来源"]),
            ose(db, "ose-taiwan-galaxy-official-product-profile", cases[4].id, "银河磁体官网：粘结钕铁硼、热压磁体及钐钴产品体系", "company_disclosure", "Chengdu Galaxy Magnets", GALAXY_PROFILE, "公司官网确认正式主体为Chengdu Galaxy Magnets，并生产粘结磁体、热压磁体和钐钴磁体，产品销往美国等市场。", ["正式中文主体为成都银河磁体股份有限公司", "主营粘结钕铁硼、热压磁体和钐钴磁体", "存在美国等海外市场"], "A", "verified", ["官网未披露Moog客户名称或军用最终用途"]),
            ose(db, "ose-taiwan-galaxy-moog-trade-index", cases[4].id, "贸易情报索引：银河磁体与Moog Components Group/Moog Aspen存在贸易关系", "trade_intelligence", "ImportGenius", GALAXY_TRADE, "公开供应商页将MOOG COMPONENTS GROUP和MOOG ASPEN-RADFORD列入成都银河磁体主要贸易伙伴，并将产品类别展示为bonded magnet。", ["公开索引出现Moog体系贸易伙伴", "产品类别为粘结磁体", "成都银河磁体为中国供应主体"], "B", "follow_up", ["免费页面未展示全部逐票提单", "尚缺对应Moog批次的重量、提单号和最终项目", "不能据此认定进入PAC-3 MSE"]),
        ]
        attach(inv, "open_source_evidence_ids", *(row.id for row in opens))

        report = upsert(db, SupplyChainReport, "scr-taiwan-moog-tianhe-pac3-chain", country="Taiwan", title="中国磁材—穆格—洛克希德·马丁涉台供应链核验报告", case_ids=[row.id for row in cases], evidence_ids=[ev_trade.id, ev_pac3.id, ev_black.id], model_id="manual-verified-import", status="completed", content=("结论：中国供应端包括天和磁材和成都银河磁体两个并列节点。报告提供天和磁材—Moog稀土永磁体贸易线索；公开贸易情报索引支持成都银河磁体—Moog体系的粘结磁体贸易关系；Moog PAC-3 MSE作动器供应角色和台湾PAC-3 MSE军售均有独立公开来源。\n\n" "边界：目前没有元素成分、BOM、批号/序列号或最终用户文件，不能将任一中国磁体批次直接归因于台湾PAC-3或Black Arrow装备。"), summary="天和磁材/成都银河磁体并列供应Moog体系；官方PAC-3作动器和台湾军售证据已核，批次到武器闭环待补。", generated_at=datetime.now(timezone.utc))
        attach(inv, "report_ids", report.id)
        inv.updated_at = datetime.now(timezone.utc)
        db.commit()
        print(f"imported {INV_ID}: {len(entities)} entities, {len(cases)} cases, 1 shipment, {len(opens)} OSE, 3 relations")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
