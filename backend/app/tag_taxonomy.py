"""受控标签分类体系（tag taxonomy）。

采集条目经 AI 分析后，其业务分类（category）与自动打标签必须收敛到本模块定义的
受控分类集合，避免 LLM 自由生成业务分类导致标签爆炸。

设计目标：
- 所有 ``category:*`` 标签收敛到 :data:`CONTROLLED_CATEGORIES` 之一；
- 提供 :func:`normalize_category` 把任意文本（英文受控值、中文细分分类、空值）归一化；
- 供采集引擎（engine.py）、AI 审核（content_quality.py）与数据迁移脚本复用。
"""
from __future__ import annotations

# 受控业务分类：value 使用稳定的英文 slug，label 为中文显示名。
CONTROLLED_CATEGORIES: dict[str, str] = {
    "trade": "贸易政策",
    "tariff": "关税税则",
    "regulation": "法规与合规",
    "technology": "技术性贸易措施",
    "security": "出口管制",
    "enforcement": "执法与缉私",
    "market": "市场与商品",
    "energy": "能源",
    "defense_procurement": "军工采购",
    "general": "综合",
}

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
        "energy",
        ("能源", "原油", "燃油", "燃料", "油气", "成品油"),
    ),
    (
        "market",
        (
            "关键矿产", "稀土", "矿产", "贵金属", "黄金", "化肥", "粮食",
            "农产品", "濒危物种", "烟草", "商品",
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
    - 无法识别 → ``"general"``。
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
    for slug, keywords in _NORMALIZE_RULES:
        if any(kw in v for kw in keywords):
            return slug
    return "general"
