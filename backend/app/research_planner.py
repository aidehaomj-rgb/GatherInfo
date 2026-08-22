"""LLM-assisted query planning for prompt-driven public web research."""
from __future__ import annotations

import json
import logging
import re
import asyncio
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from app.llm_client import call_llm
from app.models import ModelConfig, Topic
from app.topic_research_context import (
    TopicResearchContext,
    build_topic_research_context,
)
from app.trade_semantics import (
    POLICY_INSTRUMENTS,
    TOPIC_SEMANTIC_PROFILES,
    channel_terms,
    instrument_terms,
)

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

CHINA_NEXUS_SEARCH_MISSIONS = (
    ("United States", "united states", 'site:cbp.gov seizure "from China" OR "China-origin"'),
    ("United States", "united states", 'site:justice.gov smuggling "Chinese national" OR "Chinese company"'),
    ("Canada", "canada", 'site:canada.ca CBSA seizure shipment "from China"'),
    ("Spain", "spain", 'site:agenciatributaria.es aduanas incautación mercancía China ciudadano chino'),
    ("Portugal", "portugal", 'site:gov.pt alfandega apreensão carga da China cidadão chinês'),
    ("Australia", "australia", 'site:abf.gov.au seizure "Chinese national" OR "from China"'),
    ("United Kingdom", "united kingdom", 'site:gov.uk Border Force seizure China shipment'),
    ("Philippines", "philippines", 'site:customs.gov.ph seizure shipment China'),
    ("Singapore", "singapore", 'site:customs.gov.sg seizure China shipment'),
    ("Japan", "japan", 'site:customs.go.jp 税関 摘発 中国 中国人 中国製'),
    ("South Korea", "south korea", 'site:customs.go.kr 세관 적발 중국산 중국인'),
    ("India", "india", 'site:dri.nic.in seizure Chinese national China origin'),
    ("Pakistan", "pakistan", 'site:fbr.gov.pk customs seizure Chinese national China cargo'),
    ("Brazil", "brazil", 'site:gov.br receita federal apreensão carga da China cidadão chinês'),
    ("France", "france", 'site:douane.gouv.fr saisie marchandises Chine ressortissant chinois'),
    ("Germany", "germany", 'site:zoll.de Beschlagnahme Waren aus China chinesischer Staatsangehöriger'),
    ("Global", "", 'customs seizure counterfeit "made in China" exporter importer'),
    ("Global", "", 'customs seizure fentanyl precursor chemical supplier China'),
    ("Global", "", 'customs seizure vape tobacco shipment Shenzhen China'),
    ("Global", "", 'customs seizure firearms parts shipment China'),
    ("Global", "", 'customs detention forced labor goods China exporter'),
    ("Global", "", 'export control sanctions evasion Chinese company customs seizure'),
    ("Global", "", 'customs seizure drone electronics dual use China origin'),
    ("Global", "", 'customs seizure wildlife products route China Hong Kong'),
    ("Global", "", 'customs seizure low value parcels ecommerce China'),
    ("Global", "", 'customs seizure hazardous waste scrap shipment to China'),
    ("Global", "", 'customs seizure Shanghai Ningbo Shenzhen Yantian Qingdao Xiamen'),
    ("Global", "", 'customs seizure Shekou Nansha Tianjin Guangzhou Hong Kong transshipment'),
    ("Global", "", 'customs seizure Chinese exporter importer bill of lading container number'),
    ("Global", "", 'customs arrest Chinese citizen airport cash gold undeclared'),
    ("Global", "", 'customs seizure China manufacturer counterfeit trademark parcel'),
    ("Global", "", 'customs seizure China route vessel IMO bill of lading'),
    ("Mexico", "mexico", 'site:gob.mx aduanas aseguramiento mercancía China ciudadano chino'),
    ("Argentina", "argentina", 'site:argentina.gob.ar aduana incautación mercadería China ciudadano chino'),
)

WEAK_CHINA_SEARCH_MISSIONS = (
    ("Hong Kong", "", "Hong Kong Customs seizure smuggling arrest company shipment"),
    ("Taiwan", "", "台灣 海關 查獲 走私 中國製 中國來源"),
    ("Macao", "", "Alfândega Macau apreensão contrabando mercadoria China"),
    ("Global", "", 'customs seizure "via Hong Kong" OR "Hong Kong transit"'),
    ("Global", "", 'customs seizure Chinese brand Chinese packaging origin certificate'),
    ("Global", "", 'customs seizure WeChat Alipay Chinese phone number logistics label'),
)

CUSTOMS_HOTSPOT_SEARCH_MISSIONS = (
    "Russia refinery outage fuel shortage price differential China Russia border gasoline diesel smuggling",
    "Kazakhstan Russia Mongolia commodity shortage export restriction China land border customs illicit trade",
    "fertilizer sulfur ammonia shortage export ban China import route port border misdeclaration",
    "grain edible oil meat shortage disease export ban China import substitution quarantine origin fraud",
    "crude oil LNG shipping disruption cargo bound for China ship to ship transfer AIS origin customs",
    "China export control dual use drone rare earth hidden end user third country procurement license",
    "China import restriction quarantine food safety overseas supply diversion false certificate customs",
    "gold precious metal currency price gap concealed shipment entering leaving China border customs",
    "sanctions evasion vessel cargo ultimately shipped to China false flag bill of lading origin laundering",
    "counterfeit hazardous chemical waste scrap rerouted into China customs bonded zone misdeclaration",
    "cross-border e-commerce tax rebate fraud low value parcel China customs enforcement emerging route",
    "境外 供应中断 价差 禁运 中国进境 出境 边境 口岸 保税 走私 伪报 可核查 数据",
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
    research_context: TopicResearchContext | None = None,
    round_number: int = 1,
    gaps: dict[str, list[str]] | None = None,
) -> list[str]:
    """Turn an analyst prompt into search inputs, keeping evidence on the web."""
    current_date = today or datetime.now(timezone.utc).date()
    safe_window_days = max(1, int(window_days or 7))
    target_start = window_start_date or (
        current_date - timedelta(days=safe_window_days)
    )
    target_end = window_end_date or current_date
    context = research_context or build_topic_research_context(
        topic,
        prompt=user_prompt,
        window_start=target_start,
        window_end=target_end,
    )
    request = _collection_instruction(context, user_prompt)
    gap_block = _gap_instruction(round_number, gaps)
    if gap_block:
        request = f"{request}\n\n{gap_block}"
    time_constraint = (
        f"Today is {current_date.isoformat()}. The target publication window is "
        f"{target_start.isoformat()} through {target_end.isoformat()}. "
        "Search for recent or latest publications in this window. Do not use "
        "an obsolete year or month. Do not make an exact quoted date a required match."
    )
    request = f"{request}\n\n{time_constraint}"

    if round_number >= 2 and gaps:
        followups = _parse_followup_queries(user_prompt)
        gap_queries = _gap_queries(context, gaps, current_date, max_queries)
        return list(dict.fromkeys([*followups, *gap_queries]))[:max_queries]

    if topic.id == "weekly-enforcement-intelligence":
        followups = _parse_followup_queries(user_prompt)
        if followups:
            # Later Research Agent rounds are evidence-led. Keep a small
            # geographic baseline while spending most of the budget on gaps
            # and named entities discovered in earlier rounds.
            baseline = _enforcement_quota_queries(current_date, min(12, max_queries))
            return list(dict.fromkeys([*followups, *baseline]))[:max_queries]
        # A fixed geographic mission matrix is more reliable than asking a
        # sometimes-slow model to invent a new plan for every weekly run. The
        # model remains authoritative at the evidence-review stage.
        return _contextualize_queries(_fallback_queries(
            topic, current_date, safe_window_days, max_queries,
        ), context, max_queries)
    if topic.id == "weekly-trade-current-affairs":
        # The customs-risk chain must be represented even when query-planning
        # models are unavailable. A stable mission matrix also makes recurring
        # runs comparable across periods.
        return _contextualize_queries(_fallback_queries(
            topic, current_date, safe_window_days, max_queries,
        ), context, max_queries)
    if bool(getattr(topic, "weekly_digest_enabled", False)):
        request += (
            "\n\nWeekly global-coverage constraints: cover at least English, Spanish, "
            "Portuguese, French, Japanese and Korean source languages across the query set. "
            "Use one language per query and vary customs, tariff, trade-remedy, sanctions, "
            "export-control, import-rule and supply-chain authorities across regions."
        )

    keywords = list(context.keywords)
    topic_desc = context.description
    instrument_vocab = ", ".join(instrument_terms())
    channel_vocab = ", ".join(channel_terms())
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
7. Prefer queries that express one of these trade-policy instruments as the
   semantic direction (use their English terms, synonyms or translations):
   {instrument_vocab}
   and, where relevant, one of these trade-impact channels:
   {channel_vocab}

Topic: {topic.name}
Topic description: {topic_desc}
Topic keywords: {", ".join(map(str, keywords[:40]))}
Unified topic research context: {json.dumps(context.to_dict(), ensure_ascii=False)}
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
        if round_number >= 2 and gaps:
            fallback = _gap_queries(context, gaps, current_date, max_queries) or fallback
        fallback = _contextualize_queries(fallback, context, max_queries)
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
    queries = _contextualize_queries(cleaned, context, max_queries) if cleaned else (
        _contextualize_queries(_fallback_queries(
            topic, current_date, safe_window_days, max_queries,
        ), context, max_queries)
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


def _parse_followup_queries(prompt: str) -> list[str]:
    marker = "[FOLLOWUP_QUERIES]"
    if marker not in (prompt or ""):
        return []
    raw = prompt.split(marker, 1)[1].strip().splitlines()[0].strip()
    try:
        values = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(values, list):
        return []
    return [re.sub(r"\s+", " ", str(value)).strip()[:420] for value in values if str(value).strip()][:32]


def _collection_instruction(topic: Topic | TopicResearchContext, user_prompt: str) -> str:
    explicit = (user_prompt or "").strip()
    if explicit:
        return explicit
    keywords = [str(value).strip() for value in (topic.keywords or []) if str(value).strip()]
    synonyms = [str(value).strip() for value in (getattr(topic, "synonyms", ()) or ()) if str(value).strip()]
    return (
        f"Collect information closely related to the topic '{topic.name}'. "
        f"Topic description: {topic.description or 'not provided'}. "
        f"Semantic directions: {', '.join([*keywords, *synonyms]) or topic.name}. "
        "Use the concepts as a combined information direction, including synonyms, "
        "translations and equivalent events; do not require literal keyword matching."
    )


def _gap_instruction(round_number: int, gaps: dict[str, list[str]] | None) -> str:
    if round_number < 2 or not gaps:
        return ""
    return (
        "This is collection round 2. Fill only the measured coverage and evidence gaps; "
        "prioritise official originals, verifiable publication dates, named actors, routes "
        "and case numbers. Gaps: " + json.dumps(gaps, ensure_ascii=False)
    )


def _gap_queries(
    context: TopicResearchContext,
    gaps: dict[str, list[str]],
    today: date,
    max_queries: int,
) -> list[str]:
    """Build deterministic second-round queries from acceptance gaps."""
    countries = _clean_gap_values(gaps.get("countries")) or list(context.focus_countries) or [""]
    languages = _clean_gap_values(gaps.get("languages")) or list(context.focus_languages) or [""]
    instruments = _clean_gap_values(gaps.get("policy_instruments")) or list(context.policy_instruments[:3]) or list(context.keywords[:3])
    products = _clean_gap_values(gaps.get("products")) or [""]
    grades = _clean_gap_values(gaps.get("source_grades"))
    evidence_hint = "official government original notice case PDF" if "A" in grades else "independent authoritative source"
    date_hint = f"since {context.window.start.isoformat()} through {context.window.end.isoformat() or today.isoformat()}"
    queries = [
        " ".join(filter(None, (country, language, instrument, product, evidence_hint, date_hint)))
        for country in countries
        for language in languages[:2]
        for instrument in instruments[:3]
        for product in products[:2]
    ]
    return list(dict.fromkeys(query[:240] for query in queries if len(query.strip()) >= 3))[:max_queries]


def build_followup_queries(
    context: TopicResearchContext,
    gaps: dict[str, list[str]],
    *,
    max_queries: int = 12,
    today: date | None = None,
) -> list[str]:
    """Public deterministic adapter for a batch acceptance result."""
    return _gap_queries(context, gaps, today or context.window.end, max_queries)


def _contextualize_queries(
    queries: list[str],
    context: TopicResearchContext,
    max_queries: int,
) -> list[str]:
    """Apply configured country, language, target-site and exclusion lanes offline."""
    if not queries:
        return []
    exclusions = " ".join(f'-"{term}"' for term in context.exclude_keywords[:4])
    base = [" ".join(filter(None, (query, exclusions)))[:240] for query in queries]
    countries = context.focus_countries[:3]
    languages = context.focus_languages[:3]
    target_hosts = [urlparse(url).netloc for url in context.target_urls[:3] if urlparse(url).netloc]
    lanes = [
        " ".join(filter(None, (
            base[index % len(base)],
            countries[index % len(countries)] if countries else "",
            languages[index % len(languages)] if languages else "",
            f"site:{target_hosts[index % len(target_hosts)]}" if target_hosts else "",
        )))[:240]
        for index in range(max(len(countries), len(languages), len(target_hosts), 0))
    ]
    if not lanes:
        return base[:max_queries]
    keep = max(0, max_queries - len(lanes))
    return list(dict.fromkeys([*base[:keep], *lanes]))[:max_queries]


def _clean_gap_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(entry).strip() for entry in value if str(entry).strip()))


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
        return _enforcement_quota_queries(today, max_queries)

    if topic.id == "weekly-trade-current-affairs":
        queries = [
            f"{mission} {date_hint}"
            for mission in CUSTOMS_HOTSPOT_SEARCH_MISSIONS
        ]
        return queries[:max_queries]

    # 贸易类主题：优先用受控政策工具词表生成语义检索式（替代散装关键词）
    semantic = _trade_semantic_queries(topic, date_hint, max_queries)
    if semantic:
        return semantic

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


def _trade_semantic_queries(topic: Topic, date_hint: str, max_queries: int) -> list[str]:
    """用主题绑定的政策工具词表生成确定性语义检索式（贸易类主题）。

    未绑定语义画像的主题（关键矿产、军工采购等）返回空列表，走原关键词逻辑。
    """
    profile = TOPIC_SEMANTIC_PROFILES.get(topic.id)
    if not profile:
        return []

    instrument_slugs = profile.get("policy_instruments", [])
    if "all" in instrument_slugs:
        instrument_slugs = list(POLICY_INSTRUMENTS.keys())
    # 每个政策工具取代表性英文搜索词（词表已按具体度排序，首词即可用）
    terms = [
        POLICY_INSTRUMENTS[slug][0]
        for slug in instrument_slugs
        if slug in POLICY_INSTRUMENTS
    ]
    if not terms:
        return []

    # 主题的英文关键词作为种子（过滤中文关键词，避免中英混拼）
    en_seeds = [
        str(kw).strip()
        for kw in (topic.keywords or [])
        if kw and not re.search(r"[\u4e00-\u9fff]", str(kw))
    ][:4]

    queries: list[str] = []
    # 单工具查询：种子 + 政策工具 + 官方/最新
    for term in terms:
        seed = en_seeds[0] if en_seeds else "trade policy"
        queries.append(f"{seed} {term} official announcement latest {date_hint}"[:240])
    # 组合查询：2~3 个工具词组合，覆盖更广
    for index in range(0, len(terms), 3):
        combo = " ".join(terms[index : index + 3])
        seed = en_seeds[0] if en_seeds else "trade policy"
        queries.append(f"{seed} {combo} regulation measure {date_hint}"[:240])
    return list(dict.fromkeys(queries))[:max_queries]


def _enforcement_quota_queries(today: date, max_queries: int) -> list[str]:
    exclusions = " -site:customs.gov.cn -site:*.customs.gov.cn -site:renrendoc.com -site:doc88.com -site:wenku.baidu.com -site:baike.baidu.com -site:baijiahao.baidu.com"
    strong_budget = max(1, int(max_queries * 0.70))
    weak_budget = max(1, int(max_queries * 0.20))
    general_budget = max(0, max_queries - strong_budget - weak_budget)
    if max_queries <= 12:
        selected = []
        seen_jurisdictions = set()
        for mission in CHINA_NEXUS_SEARCH_MISSIONS:
            if mission[0] in seen_jurisdictions:
                continue
            selected.append(mission); seen_jurisdictions.add(mission[0])
            if len(selected) >= max_queries:
                break
    else:
        selected = [
            *CHINA_NEXUS_SEARCH_MISSIONS[:strong_budget],
            *WEAK_CHINA_SEARCH_MISSIONS[:weak_budget],
        ]
    if general_budget and max_queries > 12:
        selected.extend(ENFORCEMENT_SEARCH_MISSIONS[-general_budget:])
    if max_queries >= 35:
        local_language = [
            next(m for m in ENFORCEMENT_SEARCH_MISSIONS if m[0] == jurisdiction)
            for jurisdiction in ("Thailand", "Indonesia", "Japan", "South Korea", "United Arab Emirates")
        ]
        selected[-len(local_language):] = local_language
    while len(selected) < max_queries:
        selected.append(CHINA_NEXUS_SEARCH_MISSIONS[len(selected) % len(CHINA_NEXUS_SEARCH_MISSIONS)])
    queries = []
    for jurisdiction, country, query in selected:
        directives = f"jurisdiction={jurisdiction}"
        if country:
            directives += f";country={country}"
        queries.append(f"{directives} || {query} {today.year}{exclusions}"[:420])
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
