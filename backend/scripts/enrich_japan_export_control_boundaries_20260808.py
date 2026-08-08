"""Add exact export-control entity boundaries and Taiwan-transfer screening.

The official records identify several Japanese legal entities covered by
China's 2026 dual-use export controls. Except for Kawasaki Heavy Industries
Aerospace Systems Company, the names must not be expanded to the whole parent
group. Japan's PAC-3 transfer to the United States is recorded only as a
screening boundary: it does not identify a manufacturer or a Taiwan onward
transfer. The script is idempotent.
"""
from __future__ import annotations

from app.database import Base, SessionLocal, engine
from app.models import SupplyChainInvestigation, SupplyChainOpenSourceEvidence


CONTROL_URL = (
    "https://exportcontrol.mofcom.gov.cn/article/zcfg/gnzcfg/"
    "zcfggzqd/202602/1209.html"
)
PAC3_TRANSFER_URL = "https://www.cas.go.jp/jp/gaiyou/jimu/pdf/r711_iten.pdf"
TRANSFER_CONTROL_URL = (
    "https://www.clearing.mod.go.jp/hakusho_data/2024/html/"
    "n410304000.html"
)
MARKER = "【2026-08-08中国出口管制主体边界】"
MHI_OLD_DESCRIPTION = (
    "三菱重工航空发动机承担日本防卫航空动力业务，被列入中国两用物项出口管制名单；"
    "重稀土、耐高温磁材等具体来源和装备项目待穿透。"
)
MHI_CORRECTED_DESCRIPTION = (
    "三菱重工本体承担日本防卫航空动力业务；商务部名单点名的是"
    "三菱重工航空发动机株式会社这一具体法律主体，并非三菱重工本体。"
    "重稀土、耐高温磁材等具体来源和装备项目待穿透。"
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


def attach(row, field: str, *row_ids: str) -> None:
    values = list(getattr(row, field) or [])
    for row_id in row_ids:
        if row_id not in values:
            values.append(row_id)
    setattr(row, field, values)


def evidence(
    db,
    row_id: str,
    case_id: str | None,
    title: str,
    source_type: str,
    publisher: str,
    url: str,
    excerpt: str,
    facts: list[str],
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
        evidence_grade="A",
        status="verified",
        limitations=limitations,
    )


CONTROL_SPECS = [
    {
        "inv_id": "inv-japan-lead-mhi-aeroengine-critical-materials",
        "case_id": "case-japan-lead-mhi-aeroengine-critical-materials",
        "ose_id": "ose-20260808-mhi-aeroengines-china-control-boundary",
        "title": "商务部点名三菱重工航空发动机公司，但不能扩张至三菱重工本体",
        "excerpt": (
            "商务部公告2026年第11号附件第2项列出三菱重工航空发动机株式会社，"
            "并禁止向名单实体出口或转移中国原产两用物项。"
        ),
        "facts": [
            "公告发布日期为2026年2月24日",
            "被列名法律主体为Mitsubishi Heavy Industries Aero Engines, Ltd.",
            "禁令同时覆盖境外组织或个人转移、提供中国原产两用物项",
            "公告要求正在开展的相关活动立即停止",
        ],
        "limitations": [
            "被列名的是三菱重工航空发动机株式会社，不等于三菱重工株式会社全部业务",
            "公告没有披露历史进口物项、供应商、订单、批次、数量或最终装备",
            "不得据此认定中国材料已进入三菱重工防卫航空发动机",
        ],
        "note": (
            "商务部公告点名的是三菱重工航空发动机株式会社这一具体法律主体；"
            "它不能与三菱重工本体的防卫航空发动机业务混同。公告证明管制状态，"
            "不证明历史进口或军用装机。"
        ),
    },
    {
        "inv_id": "inv-japan-lead-khi-aerospace-materials",
        "case_id": "case-japan-lead-khi-aerospace-materials",
        "ose_id": "ose-20260808-khi-aerospace-china-control-boundary",
        "title": "商务部出口管制名单直接点名川崎重工航空宇宙系统公司",
        "excerpt": (
            "商务部公告2026年第11号附件第6项列出川崎重工航空宇宙系统公司，"
            "禁止向其出口或转移中国原产两用物项。"
        ),
        "facts": [
            "公告发布日期为2026年2月24日",
            "Kawasaki Heavy Industries Aerospace Systems Company被直接列名",
            "禁令覆盖直接出口和境外转移、提供中国原产两用物项",
            "公告要求正在开展的相关活动立即停止",
        ],
        "limitations": [
            "公告没有披露该主体此前是否实际自中国进口",
            "公告没有披露物项、供应商、订单、批次、数量或最终装备",
            "不得据此认定任何中国物项已进入P-1、C-2、CH-47J或台湾装备",
        ],
        "note": (
            "川崎重工航空宇宙系统公司与公告被列名主体直接对应；但公告只证明"
            "2026年2月24日起的管制状态，未披露此前中国进口及具体军机装机记录。"
        ),
    },
    {
        "inv_id": "inv-japan-lead-ihi-aerospace-materials",
        "case_id": "case-japan-lead-ihi-aerospace-materials",
        "ose_id": "ose-20260808-ihi-subsidiaries-china-control-boundary",
        "title": "商务部点名六家IHI系主体，不能扩张至IHI株式会社全部业务",
        "excerpt": (
            "商务部公告2026年第11号附件第9至14项分别列出IHI原动机、IHI主要金属、"
            "IHI喷气机服务、IHI宇航、IHI航空制造和IHI宇航工程。"
        ),
        "facts": [
            "公告发布日期为2026年2月24日",
            "六家IHI系具体法律主体被列入出口管制管控名单",
            "禁令覆盖直接出口和境外转移、提供中国原产两用物项",
            "公告要求正在开展的相关活动立即停止",
        ],
        "limitations": [
            "名单没有直接列出IHI Corporation本体",
            "不能把子公司被列名自动扩张为IHI本体F7或F110业务已经进口中国物项",
            "公告没有披露物项、供应商、批次、数量或对台最终用途",
        ],
        "note": (
            "公告点名六家IHI系具体主体，但没有直接点名IHI株式会社本体；"
            "其价值是确定优先筛查对象和管制边界，不是F7、F110或宇航项目的进口凭证。"
        ),
    },
    {
        "inv_id": "inv-japan-lead-nec-defense-electronics",
        "case_id": "case-japan-lead-nec-defense-electronics",
        "ose_id": "ose-20260808-nec-subsidiaries-china-control-boundary",
        "title": "商务部点名两家NEC系防务主体，不能扩张至NEC本体",
        "excerpt": (
            "商务部公告2026年第11号附件第15、16项列出日本电气网络传感器株式会社"
            "和日本电气航空宇宙系统株式会社。"
        ),
        "facts": [
            "公告发布日期为2026年2月24日",
            "NEC Network and Sensor Systems与NEC Aerospace Systems被直接列名",
            "禁令覆盖直接出口和境外转移、提供中国原产两用物项",
            "公告要求正在开展的相关活动立即停止",
        ],
        "limitations": [
            "名单没有直接列出NEC Corporation本体",
            "不能把两家子公司被列名扩张成NEC全部雷达、通信和传感器业务的进口事实",
            "公告没有披露中国供应商、物项、订单、批次、数量或对台最终用途",
        ],
        "note": (
            "公告直接点名NEC Network and Sensor Systems与NEC Aerospace Systems，"
            "但未点名NEC本体，也未披露中国电子材料进入具体防务系统的历史批次。"
        ),
    },
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        investigation_rows = []
        for spec in CONTROL_SPECS:
            inv = db.get(SupplyChainInvestigation, spec["inv_id"])
            if inv is None:
                raise RuntimeError(f"Missing investigation: {spec['inv_id']}")
            evidence(
                db,
                spec["ose_id"],
                spec["case_id"],
                spec["title"],
                "official_export_control",
                "中华人民共和国商务部",
                CONTROL_URL,
                spec["excerpt"],
                spec["facts"],
                spec["limitations"],
            )
            attach(inv, "open_source_evidence_ids", spec["ose_id"])
            if spec["inv_id"] == "inv-japan-lead-mhi-aeroengine-critical-materials":
                inv.description = (inv.description or "").replace(
                    MHI_OLD_DESCRIPTION, MHI_CORRECTED_DESCRIPTION
                )
            if MARKER not in (inv.description or ""):
                inv.description = f"{inv.description or ''}\n\n{MARKER}{spec['note']}"
            investigation_rows.append(inv)

        pac3 = evidence(
            db,
            "ose-20260808-japan-pac3-us-transfer-boundary",
            None,
            "日本政府确认PAC-3转美，但未确认制造商或向台湾转供",
            "official_policy_document",
            "日本内阁官房国家安全保障局",
            PAC3_TRANSFER_URL,
            (
                "日本政府防卫装备转移资料称，2023年12月根据修订后的运用指针，"
                "日本将自卫队保有的PAC-3导弹转移给美国；这是首次向美国转移防卫装备完成品。"
            ),
            [
                "日本向美国转移的是自卫队保有的PAC-3导弹",
                "转移依据为2023年12月修订后的防卫装备转移运用指针",
                "该案是日本首次向美国转移防卫装备完成品",
            ],
            [
                "资料没有披露导弹制造商、批号、序列号或生产用材料来源",
                "资料没有提及台湾，也没有证明这些PAC-3由美国继续转供台湾",
                "不得把日本至美国的转移与美国对台PAC-3军售自动串联",
            ],
        )
        consent = evidence(
            db,
            "ose-20260808-japan-third-party-transfer-consent-boundary",
            None,
            "日本防卫白皮书确认第三方转移须防止未经日本事先同意",
            "official_policy_document",
            "日本防卫省",
            TRANSFER_CONTROL_URL,
            (
                "日本防卫白皮书说明，与受让国政府须缔结国际约定，防止被转移装备"
                "在未经日本事先同意的情况下改变用途或向第三方转移。"
            ),
            [
                "日本防卫装备海外转移按个案判断",
                "受让国政府需接受适当管理框架",
                "未经日本事先同意的目的外使用和第三方转移须被防止",
            ],
            [
                "这是制度性管理规则，不等于任何具体对台转移已提出或获准",
                "规则本身不识别制造商、物项批次或中国上游材料",
            ],
        )
        for inv in investigation_rows:
            attach(inv, "open_source_evidence_ids", pac3.id, consent.id)

        db.commit()
        print("Enriched four Japan investigations with 6 official boundary records.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
