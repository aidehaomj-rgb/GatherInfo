"""LLM-assisted query planning for prompt-driven public web research."""
from __future__ import annotations

import json
import logging
import re
import asyncio
from datetime import datetime, timedelta, timezone

from app.llm_client import call_llm
from app.models import ModelConfig, Topic

logger = logging.getLogger(__name__)


async def build_research_queries(
    topic: Topic,
    user_prompt: str,
    model: ModelConfig | None,
    max_queries: int = 12,
) -> list[str]:
    """Turn an analyst prompt into search inputs, keeping evidence on the web."""
    request = (user_prompt or "").strip()
    if not request:
        return _fallback_queries(topic, datetime.now(timezone.utc).date(), max_queries)

    today = datetime.now(timezone.utc).date()
    window_start = today - timedelta(days=6)
    time_constraint = (
        f"Today is {today.isoformat()}. The target publication window is "
        f"{window_start.isoformat()} through {today.isoformat()}. "
        "Search for recent or latest publications in this window. Do not use "
        "an obsolete year or month. Do not make an exact quoted date a required match."
    )
    request = f"{request}\n\n{time_constraint}"

    if topic.id == "weekly-enforcement-intelligence":
        request += (
            "\n\nEnforcement-weekly constraints: generate a multilingual query set. "
            "Prioritize overseas customs, border, prosecutorial, judicial, or "
            "reputable news sources. Cover customs, border, seizure, smuggling, "
            "Hong Kong Customs, Taiwan Customs, Macao Customs, China, Chinese-origin, "
            "Chinese national, China destination, China route, China-linked logistics "
            "and trade. Also cover firearms, ammunition, explosives, weapons, violent "
            "crime, drugs, narcotics, wildlife, endangered species, tobacco, cigarettes, "
            "counterfeit goods, and other serious contraband. Include English, Spanish, Portuguese "
            "and, where useful, French, Arabic, Indonesian, Thai, Japanese, Korean "
            "or local-language queries. Do not search mainland China Customs, Chinese "
            "document sites, download sites, paper sites, or generic content farms."
        )

    keywords = topic.keywords if isinstance(topic.keywords, list) else []
    topic_desc = topic.description or ""
    system_prompt = f"""
You are a customs risk intelligence search planner. Based on the request below,
return at most {max_queries} high-quality public-web search queries as strict JSON:
{{"queries":["query 1","query 2"]}}

Requirements:
1. Return search queries only, never conclusions.
2. Prefer official announcements, enforcement cases, regulatory sources,
   international organisations, or reputable news.
3. Make queries specific with an authority, action, product, country, or route.
4. For enforcement cases, vary the wording so that a China nexus in the article
   body can still be found even when it is absent from the title.
5. Do not include mainland China Customs domains or document farms.

Topic: {topic.name}
Topic description: {topic_desc}
Topic keywords: {", ".join(map(str, keywords[:40]))}
Analyst request: {request}
""".strip()

    try:
        # Query planning is an enhancement. A slow or unavailable model must
        # never hold up the scheduled collection job; deterministic queries are
        # used immediately when this short budget is exceeded.
        result = await asyncio.wait_for(call_llm(model, system_prompt), timeout=35)
        content = str(result.get("content") or "")
    except Exception as exc:
        logger.warning("AI research query planning failed: %s", exc)
        return _fallback_queries(topic, today, max_queries)

    queries = _parse_query_json(content)
    cleaned: list[str] = []
    seen: set[str] = set()
    for query in queries:
        value = re.sub(r"\s+", " ", str(query)).strip().strip('"').strip("'")
        if not value or len(value) < 3:
            continue
        lowered = value.lower()
        if "customs.gov.cn" in lowered or "海关总署" in value:
            continue
        if topic.id == "weekly-enforcement-intelligence":
            if re.search(r"[\u4e00-\u9fff]", value):
                continue
            value = (
                f"{value} -site:customs.gov.cn -site:*.customs.gov.cn "
                "-site:renrendoc.com -site:doc88.com -site:wenku.baidu.com"
            )
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value[:240])
        if len(cleaned) >= max_queries:
            break
    return cleaned or _fallback_queries(topic, today, max_queries)


def _fallback_queries(topic: Topic, today, max_queries: int) -> list[str]:
    """Deterministic multilingual plan used when the planning model is unavailable."""
    start = today - timedelta(days=6)
    date_hint = f"recent since {start.isoformat()} latest"
    queries = [
        f"Hong Kong Customs seizure drugs firearms wildlife tobacco counterfeit {date_hint}",
        f"Taiwan Customs seizure drugs firearms wildlife tobacco counterfeit {date_hint}",
        f"Macao Customs seizure smuggling drugs counterfeit {date_hint}",
        f"U.S. CBP customs seizure smuggling Chinese-origin goods {date_hint}",
        f"Canada CBSA border seizure Chinese-origin goods {date_hint}",
        f"UK Border Force customs seizure Chinese-made goods {date_hint}",
        f"Australia Border Force Chinese national customs smuggling seizure {date_hint}",
        f"Singapore Customs seizure Chinese-origin goods {date_hint}",
        f"South Africa SARS customs seizure China-origin goods {date_hint}",
        f"Colombia DIAN incautación mercancía de origen chino contrabando {date_hint}",
        f"Ecuador policía incautó cocaína destino China contenedor banano {date_hint}",
        f"Perú SUNAT incautó contrabando mercancía china {date_hint}",
        f"Brasil Receita Federal apreensão contrabando origem China {date_hint}",
        f"India DRI seized Chinese-origin goods smuggling customs {date_hint}",
        f"Sri Lanka Customs seized Chinese cigarettes smuggling {date_hint}",
        f"customs border seizure firearms ammunition explosives drugs narcotics {date_hint}",
        f"customs border seizure wildlife endangered species tobacco counterfeit {date_hint}",
        f"customs enforcement Chinese-origin pharmaceuticals electronics minerals {date_hint}",
    ]
    return queries[:max_queries]


def _parse_query_json(content: str) -> list[str]:
    text = content.strip()
    candidates = [text]
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        values = data.get("queries") if isinstance(data, dict) else None
        if isinstance(values, list):
            return [str(item) for item in values]

    lines = []
    for raw in text.splitlines():
        line = re.sub(r"^\s*[-*\d.]+\s*", "", raw).strip()
        if line and not line.startswith("{") and "queries" not in line.lower():
            lines.append(line)
    return lines
