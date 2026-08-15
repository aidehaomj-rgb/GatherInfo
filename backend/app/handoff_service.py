"""Structured handoff contracts for downstream research and translation systems."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.models import CollectedItem, Report, Topic

YMG_BASE_URL = os.getenv("YMG_DEEP_BASE_URL", "http://127.0.0.1:8401").rstrip("/")
HAISEE_BASE_URL = os.getenv("HAISEE_BASE_URL", "http://127.0.0.1:8400").rstrip("/")
HAISEE_WEB_URL = os.getenv("HAISEE_WEB_URL", "http://127.0.0.1:5400").rstrip("/")
HANDOFF_TIMEOUT_SECONDS = 45
MAX_MATERIAL_ITEMS = 80
MAX_ITEM_CONTENT_CHARS = 8_000
MAX_HAISEE_CONTENT_CHARS = 180_000
HAISEE_BATCH_SIZE = 50


def build_material_bundle(
    items: list[CollectedItem | Any],
    topic: Topic | Any | None = None,
    report: Report | Any | None = None,
) -> dict[str, Any]:
    """Build a bounded, source-linked material set for the next analysis stage."""
    return {
        "format": "risk-intelligence-material-set/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "producer": "GatherInfo",
        "purpose": "deep_research_and_customs_translation_analysis",
        "topic": _topic_record(topic),
        "report": _report_record(report),
        "items": [_material_record(item) for item in items[:MAX_MATERIAL_ITEMS]],
        "evidence_rules": [
            "采集条目及原文链接属于证据材料，报告属于阶段性分析材料。",
            "下游分析应区分来源事实、分析推断和待核验缺口。",
            "不得把模型生成内容当作已由外部来源证实的事实。",
        ],
    }


async def start_ymg_research(
    analysis_topic: str,
    materials: dict[str, Any],
    extra_requirements: str | None = None,
    depth: str = "standard",
    mode: str = "swarm",
) -> dict[str, Any]:
    requirements = _ymg_requirements(materials, extra_requirements)
    payload = {
        "topic": analysis_topic,
        "requirements": requirements,
        "materials": materials,
        "depth": depth if depth in {"standard", "deep"} else "standard",
        "mode": mode if mode in {"swarm", "solo"} else "swarm",
    }
    return await _post_json(f"{YMG_BASE_URL}/api/research", payload)


async def push_items_to_haisee(
    items: list[CollectedItem | Any],
) -> dict[str, Any]:
    if not items:
        raise ValueError("至少选择一条信息")
    tasks = [_haisee_task(item) for item in items]
    if len(tasks) == 1:
        result = await _haisee_request("/api/v1/tasks", tasks[0])
        return {
            "batch_id": None,
            "task_ids": [result["id"]],
            "status": str(result.get("status") or "queued"),
            "web_url": HAISEE_WEB_URL,
        }
    chunks = [
        tasks[index:index + HAISEE_BATCH_SIZE]
        for index in range(0, len(tasks), HAISEE_BATCH_SIZE)
    ]
    results = [
        await _haisee_request("/api/v1/tasks/batch", {"tasks": chunk})
        for chunk in chunks
    ]
    batch_ids = [
        str(result["batch_id"])
        for result in results
        if result.get("batch_id")
    ]
    task_ids = [
        str(task_id)
        for result in results
        for task_id in (result.get("task_ids") or [])
    ]
    return {
        "batch_id": batch_ids[0] if batch_ids else None,
        "batch_ids": batch_ids,
        "task_ids": task_ids,
        "status": "queued",
        "web_url": HAISEE_WEB_URL,
    }


async def check_service_health(base_url: str, path: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base_url}{path}")
        return {
            "reachable": response.status_code == 200,
            "base_url": base_url,
            "message": "服务在线" if response.status_code == 200 else f"状态码 {response.status_code}",
        }
    except Exception as exc:
        return {"reachable": False, "base_url": base_url, "message": f"服务未启动: {exc}"}


def _material_record(
    item: CollectedItem | Any,
    max_content_chars: int = MAX_ITEM_CONTENT_CHARS,
) -> dict[str, Any]:
    metadata = item.raw_metadata if isinstance(getattr(item, "raw_metadata", None), dict) else {}
    translation = metadata.get("translation_zh") if isinstance(metadata.get("translation_zh"), dict) else {}
    return {
        "id": str(item.id),
        "title": str(translation.get("title_zh") or item.title or "")[:500],
        "summary": str(translation.get("summary_zh") or item.summary or "")[:2_000],
        "content": str(translation.get("content_zh") or item.content or "")[:max_content_chars],
        "source_url": item.url,
        "source_id": item.source_id,
        "topic_id": item.topic_id,
        "published_at": _iso(getattr(item, "published_at", None)),
        "language": item.language,
        "quality_score": float(item.quality_score or 0),
        "relevance_score": float(item.relevance_score or 0),
        "quality_review": metadata.get("quality_review"),
    }


def _topic_record(topic: Topic | Any | None) -> dict[str, Any] | None:
    if topic is None:
        return None
    return {
        "id": str(topic.id),
        "name": str(topic.name),
        "description": str(topic.description or ""),
        "keywords": list(topic.keywords or []),
    }


def _report_record(report: Report | Any | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "id": str(report.id),
        "title": str(report.title),
        "summary": str(report.summary or "")[:4_000],
        "content": str(report.content or "")[:20_000],
    }


def _haisee_task(item: CollectedItem | Any) -> dict[str, Any]:
    material = _material_record(item, MAX_HAISEE_CONTENT_CHARS)
    content = "\n\n".join([
        f"标题：{material['title']}",
        f"发布时间：{material['published_at'] or '待核验'}",
        f"来源：{material['source_id']}",
        material["content"] or material["summary"],
        f"原文链接：{material['source_url'] or '无'}",
    ])
    return {
        "source_type": "article",
        "content": content,
        "perspective": "customs_enforcement",
        "meta": {
            "producer": "GatherInfo",
            "gatherinfo_item_id": material["id"],
            "topic_id": material["topic_id"],
            "source_id": material["source_id"],
            "source_url": material["source_url"],
            "published_at": material["published_at"],
        },
    }


def _ymg_requirements(materials: dict[str, Any], extra: str | None) -> str:
    compact = {
        "format": materials.get("format"),
        "topic": materials.get("topic"),
        "report": materials.get("report"),
        "items": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "summary": item.get("summary"),
                "content": str(item.get("content") or "")[:2_000],
                "source_url": item.get("source_url"),
                "published_at": item.get("published_at"),
            }
            for item in materials.get("items", [])[:40]
        ],
    }
    sections = [
        "以下为 GatherInfo 生成的本地情报素材集。请把条目作为下一阶段研究素材，"
        "把阶段性报告作为分析线索，并对关键结论继续检索、交叉验证和溯源：",
        json.dumps(compact, ensure_ascii=False),
        (
            "海关风险分析要求：区分来源事实、分析推断与待核验缺口；识别申报掩体货物、"
            "实际风险货物、数量级、运输方式、港口路线、集装箱号及企业关系；从企业、"
            "商品、港口、路线和共船箱号等多个角度分别构建可核验假设，不要把全部条件"
            "机械地用 AND 合并；重点研判与中国企业及中国海关监管的潜在关联。"
        ),
    ]
    if extra:
        sections.extend(["附加要求：", extra.strip()])
    return "\n\n".join(sections)


async def _haisee_request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = os.getenv("HAISEE_API_KEY", "").strip() or await _haisee_development_token()
    if not token:
        raise RuntimeError("HaiSee 未配置接口凭证，请设置 HAISEE_API_KEY")
    return await _post_json(
        f"{HAISEE_BASE_URL}{path}",
        payload,
        headers={"Authorization": f"Bearer {token}"},
    )


async def _haisee_development_token() -> str:
    username = os.getenv("HAISEE_USERNAME", "rfg")
    password = os.getenv("HAISEE_PASSWORD", "")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{HAISEE_BASE_URL}/api/v1/auth/token",
                data={"username": username, "password": password},
            )
        if response.status_code != 200:
            return ""
        return str(response.json().get("access_token") or "")
    except Exception:
        return ""


async def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=HANDOFF_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=payload, headers=headers)
    if response.status_code not in {200, 201, 202}:
        detail = response.text[:500]
        raise RuntimeError(f"下游服务返回 {response.status_code}: {detail}")
    return response.json()


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)
