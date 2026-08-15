"""Article-quality gate for collection candidates and historical cleanup."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.connectors.base import FetchItem
from app.llm_client import call_llm
from app.models import CollectedItem, ModelConfig
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
REVIEW_BATCH_SIZE = 3
REVIEW_SEMAPHORE = asyncio.Semaphore(2)
MIN_SOURCE_CHARS = 180
MIN_CURATED_CHARS = 100

BLOCKED_HOSTS = (
    "wgi888.com", "bet", "casino", "gambling", "博彩", "娱乐城",
)
PROMOTION_MARKERS = (
    "体育", "博彩", "赌场", "投注", "娱乐城", "招租", "u存", "u取",
    "官方投注平台", "五星大站", "四星大站", "ebpay", "side1", "side2",
    "推荐供应商", "口碑汇总", "选购指南", "哪家代理", "靠谱推荐",
    "代理公司", "物流服务商", "厂家推荐",
)
LISTING_PATHS = ("/tag/", "/tags/", "/category/", "/search", "/archive/")


@dataclass(frozen=True)
class RejectedArticle:
    item: FetchItem
    reason: str


def rule_rejection_reason(item: FetchItem) -> str | None:
    """Reject obvious non-article, promotional, and low-information pages."""
    url = (item.url or "").strip()
    host = urlparse(url).netloc.casefold()
    path = urlparse(url).path.casefold()
    text = " ".join((item.title or "", item.summary or "", item.content or ""))
    normalized = " ".join(text.casefold().split())

    if any(blocked in host for blocked in BLOCKED_HOSTS):
        return "非独立文章或低价值推广/聚合页面"
    if any(path.startswith(prefix) for prefix in LISTING_PATHS):
        return "非独立文章或低价值推广/聚合页面"
    promotion_hits = sum(marker in normalized for marker in PROMOTION_MARKERS)
    if promotion_hits >= 2 or "copyright ©" in normalized and promotion_hits:
        return "非独立文章或低价值推广/聚合页面"
    if len(_meaningful_text(text)) < MIN_SOURCE_CHARS:
        return "正文不足，无法构成可独立阅读的信息"
    if normalized.count("##") >= 4 or len(re.findall(r"(?:编辑推荐|read more|推荐阅读)", normalized)) >= 3:
        return "页面以标题列表或推荐内容为主，缺少独立正文"
    return None


async def curate_article_candidates(
    items: list[FetchItem],
    model: ModelConfig | Any | None,
    topic_context: dict[str, Any] | None = None,
) -> tuple[list[FetchItem], list[RejectedArticle]]:
    """Return only complete, independent, customs-relevant articles in Chinese."""
    candidates: list[FetchItem] = []
    rejected: list[RejectedArticle] = []
    for item in items:
        reason = rule_rejection_reason(item)
        if reason:
            rejected.append(RejectedArticle(item=item, reason=reason))
        else:
            candidates.append(item)

    if not candidates:
        return [], rejected
    if not _can_use_model(model):
        if _is_customs_hotspot_topic(topic_context):
            fallback = [_rule_curate_customs_hotspot(item) for item in candidates]
            approved = [item for item in fallback if item is not None]
            rejected.extend(
                RejectedArticle(item=item, reason="未形成可验证的海关进出口监管风险链条")
                for item, curated in zip(candidates, fallback) if curated is None
            )
            return approved, rejected
        logger.warning("No active model for article-quality review; rejecting uncurated candidates")
        rejected.extend(
            RejectedArticle(item=item, reason="未配置有效模型，无法完成信息质量整理")
            for item in candidates
        )
        return [], rejected

    approved: list[FetchItem] = []
    for offset in range(0, len(candidates), REVIEW_BATCH_SIZE):
        batch = candidates[offset:offset + REVIEW_BATCH_SIZE]
        try:
            decisions = await _review_batch(batch, model, topic_context)
        except Exception as exc:
            logger.warning("Article-quality model review failed: %s", exc)
            if _is_customs_hotspot_topic(topic_context):
                for item in batch:
                    curated = _rule_curate_customs_hotspot(item)
                    if curated:
                        approved.append(curated)
                    else:
                        rejected.append(RejectedArticle(
                            item=item, reason="模型审核不可用，且规则未确认海关监管风险链条",
                        ))
            else:
                rejected.extend(RejectedArticle(item=item, reason="大模型审核失败，未入库") for item in batch)
            continue
        for index, item in enumerate(batch):
            decision = decisions.get(index, {})
            curated = _curate_approved_item(
                item, decision, bool(topic_context), _is_customs_hotspot_topic(topic_context),
            )
            if curated:
                approved.append(curated)
            else:
                rejected.append(RejectedArticle(
                    item=item,
                    reason=_decision_rejection_reason(decision, bool(topic_context)),
                ))
    return approved, rejected


async def review_persisted_items(
    db: Session,
    model: ModelConfig | None,
    item_ids: list[str] | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Re-check historical items and delete entries that fail the same gate."""
    query = db.query(CollectedItem).order_by(CollectedItem.collected_at.desc())
    if item_ids:
        query = query.filter(CollectedItem.id.in_(item_ids))
    rows = query.limit(limit).all()
    if not rows:
        return {"reviewed": 0, "curated": 0, "deleted": 0, "retained": 0}
    if not _can_use_model(model):
        low_value_rows = [row for row in rows if rule_rejection_reason(FetchItem(
            title=row.title, content=row.content, summary=row.summary, url=row.url,
        ))]
        for row in low_value_rows:
            db.delete(row)
        db.commit()
        return {
            "reviewed": len(rows),
            "curated": 0,
            "deleted": len(low_value_rows),
            "retained": len(rows) - len(low_value_rows),
        }

    candidates = [
        FetchItem(
            title=row.title,
            content=row.content,
            summary=row.summary,
            url=row.url,
            published_at=row.published_at.isoformat() if row.published_at else None,
            language=row.language,
            category=row.category,
            quality_score=row.quality_score or 0,
            relevance_score=row.relevance_score or 0,
            entities=row.entities,
            raw_metadata={**(row.raw_metadata or {}), "_quality_item_id": row.id},
        )
        for row in rows
    ]
    approved, rejected = await curate_article_candidates(candidates, model)
    by_id = {row.id: row for row in rows}
    curated = 0
    for item in approved:
        metadata = dict(item.raw_metadata or {})
        item_id = str(metadata.pop("_quality_item_id", ""))
        row = by_id.get(item_id)
        if not row:
            continue
        row.title = item.title
        row.summary = item.summary
        row.content = item.content
        row.language = item.language
        row.quality_score = item.quality_score
        row.raw_metadata = metadata
        curated += 1

    deleted = 0
    for rejection in rejected:
        item_id = str((rejection.item.raw_metadata or {}).get("_quality_item_id", ""))
        row = by_id.get(item_id)
        if row:
            db.delete(row)
            deleted += 1
    db.commit()
    return {
        "reviewed": len(rows),
        "curated": curated,
        "deleted": deleted,
        "retained": len(rows) - deleted,
    }


def _can_use_model(model: ModelConfig | Any | None) -> bool:
    return bool(model and getattr(model, "is_active", False) and getattr(model, "model_name", ""))


async def _review_batch(
    items: list[FetchItem],
    model: ModelConfig | Any,
    topic_context: dict[str, Any] | None,
) -> dict[int, dict[str, Any]]:
    candidates = [{
        "index": index,
        "title": item.title,
        "url": item.url,
        "published_at": item.published_at,
        "content": _meaningful_text(item.content or item.summary or "")[:3500],
    } for index, item in enumerate(items)]
    topic_block = ""
    if topic_context:
        topic_block = (
            "\n本次采集主题（按语义相关而非逐字匹配）：\n"
            + json.dumps(topic_context, ensure_ascii=False)
            + "\n候选信息必须与主题方向较密切相关；同义词、近义事件、翻译词和上下位概念均可视为相关。"
        )
    prompt = """你是服务海关关员的贸易与监管情报编辑。审核下列候选信息，并且只保留一篇可独立阅读、事实完整、对海关岗位有参考价值的文章、政策原文或权威介绍。

拒绝以下内容：标签页、栏目页、搜索结果页、广告/博彩/导流页、多个标题或链接堆叠页、无法辨认原始来源的转载拼贴、正文过短、不能说明主体/行为/对象/时间或影响的片段。不得根据常识补充原文没有的事实。

对每条候选仅返回 JSON：
{"reviews":[{"index":0,"decision":"approve|reject","confidence":0-100,"independence_score":0-100,"completeness_score":0-100,"customs_value_score":0-100,"topic_relevance_score":0-100,"china_customs_score":0-100,"transmission_evidence_score":0-100,"executable_check_score":0-100,"foreign_enforcement_only":false,"china_customs_stage":"中国进境|中国出境|中外陆路边境|中国港口与舱单|保税监管|中国出口管制|中国检验检疫|跨境电商|无直接落点","transmission_chain":"境外事件→供需/价差/物流/政策变化→具体对华贸易路线或主体→中国海关监管风险","topic_relevance_reason":"中文简短理由","reason":"中文简短理由","title_zh":"精确中文标题","summary_zh":"80-160字中文摘要","content_zh":"180-700字中文整理稿","source_type":"政府公告|官方执法通报|通讯社报道|行业数据报道|研究材料|其他","facts":"仅依据原文概括的事实","customs_risk":"明确落在中国海关监管环节的风险，使用可能、或等研判措辞","data_checks":"至少包括数据表或单证、商品/国别/路线范围、异常指标和下一步核查动作","risk_level":"高|中高|中"}]}。

只有在 independence_score、completeness_score 均不低于70，且能写出不臆测的完整中文整理稿时才允许 approve。对于“涉进出口时政热点”主题另须同时满足：customs_value_score、topic_relevance_score、china_customs_score、transmission_evidence_score、executable_check_score均不低于75；china_customs_stage不能是“无直接落点”；transmission_chain必须说明风险如何落到中国进境、出境、陆路边境、港口舱单、保税、出口管制、检验检疫或跨境电商监管；data_checks必须明确数据表或单证、商品/国别/路线范围、异常指标及下一步动作。原文不必出现中国，但从境外事件到中国海关风险的传导必须有贸易方向、地理邻接、价差、现有航线、管制对象或供应依赖等客观依据。仅影响外国海关征税、外国贸易救济、外国市场准入或外国进口商合规，foreign_enforcement_only应为true并必须拒绝；不得把一般性的“可能影响中国”作为入选理由。整理稿必须区分原文事实与分析推演。只输出 JSON，不要 Markdown。

CANDIDATES:\n""" + topic_block + "\n" + json.dumps(candidates, ensure_ascii=False)
    async with REVIEW_SEMAPHORE:
        response = await asyncio.wait_for(call_llm(model, prompt), timeout=120)
    payload = _decode_json(response.get("content", ""))
    reviews = payload.get("reviews", []) if isinstance(payload, dict) else []
    return {
        review["index"]: review
        for review in reviews
        if isinstance(review, dict) and isinstance(review.get("index"), int)
    }


def _curate_approved_item(
    item: FetchItem,
    decision: dict[str, Any],
    require_topic_relevance: bool,
    require_china_customs_value: bool = False,
) -> FetchItem | None:
    if str(decision.get("decision", "")).lower() != "approve":
        return None
    if min(_score(decision, "confidence"), _score(decision, "independence_score"),
           _score(decision, "completeness_score")) < 70:
        return None
    threshold = 75 if require_china_customs_value else 60
    if _score(decision, "customs_value_score") < threshold:
        return None
    if require_topic_relevance and _score(decision, "topic_relevance_score") < threshold:
        return None
    if require_china_customs_value:
        if bool(decision.get("foreign_enforcement_only")):
            return None
        if min(
            _score(decision, "china_customs_score"),
            _score(decision, "transmission_evidence_score"),
            _score(decision, "executable_check_score"),
        ) < 75:
            return None
        if _clean_text(decision.get("china_customs_stage")) in ("", "无直接落点"):
            return None
        if len(_clean_text(decision.get("transmission_chain"))) < 20:
            return None
        if len(_clean_text(decision.get("data_checks"))) < 30:
            return None
    title = _clean_text(decision.get("title_zh"))
    summary = _clean_text(decision.get("summary_zh"))
    content = _clean_text(decision.get("content_zh"))
    if len(title) < 6 or len(summary) < 30 or len(content) < MIN_CURATED_CHARS:
        return None
    metadata = dict(item.raw_metadata or {})
    metadata["source_snapshot"] = {
        "title": (item.title or "")[:500],
        "summary": (item.summary or "")[:1200],
        "content": (item.content or "")[:4000],
        "language": item.language,
    }
    metadata["quality_review"] = {
        "decision": "approved",
        "method": "llm",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "confidence": _score(decision, "confidence"),
        "independence_score": _score(decision, "independence_score"),
        "completeness_score": _score(decision, "completeness_score"),
        "customs_value_score": _score(decision, "customs_value_score"),
        "topic_relevance_score": _score(decision, "topic_relevance_score"),
        "china_customs_score": _score(decision, "china_customs_score"),
        "transmission_evidence_score": _score(decision, "transmission_evidence_score"),
        "executable_check_score": _score(decision, "executable_check_score"),
        "topic_relevance_reason": _clean_text(decision.get("topic_relevance_reason"))[:500],
        "reason": _clean_text(decision.get("reason"))[:500],
    }
    metadata["translation_zh"] = {
        "title_zh": title,
        "summary_zh": summary,
        "content_zh": content,
        "status": "curated",
    }
    metadata["customs_hotspot_review"] = {
        "method": "llm",
        "source_type": _clean_text(decision.get("source_type"))[:100],
        "facts": _clean_text(decision.get("facts"))[:1500],
        "customs_risk": _clean_text(decision.get("customs_risk"))[:1500],
        "data_checks": _clean_text(decision.get("data_checks"))[:1500],
        "risk_level": _clean_text(decision.get("risk_level"))[:20],
        "china_customs_stage": _clean_text(decision.get("china_customs_stage"))[:100],
        "transmission_chain": _clean_text(decision.get("transmission_chain"))[:1200],
        "china_customs_score": _score(decision, "china_customs_score"),
        "transmission_evidence_score": _score(decision, "transmission_evidence_score"),
        "executable_check_score": _score(decision, "executable_check_score"),
        "foreign_enforcement_only": bool(decision.get("foreign_enforcement_only")),
        "is_inference": True,
    }
    quality_scores = [
        _score(decision, "confidence"), _score(decision, "independence_score"),
        _score(decision, "completeness_score"), _score(decision, "customs_value_score"),
    ]
    if require_topic_relevance:
        quality_scores.append(_score(decision, "topic_relevance_score"))
    quality = min(quality_scores) / 100
    return replace(
        item, title=title, summary=summary, content=content, language="zh",
        quality_score=max(float(item.quality_score or 0), quality), raw_metadata=metadata,
    )


def _decision_rejection_reason(
    decision: dict[str, Any],
    require_topic_relevance: bool,
) -> str:
    if str(decision.get("decision", "")).lower() == "approve":
        if bool(decision.get("foreign_enforcement_only")):
            return "风险主要落在外国海关或外国市场准入，缺少中国海关直接监管抓手"
        if "china_customs_score" in decision and _score(decision, "china_customs_score") < 75:
            return "未形成与中国海关法定监管环节紧密相连的风险"
        if "executable_check_score" in decision and _score(decision, "executable_check_score") < 75:
            return "下一步核查方向不够具体或不可执行"
        if require_topic_relevance and _score(decision, "topic_relevance_score") < 60:
            return "候选信息与主题语义方向关联不足"
        return "大模型未确认文章完整性或海关业务价值"
    return _clean_text(decision.get("reason")) or "大模型判定为非独立、非完整或低价值信息"


def _decode_json(value: str) -> dict[str, Any]:
    text = value.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _score(decision: dict[str, Any], key: str) -> int:
    try:
        return max(0, min(100, int(float(decision.get(key, 0)))))
    except (TypeError, ValueError):
        return 0


def _meaningful_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_customs_hotspot_topic(topic_context: dict[str, Any] | None) -> bool:
    return bool(topic_context and topic_context.get("topic_id") == "weekly-trade-current-affairs")


def _rule_curate_customs_hotspot(item: FetchItem) -> FetchItem | None:
    """Conservative fallback when the model is unavailable for this topic."""
    metadata = dict(item.raw_metadata or {})
    # Eligibility must come from the source itself. Search queries and provider
    # metadata commonly contain topic keywords and must never satisfy the gate.
    text = " ".join((item.title or "", item.summary or "", item.content or "")).casefold()
    focus_text = " ".join((item.title or "", item.summary or "")).casefold()
    shock_terms = (
        "shortage", "price surge", "price increase", "export ban", "export control",
        "sanction", "disruption", "congestion", "attack", "black market", "restriction",
        "短缺", "涨价", "价格上涨", "出口管制", "禁运", "制裁", "中断", "拥堵", "受袭", "黑市",
    )
    customs_terms = (
        "customs", "smuggl", "transship", "third countr", "origin", "tariff", "import",
        "export", "border", "misdeclar", "sanctions evasion", "vat fraud",
        "海关", "走私", "转口", "转运", "第三国", "原产地", "关税", "进口", "出口", "边境", "伪报", "骗税",
    )
    china_terms = (
        "china", "chinese", "sino-", "from china", "to china", "china-origin",
        "中国", "中国企业", "中国来源", "对华", "中俄", "中哈", "中印", "中国口岸",
    )
    china_customs_stage_terms = (
        "china border", "chinese border", "to china", "from china", "china-bound",
        "china customs", "chinese customs", "中国边境", "中国口岸", "输华", "自华",
        "对华出口", "中国进口", "中国出口", "中国海关", "保税区", "跨境电商",
    )
    foreign_only_terms = (
        "anti-dumping", "antidumping", "countervailing duty", "circumvention inquiry",
        "foreign importer", "反倾销", "反补贴", "反规避调查",
    )
    if (
        not any(term in text for term in shock_terms)
        or not any(term in text for term in customs_terms)
        or not any(term in text for term in china_terms)
        or not any(term in text for term in china_customs_stage_terms)
        or any(term in text for term in foreign_only_terms)
    ):
        return None

    risk_level = "中高" if any(term in text for term in ("smuggl", "走私", "export control", "出口管制", "sanction", "制裁")) else "中"
    risk_type = "供需或价格冲击引发的跨境异常贸易风险"
    checks = "核查相关商品近20天进出口量价、贸易国别和口岸变化，关注第三国转运、原产地异常、税号迁移及新设贸易商。"
    if any(term in focus_text for term in ("oil", "fuel", "diesel", "gasoline", "原油", "燃油", "汽油", "柴油")):
        risk_type = "能源价差可能带来的边境走私、油品伪报或转运风险"
        checks = "核查原油及成品油量价、启运国与原产国、边境车辆频次和油箱容积，并比对船舶AIS及换船记录。"
    elif any(term in focus_text for term in ("fertil", "urea", "dap", "ammonia", "化肥", "尿素", "氨")):
        risk_type = "化肥或原料缺口可能带来的第三国转口、原产地替换和品名错报风险"
        checks = "核查HS 3102至3105及氨、硫磺等原料的量价、原产地和第三国再出口，验证境外供应商实际产能。"
    elif any(term in focus_text for term in ("mineral", "rare earth", "gallium", "germanium", "antimony", "矿产", "稀土", "镓", "锗", "锑")):
        risk_type = "战略矿产管制可能带来的拆分出口、低含量申报和第三国绕道风险"
        checks = "核查矿物、化合物、合金、废料和下游组件的关联税号，穿透最终用户、许可证及第三国加工能力。"
    elif any(term in focus_text for term in ("tariff", "import price", "duty", "关税", "进口价格", "进口成本")):
        risk_type = "对华进口价格和关税变化可能带来的低报价格、税号调整或原产地规避风险"
        checks = "核查对华进口商品申报价格、完税价格、税号和原产地变化，比较同类商品市场价格及第三国转口增量。"

    host = urlparse(item.url or "").netloc.casefold()
    source_type = (
        "政府公告"
        if re.search(r"(?:^|\.)gov(?:\.|$)|(?:^|\.)gouv(?:\.|$)", host)
        else "研究材料" if "doi.org" in host
        else "新闻或行业报道"
    )
    metadata["quality_review"] = {
        "decision": "approved", "method": "customs_hotspot_rule_fallback",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "confidence": 72, "independence_score": 70, "completeness_score": 70,
        "customs_value_score": 75, "topic_relevance_score": 78,
        "china_customs_score": 78, "transmission_evidence_score": 76,
        "executable_check_score": 78,
        "reason": "同时出现供需/价格/管制冲击与跨境监管路径，保守纳入待数据验证。",
    }
    metadata["customs_hotspot_review"] = {
        "method": "rule_fallback", "source_type": source_type,
        "facts": _meaningful_text(item.summary or item.content or "")[:1500],
        "customs_risk": risk_type, "data_checks": checks,
        "risk_level": risk_level, "is_inference": True,
        "china_customs_stage": "中国进境或出境",
        "transmission_chain": _china_nexus_evidence(text),
        "china_customs_score": 78,
        "transmission_evidence_score": 76,
        "executable_check_score": 78,
        "foreign_enforcement_only": False,
    }
    return replace(
        item,
        summary=(item.summary or risk_type),
        quality_score=max(float(item.quality_score or 0), 0.72),
        relevance_score=max(float(item.relevance_score or 0), 0.78),
        raw_metadata=metadata,
    )


def _china_nexus_evidence(text: str) -> str:
    sentences = re.split(r"(?<=[。！？.!?])\s+|[\r\n]+", text)
    markers = ("china", "chinese", "中国", "对华", "中俄", "中哈", "中印")
    for sentence in sentences:
        cleaned = _clean_text(sentence)
        if cleaned and any(marker in cleaned.casefold() for marker in markers):
            return cleaned[:800]
    return "原文明确涉及中国相关主体、货物、贸易方向或跨境路线。"
