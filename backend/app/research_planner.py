"""LLM-assisted query planning for prompt-driven public web research."""
from __future__ import annotations

import json
import logging
import re
import asyncio
from datetime import date, datetime, timedelta, timezone

from app.llm_client import call_llm
from app.models import ModelConfig, Topic

logger = logging.getLogger(__name__)

ENFORCEMENT_SEARCH_MISSIONS = (
    # jurisdiction, Tavily country boost, local-language discovery query
    ("Hong Kong", "", "Hong Kong Customs seizure arrest smuggling drugs wildlife counterfeit"),
    ("Taiwan", "", "台灣 關務署 海關 查獲 走私 毒品 槍械 涉中國"),
    ("Macao", "", "Alfândega Macau apreensão contrabando droga tabaco mercadoria"),
    ("United States", "united states", "CBP customs seizure arrest smuggling China-origin Chinese national shipment"),
    ("Canada", "canada", "CBSA customs seizure arrest smuggling drugs counterfeit shipment from China"),
    ("Australia", "australia", "Australian Border Force seizure arrest smuggling Chinese national China shipment"),
    ("New Zealand", "new zealand", "New Zealand Customs seizure smuggling drugs wildlife shipment from China"),
    ("United Kingdom", "united kingdom", "UK Border Force seizure smuggling tobacco counterfeit shipment China"),
    ("Spain", "spain", "aduanas incautación contrabando drogas armas mercancía procedente de China"),
    ("Portugal", "portugal", "alfandega apreensão contrabando droga mercadoria proveniente da China"),
    ("France", "france", "douane saisie contrebande drogue armes marchandises en provenance de Chine"),
    ("Germany", "germany", "Zoll Beschlagnahme Schmuggel Drogen Waffen Waren aus China"),
    ("Italy", "italy", "Guardia di Finanza dogana sequestro contrabbando droga merce dalla Cina"),
    ("Netherlands", "netherlands", "douane onderschept smokkel drugs wapens goederen uit China"),
    ("Singapore", "singapore", "Singapore Customs CNB seizure arrest smuggling Chinese national China shipment"),
    ("Malaysia", "malaysia", "kastam rampasan penyeludupan dadah rokok barangan dari China"),
    ("Thailand", "thailand", "ศุลกากร จับกุม ยึด ของกลาง ลักลอบ ยาเสพติด สินค้าจากจีน"),
    ("Indonesia", "indonesia", "Bea Cukai penindakan penyelundupan narkotika barang dari Tiongkok warga China"),
    ("Vietnam", "vietnam", "hải quan bắt giữ buôn lậu ma túy hàng hóa từ Trung Quốc"),
    ("Philippines", "philippines", "Bureau of Customs seizure smuggling drugs counterfeit shipment from China"),
    ("Japan", "japan", "税関 摘発 押収 密輸 薬物 金 偽ブランド 中国から"),
    ("South Korea", "south korea", "세관 적발 압수 밀수 마약 위조품 중국산"),
    ("India", "india", "India customs DRI seizure smuggling arrest Chinese national China-origin goods"),
    ("Pakistan", "pakistan", "Pakistan Customs seizure smuggling arrest Chinese national China cargo"),
    ("United Arab Emirates", "united arab emirates", "جمارك ضبط تهريب مخدرات أسلحة شحنة من الصين"),
    ("South Africa", "south africa", "SARS customs seizure smuggling drugs counterfeit Chinese cargo"),
    ("Nigeria", "nigeria", "Nigeria Customs seizure smuggling drugs weapons counterfeit Chinese goods"),
    ("Kenya", "kenya", "Kenya Revenue Authority customs seizure smuggling drugs Chinese goods"),
    ("Brazil", "brazil", "Receita Federal apreensão contrabando drogas armas carga da China"),
    ("Argentina", "argentina", "Aduana Argentina incautación contrabando drogas ciudadano chino mercadería china"),
    ("Chile", "chile", "Aduanas Chile incautación contrabando drogas cigarrillos mercancía china"),
    ("Colombia", "colombia", "DIAN incautación contrabando drogas mercancía procedente de China"),
    ("Peru", "peru", "SUNAT Aduanas incautación contrabando drogas mercancía procedente de China"),
    ("Mexico", "mexico", "Aduanas México aseguramiento contrabando drogas armas mercancía china"),
    ("Global", "", "customs enforcement seizure smuggling Chinese national China-origin shipment"),
    ("Global", "", "customs border major seizure drugs firearms wildlife tobacco counterfeit organized crime"),
)

CUSTOMS_HOTSPOT_SEARCH_MISSIONS = (
    "oil refinery attack fuel shortage price surge border smuggling black market customs",
    "fertilizer shortage price surge port congestion China third country import transshipment customs",
    "chemical feedstock shortage temporary tariff exemption customs misdeclaration trade risk",
    "critical minerals export control third country transshipment false declaration customs",
    "dual use export restrictions hidden end user intermediary procurement customs",
    "sanctions evasion ship to ship transfer origin laundering customs Asia trade",
    "gold precious metal concealed electronic equipment VAT fraud customs",
    "rice grain food price surge export restriction origin fraud phytosanitary customs",
    "agricultural input shortage counterfeit fertilizer smuggling customs Asia",
    "trade remedy anti dumping duty circumvention third country customs China",
    "supply disruption commodity price differential border illicit trade customs China",
    "海关 走私 风险 价格上涨 供应短缺 第三国 转口 原产地 近一个月",
)


async def build_research_queries(
    topic: Topic,
    user_prompt: str,
    model: ModelConfig | None,
    max_queries: int = 12,
    window_days: int = 7,
    today: date | None = None,
    window_start_date: date | None = None,
    window_end_date: date | None = None,
) -> list[str]:
    """Turn an analyst prompt into search inputs, keeping evidence on the web."""
    current_date = today or datetime.now(timezone.utc).date()
    safe_window_days = max(1, int(window_days or 7))
    target_start = window_start_date or (
        current_date - timedelta(days=safe_window_days)
    )
    target_end = window_end_date or current_date
    request = _collection_instruction(topic, user_prompt)
    time_constraint = (
        f"Today is {current_date.isoformat()}. The target publication window is "
        f"{target_start.isoformat()} through {target_end.isoformat()}. "
        "Search for recent or latest publications in this window. Do not use "
        "an obsolete year or month. Do not make an exact quoted date a required match."
    )
    request = f"{request}\n\n{time_constraint}"

    if topic.id == "weekly-enforcement-intelligence":
        # A fixed geographic mission matrix is more reliable than asking a
        # sometimes-slow model to invent a new plan for every weekly run. The
        # model remains authoritative at the evidence-review stage.
        return _fallback_queries(
            topic, current_date, safe_window_days, max_queries,
        )
    if topic.id == "weekly-trade-current-affairs":
        # The customs-risk chain must be represented even when query-planning
        # models are unavailable. A stable mission matrix also makes recurring
        # runs comparable across periods.
        return _fallback_queries(
            topic, current_date, safe_window_days, max_queries,
        )
    if bool(getattr(topic, "weekly_digest_enabled", False)):
        request += (
            "\n\nWeekly global-coverage constraints: cover at least English, Spanish, "
            "Portuguese, French, Japanese and Korean source languages across the query set. "
            "Use one language per query and vary customs, tariff, trade-remedy, sanctions, "
            "export-control, import-rule and supply-chain authorities across regions."
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
6. Treat the configured keywords as semantic intent. Do not require every literal keyword
   to appear in a result; use close concepts, synonyms, translations,
   authorities, conduct, goods and routes that express the same information direction.

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
        fallback = _fallback_queries(
            topic, current_date, safe_window_days, max_queries,
        )
        return _with_weekly_global_lanes(topic, fallback, max_queries)

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
    queries = cleaned or _fallback_queries(
        topic, current_date, safe_window_days, max_queries,
    )
    return _with_weekly_global_lanes(topic, queries, max_queries)


def _with_weekly_global_lanes(
    topic: Topic,
    queries: list[str],
    max_queries: int,
) -> list[str]:
    if not bool(getattr(topic, "weekly_digest_enabled", False)):
        return list(queries)[:max_queries]
    lanes = [
        "official customs tariff trade remedy export control latest",
        "aduanas arancel antidumping control de exportaciones comunicado oficial",
        "aduana tarifa antidumping controle de exportação notícia oficial",
        "douanes tarif antidumping contrôle des exportations communiqué officiel",
        "税関 関税 アンチダンピング 輸出管理 最新 発表",
        "관세청 관세 반덤핑 수출통제 최신 발표",
    ][:max_queries]
    prefix_budget = max(0, max_queries - len(lanes))
    combined = [*queries[:prefix_budget], *lanes]
    return list(dict.fromkeys(combined))[:max_queries]


def _collection_instruction(topic: Topic, user_prompt: str) -> str:
    explicit = (user_prompt or "").strip()
    if explicit:
        return explicit
    keywords = [str(value).strip() for value in (topic.keywords or []) if str(value).strip()]
    return (
        f"Collect information closely related to the topic '{topic.name}'. "
        f"Topic description: {topic.description or 'not provided'}. "
        f"Semantic directions: {', '.join(keywords) or topic.name}. "
        "Use the concepts as a combined information direction, including synonyms, "
        "translations and equivalent events; do not require literal keyword matching."
    )


def _fallback_queries(
    topic: Topic,
    today: date,
    window_days: int,
    max_queries: int,
) -> list[str]:
    """Build deterministic topic-specific queries when the model is unavailable."""
    start = today - timedelta(days=max(1, window_days))
    date_hint = f"since {start.isoformat()} through {today.isoformat()}"
    if topic.id == "weekly-enforcement-intelligence":
        exclusions = (
            " -site:customs.gov.cn -site:*.customs.gov.cn"
            " -site:renrendoc.com -site:doc88.com -site:wenku.baidu.com"
            " -site:baike.baidu.com -site:baijiahao.baidu.com"
        )
        year_hint = str(today.year)
        queries = []
        for jurisdiction, country, query in ENFORCEMENT_SEARCH_MISSIONS:
            directives = f"jurisdiction={jurisdiction}"
            if country:
                directives += f";country={country}"
            queries.append(
                (
                    f"{directives} || {query} {year_hint}{exclusions}"
                )[:420]
            )
        return queries[:max_queries]

    if topic.id == "weekly-trade-current-affairs":
        queries = [
            f"{mission} China Chinese goods company border trade {date_hint}"
            for mission in CUSTOMS_HOTSPOT_SEARCH_MISSIONS
        ]
        return queries[:max_queries]

    keywords = [str(value).strip() for value in (topic.keywords or []) if str(value).strip()]
    directions = keywords[:4] or [topic.name]
    query_suffixes = [
        "official announcement latest",
        "news enforcement policy case",
        "customs trade supply chain risk",
        "regulation authority evidence",
    ]
    queries = [
        f"{topic.name} {direction} {query_suffixes[index % len(query_suffixes)]} {date_hint}"
        for index, direction in enumerate(directions)
    ]
    return list(dict.fromkeys(queries))[:max_queries]


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
