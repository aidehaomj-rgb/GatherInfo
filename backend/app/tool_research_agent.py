"""Bounded model-directed research loop over public evidence tools."""
from __future__ import annotations

import json
import re
from typing import Any

from app.llm_client import call_llm
from app.models import ModelConfig
from app.research_document_reader import read_document
from app.connectors.tavily_search import TavilyCollector


async def run_tool_research(objective: str, model: ModelConfig, *, search_config=None, max_steps: int = 6) -> dict[str, Any]:
    observations: list[dict] = []
    for step in range(1, max_steps + 1):
        result = await call_llm(model, _prompt(objective, observations, step, max_steps), max_tokens_override=1200, timeout_seconds=90, minimum_content_length=10)
        decision = _parse_json(result.get("content", ""))
        action = decision.get("action")
        if not action and step == 1:
            decision = {"action": "search_web", "query": objective}
            action = "search_web"
        elif not action:
            attempted = {obs.get("url") for obs in observations if obs.get("url")}
            candidates = [row.get("url") for obs in reversed(observations) for row in (obs.get("results") or []) if row.get("url") and row.get("url") not in attempted]
            if candidates:
                decision = {"action": "open_url", "url": candidates[0], "render": False}
                action = "open_url"
        if action == "finish":
            return {"status": "completed", "steps": step, "answer": decision.get("answer", ""), "evidence": observations}
        if action == "search_web":
            query = str(decision.get("query") or "").strip()
            if not query or search_config is None:
                observations.append({"step": step, "error": "web search unavailable"})
                continue
            response = await TavilyCollector(search_config).fetch([query], max_items=8)
            rows = [{"title": item.title, "url": item.url, "summary": item.summary} for item in response.items if "customs.gov.cn" not in str(item.url or "").casefold()]
            observations.append({"step": step, "action": action, "query": query, "results": rows})
            continue
        if action in {"open_url", "follow_links"}:
            url = str(decision.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                observations.append({"step": step, "error": "invalid URL"})
                continue
            document = await read_document(url, render=bool(decision.get("render")), follow_links=2 if action == "follow_links" else 0)
            document["text"] = str(document.get("text") or "")[:12000]
            observations.append({"step": step, "action": action, **document})
            continue
        observations.append({"step": step, "error": f"unsupported action: {action}"})
    return {"status": "step_limit", "steps": max_steps, "answer": "", "evidence": observations}


def _prompt(objective: str, observations: list[dict], step: int, maximum: int) -> str:
    return f"""You are operating a bounded public-source research agent ({step}/{maximum}).
Objective: {objective}
Evidence observed so far: {json.dumps(observations[-4:], ensure_ascii=False)[:24000]}
Choose exactly one next action as strict JSON:
{{"action":"search_web","query":"specific public-web query","reason":"at least 60 characters explaining the evidence gap"}}
{{"action":"open_url","url":"https://...","render":false,"reason":"at least 60 characters"}}
{{"action":"follow_links","url":"https://...","render":true,"reason":"at least 60 characters"}}
{{"action":"finish","answer":"Chinese evidence-based answer with source URLs","reason":"at least 60 characters"}}
Never claim facts absent from observed evidence. Prefer an independent second domain and named entities."""


def _parse_json(text: str) -> dict:
    raw = str(text)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", raw):
        try:
            value, _ = decoder.raw_decode(raw[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("action"):
            return value
    return {}
