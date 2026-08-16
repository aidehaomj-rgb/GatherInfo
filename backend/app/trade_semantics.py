"""涉进出口贸易主题的语义受控词表（源自 InfoRoute global_trade_hotspot 三轴分类）。

本模块把「时政热点」这类主题的语义意图固化为受控词表，用于：

1. **语义检索式生成**（``research_planner.build_research_queries``）——
   用政策工具 + 影响渠道把主题意图展开为具体检索式，替代散装关键词；
2. **语义相关性兜底**（``engine._persist_items``）——
   当字面关键词未命中时，用政策工具词表判定语义相关性，避免中英措辞差异导致的漏采；
3. **分类对齐**（``tag_taxonomy.normalize_category``）——
   把英文政策工具值映射到本项目的受控业务分类，让标签浓缩更准。

词表与主题绑定仅在「贸易类」主题生效；关键矿产、军工采购等主题不受影响
（其 ``topic_id`` 不在 :data:`TOPIC_SEMANTIC_PROFILES` 中）。
"""
from __future__ import annotations

# ── 政策工具（policy_instrument）多语言关键词 ─────────────────────────
# slug → 命中关键词（全部小写子串匹配）。关键词刻意取较长形态，避免短缩写
# （如 "sps"、"tbt"）误匹配到无关英文单词片段。
POLICY_INSTRUMENTS: dict[str, tuple[str, ...]] = {
    "tariff": (
        "tariff", "customs duty", "import duty", "duty rate",
        "关税", "税则", "关税率", "tarifa", "arancel", "droits de douane", "zoll",
    ),
    "anti_dumping": (
        "anti-dumping", "antidumping", "anti dumping", "反倾销", "倾销",
        "dumping margin", "倾销幅度",
    ),
    "countervailing": (
        "countervailing", "反补贴", "补贴", "subsidy", "countervailable",
    ),
    "safeguard": (
        "safeguard measure", "保障措施", "safeguard tariff", "紧急进口限制",
    ),
    "quota_license": (
        "import quota", "export quota", "配额", "许可证",
        "export license", "import license", "licensing requirement", "出口许可", "进口许可",
    ),
    "export_control": (
        "export control", "出口管制", "dual-use", "两用物项", "entity list", "实体清单",
        "end-user", "最终用户", "export restriction", "管制清单",
    ),
    "sanctions": (
        "sanction", "制裁", "反制", "embargo", "禁运", "sanctioned entity", "受制裁",
    ),
    "import_export_ban": (
        "import ban", "export ban", "禁令", "禁限", "禁止进口", "禁止出口", "prohibition",
    ),
    "sps_tbt": (
        "technical barriers to trade", "技术性贸易壁垒", "sanitary and phytosanitary",
        "卫生与植物卫生", "tbt notification", "sps measures", "技术壁垒",
    ),
    "customs_procedure": (
        "customs", "海关", "clearance", "清关", "报关", "customs declaration",
        "aduana", "zoll", "税関", "세관", "海关程序",
    ),
    "rules_of_origin": (
        "rules of origin", "origin certificate", "原产地", "产地证",
        "origin fraud", "原产地规避", "原产地证",
    ),
    "trade_facilitation": (
        "trade facilitation", "贸易便利化", "single window", "单一窗口",
        "authorized economic operator", "aeo",
    ),
    "recall": (
        "product recall", "召回", "withdrawal", "market recall", "产品召回",
    ),
}

# ── 影响渠道（impact_channel）多语言关键词 ─────────────────────────────
IMPACT_CHANNELS: dict[str, tuple[str, ...]] = {
    "price": (
        "price surge", "price spike", "价格", "涨价", "跌价", "价差", "price differential",
    ),
    "trade_volume": (
        "trade volume", "进出口量", "出口量", "进口量", "import volume",
        "export volume", "shipment volume",
    ),
    "capacity": (
        "production capacity", "产能", "产量", "开工率", "capacity utilization", "output",
    ),
    "logistics_route": (
        "logistics", "物流", "航线", "shipping route", "freight", "运输", "航运",
    ),
    "port_operation": (
        "port congestion", "港口", "口岸", "码头", "堆场", "port operation", "vessel schedule",
    ),
    "inventory": (
        "inventory", "库存", "stockpile", "储备", "inventories",
    ),
    "supply_chain": (
        "supply chain", "供应链", "断链", "supply disruption", "supply chain risk", "供应链中断",
    ),
    "market_access": (
        "market access", "市场准入", "准入", "access to market", "market entry",
    ),
    "compliance_cost": (
        "compliance cost", "合规成本", "compliance burden", "regulatory cost", "合规",
    ),
}

# ── 政策工具 → 受控业务分类（对齐 tag_taxonomy.CONTROLLED_CATEGORIES）──
POLICY_INSTRUMENT_CATEGORY: dict[str, str] = {
    "tariff": "tariff",
    "anti_dumping": "tariff",
    "countervailing": "tariff",
    "safeguard": "tariff",
    "quota_license": "trade",
    "export_control": "security",
    "sanctions": "security",
    "import_export_ban": "security",
    "sps_tbt": "technology",
    "customs_procedure": "trade",
    "rules_of_origin": "trade",
    "trade_facilitation": "trade",
    "recall": "regulation",
}

# ── 主题语义画像（仅贸易类主题；"all" 表示用全部词表）────────────────
TOPIC_SEMANTIC_PROFILES: dict[str, dict[str, list[str]]] = {
    "item-56adc0": {  # 中国出口管制
        "policy_instruments": ["export_control", "sanctions", "import_export_ban", "quota_license"],
        "impact_channels": ["supply_chain", "market_access", "compliance_cost", "trade_volume"],
    },
    "global-trade": {  # 关税类贸易政策
        "policy_instruments": [
            "tariff", "anti_dumping", "countervailing", "safeguard",
            "rules_of_origin", "trade_facilitation",
        ],
        "impact_channels": ["price", "trade_volume", "market_access", "compliance_cost"],
    },
    "foreign-trade-forum-risk-monitoring": {  # 外贸论坛违规清关与走私
        "policy_instruments": [
            "customs_procedure", "rules_of_origin", "import_export_ban",
            "quota_license", "tariff",
        ],
        "impact_channels": ["logistics_route", "port_operation", "trade_volume"],
    },
    "weekly-enforcement-intelligence": {  # 执法信息采集
        "policy_instruments": [
            "customs_procedure", "export_control", "sanctions",
            "rules_of_origin", "import_export_ban",
        ],
        "impact_channels": ["logistics_route", "port_operation", "trade_volume"],
    },
    "tech-regulations": {  # 技术性贸易措施
        "policy_instruments": ["sps_tbt", "recall", "trade_facilitation"],
        "impact_channels": ["market_access", "compliance_cost"],
    },
    "weekly-trade-current-affairs": {  # 涉进出口时政热点（全局）
        "policy_instruments": ["all"],
        "impact_channels": ["all"],
    },
}


def _slugs_for(profile: dict[str, list[str]] | None, table: dict[str, tuple[str, ...]]) -> list[str]:
    if not profile:
        return list(table.keys())
    slugs = profile.get("policy_instruments", []) if table is POLICY_INSTRUMENTS else profile.get("impact_channels", [])
    if "all" in slugs:
        return list(table.keys())
    return [slug for slug in slugs if slug in table]


def match_semantics(text: str) -> tuple[list[str], list[str]]:
    """返回整段文本命中的 (policy_instrument slugs, impact_channel slugs)。"""
    lowered = (text or "").lower()
    instruments = [
        slug for slug, kws in POLICY_INSTRUMENTS.items()
        if any(kw in lowered for kw in kws)
    ]
    channels = [
        slug for slug, kws in IMPACT_CHANNELS.items()
        if any(kw in lowered for kw in kws)
    ]
    return instruments, channels


def match_semantics_for_topic(
    text: str,
    topic_id: str | None = None,
) -> tuple[list[str], list[str]]:
    """按主题语义画像匹配，未绑定的主题退化为全词表匹配。"""
    profile = TOPIC_SEMANTIC_PROFILES.get(topic_id) if topic_id else None
    lowered = (text or "").lower()
    instruments = [
        slug for slug in _slugs_for(profile, POLICY_INSTRUMENTS)
        if any(kw in lowered for kw in POLICY_INSTRUMENTS[slug])
    ]
    channels = [
        slug for slug in _slugs_for(profile, IMPACT_CHANNELS)
        if any(kw in lowered for kw in IMPACT_CHANNELS[slug])
    ]
    return instruments, channels


def is_semantically_relevant(text: str, topic_id: str | None = None) -> bool:
    """字面关键词未命中时的语义兜底：仅对绑定了语义画像的贸易类主题生效。

    政策工具是强信号（关税/反倾销/出口管制/海关程序/原产地…），单独命中即可放行；
    影响渠道（价格/库存/物流…）过于宽泛，不作为兜底判定依据。

    未绑定画像的主题（如关键矿产、军工采购）返回 False，不改变其原有过滤行为。
    """
    if not topic_id or topic_id not in TOPIC_SEMANTIC_PROFILES:
        return False
    instruments, _channels = match_semantics_for_topic(text, topic_id)
    return bool(instruments)


def instrument_category(instrument_slug: str) -> str | None:
    """政策工具 → 受控业务分类 slug（用于标签浓缩对齐）。"""
    return POLICY_INSTRUMENT_CATEGORY.get(instrument_slug)


def instrument_terms() -> list[str]:
    """导出全部政策工具英文 slug（供检索式生成提示词引用）。"""
    return list(POLICY_INSTRUMENTS.keys())


def channel_terms() -> list[str]:
    """导出全部影响渠道英文 slug。"""
    return list(IMPACT_CHANNELS.keys())
