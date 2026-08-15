"""Translation helpers for collected intelligence items."""
from __future__ import annotations

import json
import logging
import os
import re
import asyncio
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.connectors.base import FetchItem
from app.llm_client import (
    default_model_base_url,
    is_ollama_provider,
    ollama_api_url,
    openai_compatible_url,
)
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
    batch_size: int = 4,
) -> int:
    """Translate non-Chinese items and store translations in raw_metadata."""
    targets = [
        it for it in items
        if needs_translation(it.language, f"{it.title} {it.summary or ''} {it.content or ''}")
    ]
    translated = 0
    for offset in range(0, len(targets), batch_size):
        batch = targets[offset:offset + batch_size]
        # Clean content before translation - remove nav remnants
        records = []
        for i, it in enumerate(batch):
            clean_content = _clean_for_translation(it.content or "")
            clean_summary = _clean_for_translation(it.summary or "")
            records.append({
                "id": str(i),
                "title": it.title or "",
                "summary": clean_summary[:800],
                "content": clean_content[:2000],
            })
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

    records = []
    for item in candidates:
        clean_content = _clean_for_translation(item.content or "")
        clean_summary = _clean_for_translation(item.summary or "")
        records.append({
            "id": item.id,
            "title": item.title or "",
            "summary": clean_summary[:800],
            "content": clean_content[:2000],
        })

    if not records:
        return {"requested": limit, "translated": 0, "items": []}

    translated = 0
    errors: list[str] = []
    for offset in range(0, len(records), 4):
        batch_records = records[offset:offset + 4]
        batch_items = candidates[offset:offset + 4]
        try:
            results = await _translate_records(model, batch_records)
        except Exception as exc:
            logger.warning("Item translation batch failed, using web fallback: %s", exc)
            try:
                results = await _translate_records_with_web_fallback(batch_records)
            except Exception as fallback_exc:
                logger.warning("Item translation web fallback failed: %s", fallback_exc)
                errors.append(str(fallback_exc) or str(exc) or "translation failed")
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

        # Preserve completed batches if a later external translation request fails.
        db.commit()

    return {
        "requested": limit,
        "translated": translated,
        "items": [item.id for item in candidates[:translated]],
        "errors": errors,
    }


def _clean_for_translation(text: str) -> str:
    """Remove navigation remnants before translation."""
    if not text:
        return ""

    # Remove skip links and nav remnants
    patterns = [
        r"Skip\s+to\s+(?:main\s+)?content\s*",
        r"跳至(?:正文|主要)?内容\s*",
        r"Breadcrumb\s*",
        r"面包屑\s*",
        r"Quick\s+links\s*",
        r"快速链接\s*",
        r"Frequently\s+asked\s+questions\s*",
        r"常见问题\s*",
        r"Useful\s+links\s*",
        r"有用链接\s*",
        r"Search\s*",
        r"搜索\s*",
        r"News\s+Center\s*",
        r"新闻中心\s*",
        r"Press\s+Office\s*",
        r"媒体发布\s*",
        r"Media\s+Library\s*",
        r"多媒体图书馆\s*",
        r"Social\s+Media\s*",
        r"社交媒体\s*",
        r"Official\s+Statements\s*",
        r"官方声明\s*",
        r"Publications\s*",
        r"出版物\s*",
        r"Spotlight\s*",
        r"聚光灯\s*",
        r"Newsletter\s*",
        r"新闻通讯\s*",
        r"Announcements\s*",
        r"公告\s*",
        r"About\s+Us\s*",
        r"关于我们\s*",
        r"Contact\s+Us\s*",
        r"联系我们\s*",
        r"Site\s+Map\s*",
        r"网站地图\s*",
        r"Accessibility\s*",
        r"无障碍\s*",
        r"Privacy\s+Policy\s*",
        r"隐私政策\s*",
        r"Terms\s+of\s+Use\s*",
        r"使用条款\s*",
        r"Cookie\s+Policy\s*",
        r"Cookie\s*",
        r"Legal\s+Disclaimer\s*",
        r"法律声明\s*",
        r"Frontline\s+Digital\s+Magazine\s*",
        r"前线数字杂志\s*",
        r"Statistics\s+and\s+Summaries\s*",
        r"统计数据和摘要\s*",
        r"Accountability\s+and\s+Transparency\s*",
        r"问责制和透明度\s*",
        r"Press\s+Releases\s*",
        r"Press\s+Officer\s*",
        r"新闻官员\s*",
        r"File\s+Library\s*",
        r"文件库\s*",
    ]

    for pattern in patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    # Clean up extra whitespace
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


async def _translate_records(model: ModelConfig, records: list[dict[str, str]]) -> list[dict[str, str]]:
    if model.provider == "web_fallback":
        return await _translate_records_with_web_fallback(records)

    prompt = (
        "请把下面 JSON 数组中的英文或其他非中文信息翻译成简体中文。"
        "只返回 JSON 数组，不要添加任何解释。"
        "翻译要求："
        "1. 保留原文的段落结构"
        "2. 标题要准确反映文章主题"
        "3. 摘要要简洁概括文章核心内容（100-200字）"
        "4. 正文要完整翻译，保持段落格式"
        "5. 专有名词（如机构名、人名）保留英文并加中文注释"
        "\n\n"
        + json.dumps(records, ensure_ascii=False, indent=2)
        + "\n\n"
        "请只返回翻译后的 JSON 数组，格式为: [{\"id\":\"...\",\"title_zh\":\"...\",\"summary_zh\":\"...\",\"content_zh\":\"...\"}]"
    )

    base_url = model.base_url or default_model_base_url(model.provider)
    model_name = model.model_name or ""

    if is_ollama_provider(model.provider):
        url = ollama_api_url(base_url, "/api/chat")
        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = "Bearer " + model.api_key
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1},
        }
        # Keep local-model failures bounded so public-source translation can
        # promptly fall back instead of leaving new items without a rendition.
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            raw = msg.get("content") or msg.get("thinking") or ""
            return _parse_translation_response(raw)

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
        raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _parse_translation_response(raw)


def _parse_translation_response(text: str) -> list[dict[str, str]]:
    """Parse LLM translation response, handling various formats."""
    if not text:
        return []

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # Maybe wrapped in an object
            for key in ["translations", "results", "data"]:
                if key in result and isinstance(result[key], list):
                    return result[key]
            # Single item
            return [result]
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in text
    match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse translation response")
    return []


def _normalize_translation(row: dict[str, Any]) -> dict[str, str]:
    return {
        "title_zh": _clean(row.get("title_zh")) or _clean(row.get("title")) or "",
        "summary_zh": _clean(row.get("summary_zh")) or _clean(row.get("summary")) or "",
        "content_zh": _clean(row.get("content_zh")) or _clean(row.get("content")) or "",
        "status": "translated",
    }


async def _translate_records_with_web_fallback(records: list[dict[str, str]]) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=60, proxy=_translation_proxy()) as client:
        async def translate_record(record: dict[str, str]) -> dict[str, str]:
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
            return row

        return list(await asyncio.gather(*(translate_record(record) for record in records)))


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
