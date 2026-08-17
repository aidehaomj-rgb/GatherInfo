"""受控多维标签体系（tag taxonomy v2）。

把标签从「扁平 category 一维」升级为「多维度受控分类」，每个维度是一组互斥的受控
取值，采集入库时按语义自动打上各维度的标签，用户在「标签系统」页面按维度分行展示、
点击标签实现组合筛选（AND）。

维度设计（依据项目主题现状与 InfoRoute 三轴分类）：
- ``policy``      政策工具（关税/反倾销/出口管制/海关程序…）—— 来自 trade_semantics
- ``impact``      影响渠道（价格/贸易量/供应链/物流…）
- ``category``    业务主题（保留原受控 10 类，向后兼容）
- ``region``      涉华关联/区域（中国/美国/欧盟/东盟/全球…）
- ``evidence``    证据强度（可追溯单证/官方公告/新闻报道）

各维度标签在打标签阶段由 :func:`classify_item_dimensions` 一次性计算，收敛到受控取值，
避免 LLM 自由生成导致的标签爆炸。
"""
from __future__ import annotations

from app.trade_semantics import (
    IMPACT_CHANNELS,
    POLICY_INSTRUMENTS,
    POLICY_INSTRUMENT_CATEGORY,
)

# ── 维度定义：维度 slug → (中文名, 有序受控取值 slug → 中文标签) ─────────
# 取值顺序即「标签系统」页面每行的展示顺序（按重要性/使用频率）。
# 浓缩原则：语义相近的低频标签合并为更高层级标签，总量控制在 30 个以内。
TAXONOMY_DIMENSIONS: dict[str, tuple[str, dict[str, str]]] = {
    "policy": (
        "政策工具",
        {
            "tariff": "关税",
            "trade_remedy": "贸易救济",   # 反倾销 + 反补贴 + 保障措施
            "export_control": "出口管制",
            "sanctions_ban": "制裁与禁限",  # 制裁 + 进出口禁限
            "sps_tbt": "技术性壁垒",
            "customs_procedure": "海关程序",  # 含配额许可证 + 原产地 + 贸易便利化
            "recall": "产品召回",
        },
    ),
    "impact": (
        "影响渠道",
        {
            "price": "价格",
            "supply_chain": "供应链",
            "logistics_port": "物流港航",  # 物流航线 + 港口运营
            "supply_demand": "供需动态",   # 产能 + 库存 + 贸易量
            "market_access": "市场准入",
            "compliance_cost": "合规成本",
        },
    ),
    "category": (
        "业务主题",
        {
            "tariff": "关税税则",
            "trade": "贸易政策",
            "enforcement": "执法与缉私",
            "security": "出口管制",
            "technology": "技术性贸易措施",
            "regulation": "法规与合规",
            "market": "市场与商品",
            "defense_procurement": "军工采购",
        },
    ),
    "region": (
        "涉华与区域",
        {
            "china": "中国",
            "usa": "美国",
            "eu": "欧盟",
            "asean": "东盟",
            "global": "全球",
        },
    ),
    "evidence": (
        "证据强度",
        {
            "official": "官方公告",
            "traceable": "可追溯单证",
            "news": "新闻报道",
        },
    ),
}

# 维度展示顺序（「标签系统」页面从上到下分行展示）
DIMENSION_ORDER: list[str] = ["policy", "impact", "category", "region", "evidence"]


def dimension_label(dim: str) -> str:
    return TAXONOMY_DIMENSIONS[dim][0]


def dimension_values(dim: str) -> dict[str, str]:
    return TAXONOMY_DIMENSIONS[dim][1]


def tag_id_for(dim: str, value: str) -> str:
    """维度标签的统一 tag id 格式：``<dim>:<value>``。"""
    return f"{dim}:{value}"


def all_tag_ids() -> list[tuple[str, str, str]]:
    """返回 (dimension, value_slug, label) 的全部受控标签。"""
    result: list[tuple[str, str, str]] = []
    for dim in DIMENSION_ORDER:
        for value, label in TAXONOMY_DIMENSIONS[dim][1].items():
            result.append((dim, value, label))
    return result


# ── 语义打标签 ──────────────────────────────────────────────────────────

def classify_item_dimensions(
    title: str,
    content: str,
    category: str | None,
    china_relevance: str | None = None,
) -> dict[str, list[str]]:
    """对一条采集条目做多维分类，返回 {维度: [受控取值, ...]}。

    - ``policy`` / ``impact`` 用受控词表对标题+正文做多语言子串匹配；
    - ``category`` 沿用原 normalize_category 语义（业务主题维度）；
    - ``region`` 依据 china_relevance 及正文区域词表；
    - ``evidence`` 依据正文是否含单证/企业/公告等证据信号。
    """
    text = f"{title or ''} {content or ''}".lower()

    # policy / impact 命中（细粒度 slug，随后合并到浓缩标签）
    policy_hits = [
        slug for slug, kws in POLICY_INSTRUMENTS.items()
        if any(kw in text for kw in kws)
    ]
    impact_hits = [
        slug for slug, kws in IMPACT_CHANNELS.items()
        if any(kw in text for kw in kws)
    ]

    policies = _compact_policies(policy_hits)
    impacts = _compact_impacts(impact_hits)

    # category 维度：优先归一化已有 category，否则用政策工具映射兜底
    categories: list[str] = []
    if category:
        cat = normalize_category(category)
        if cat:
            categories.append(cat)
    if not categories:
        # 用政策工具命中映射到业务主题维度（先映射到细粒度，再浓缩）
        for slug in policy_hits:
            mapped = POLICY_INSTRUMENT_CATEGORY.get(slug)
            if mapped and mapped not in categories:
                categories.append(mapped)
    if not categories:
        categories.append("trade")

    # region 维度（浓缩后）
    regions = _classify_region(text, china_relevance)

    # evidence 维度
    evidence = _classify_evidence(text)

    return {
        "policy": policies,
        "impact": impacts,
        "category": categories,
        "region": regions,
        "evidence": evidence,
    }


# ── 细粒度 → 浓缩标签合并映射 ───────────────────────────────────────────

_POLICY_COMPACT: dict[str, str] = {
    "anti_dumping": "trade_remedy",
    "countervailing": "trade_remedy",
    "safeguard": "trade_remedy",
    "sanctions": "sanctions_ban",
    "import_export_ban": "sanctions_ban",
    "quota_license": "customs_procedure",
    "rules_of_origin": "customs_procedure",
    "trade_facilitation": "customs_procedure",
    # 以下 slug 名称与浓缩后一致，直接保留
    "tariff": "tariff",
    "export_control": "export_control",
    "sps_tbt": "sps_tbt",
    "customs_procedure": "customs_procedure",
    "recall": "recall",
}

_IMPACT_COMPACT: dict[str, str] = {
    "logistics_route": "logistics_port",
    "port_operation": "logistics_port",
    "capacity": "supply_demand",
    "inventory": "supply_demand",
    "trade_volume": "supply_demand",
    "price": "price",
    "supply_chain": "supply_chain",
    "market_access": "market_access",
    "compliance_cost": "compliance_cost",
}


def _compact_policies(hits: list[str]) -> list[str]:
    result: list[str] = []
    for slug in hits:
        mapped = _POLICY_COMPACT.get(slug, slug)
        if mapped not in result:
            result.append(mapped)
    return result


def _compact_impacts(hits: list[str]) -> list[str]:
    result: list[str] = []
    for slug in hits:
        mapped = _IMPACT_COMPACT.get(slug, slug)
        if mapped not in result:
            result.append(mapped)
    return result


_REGION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "china": ("中国", "china", "chinese", "中方", "北京"),
    "usa": ("美国", "united states", "u.s.", "usa", "华盛顿", "washington"),
    "eu": ("欧盟", "european union", "eu ", "布鲁塞尔", "brussels", "欧洲委员会"),
    "asean": ("东盟", "asean", "东南亚", "越南", "泰国", "印尼", "菲律宾", "马来西亚", "新加坡"),
    "global": ("全球", "global", "worldwide", "国际"),
}


def _classify_region(text: str, china_relevance: str | None) -> list[str]:
    # 涉华关联并入「中国」区域标签（浓缩后去掉强弱关联细分）
    regions: list[str] = []
    if china_relevance in ("强涉华关联", "strong", "弱涉华关联", "weak"):
        if "china" not in regions:
            regions.append("china")
    for slug, kws in _REGION_KEYWORDS.items():
        if any(kw in text for kw in kws) and slug not in regions:
            regions.append(slug)
    return regions


_EVIDENCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "official": ("official", "公告", "通知", "令", "announcement", "gazette", "法规", "规定"),
    "traceable": ("企业", "公司", "海关编码", "hs code", "运单", "提单", "发票", "单证", "container", "集装箱"),
    "news": ("新闻", "报道", "news", "report", "消息"),
}


def _classify_evidence(text: str) -> list[str]:
    return [
        slug for slug, kws in _EVIDENCE_KEYWORDS.items()
        if any(kw in text for kw in kws)
    ]


# ── 向后兼容：原单维 category 归一化 ─────────────────────────────────────

# 受控业务分类：value 使用稳定的英文 slug，label 为中文显示名。
CONTROLLED_CATEGORIES: dict[str, str] = TAXONOMY_DIMENSIONS["category"][1]

CATEGORY_LABEL: dict[str, str] = CONTROLLED_CATEGORIES

# 归一化关键词映射：value → 命中的受控分类 slug。
# 顺序即优先级；关键词按“长词在前”排序以降低误匹配。
_NORMALIZE_RULES: list[tuple[str, tuple[str, ...]]] = [
    (
        "defense_procurement",
        ("军工", "国防", "无人机", "无人系统", "军用电池", "军用"),
    ),
    (
        "security",
        (
            "出口管制", "两用物项", "实体清单", "最终用户", "制裁",
            "供应链穿透", "受限最终用户", "转运规避", "来源国管制", "管制",
        ),
    ),
    (
        "tariff",
        ("关税", "税则", "税号", "逃税", "骗税", "低报", "申报与归类", "归类"),
    ),
    (
        "market",
        (
            "关键矿产", "稀土", "矿产", "贵金属", "黄金", "化肥", "粮食",
            "农产品", "濒危物种", "烟草", "商品", "能源", "原油", "燃油",
            "燃料", "油气", "成品油",
        ),
    ),
    (
        "regulation",
        ("强迫劳动", "知识产权", "产品安全", "合规", "规则"),
    ),
    (
        "enforcement",
        (
            "走私", "查获", "缉私", "毒品", "边境", "瞒报", "申报不实",
            "欺诈", "诈骗", "非法", "执法", "洗钱", "监管风险", "核查",
            "现金申报", "税收走私", "商业瞒报", "口岸", "五金", "药品",
        ),
    ),
    (
        "trade",
        (
            "贸易", "原产地", "供应链", "转运", "转口", "救济", "时政",
            "第三国", "航运", "船舶", "保税", "配额", "许可证", "转口监管",
        ),
    ),
]


def normalize_category(value: str | None) -> str:
    """把任意业务分类文本归一化到受控分类 slug。

    - 空值/空白 → 空字符串（表示无需 category 标签）；
    - 已命中受控英文值 → 原样返回；
    - 中文细分分类 → 按关键词规则映射到受控分类；
    - 无法识别 → ``"trade"``。
    """
    if not value:
        return ""
    v = str(value).strip()
    if not v:
        return ""
    lowered = v.lower()
    for slug in CONTROLLED_CATEGORIES:
        if lowered == slug:
            return slug
    # 英文政策工具值对齐（InfoRoute policy_instrument → 受控分类）：
    policy_slug = lowered.replace(" ", "_").replace("-", "_")
    if policy_slug in POLICY_INSTRUMENT_CATEGORY:
        mapped = POLICY_INSTRUMENT_CATEGORY[policy_slug]
        return mapped if mapped in CONTROLLED_CATEGORIES else "trade"
    for slug, keywords in _NORMALIZE_RULES:
        if any(kw in v for kw in keywords):
            return slug
    return "trade"
