"""Enrich four priority chains without overstating shipment-level evidence."""
from __future__ import annotations

from datetime import datetime, timezone

from app.database import Base, SessionLocal, engine
from app.models import (
    SupplyChainEntity,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
    SupplyChainShipment,
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


def attach(row, field, *ids):
    values = list(getattr(row, field) or [])
    for row_id in ids:
        if row_id not in values:
            values.append(row_id)
    setattr(row, field, values)


def entity(db, row_id, name, name_zh, country, entity_type, roles, url, notes):
    return upsert(
        db, SupplyChainEntity, row_id, name=name, name_zh=name_zh,
        country=country, entity_type=entity_type, aliases=[], parent_id=None,
        defense_roles=roles, source_url=url, notes=notes,
    )


def evidence(db, row_id, case_id, title, publisher, url, excerpt, facts, grade, limits):
    return upsert(
        db, SupplyChainOpenSourceEvidence, row_id, case_id=case_id, title=title,
        source_type="trade_database" if "贸易" in title else "official_document",
        source_publisher=publisher, source_url=url, source_excerpt=excerpt,
        verified_facts=facts, evidence_grade=grade, status="verified",
        limitations=limits,
    )


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # F-35: identify the disclosed tiers, but preserve anonymity at lower tiers.
        inv = db.get(SupplyChainInvestigation, "inv-us-lead-f35-china-smco")
        f35_entities = [
            ("ent-f35-lockheed", "Lockheed Martin Corporation", "洛克希德·马丁",
             "United States", "prime_contractor", ["F-35总承包商"]),
            ("ent-f35-honeywell", "Honeywell International Inc.", "Honeywell",
             "United States", "tier1_supplier", ["F-35综合动力包及涡轮机械制造商"]),
            ("ent-f35-lube-pump-anon", "F-35 IPP Lube Pump Supplier (undisclosed)",
             "F-35润滑泵供应商（未披露）", "United States", "tier2_supplier",
             ["向Honeywell供应涡轮机械润滑泵"]),
            ("ent-f35-magnet-anon", "F-35 Magnet Supplier (undisclosed)",
             "F-35磁体供应商（未披露）", "Unknown", "tier3_supplier",
             ["使用中国来源钐钴合金制造磁体"]),
            ("ent-f35-china-alloy-anon", "Chinese Samarium-Cobalt Alloy Manufacturer (undisclosed)",
             "中国钐钴合金制造商（未披露）", "China", "china_exporter",
             ["F-35涉事钐钴合金原始制造节点"]),
        ]
        for row in f35_entities:
            entity(db, *row,
                   "https://www.pogo.org/commentaries/use-of-chinese-material-in-f-35-highlights-pentagons-complexity-problem",
                   "公开材料确认供应层级，但下三级企业名称未披露；不得将候选磁材企业直接等同于涉事供应商。")
        db.flush()
        evidence(db, "ose-f35-2026-no-continuing-import", "case-us-lead-f35-china-smco",
                 "F-35钐钴合金链2026年延续性核验",
                 "FlightGlobal / GAO",
                 "https://www.flightglobal.com/fixed-wing/all-f-35s-contain-component-made-from-chinese-origin-metal-pentagon/150165.article",
                 "Honeywell在发现问题后停止与涉事合金供应链合作；本轮未发现2026年同一链条继续自华进口的可核验记录。",
                 ["涉事磁体用于Honeywell F-35涡轮机械", "Honeywell已停止使用涉事供应商",
                  "截至本轮检索未发现2026年同链条继续进口记录"],
                 "A", ["下级供应商匿名，无法直接用企业名开展完整提单反查"])
        attach(inv, "entity_ids", *(row[0] for row in f35_entities))
        attach(inv, "open_source_evidence_ids", "ose-f35-2026-no-continuing-import")
        inv.description = (
            "中国钐钴合金制造商（未披露）→磁体供应商（未披露）→润滑泵供应商（未披露）"
            "→Honeywell涡轮机械→Lockheed Martin F-35。Honeywell已停止涉事供应，"
            "暂未发现2026年同一链条继续自华进口记录。"
        )

        # Quadrant: add the confirmed Chinese manufacturing and shipment node.
        inv = db.get(SupplyChainInvestigation, "inv-us-lead-quadrant-fighter-magnets")
        quadrant_entities = [
            ("ent-quadrant-hangzhou-xmag", "Hangzhou X-Mag Inc.", "杭州X-Mag公司",
             "China", "china_exporter", ["Quadrant历史磁体供应商"]),
            ("ent-quadrant-hangzhou-hub", "Quadrant Magnetics (Hangzhou)",
             "Quadrant杭州制造中心", "China", "manufacturing_site",
             ["Quadrant磁性技术、模组设计和量产中心"]),
            ("ent-quadrant-us-component-1", "U.S. Component Company 1 (undisclosed)",
             "美国零部件企业1（未披露）", "United States", "tier_supplier",
             ["Quadrant磁体下游国防零部件企业"]),
            ("ent-quadrant-us-component-2", "U.S. Component Company 2 (undisclosed)",
             "美国零部件企业2（未披露）", "United States", "tier_supplier",
             ["Quadrant磁体下游国防零部件企业"]),
        ]
        for row in quadrant_entities:
            entity(db, *row, "https://www.importgenius.com/importers/quadrant-magnetics",
                   "主体来自企业官网、美国司法部或贸易数据库；匿名美国企业仍待司法案卷解密。")
        db.flush()
        shipment_id = "shp-quadrant-xmag-20240505"
        upsert(
            db, SupplyChainShipment, shipment_id,
            exporter_name="Hangzhou X-Mag Inc.", exporter_country="China",
            importer_entity_id="ent-us-lead-quadrant-fighter-magnets",
            importer_name="Quadrant Magnetics LLC", product="稀土磁体",
            hs_code="850511", shipment_date=datetime(2024, 5, 5, tzinfo=timezone.utc),
            weight_kg=3050, quantity=6, quantity_unit="packages",
            origin_country="China", destination_country="United States",
            bill_no="EXDO6395875046", source_name="ImportGenius公开贸易记录",
            source_url="https://www.importgenius.com/importers/quadrant-magnetics",
            raw_record={"evidence_boundary": "历史直接记录；不是2026年记录"},
        )
        evidence(db, "ose-quadrant-2026-trade-check", "case-us-lead-quadrant-fighter-magnets",
                 "Quadrant及杭州X-Mag 2026年贸易延续性核验", "ImportInfo / Trademo",
                 "https://www.importinfo.com/hangzhou-x-mag-inc",
                 "杭州X-Mag截至2026年4月仍有对美出货，但公开2026记录未显示Quadrant为收货方；Quadrant与其直接贸易可确认至2024年。",
                 ["杭州X-Mag最近对美记录日期为2026年4月23日",
                  "Quadrant与杭州X-Mag可见直接磁体记录为2024年5月、3,050千克",
                  "Quadrant杭州制造中心仍为集团中国制造节点"],
                 "B", ["不能把杭州X-Mag 2026年对其他美国买家的出货归入Quadrant"])
        attach(inv, "entity_ids", *(row[0] for row in quadrant_entities))
        attach(inv, "shipment_ids", shipment_id)
        attach(inv, "open_source_evidence_ids", "ose-quadrant-2026-trade-check")
        inv.description = (
            "杭州X-Mag及Quadrant杭州制造中心→Quadrant Magnetics LLC→两家匿名美国零部件企业"
            "→F-16、F/A-18等装备。直接自华磁体记录可确认至2024年；2026年杭州X-Mag仍对美"
            "出货，但未确认收货方为Quadrant。"
        )

        # India drones: preserve aggregate trade evidence, not a fabricated bill of lading.
        inv = db.get(SupplyChainInvestigation, "inv-india-lead-dhaksha-logistics-drone")
        india_entities = [
            ("ent-dhaksha-coromandel", "Coromandel International Limited",
             "科罗曼德国际有限公司", "India", "parent_company", ["Dhaksha控股母公司"]),
            ("ent-dhaksha-china-suppliers-anon", "Dhaksha China/Hong Kong Suppliers (undisclosed)",
             "Dhaksha中国内地及香港供应商（未披露）", "China", "china_exporter",
             ["无人机零部件进口供应网络"]),
            ("ent-dhaksha-indian-army", "Indian Army", "印度陆军",
             "India", "military_end_user", ["200架中空物流无人机采购方"]),
        ]
        for row in india_entities:
            entity(db, *row, "https://www.volza.com/company-profile/dhaksha-unmanned-systems-pvt-ltd-16671722/",
                   "贸易数据库公开页显示供应网络汇总，逐票供应商和产品需付费明细进一步核验。")
        db.flush()
        evidence(db, "ose-dhaksha-2026-import-network", "case-india-lead-dhaksha-logistics-drone",
                 "Dhaksha截至2026年7月进口网络贸易证据", "Volza / Eximpedia",
                 "https://www.volza.com/company-profile/dhaksha-unmanned-systems-pvt-ltd-16671722/",
                 "贸易数据库截至2026年7月显示Dhaksha有632票进口、42家供应商，来源覆盖香港、中国和美国；另一数据库显示中国方向94票。",
                 ["数据更新至2026年7月", "Dhaksha存在来自中国内地及香港的进口网络",
                  "公开页显示中国方向94票、42家全球供应商"],
                 "B", ["公开页未展示逐票日期、产品和供应商名称", "不能证明有关进口用于印度陆军200架合同"])
        attach(inv, "entity_ids", *(row[0] for row in india_entities))
        attach(inv, "open_source_evidence_ids", "ose-dhaksha-2026-import-network")
        inv.description = (
            "中国内地及香港供应商（公开页未披露）→Dhaksha Unmanned Systems"
            "→印度陆军200架中空物流无人机项目。贸易数据库截至2026年7月仍显示中国方向进口网络，"
            "但逐票产品与军用合同归属尚待核验。"
        )

        # Japan: add upstream material categories and 2026 cessation evidence.
        japan_chains = [
            ("inv-japan-lead-mhi-aeroengine-critical-materials",
             "case-japan-lead-mhi-aeroengine-critical-materials",
             "ent-japan-mhi-china-material-node", "三菱重工中国关键材料供应节点（待识别）",
             ["重稀土、耐高温磁材、镓及航空发动机材料"]),
            ("inv-japan-lead-khi-aerospace-materials",
             "case-japan-lead-khi-aerospace-materials",
             "ent-japan-khi-china-material-node", "川崎重工中国关键材料供应节点（待识别）",
             ["钕铁硼磁体、重稀土及航空电子材料"]),
            ("inv-japan-lead-ihi-aerospace-materials",
             "case-japan-lead-ihi-aerospace-materials",
             "ent-japan-ihi-china-material-node", "IHI中国关键材料供应节点（待识别）",
             ["航空发动机合金、磁材及宇航电子材料"]),
            ("inv-japan-lead-nec-defense-electronics",
             "case-japan-lead-nec-defense-electronics",
             "ent-japan-nec-china-material-node", "NEC中国电子材料供应节点（待识别）",
             ["镓、半导体、雷达和传感器相关材料"]),
        ]
        for inv_id, case_id, ent_id, ent_zh, roles in japan_chains:
            inv = db.get(SupplyChainInvestigation, inv_id)
            entity(db, ent_id, f"China-origin material suppliers for {inv.name}",
                   ent_zh, "China", "china_exporter", roles,
                   "https://static.rusi.org/china-and-rare-earths-supply-chain-june-2026-sanderson-rp.pdf",
                   "目前只能确认材料类别依赖和管制对象，尚无企业级提单证据。")
            db.flush()
            ose_id = f"ose-{inv_id}-2026-flow-check"
            evidence(db, ose_id, case_id, f"{inv.name}2026年贸易流核验",
                     "RUSI / 中国商务部 / 日本贸易统计相关报道",
                     "https://static.rusi.org/china-and-rare-earths-supply-chain-june-2026-sanderson-rp.pdf",
                     "2026年对日重稀土管制后，镝、铽、氧化钇及镓等对日出口基本停止；未发现可归属于该企业的2026年持续进口记录。",
                     ["2026年相关日本军工实体被纳入两用物项出口管制",
                      "中国对日镝、铽、氧化钇和镓出口出现断流或仅余极少量",
                      "当前无企业级2026年进口批次可核验"],
                     "A", ["宏观海关流量不能直接对应单一日本企业", "不得虚构供应商和提单"])
            attach(inv, "entity_ids", ent_id)
            attach(inv, "open_source_evidence_ids", ose_id)
            inv.description += " 2026年管制后相关材料对日贸易显著收缩，暂未发现可归属于该企业的持续进口批次。"

        db.commit()
        print("Enriched F-35, Quadrant, Dhaksha and four Japan material chains.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
