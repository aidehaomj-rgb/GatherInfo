"""Translation helpers for collected intelligence items."""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.connectors.base import FetchItem
from app.llm_client import openai_compatible_url
from app.models import CollectedItem, ModelConfig

logger = logging.getLogger(__name__)

ZH_LANGS = {"zh", "zh-cn", "cn", "zh-hans", "zh-hant"}


def needs_translation(language: str | None, text: str | None = None) -> bool:
    lang = (language or "").strip().lower()
    if lang in ZH_LANGS:
        return False
    if text and _mostly_chinese(text):
        return False
    return True


def translation_payload(metadata: dict | None) -> dict[str, str] | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get("translation_zh")
    return value if isinstance(value, dict) else None


def item_translation_fields(item: CollectedItem) -> dict[str, str | None]:
    trans = translation_payload(item.raw_metadata)
    return {
        "title_zh": _clean(trans.get("title_zh") if trans else None),
        "summary_zh": _clean(trans.get("summary_zh") if trans else None),
        "content_zh": _clean(trans.get("content_zh") if trans else None),
        "translation_status": _clean(trans.get("status") if trans else None),
    }


async def translate_fetch_items_to_metadata(
    items: list[FetchItem],
    model: ModelConfig,
    batch_size: int = 8,
) -> int:
    targets = [
        it for it in items
        if needs_translation(it.language, f"{it.title} {it.summary or ''} {it.content or ''}")
    ]
    translated = 0
    for offset in range(0, len(targets), batch_size):
        batch = targets[offset:offset + batch_size]
        records = [
            {
                "id": str(i),
                "title": it.title or "",
                "summary": it.summary or "",
                "content": (it.content or "")[:1200],
            }
            for i, it in enumerate(batch)
        ]
        results = await _translate_records(model, records)
        by_id = {str(row.get("id")): row for row in results}
        for i, it in enumerate(batch):
            row = by_id.get(str(i))
            if not row:
                continue
            metadata = dict(it.raw_metadata or {})
            metadata["translation_zh"] = _normalize_translation(row)
            metadata["original_language"] = it.language
            it.raw_metadata = metadata
            translated += 1
    return translated


async def translate_existing_items(
    db: Session,
    model: ModelConfig,
    limit: int = 20,
    item_ids: list[str] | None = None,
) -> dict[str, Any]:
    query = db.query(CollectedItem)
    if item_ids:
        query = query.filter(CollectedItem.id.in_(item_ids))
    else:
        query = query.order_by(CollectedItem.collected_at.desc())

    candidates: list[CollectedItem] = []
    for item in query.limit(max(limit * 3, limit)).all():
        if len(candidates) >= limit:
            break
        if translation_payload(item.raw_metadata):
            continue
        if needs_translation(item.language, f"{item.title} {item.summary or ''} {item.content or ''}"):
            candidates.append(item)

    records = [
        {
            "id": item.id,
            "title": item.title or "",
            "summary": item.summary or "",
            "content": (item.content or "")[:1200],
        }
        for item in candidates
    ]
    if not records:
        return {"requested": limit, "translated": 0, "items": []}

    translated = 0
    errors: list[str] = []
    for offset in range(0, len(records), 8):
        batch_records = records[offset:offset + 8]
        batch_items = candidates[offset:offset + 8]
        try:
            results = await _translate_records(model, batch_records)
        except Exception as exc:
            logger.warning("Item translation batch failed: %s", exc)
            errors.append(str(exc))
            continue

        by_id = {str(row.get("id")): row for row in results}
        for item in batch_items:
            row = by_id.get(item.id)
            if not row:
                continue
            metadata = dict(item.raw_metadata or {})
            metadata["translation_zh"] = _normalize_translation(row)
            metadata["original_language"] = item.language
            item.raw_metadata = metadata
            translated += 1

    db.commit()
    return {
        "requested": limit,
        "translated": translated,
        "items": [item.id for item in candidates[:translated]],
        "errors": errors,
    }


async def _translate_records(model: ModelConfig, records: list[dict[str, str]]) -> list[dict[str, str]]:
    if model.provider == "web_fallback":
        return await _translate_records_with_web_fallback(records)

    prompt = (
        "请把下面 JSON 数组中的英文或其他非中文信息翻译成简体中文。"
        "只返回 JSON 数组，不要解释，不要 Markdown。"
        "每个对象必须保留 id，并返回 title_zh、summary_zh、content_zh。"
        "如果原字段为空，对应译文字段也返回空字符串。\n\n"
        f"{json.dumps(records, ensure_ascii=False)}"
    )
    try:
        output = await _call_translation_model(model, prompt)
        parsed = _parse_json_array(output)
        if not isinstance(parsed, list):
            raise ValueError("Translation model did not return a JSON array")
        rows = [row for row in parsed if isinstance(row, dict)]
        if rows:
            return rows
    except Exception as exc:
        logger.warning("Model translation failed, using web fallback: %s", exc)
    return await _translate_records_with_web_fallback(records)


async def _call_translation_model(model: ModelConfig, prompt: str) -> str:
    base_url = model.base_url or "http://localhost:11434"
    model_name = model.model_name or ""

    if model.provider == "ollama":
        url = base_url.rstrip("/") + "/api/chat"
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1, "num_predict": 4096},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            return msg.get("content") or msg.get("thinking") or ""

    url = openai_compatible_url(base_url, "/chat/completions")
    headers = {"Content-Type": "application/json"}
    if model.api_key:
        headers["Authorization"] = "Bearer " + model.api_key
    payload = {
        "model": model_name,
        "temperature": 0.1,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def _parse_json_array(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            return json.loads(match.group(0))
        raise


def _normalize_translation(row: dict[str, Any]) -> dict[str, str]:
    return {
        "title_zh": _clean(row.get("title_zh")) or _clean(row.get("title")) or "",
        "summary_zh": _clean(row.get("summary_zh")) or _clean(row.get("summary")) or "",
        "content_zh": _clean(row.get("content_zh")) or _clean(row.get("content")) or "",
        "status": "translated",
    }


async def _translate_records_with_web_fallback(records: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=60, proxy=_translation_proxy()) as client:
        for record in records:
            row = {
                "id": str(record.get("id", "")),
                "title_zh": "",
                "summary_zh": "",
                "content_zh": "",
            }
            for source_key, target_key in (
                ("title", "title_zh"),
                ("summary", "summary_zh"),
                ("content", "content_zh"),
            ):
                try:
                    row[target_key] = await _translate_text_with_google(
                        client,
                        record.get(source_key, ""),
                    )
                except Exception as exc:
                    logger.warning(
                        "Web translation failed for %s/%s: %r",
                        row["id"],
                        source_key,
                        exc,
                    )
            rows.append(row)
    return rows


def _translation_proxy() -> str | None:
    """Reuse the local proxy for HTTPS translation calls when only HTTP_PROXY is set."""
    return (
        os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
        or os.getenv("ALL_PROXY")
        or os.getenv("all_proxy")
        or os.getenv("HTTP_PROXY")
        or os.getenv("http_proxy")
    )


async def _translate_text_with_google(client: httpx.AsyncClient, text: str | None) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    chunks = _split_text(value, 1400)
    translated: list[str] = []
    for chunk in chunks:
        resp = await client.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": chunk},
        )
        resp.raise_for_status()
        data = resp.json()
        translated.append("".join(part[0] for part in (data[0] or []) if part and part[0]))
    return "\n".join(part for part in translated if part).strip()


def _split_text(text: str, max_len: int) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    current = ""
    for piece in re.split(r"(\n+|(?<=[.!?。！？])\s+)", text):
        if not piece:
            continue
        if len(current) + len(piece) <= max_len:
            current += piece
            continue
        if current.strip():
            chunks.append(current.strip())
        current = piece
        while len(current) > max_len:
            chunks.append(current[:max_len].strip())
            current = current[max_len:]
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def _mostly_chinese(text: str) -> bool:
    letters = re.findall(r"[A-Za-z]", text)
    cjk = re.findall(r"[\u3400-\u9fff]", text)
    if not cjk:
        return False
    if not letters:
        return True
    return len(cjk) >= len(letters) * 0.8
