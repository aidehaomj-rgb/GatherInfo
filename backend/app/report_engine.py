"""
Report Engine — Generates comprehensive reports from collected items using an LLM.

Architecture:
    Topic → CollectedItem[] → Build prompt → LLM call → Report (persisted)

Supports:
    - Local models via Ollama API
    - OpenAI-compatible APIs
    - LM Studio local inference
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import CollectedItem, Topic, ModelConfig, Report

logger = logging.getLogger(__name__)

# Re-export LLM client functions for backward compatibility
from app.llm_client import call_llm as _call_llm, auto_summary as _auto_summary, translate_item_context as _translate_item_context  # noqa: E501


async def generate_report(
    topic_id: str,
    model_id: str | None = None,
    title_override: str | None = None,
    collection_run_id: str | None = None,
    collection_run_ids: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    model_name_override: str | None = None,
) -> Report:
    """Main entry point: generate a report for a topic using the specified model."""
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError(f"Topic not found: {topic_id}")

        model = None
        if model_id:
            model = db.query(ModelConfig).filter(
                ModelConfig.id == model_id, ModelConfig.is_active == True
            ).first()
            if not model:
                raise ValueError(f"Model not found or inactive: {model_id}")
        else:
            model = db.query(ModelConfig).filter(
                ModelConfig.is_default == True, ModelConfig.is_active == True
            ).first()
            if not model:
                raise ValueError("No default active model configured.")

        dt_from = _parse_iso(date_from)
        dt_to = _parse_iso(date_to)

        q = db.query(CollectedItem).filter(CollectedItem.topic_id == topic_id)
        if collection_run_ids:
            q = q.filter(CollectedItem.run_id.in_(collection_run_ids))
        elif collection_run_id:
            q = q.filter(CollectedItem.run_id == collection_run_id)
        if dt_from:
            q = q.filter(CollectedItem.collected_at >= dt_from)
        if dt_to:
            q = q.filter(CollectedItem.collected_at <= dt_to)
        items = q.order_by(CollectedItem.published_at.desc()).all()
        if not items:
            raise ValueError(f"No collected items found for topic '{topic.name}'")

        # Weekly intelligence reports describe publication dates, not the
        # moment the local crawler happened to persist the records.
        published_times = [it.published_at for it in items if it.published_at]
        range_start = dt_from or (min(published_times) if published_times else None)
        range_end = dt_to or (max(published_times) if published_times else None)

        item_context = _build_item_context(items)

        # Translate non-Chinese items to Chinese
        if model and item_context:
            try:
                non_zh = [
                    it for it in item_context
                    if it.get('language', '') not in ('zh', 'zh-CN', 'cn')
                ]
                if non_zh and len(non_zh) <= 50:
                    logger.info("Translating %d non-Chinese items for topic %s",
                                len(non_zh), topic_id)
                    await _translate_item_context(model, non_zh)
            except Exception as exc:
                logger.warning("Translation step failed (non-blocking): %s", exc,
                               exc_info=True)

        prompt = _build_report_prompt(topic, item_context, range_start, range_end)

        report = Report(
            id=f"rpt-{uuid4().hex[:12]}",
            topic_id=topic_id,
            title=title_override or f"{topic.name} 综合分析报告",
            status="generating",
            model_id=model.id,
            item_count=len(items),
            item_ids=[it.id for it in items],
            collection_run_id=collection_run_id,
            date_range_start=range_start,
            date_range_end=range_end,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        try:
            llm_result = await _call_llm(model, prompt)
            report.content = llm_result["content"]
            report.summary = llm_result["summary"]
            report.tokens_used = llm_result["tokens_used"]
            report.status = "completed"
        except Exception as exc:
            logger.error("LLM call failed for report %s: %s", report.id, exc)
            report.content = _build_fallback_report(
                topic, item_context, range_start, range_end, str(exc)
            )
            report.summary = "模型生成不稳定，已基于采集条目生成本地规则兜底报告。"
            report.tokens_used = 0
            report.status = "completed"
            report.error_log = f"LLM 生成失败，已使用本地规则兜底：{exc}"

        db.commit()
        db.refresh(report)

        if report.status == "completed" and (report.content or "").strip():
            try:
                _export_report_files(db, report, topic)
            except Exception as exc:
                logger.warning("Export step failed for report %s: %s", report.id, exc)

        return report
    finally:
        db.close()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        s = value.strip()
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _export_report_files(db: Session, report: Report, topic: Topic | None) -> None:
    try:
        from app.report_export import export_report
        from app.services.report_service import get_system_config

        system = get_system_config(db)
        export_report(report, system, topic)
        db.commit()
        db.refresh(report)
    except ImportError:
        logger.warning("report_export module not available, skipping export")


def _build_item_context(items: list[CollectedItem]) -> list[dict]:
    """Build structured item context dict from ORM objects for prompt building."""
    context = []
    for idx, it in enumerate(items[:50], 1):
        context.append({
            "id": it.id,
            "index": idx,
            "title": it.title or "",
            "content": (it.content or "")[:2000],
            "summary": (it.summary or "")[:500],
            "url": it.url or "",
            "language": it.language or "unknown",
            "category": it.category or "unknown",
            "source": it.source_id or "",
            "published_at": it.published_at.isoformat() if it.published_at else "",
            "tags": [{"namespace": t.namespace, "value": t.value}
                     for t in it.tags] if it.tags else [],
            "published_at": it.published_at.isoformat() if it.published_at else "",
            "quality_score": it.quality_score or 0.0,
            "relevance_score": it.relevance_score or 0.0,
        })
    return context


def _build_collection_summary_context(items: list[dict]) -> str:
    """Summarize the information set before asking the LLM to synthesize."""
    category_counts = _count_by(items, "category", "未分类")
    source_counts = _count_by(items, "source", "未知来源")
    out_of_range = [it for it in items if _has_tag_value(it, "超限采集")]
    evidence_lines = []
    for item in items[:8]:
        idx = item.get("index") or "?"
        title = item.get("title") or "无标题"
        summary = item.get("summary") or item.get("content") or ""
        evidence_lines.append(f"- [条目{idx}] {title}：{' '.join(summary.split())[:180]}")
    return "\n".join([
        "信息集合摘要",
        f"- 条目数量: {len(items)} 条",
        f"- 分类分布: {_format_counts(category_counts)}",
        f"- 来源分布: {_format_counts(source_counts)}",
        f"- 超限采集: {len(out_of_range)} 条",
        "- 关键证据:",
        *(evidence_lines or ["- 暂无可用证据"]),
    ])


def _build_report_prompt(
    topic: Topic,
    items: list[dict],
    range_start: datetime | None = None,
    range_end: datetime | None = None,
) -> str:
    """Build the LLM prompt from topic metadata and item context."""
    # Keywords with weights
    kw_info = ""
    if getattr(topic, 'keyword_tags', None):
        try:
            kw_tags = json.loads(topic.keyword_tags) if isinstance(
                topic.keyword_tags, str) else topic.keyword_tags
            if kw_tags:
                kw_lines = [f"- {t['keyword']}（权重: {t['weight']}）"
                           for t in kw_tags]
                kw_info = "关键词及权重:\n" + "\n".join(kw_lines) + "\n"
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    # Date range
    range_info = ""
    if range_start:
        start_str = range_start.strftime("%Y-%m-%d")
        end_str = range_end.strftime("%Y-%m-%d") if range_end else "(不限)"
        range_info = f"数据时间范围: {start_str} ~ {end_str}\n"

    collection_summary = _build_collection_summary_context(items)

    # Items text — use enumerate for robust indexing
    items_text_parts = []
    for idx, it in enumerate(items, 1):
        title = it.get("title", "")
        source = it.get("source", "")
        url = it.get("url", "")
        category = it.get("category", "unknown")
        summary = it.get("summary", "")
        content = it.get("content", "")
        index = it.get("index", idx)
        parts = [
            f"## 条目 {index}",
            f"- 标题: {title}",
            f"- 来源: {source}",
            f"- URL: {url}",
            f"- published_at: {it.get('published_at') or 'unverified'}",
            f"- 分类: {category}",
        ]
        if summary:
            parts.append(f"- 内容摘要: {summary}")
        if content:
            parts.append(f"\n{content[:2000]}")
        items_text_parts.append("\n".join(parts))
    items_text = "\n\n".join(items_text_parts)

    prompt = f"""你是一位专业的跨境贸易监管与风险情报分析师。
请基于以下采集数据，为用户生成一份专业的综合分析报告。

【主题信息】
主题名称: {topic.name}
主题描述: {topic.description or '(无)'}
{kw_info}
{range_info}
【采集数据】
本次用于分析的代表性信息共 {len(items)} 条；完整入库条目数以报告元数据为准。

【信息集合摘要】
{collection_summary}

【详细条目】

{items_text}

【报告要求】
先基于信息集合摘要形成判断，再用详细条目补充论据，综合写成一篇有观点、有层次、有论据的信息。
请按照以下结构生成中文报告（约 1500-3000 字）：

1. **执行摘要** — 200字以内的核心结论
2. **关键发现** — 列出最重要的 3-5 个发现
3. **数据概览** — 来源分布、分类统计、时间趋势
4. **详细分析** — 按主题或类别深入分析关键条目
5. **趋势研判** — 对重要信号的趋势判断
6. **建议行动** — 基于发现的可操作建议

格式要求：
- 使用 Markdown 格式，每个部分以 "## " 标题开头
- 引用条目时标注编号，如 [参见条目1]
- 语言：中文

请回复两份内容，以 ===SEPARATOR=== 分隔：
第一部分：报告全文
第二部分：150字以内的摘要
"""
    prompt += (
        "\n\nStrict evidence rules: use each item's published_at as the only publication date. "
        "Do not use collection timestamps as publication dates. Do not invent numbers, "
        "authorities, legal outcomes, locations, or trends not present in the supplied items. "
        "When evidence is missing, write '待核验' instead of guessing."
    )
    return prompt


def _count_by(items: list[dict], key: str, fallback: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or fallback)
        counts = {**counts, value: counts.get(value, 0) + 1}
    return counts


def _format_counts(counts: dict[str, int]) -> str:
    return "、".join(f"{key} {value} 条" for key, value in counts.items()) or "暂无"


def _has_tag_value(item: dict, value: str) -> bool:
    tags = item.get("tags") or []
    return any(tag.get("value") == value for tag in tags if isinstance(tag, dict))


def _build_fallback_report(
    topic: Topic,
    items: list[dict],
    range_start: datetime | None,
    range_end: datetime | None,
    reason: str,
) -> str:
    source_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for item in items:
        source = item.get("source") or "未知来源"
        category = item.get("category") or "未分类"
        source_counts[source] = source_counts.get(source, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1

    def fmt_counts(counts: dict[str, int]) -> str:
        return "、".join(f"{key} {value} 条" for key, value in counts.items()) or "暂无"

    start = range_start.strftime("%Y-%m-%d") if range_start else "未知"
    end = range_end.strftime("%Y-%m-%d") if range_end else "未知"
    top_items = items[:8]
    item_lines = []
    for item in top_items:
        idx = item.get("index", "?")
        title = item.get("title") or "无标题"
        source = item.get("source") or "未知来源"
        url = item.get("url") or ""
        text = item.get("summary") or item.get("content") or ""
        text = " ".join(text.split())[:220]
        item_lines.append(
            f"- [参考条目 {idx}] {title}（来源：{source}）。"
            f"{' 摘要：' + text if text else ''}"
            f"{' 链接：' + url if url else ''}"
        )

    return f"""## 执行摘要
本报告基于“{topic.name}”主题下已采集的信息生成，覆盖时间范围为 {start} 至 {end}。由于本机模型生成过程返回异常内容，系统已启用本地规则兜底生成，以便先形成可阅读、可导出的分析材料。当前样本主要来自 {fmt_counts(source_counts)}，信息集中在贸易协定、关税政策、监管措施、国际经贸合作与供应链影响等方向。

## 关键发现
- 美国贸易代表办公室等官方渠道的信息占比较高，说明当前样本更偏向官方政策口径和制度性安排。
- 条目标题和正文显示，贸易协定、互惠贸易安排、投资框架、关税及市场准入仍是全球贸易政策监测的核心线索。
- 部分网页内容包含导航、页脚或访问限制提示，后续需要进一步优化正文抽取规则，减少页面模板噪声。
- 对企业而言，政策变化可能影响关税成本、供应链布局、市场准入条件和合规审查要求。

## 数据概览
- 代表性条目数：{len(items)} 条
- 来源分布：{fmt_counts(source_counts)}
- 分类分布：{fmt_counts(category_counts)}
- 时间范围：{start} 至 {end}

## 重点条目
{chr(10).join(item_lines) if item_lines else '- 暂无可展示条目'}

## 趋势研判
从现有条目看，全球贸易政策正在从单纯降低关税，转向更综合的制度安排，包括供应链安全、产业政策、投资限制、出口管制、区域贸易协定和绿色贸易规则。美国及主要经济体会继续通过双边或区域机制强化自身贸易利益，同时在关键产业、技术产品和战略资源方面维持更高的审查强度。

## 建议行动
- 持续跟踪 USTR、WTO、各国海关及商务部门的官方发布，优先监控关税、贸易救济、出口管制和原产地规则变化。
- 对涉及美国、欧盟及主要贸易伙伴市场的产品，建立政策变更清单，评估成本、交付周期和合规风险。
- 优化采集源质量，优先使用 RSS、官方 API、站内搜索接口或结构化公告页面，减少普通网页模板噪声。
- 对重要条目进行人工复核，必要时补充原文链接、发布日期、政策生效日期和适用行业。

## 生成说明
本报告由本地规则兜底生成。触发原因：{reason}
"""
