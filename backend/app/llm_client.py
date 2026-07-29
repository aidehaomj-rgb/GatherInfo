"""
LLM Client — HTTP wrappers for calling local and remote LLM APIs.

Used by both the report engine and the collection engine for
report generation and item translation.
"""
import logging
from typing import Any

import httpx

from app.models import ModelConfig

logger = logging.getLogger(__name__)

OLLAMA_CLOUD_BASE_URL = "https://ollama.com"
OLLAMA_PROVIDERS = {"ollama", "ollama_cloud"}


def openai_compatible_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    if base.endswith("/v1"):
        return f"{base}{path}"
    return f"{base}/v1{path}"


def is_ollama_provider(provider: str) -> bool:
    return provider in OLLAMA_PROVIDERS


def default_model_base_url(provider: str) -> str:
    if provider == "ollama_cloud":
        return OLLAMA_CLOUD_BASE_URL
    return "http://localhost:11434"


def ollama_api_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    return f"{base}{path}"


async def call_llm(
    model: ModelConfig,
    prompt: str,
    *,
    max_tokens_override: int | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Call the LLM and return content, summary, tokens_used."""
    base_url = model.base_url or default_model_base_url(model.provider)
    model_name = model.model_name

    if is_ollama_provider(model.provider):
        url = ollama_api_url(base_url, "/api/chat")
        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = f"Bearer {model.api_key}"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一位专业的跨境贸易与监管情报分析师。"},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": model.temperature or 0.7,
                "num_predict": max_tokens_override or model.max_tokens or 4096,
            },
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            full = msg.get("content") or msg.get("thinking") or ""

    elif model.provider in ("openai", "lmstudio", "custom", "cc_switch"):
        url = openai_compatible_url(base_url, "/chat/completions")
        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = f"Bearer {model.api_key}"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是一位专业的跨境贸易与监管情报分析师。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": model.temperature or 0.7,
            "max_tokens": max_tokens_override or model.max_tokens or 4096,
            "top_p": model.top_p or 0.9,
        }
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            full = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    else:
        raise ValueError(f"Unsupported provider: {model.provider}")

    parts = full.split("===SEPARATOR===")
    content = parts[0].strip() if parts else full
    summary = parts[1].strip() if len(parts) > 1 else auto_summary(content)

    if len(content.strip()) < 100:
        raise ValueError(f"LLM returned too little content: {content[:80]!r}")

    return {
        "content": content,
        "summary": summary,
        "tokens_used": len(full.split()),
    }


def auto_summary(text: str) -> str:
    """Fallback: first 200 chars as summary."""
    return text[:200] + ("..." if len(text) > 200 else "")


async def translate_item_context(
    model: ModelConfig, items: list[dict],
) -> None:
    """Translate non-Chinese item context dicts to Chinese using the LLM."""
    if not items:
        return

    lines = []
    for it in items:
        idx = it.get("index", it.get("id", "?"))
        lines.append(f"[ID:{idx}] TITLE: {it.get('title', '')}")
        if it.get('summary'):
            lines.append(f"SUMMARY: {it['summary'][:500]}")
        if it.get('content'):
            lines.append(f"CONTENT: {it['content'][:800]}")
        lines.append("---")

    prompt = (
        "Translate the following items into Chinese.\n"
        "Keep [ID:xxx] markers unchanged. Each item is separated by ---.\n"
        "Return the translations in the same format:\n"
        "[ID:xxx]\nTITLE: <Chinese title>\n"
        "SUMMARY: <Chinese summary>\nCONTENT: <Chinese content>\n\n"
        + "\n".join(lines)
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
            "options": {"temperature": 0.2, "num_predict": 4096},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("message", {})
            output = msg.get("content") or msg.get("thinking") or ""
    else:
        url = openai_compatible_url(base_url, "/chat/completions")
        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = "Bearer " + model.api_key
        payload = {
            "model": model_name, "temperature": 0.2, "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            output = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    if not output:
        logger.warning("Translation returned empty output")
        return

    blocks = output.split("---")
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        id_line = block.split("\n")[0].strip() if block else ""
        item_id = ""
        if id_line.startswith("[ID:") and "]" in id_line:
            item_id = id_line.split("[ID:")[1].split("]")[0].strip()

        target = None
        for it in items:
            if str(it.get("index", it.get("id", ""))) == item_id:
                target = it
                break

        if not target:
            continue

        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("TITLE:") and len(line) > 7:
                target["title"] = line[6:].strip()
            elif line.startswith("SUMMARY:") and len(line) > 9:
                target["summary"] = line[8:].strip()
            elif line.startswith("CONTENT:") and len(line) > 9:
                target["content"] = line[8:].strip()

    logger.info("Translated %d items from %s to Chinese", len(items),
                "en" if items else "?")
