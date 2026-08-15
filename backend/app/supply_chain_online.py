from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from app.connectors.broad_web_search import (
    BroadWebSearchCollector,
    NewsRSSSearchCollector,
    PDFSearchCollector,
)
from app.connectors.tavily_search import TavilyCollector
from app.llm_client import call_llm
from app.research_document_reader import read_document
from app.supply_chain_trade_records import (
    extract_structured_trade_records as _extract_structured_trade_records,
    merge_candidate_evidence as _merge_candidate_evidence,
    merge_source_records as _merge_source_records,
    probe_public_trade_indexes as _probe_public_trade_indexes,
    trade_record_targets as _trade_record_targets,
)


COUNTRY_LABELS = {
    "United States": "United States US",
    "India": "India",
    "Japan": "Japan",
    "Taiwan": "Taiwan",
}

COUNTRY_LOCALES = {
    "United States": ("en-US",),
    "India": ("en-IN", "hi-IN"),
    "Japan": ("ja-JP", "en-US"),
    "Taiwan": ("zh-TW", "en-US"),
}

COMPANY_SEEDS = {
    "United States": ["Ultralife Corporation", "Teledyne FLIR", "AeroVironment", "L3Harris", "RTX Corporation", "General Dynamics", "Northrop Grumman", "Kratos Defense"],
    "India": ["Bharat Electronics", "Tata Advanced Systems", "Larsen Toubro Defence", "Bharat Dynamics", "Hindustan Aeronautics", "Adani Defence"],
    "Japan": ["Mitsubishi Heavy Industries", "Kawasaki Heavy Industries", "NEC defense", "IHI Corporation", "Subaru Corporation defense", "Mitsubishi Electric defense"],
    "Taiwan": ["Aerospace Industrial Development Corporation", "NCSIST", "Thunder Tiger", "Tron Future Tech", "GEOSAT Aerospace", "CSBC Corporation Taiwan"],
}

LOCALIZED_COMPANY_NAMES = {
    "India": {
        "Bharat Electronics": "भारत इलेक्ट्रॉनिक्स",
        "Tata Advanced Systems": "टाटा एडवांस्ड सिस्टम्स",
        "Hindustan Aeronautics": "हिंदुस्तान एयरोनॉटिक्स",
    },
    "Japan": {
        "Mitsubishi Heavy Industries": "三菱重工業",
        "Kawasaki Heavy Industries": "川崎重工業",
        "NEC defense": "日本電気 防衛",
        "IHI Corporation": "IHI 防衛",
        "Subaru Corporation defense": "SUBARU 防衛",
        "Mitsubishi Electric defense": "三菱電機 防衛",
    },
    "Taiwan": {
        "Aerospace Industrial Development Corporation": "漢翔航空工業",
        "NCSIST": "國家中山科學研究院",
        "Thunder Tiger": "雷虎科技",
        "Tron Future Tech": "創未來科技",
        "GEOSAT Aerospace": "經緯航太",
        "CSBC Corporation Taiwan": "台灣國際造船",
    },
}

TRADE_SIGNAL_TERMS = (
    "import", "export", "shipment", "bill of lading", "supplier", "customs",
    "importyeti", "importgenius", "panjiva", "trade data", "中国", "中國", "进口", "進口",
    "出口", "提单", "提單", "輸入", "船荷証券", "आयात", "शिपमेंट",
)
MILITARY_SIGNAL_TERMS = (
    "defense", "defence", "military", "contract award", "procurement", "army",
    "navy", "air force", "department of defense", "weapon", "国防", "國防", "军方", "軍方",
    "合同", "防衛", "契約", "調達", "रक्षा", "अनुबंध",
)

CHINA_SOURCE_TERMS = (
    "china", "chinese", "people's republic of china", "prc", "中国", "中國", "中国大陆",
    "中國大陸", "中国製", "中国から", "चीन", "चीनी",
)
TRADE_FLOW_TERMS = (
    "import", "imports", "imported", "shipment", "shipments", "bill of lading", "customs",
    "supplier", "supplied", "consignee", "shipper", "进口", "進口", "提单", "提單", "海关",
    "海關", "輸入", "船荷証券", "供給", "आयात", "शिपमेंट", "आपूर्तिकर्ता",
)
DEFENSE_CONTRACT_TERMS = (
    "defense", "defence", "military", "army", "navy", "air force", "contract award",
    "procurement", "department of defense", "国防", "國防", "军方", "軍方", "合同", "採購",
    "防衛", "契約", "調達", "रक्षा", "अनुबंध", "खरीद",
)
CONTRACT_ACTION_TERMS = (
    "contract", "award", "awarded", "order", "idiq", "procurement", "purchase",
    "合同", "中标", "订单", "採購", "采购", "契約", "調達", "अनुबंध", "खरीद",
)
MILITARY_ROLE_TERMS = (
    "defense", "defence", "military", "army", "navy", "air force", "soldier",
    "defense logistics agency", "国防", "國防", "军方", "軍方", "陆军", "海军",
    "防衛", "自衛隊", "रक्षा",
)
PRODUCT_TERM_FAMILIES = (
    ("battery", "batteries", "lithium", "cell"),
    ("container", "metal box"),
    ("radar", "antenna", "sensor"),
    ("radio", "transceiver", "microphone", "charger", "cable"),
    ("aircraft", "uav", "drone", "aerospace"),
    ("missile", "rocket", "munition"),
    ("magnet", "rare earth"),
)
GOVERNMENT_AGENCY_TERMS = (
    "department of defense", "department of defence", "ministry of defense", "ministry of defence",
    "customs and border protection", "government of", "united states army", "u.s. army",
    "united states navy", "u.s. navy", "air force", "防衛省", "国防部", "國防部", "海关", "海關",
    "रक्षा मंत्रालय",
)
TRADE_INDEX_HOSTS = (
    "importgenius.com", "importyeti.com", "panjiva.com", "volza.com", "52wmb.com",
    "trademo.com", "seair.co.in", "exportgenius.in", "tradeatlas.com",
)


def _collector_config(mode: str):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=f"supply-chain-{mode}", timeout_seconds=45, rate_limit_rps=1.0,
        auth_config={}, api_key=None, api_key_ref=None, base_url=None,
        api_endpoint=None, default_keywords=[], default_categories=[],
    )


def _locale_query(locale: str, query: str) -> str:
    return f"{locale}||{query}"


def _query_text(value: str) -> str:
    return value.split("||", 1)[-1].strip()


def _window_years(as_of: datetime, window_days: int) -> str:
    cutoff = as_of - timedelta(days=window_days)
    return " ".join(str(year) for year in range(cutoff.year, as_of.year + 1))


def _queries(
    country: str, *, as_of: datetime | None = None, import_record_window_days: int = 365,
) -> list[str]:
    as_of = as_of or datetime.now(timezone.utc)
    years = _window_years(as_of, import_record_window_days)
    label = COUNTRY_LABELS.get(country, country)
    queries = [
        _locale_query("en-US", f'Chinese components in {label} military equipment investigation report'),
        _locale_query("en-US", f'{label} military supply chain China supplier audit report'),
    ]
    for company in COMPANY_SEEDS.get(country, []):
        queries.extend([
            _locale_query(COUNTRY_LOCALES.get(country, ("en-US",))[0], f'"{company}" {years} imports from China supplier shipment bill of lading'),
            _locale_query(COUNTRY_LOCALES.get(country, ("en-US",))[0], f'"{company}" defense contract award government procurement'),
        ])
        localized = LOCALIZED_COMPANY_NAMES.get(country, {}).get(company)
        if localized and country == "Japan":
            queries.extend([
                _locale_query("ja-JP", f'"{localized}" 中国から輸入 サプライヤー 船荷証券 {years}'),
                _locale_query("ja-JP", f'"{localized}" 防衛省 契約 調達'),
            ])
        elif localized and country == "Taiwan":
            queries.extend([
                _locale_query("zh-TW", f'"{localized}" 中國進口 供應商 提單 {years}'),
                _locale_query("zh-TW", f'"{localized}" 國防 採購 合約'),
            ])
        elif localized and country == "India":
            queries.extend([
                _locale_query("hi-IN", f'"{localized}" चीन से आयात आपूर्तिकर्ता शिपमेंट {years}'),
                _locale_query("hi-IN", f'"{localized}" रक्षा अनुबंध सरकारी खरीद'),
            ])
    return queries


def _deep_china_trade_queries(
    country: str, *, as_of: datetime | None = None, import_record_window_days: int = 365,
) -> list[str]:
    as_of = as_of or datetime.now(timezone.utc)
    years = _window_years(as_of, import_record_window_days)
    companies = COMPANY_SEEDS.get(country, [])
    templates = (
        f'"{{company}}" {years} China supplier shipment bill of lading',
        f'"{{company}}" {years} imports from China customs trade data',
        'site:importgenius.com "{company}" China shipment',
        'site:importyeti.com "{company}" supplier',
        'site:panjiva.com "{company}" shipment',
        'site:52wmb.com "{company}" import',
        '"{company}" China suppliers annual report supply chain',
        '"{company}" China sourcing components 10-K',
    )
    locale = COUNTRY_LOCALES.get(country, ("en-US",))[0]
    return [
        _locale_query(locale, template.format(company=company))
        for template in templates for company in companies
    ]


def _configured_provider_queries(
    country: str, trade_records: list[dict[str, Any]], *,
    as_of: datetime, import_record_window_days: int,
) -> list[str]:
    years = _window_years(as_of, import_record_window_days)
    military_authority = {
        "United States": "U.S. Army Defense Logistics Agency",
        "India": "Indian Ministry of Defence armed forces",
        "Japan": "Japan Ministry of Defense Self-Defense Forces",
        "Taiwan": "Taiwan Ministry of National Defense armed forces",
    }.get(country, "military defense ministry")
    record_targets = [
        item for item in trade_records if item.get("country") == country
    ]
    if record_targets:
        return [
            query
            for item in record_targets[:4]
            for query in (
                f"{str(item['importer_name']).title()} military "
                f"{next((family[0] for family in PRODUCT_TERM_FAMILIES if any(term in str(item['product']).casefold() for term in family)), '')} contract",
                f"{str(item['importer_name']).title()} {military_authority} contract award",
            )
        ]
    companies = COMPANY_SEEDS.get(country, [])[:2]
    return [
        query
        for company in companies
        for query in (
            f"{company} {years} imports from China supplier shipment bill of lading",
            f"{company} military defense contract award official procurement",
        )
    ]


def _seed_research_targets(countries: list[str]) -> list[dict[str, Any]]:
    """Provide a bounded fallback when the first entity-extraction call is unavailable."""
    return [
        {
            "country": country,
            "company_name": company,
            "aliases": [],
            "role": "defense_importer",
            "address": "",
            "products": [],
            "contract_refs": [],
            "trade_counterparties": [],
            "source_urls": [],
            "seed_fallback": True,
        }
        for country in countries
        for company in COMPANY_SEEDS.get(country, [])
    ]


def _signal_sets(sources: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    trade, military = [], []
    for source in sources:
        text = f"{source.get('title', '')} {source.get('summary', '')}".casefold()
        compact = {key: source.get(key) for key in ("title", "url", "summary", "country_hint", "mode")}
        if any(term in text for term in TRADE_SIGNAL_TERMS):
            trade.append(compact)
        if any(term in text for term in MILITARY_SIGNAL_TERMS):
            military.append(compact)
    return {"china_trade_signals": trade, "military_use_signals": military}


def _source_priority(item: dict[str, Any]) -> tuple[int, int, int, int]:
    text = f"{item.get('title', '')} {item.get('summary', '')}".casefold()
    host = _source_host(str(item.get("url") or ""))
    trade_index = any(host.endswith(value) for value in TRADE_INDEX_HOSTS)
    strong_signal = any(term in text for term in TRADE_FLOW_TERMS) or any(
        term in text for term in DEFENSE_CONTRACT_TERMS
    )
    return (
        0 if trade_index else 1,
        0 if strong_signal else 1,
        0 if item.get("summary") else 1,
        1 if item.get("mode") == "pdf" else 0,
    )


async def _localize_candidates(candidates: list[dict[str, Any]], model: Any) -> list[dict[str, Any]]:
    """Translate candidate-facing text while retaining original values for audit."""
    if not candidates:
        return candidates
    fields = ("importer_name", "exporter_name", "product", "contract_title", "target_program")
    payload = [{"index": index, **{key: item.get(key) for key in fields}} for index, item in enumerate(candidates)]
    prompt = f"""
把以下供应链候选的展示字段翻译成简洁、准确的中文。公司等实体名称使用“中文名（英文原名）”格式；没有通行中文名时也要给出清晰音译，不能原样重复两次英文。产品、合同标题和项目名称只使用中文。型号、合同号、缩写和金额保持原样。
只返回 JSON 数组，保留 index，并返回这些字段：{', '.join(fields)}。不得增加或推测事实。
数据：{json.dumps(payload, ensure_ascii=False)}
""".strip()
    try:
        result = await call_llm(model, prompt, timeout_seconds=180, minimum_content_length=2)
        translations = {row.get("index"): row for row in _extract_json_array(result["content"])}
    except Exception:
        return candidates
    localized = []
    for index, item in enumerate(candidates):
        translated = translations.get(index, {})
        original_fields = {key: item.get(key) for key in fields}
        updates = {
            key: translated.get(key).strip()
            for key in fields
            if isinstance(translated.get(key), str) and translated[key].strip()
        }
        for key in ("importer_name", "exporter_name"):
            original = original_fields.get(key)
            if isinstance(original, str) and original.strip():
                updates[key] = _entity_display_name(original, updates.get(key))
        localized.append({**item, **updates, "original_fields": original_fields})
    return localized


def _entity_display_name(original: str, translated: Any) -> str:
    original = original.strip()
    if not re.search(r"[A-Za-z]", original):
        return str(translated).strip() if isinstance(translated, str) and translated.strip() else original
    proposed = str(translated or "").strip()
    if not re.search(r"[\u4e00-\u9fff]", proposed):
        return original
    if _normalized_entity_text(original) in _normalized_entity_text(proposed):
        return proposed
    return f"{proposed}（{original}）"


def _extract_json_array(content: str) -> list[dict[str, Any]]:
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", content, re.S)
    raw = fenced.group(1) if fenced else None
    if raw is None:
        match = re.search(r"\[.*\]", content, re.S)
        raw = match.group(0) if match else "[]"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _resolve_allowed_url(value: Any, allowed_urls: set[str]) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().rstrip("/").split("#", 1)[0]
    for allowed in allowed_urls:
        if allowed.rstrip("/").split("#", 1)[0] == normalized:
            return allowed if urlparse(allowed).scheme in {"http", "https"} else None
    return None


def _url_key(value: str) -> str:
    return value.strip().rstrip("/").split("#", 1)[0]


def _source_text(source: dict[str, Any] | None) -> str:
    if not source:
        return ""
    return " ".join(str(source.get(key) or "") for key in ("title", "summary", "content"))


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    return []


def _name_matches_source(names: list[Any], source_text: str) -> bool:
    normalized_source = _normalized_entity_text(source_text)
    legal_terms = {
        "co", "company", "corp", "corporation", "inc", "incorporated", "limited", "ltd",
        "plc", "llc", "group", "holdings", "systems", "technology", "technologies",
    }
    for value in names:
        if not isinstance(value, str) or not value.strip():
            continue
        normalized_name = _normalized_entity_text(value)
        if len(normalized_name) >= 4 and normalized_name in normalized_source:
            return True
        tokens = [
            token for token in re.findall(r"[a-z0-9\u0900-\u097f\u3040-\u30ff\u3400-\u9fff]+", value.casefold())
            if len(token) >= 3 and token not in legal_terms
        ]
        matches = sum(_normalized_entity_text(token) in normalized_source for token in dict.fromkeys(tokens))
        if matches >= min(2, len(tokens)) and matches:
            return True
    return False


def _normalized_entity_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\u0900-\u097f\u3040-\u30ff\u3400-\u9fff]+", "", value.casefold())


def _is_government_agency(item: dict[str, Any]) -> bool:
    importer = str(item.get("importer_name") or "").casefold()
    agency = str(item.get("contracting_agency") or "").casefold()
    if agency and _normalized_entity_text(importer) == _normalized_entity_text(agency):
        return True
    return any(term in importer for term in GOVERNMENT_AGENCY_TERMS)


def _source_host(source_url: str) -> str:
    return urlparse(source_url).netloc.casefold().removeprefix("www.")


def _contract_validation(
    item: dict[str, Any], source_url: str | None, source: dict[str, Any] | None,
) -> dict[str, Any]:
    if not source_url:
        return {"valid": False, "reason": "missing_contract_source"}
    text = _source_text(source).casefold()
    if _is_government_agency(item):
        return {"valid": False, "reason": "procurement_agency_used_as_importer"}
    names = [item.get("importer_name"), *_string_values(item.get("importer_aliases"))]
    if not _name_matches_source(names, text):
        return {"valid": False, "reason": "contract_source_missing_target_company"}
    host = _source_host(source_url)
    official_host = (
        host.endswith((".gov", ".gov.in", ".go.jp", ".gov.tw", ".mil"))
        or host in {"sam.gov", "defense.gov", "dod.defense.gov"}
    )
    if not official_host and not any(term in text for term in DEFENSE_CONTRACT_TERMS):
        return {"valid": False, "reason": "source_does_not_show_defense_contract_or_program"}
    return {"valid": True, "reason": "target_company_and_defense_role_confirmed"}


def _contract_product_bridge(product: str, source_text: str) -> bool:
    product_folded = product.casefold()
    source_folded = source_text.casefold()
    for family in PRODUCT_TERM_FAMILIES:
        if any(term in product_folded for term in family):
            return any(term in source_folded for term in family)
    ignored = {
        "empty", "metal", "parts", "part", "component", "components", "system",
        "equipment", "model", "order", "code", "goods", "assembly", "product",
    }
    product_terms = {
        term for term in re.findall(r"[a-z0-9-]{4,}", product_folded)
        if term not in ignored and not term.isdigit()
    }
    return any(term in source_folded for term in product_terms)


def _contract_source_rank(source: dict[str, Any]) -> tuple[int, int]:
    host = _source_host(str(source.get("url") or ""))
    official = host.endswith((".gov", ".gov.in", ".go.jp", ".gov.tw", ".mil"))
    corporate_release = any(term in host for term in ("investor.", "investors.", "newsroom."))
    published = _parse_evidence_date(source.get("published_at"))
    timestamp = int(published.timestamp()) if published else 0
    return (0 if official else 1 if corporate_release else 2, -timestamp)


def _attach_deterministic_contract_evidence(
    trade_records: list[dict[str, Any]], sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    attached = []
    for record in trade_records:
        candidates = []
        for source in sources:
            source_url = str(source.get("url") or "")
            if not source_url or source_url == record.get("trade_evidence_url"):
                continue
            if any(_source_host(source_url).endswith(host) for host in TRADE_INDEX_HOSTS):
                continue
            source_text = _source_text(source)
            folded = source_text.casefold()
            if not (
                any(term in folded for term in CONTRACT_ACTION_TERMS)
                and any(term in folded for term in MILITARY_ROLE_TERMS)
                and _contract_product_bridge(str(record.get("product") or ""), source_text)
            ):
                continue
            check = _contract_validation(record, source_url, source)
            if check.get("valid"):
                candidates = [*candidates, source]
        if not candidates:
            attached = [*attached, record]
            continue
        source = sorted(candidates, key=_contract_source_rank)[0]
        source_text = _source_text(source).strip()
        contract_date = _parse_evidence_date(source.get("published_at"))
        if not contract_date:
            contract_date = _extract_supported_date(source_text)
        attached = [*attached, {
            **record,
            "contract_title": str(source.get("title") or "国防合同或军工项目证据")[:500],
            "contract_evidence_url": source.get("url"),
            "contract_date": contract_date.date().isoformat() if contract_date else None,
            "contract_excerpt": source_text[:1200],
            "confidence_score": max(80, int(record.get("confidence_score") or 0)),
            "deterministic_contract_match": True,
        }]
    return attached


def _parse_evidence_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except ValueError:
        pass
    for pattern in (
        "%Y/%m/%d", "%Y.%m.%d", "%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y",
    ):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_supported_dates(value: str) -> list[datetime]:
    patterns = (
        r"\b(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\b",
        r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+20\d{2})\b",
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+20\d{2})\b",
    )
    dates: list[datetime] = []
    for pattern in patterns:
        for raw in re.findall(pattern, value, flags=re.I):
            parsed = _parse_evidence_date(raw.replace("Sept ", "Sep "))
            if parsed:
                dates.append(parsed)
    return dates


def _extract_supported_date(value: str) -> datetime | None:
    dates = _extract_supported_dates(value)
    return max(dates) if dates else None


def _trade_validation(
    item: dict[str, Any], source_url: str | None, source: dict[str, Any] | None,
    *, as_of: datetime, import_record_window_days: int,
) -> dict[str, Any]:
    if not source_url:
        return {"valid": False, "reason": "missing_trade_source"}
    text = _source_text(source)
    folded = text.casefold()
    importer_names = [item.get("importer_name"), *_string_values(item.get("importer_aliases"))]
    if not _name_matches_source(importer_names, text):
        return {"valid": False, "reason": "trade_source_missing_target_importer"}
    if not any(term in folded for term in TRADE_FLOW_TERMS):
        return {"valid": False, "reason": "source_does_not_show_trade_activity"}
    if not any(term in folded for term in CHINA_SOURCE_TERMS):
        return {"valid": False, "reason": "source_does_not_show_china_origin"}
    export_to_china = any(term in folded for term in (
        "exports to china", "exported to china", "shipments to china", "向中国出口", "向中國出口", "中国に輸出",
    ))
    import_from_china = any(term in folded for term in (
        "imports from china", "imported from china", "shipments from china", "supplier based in china",
        "自中国进口", "自中國進口", "从中国进口", "從中國進口", "中国から輸入", "चीन से आयात",
    ))
    exporter_names = [item.get("exporter_name"), *_string_values(item.get("exporter_aliases"))]
    exporter_confirmed = _name_matches_source(exporter_names, text)
    if export_to_china and not import_from_china and not exporter_confirmed:
        return {"valid": False, "reason": "trade_direction_is_export_to_china"}
    if not import_from_china and not exporter_confirmed:
        return {"valid": False, "reason": "china_exporter_or_import_direction_not_confirmed"}

    published_at = _parse_evidence_date((source or {}).get("published_at"))
    trade_date = _parse_evidence_date(item.get("trade_date"))
    date_basis = str(item.get("trade_date_basis") or "").strip() or "shipment_record"
    if not trade_date and date_basis == "report_publication":
        trade_date = published_at
    if not trade_date:
        trade_date = _extract_supported_date(str(item.get("trade_excerpt") or ""))
    if not trade_date and published_at and import_from_china:
        trade_date, date_basis = published_at, "report_publication"
    if not trade_date:
        return {"valid": False, "reason": "trade_date_not_verifiable"}

    cutoff = as_of - timedelta(days=import_record_window_days)
    if trade_date < cutoff or trade_date > as_of + timedelta(days=1):
        return {
            "valid": False, "reason": "trade_date_outside_selected_window",
            "trade_date": trade_date.date().isoformat(), "cutoff": cutoff.date().isoformat(),
        }

    supporting_text = f"{item.get('trade_excerpt') or ''} {text}"
    dates_in_text = _extract_supported_dates(supporting_text)
    date_supported = any(value.date() == trade_date.date() for value in dates_in_text)
    publication_matches = bool(
        published_at and abs((published_at.date() - trade_date.date()).days) <= 1
        and date_basis == "report_publication"
    )
    if not date_supported and not publication_matches:
        return {"valid": False, "reason": "trade_date_not_supported_by_source_text"}
    return {
        "valid": True, "reason": "china_to_target_trade_and_date_confirmed",
        "trade_date": trade_date.date().isoformat(), "trade_date_basis": date_basis,
        "cutoff": cutoff.date().isoformat(), "source_host": _source_host(source_url),
        "trade_index_source": any(_source_host(source_url).endswith(host) for host in TRADE_INDEX_HOSTS),
    }


def _trade_gap(reason: str, import_record_window_days: int) -> str:
    label = {90: "近一季度", 180: "近半年", 365: "近一年"}.get(
        import_record_window_days, f"近{import_record_window_days}天",
    )
    if reason == "trade_date_outside_selected_window":
        return f"待补{label}内的中国进口记录、提单或明确进口报道（现有记录超出时间范围）"
    if reason in {"trade_date_not_verifiable", "trade_date_not_supported_by_source_text"}:
        return f"待补{label}内且带可核验日期的中国进口记录、提单或明确进口报道"
    return f"待补{label}内的中国进口记录、提单或中国供应商证据"


async def _extract_research_targets(
    sources: list[dict[str, Any]], countries: list[str], model: Any,
    expert_prompt: str = "",
) -> list[dict[str, Any]]:
    """Turn first-round results into auditable entity aliases and edge targets."""
    if not sources:
        return []
    allowed_urls = {item["url"] for item in sources}
    payload = sorted(sources, key=_source_priority)[:60]
    prompt = f"""
【供应链专家长期指令】
{expert_prompt}

【当前阶段：实体与调查目标抽取】
从下列第一轮互联网搜索结果中抽取下一轮供应链调查目标。只抽取来源中明确出现的企业、别名、地址、产品/料号、合同号和贸易对手，不得推测。
不要把国防部、军种、海关、政府采购机关当成进口企业。目标国企业从中国采购时，目标国企业是 defense_importer，中国企业是 china_exporter。
trade_counterparties 只能来自提单、海关、贸易数据库或明确进出口报道；合同甲方、采购机关和最终用户不能填入 trade_counterparties。

目标国家：{json.dumps(countries, ensure_ascii=False)}
搜索结果：{json.dumps(payload, ensure_ascii=False)}

只返回 JSON 数组，每项字段：country, company_name, aliases, role（defense_importer|china_exporter|unknown）, address, products, contract_refs, trade_counterparties, source_urls。
source_urls 只能使用搜索结果中的 url；没有来源 URL 的实体不要返回。
""".strip()
    try:
        result = await call_llm(model, prompt, timeout_seconds=180, minimum_content_length=2)
    except Exception:
        return []
    targets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in _extract_json_array(result["content"]):
        country = item.get("country")
        name = item.get("company_name")
        role = item.get("role")
        source_urls = [url for url in _string_values(item.get("source_urls")) if url in allowed_urls]
        if (
            country not in countries or not isinstance(name, str) or not name.strip()
            or role not in {"defense_importer", "china_exporter", "unknown"} or not source_urls
        ):
            continue
        if role == "defense_importer" and _is_government_agency({"importer_name": name}):
            continue
        key = (country, _normalized_entity_text(name), role)
        if key in seen:
            continue
        seen.add(key)
        targets.append({
            "country": country, "company_name": name.strip(),
            "aliases": _string_values(item.get("aliases"))[:8], "role": role,
            "address": str(item.get("address") or "")[:300],
            "products": _string_values(item.get("products"))[:8],
            "contract_refs": _string_values(item.get("contract_refs"))[:8],
            "trade_counterparties": [
                value for value in _string_values(item.get("trade_counterparties"))
                if not _is_government_agency({"importer_name": value})
            ][:8],
            "source_urls": source_urls[:8],
        })
    return targets[:30]


def _target_followups(
    targets: list[dict[str, Any]], round_number: int,
) -> list[dict[str, str]]:
    """Build Codex-style edge queries from names found in the preceding evidence."""
    followups: list[dict[str, str]] = []
    for target in targets:
        if target.get("role") != "defense_importer":
            continue
        country = str(target.get("country") or "")
        locale = COUNTRY_LOCALES.get(country, ("en-US",))[0]
        name = str(target.get("company_name") or "").strip()
        if not name:
            continue
        if round_number == 2:
            followups.extend([
                {
                    "query": f'site:importgenius.com/importers "{name}"', "mode": "web",
                    "locale": locale, "country": country,
                    "gap": "补进口商、最近提单日期、中国出口商、货物和提单号",
                },
                {
                    "query": f'"{name}" defense contract award official', "mode": "web",
                    "locale": locale, "country": country,
                    "gap": "补目标企业军工合同或项目原始来源",
                },
            ])
            for counterparty in _string_values(target.get("trade_counterparties"))[:2]:
                followups.append({
                    "query": f'"{name}" "{counterparty}" shipment bill of lading', "mode": "web",
                    "locale": locale, "country": country,
                    "gap": "用已识别贸易双方反查批次记录",
                })
        else:
            refs = _string_values(target.get("contract_refs"))
            products = _string_values(target.get("products"))
            if refs:
                followups.append({
                    "query": f'"{refs[0]}" "{name}" official contract', "mode": "pdf",
                    "locale": locale, "country": country, "gap": "按合同号补原始文件",
                })
            if products:
                followups.append({
                    "query": f'"{name}" "{products[0]}" civilian commercial application', "mode": "web",
                    "locale": locale, "country": country,
                    "gap": "反证排查：同类进口货物是否进入民用业务线",
                })
            followups.append({
                "query": f'"{name}" China supply chain investigation audit report', "mode": "web",
                "locale": locale, "country": country,
                "gap": "查找已有供应链调查、审计或专题报告",
            })
    return followups


def _fair_country_limit(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(row.get("country") or "unknown", []).append(row)
    output: list[dict[str, str]] = []
    while len(output) < limit and any(groups.values()):
        for country in list(groups):
            if groups[country] and len(output) < limit:
                output.append(groups[country].pop(0))
    return output


def qualify_candidates(
    content: str,
    allowed_urls: set[str],
    countries: set[str],
    *,
    allow_partial: bool = False,
    source_records: list[dict[str, Any]] | None = None,
    import_record_window_days: int | None = None,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    as_of = (as_of or datetime.now(timezone.utc)).astimezone(timezone.utc)
    source_map = {
        _url_key(str(source.get("url") or "")): source
        for source in (source_records or []) if source.get("url")
    }
    qualified = []
    for item in _extract_json_array(content):
        contract_url = _resolve_allowed_url(item.get("contract_evidence_url"), allowed_urls)
        trade_url = _resolve_allowed_url(item.get("trade_evidence_url"), allowed_urls)
        validations: dict[str, Any] = {}
        if source_records is not None:
            contract_check = _contract_validation(
                item, contract_url, source_map.get(_url_key(contract_url)) if contract_url else None,
            )
            trade_check = _trade_validation(
                item, trade_url, source_map.get(_url_key(trade_url)) if trade_url else None,
                as_of=as_of, import_record_window_days=import_record_window_days or 365,
            )
            validations = {"contract": contract_check, "trade": trade_check}
            if not contract_check["valid"]:
                contract_url = None
            if not trade_check["valid"]:
                trade_url = None
        country = item.get("country")
        required = [item.get("importer_name"), item.get("product")]
        if not allow_partial:
            required.extend([item.get("exporter_name"), item.get("contract_title")])
        if country not in countries or not all(
            isinstance(value, str) and value.strip() for value in required
        ):
            continue
        if not contract_url and not trade_url:
            continue
        if not allow_partial and (not contract_url or not trade_url):
            continue
        if contract_url and trade_url and contract_url == trade_url:
            trade_url = None
            if not allow_partial:
                continue
        supporting = [
            resolved for url in item.get("supporting_urls", [])
            if (resolved := _resolve_allowed_url(url, allowed_urls))
        ]
        exporter_name = item.get("exporter_name") or "待识别中国供应商"
        contract_title = item.get("contract_title") or "待核实国防合同或项目"
        evidence_status = "closed" if contract_url and trade_url else (
            "contract_only" if contract_url else "trade_only"
        )
        trade_reason = str((validations.get("trade") or {}).get("reason") or "")
        verified_trade_date = (validations.get("trade") or {}).get("trade_date")
        qualified.append({
            **item,
            "exporter_name": exporter_name,
            "contract_title": contract_title,
            "contract_evidence_url": contract_url,
            "trade_evidence_url": trade_url,
            "trade_date": verified_trade_date or item.get("trade_date"),
            "contract_date": item.get("contract_date"),
            "evidence_validation": validations,
            "evidence_status": evidence_status,
            "evidence_gap": (
                _trade_gap(trade_reason, import_record_window_days or 365) if evidence_status == "contract_only"
                else "待补军工合同、采购项目或最终用途证据" if evidence_status == "trade_only"
                else ""
            ),
            "supporting_urls": list(dict.fromkeys(supporting)),
        })
    return qualified


async def discover_online_supply_chains(
    countries: list[str], tools: list[str], model: Any, max_candidates: int,
    research_rounds: int = 3,
    import_record_window_days: int = 365,
    expert_prompt: str = "",
    prompt_template_id: str | None = None,
    search_configs: list[Any] | None = None,
) -> dict[str, Any]:
    as_of = datetime.now(timezone.utc)
    trade_cutoff = as_of - timedelta(days=import_record_window_days)
    modes: list[tuple[str, type]] = []
    if "broad_web_search" in tools or "search_supply_chain_trade_records" in tools:
        modes.append(("web", BroadWebSearchCollector))
    deep_trade_enabled = "deep_search_china_trade_records" in tools
    if "multilingual_news_search" in tools or deep_trade_enabled:
        modes.append(("news", NewsRSSSearchCollector))
    if "official_pdf_search" in tools or "search_supply_chain_contracts" in tools:
        modes.append(("pdf", PDFSearchCollector))
    if not modes:
        modes = [("web", BroadWebSearchCollector), ("pdf", PDFSearchCollector)]

    searches = []
    for country in countries:
        base_queries = _queries(
            country, as_of=as_of, import_record_window_days=import_record_window_days,
        )
        contract_queries = [
            query for query in base_queries
            if any(term in _query_text(query).casefold() for term in DEFENSE_CONTRACT_TERMS)
        ]
        country_queries = base_queries
        if deep_trade_enabled:
            country_queries = [
                *base_queries[:2], *contract_queries[:8],
                *_deep_china_trade_queries(
                    country, as_of=as_of,
                    import_record_window_days=import_record_window_days,
                )[:24],
            ]
        for mode, collector_type in modes:
            collector = collector_type(_collector_config(mode))
            mode_queries = (
                contract_queries[:14] if mode == "pdf"
                else base_queries[:24] if mode == "news"
                else country_queries[:34]
            )
            searches.append((
                country, mode,
                collector.fetch(mode_queries, 50 if deep_trade_enabled else 24),
            ))
    responses = await asyncio.gather(*(task for _, _, task in searches), return_exceptions=True)

    sources: list[dict[str, Any]] = []
    errors: list[str] = []
    for (country, mode, _), response in zip(searches, responses):
        if isinstance(response, Exception):
            errors.append(f"{country}/{mode}: {response}")
            continue
        errors.extend(response.error_log or [])
        for item in response.items:
            if item.url and item.url.startswith(("http://", "https://")):
                sources.append({
                    "country_hint": country, "mode": mode, "title": item.title,
                    "url": item.url, "summary": item.summary or "",
                    "published_at": item.published_at, "language": item.language,
                    "search_locale": (item.raw_metadata or {}).get("search_locale"),
                    "search_query": (item.raw_metadata or {}).get("query"),
                    "search_engine": (item.raw_metadata or {}).get("engine"),
                })

    initial_trade_records = _extract_structured_trade_records(
        sources, countries, as_of=as_of,
        import_record_window_days=import_record_window_days,
    )
    configured_searches = []
    if search_configs and (
        deep_trade_enabled or "broad_web_search" in tools
    ):
        for config in search_configs:
            for country in countries:
                provider_queries = _configured_provider_queries(
                    country, initial_trade_records, as_of=as_of,
                    import_record_window_days=import_record_window_days,
                )
                if provider_queries:
                    configured_searches.append((
                        country, str(config.id),
                        TavilyCollector(config).fetch(
                            provider_queries, max(12, len(provider_queries) * 4),
                        ),
                    ))
    configured_responses = await asyncio.gather(
        *(task for _, _, task in configured_searches), return_exceptions=True,
    )
    for (country, provider_id, _), response in zip(configured_searches, configured_responses):
        if isinstance(response, Exception):
            errors = [*errors, f"{country}/{provider_id}: {type(response).__name__}: {response}"]
            continue
        errors = [
            *errors,
            *[f"{country}/{provider_id}: {error}" for error in (response.error_log or [])],
        ]
        sources = [
            *sources,
            *[
                {
                    "country_hint": country,
                    "mode": "configured_search",
                    "title": item.title,
                    "url": item.url,
                    "summary": item.summary or "",
                    "content": str(item.content or "")[:8000],
                    "published_at": item.published_at,
                    "language": item.language,
                    "search_query": (item.raw_metadata or {}).get("query"),
                    "search_engine": (item.raw_metadata or {}).get("engine") or provider_id,
                }
                for item in response.items
                if item.url and item.url.startswith(("http://", "https://"))
            ],
        ]

    unique_sources = _merge_source_records(sources)
    model_research_targets = await _extract_research_targets(
        unique_sources, countries, model, expert_prompt,
    )
    direct_trade_sources: list[dict[str, Any]] = []
    if deep_trade_enabled:
        discovered_keys = {
            (item["country"], _normalized_entity_text(item["company_name"]))
            for item in model_research_targets
        }
        probe_targets = [
            *model_research_targets,
            *[
                item for item in _seed_research_targets(countries)
                if (item["country"], _normalized_entity_text(item["company_name"]))
                not in discovered_keys
            ],
        ]
        direct_trade_sources, direct_trade_errors = await _probe_public_trade_indexes(
            countries, probe_targets, as_of=as_of,
            import_record_window_days=import_record_window_days,
        )
        sources = [*sources, *direct_trade_sources]
        errors = [*errors, *direct_trade_errors]
        unique_sources = _merge_source_records(sources)

    initial_trade_records = _extract_structured_trade_records(
        unique_sources, countries, as_of=as_of,
        import_record_window_days=import_record_window_days,
    )
    signal_sets = _signal_sets(unique_sources)
    deterministic_targets = _trade_record_targets(initial_trade_records)
    model_target_keys = {
        (item["country"], _normalized_entity_text(item["company_name"]), item["role"])
        for item in model_research_targets
    }
    research_targets = [
        *model_research_targets,
        *[
            item for item in deterministic_targets
            if (item["country"], _normalized_entity_text(item["company_name"]), item["role"])
            not in model_target_keys
        ],
    ]
    collector_types = {
        "web": BroadWebSearchCollector,
        "news": NewsRSSSearchCollector,
        "pdf": PDFSearchCollector,
    }
    round_traces: list[dict[str, Any]] = []
    all_followups: list[dict[str, Any]] = []
    followup_limit = min(16, max(8, len(countries) * 4))
    for round_number in range(2, research_rounds + 1):
        planning_prompt = f"""
【供应链专家长期指令】
{expert_prompt}

【当前阶段：第 {round_number} 轮补证规划】
你是供应链调查代理。当前是第 {round_number} 轮（共 {research_rounds} 轮）。
根据已有互联网搜索摘要和已抽取调查实体识别证据缺口，并规划最多 {followup_limit} 条精确查询。
目标是分别找到：国防合同或政府采购证据、中国出口或目标企业进口证据、企业别名、合同号、提单号、料号，以及已有调查或审计报告。
合同可以早于贸易记录；贸易记录日期或明确报道“自中国进口”的发布日期必须在 {trade_cutoff.date().isoformat()} 至 {as_of.date().isoformat()} 之间。
贸易流向只能是“中国出口商 → 目标国家进口企业”，不得把政府采购机关当作进口企业，也不得把目标国企业向中国出口误写成自中国进口。
印度方向同时使用英语和印地语，日本方向同时使用日语和英语，中国台湾方向同时使用繁体中文和英语；补证查询应保留来源原语种。
目标国家：{json.dumps(countries, ensure_ascii=False)}
已抽取的企业、别名、产品、合同号和贸易对手：{json.dumps(research_targets, ensure_ascii=False)}
已有结果：{json.dumps(unique_sources[-50:], ensure_ascii=False)}

只返回 JSON 数组，每项格式：
{{"query":"精确查询词","mode":"web|news|pdf","locale":"en-US|en-IN|hi-IN|ja-JP|zh-TW","country":"目标国家英文值","gap":"要补的证据缺口"}}
不要重复宽泛查询。优先组合公司名、项目名、合同号、产品名、report/audit/investigation 和 site:官方域名。
""".strip()
        planned_followups: list[dict[str, str]] = []
        try:
            plan_result = await call_llm(
                model, planning_prompt, timeout_seconds=180,
                minimum_content_length=2,
            )
            for item in _extract_json_array(plan_result["content"]):
                query, mode = item.get("query"), item.get("mode")
                if isinstance(query, str) and len(query.strip()) >= 8 and mode in collector_types:
                    locale = item.get("locale")
                    if locale not in {"en-US", "en-IN", "hi-IN", "ja-JP", "zh-TW"}:
                        locale = COUNTRY_LOCALES.get(str(item.get("country") or ""), ("en-US",))[0]
                    planned_followups.append({
                        "query": query.strip(), "mode": mode,
                        "locale": locale, "country": str(item.get("country") or ""),
                        "gap": str(item.get("gap") or ""),
                    })
        except Exception as exc:
            errors.append(f"round {round_number} planning: {exc}")
        deterministic = _fair_country_limit(
            _target_followups(research_targets, round_number), followup_limit // 2,
        )
        followups: list[dict[str, str]] = []
        seen_queries: set[tuple[str, str]] = set()
        for item in [*deterministic, *planned_followups]:
            key = (item["mode"], re.sub(r"\s+", " ", item["query"].casefold()).strip())
            if key in seen_queries:
                continue
            seen_queries.add(key)
            followups.append(item)
            if len(followups) >= followup_limit:
                break
        all_followups.extend({**item, "round": round_number} for item in followups)
        tasks = [
            collector_types[item["mode"]](_collector_config(item["mode"])).fetch(
                [_locale_query(item["locale"], item["query"])], 10,
            )
            for item in followups
        ]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        before = len(unique_sources)
        for item, response in zip(followups, responses):
            if isinstance(response, Exception):
                errors.append(f"round {round_number}/{item['mode']}: {response}")
                continue
            errors.extend(response.error_log or [])
            for result_item in response.items:
                if result_item.url and result_item.url.startswith(("http://", "https://")):
                    sources.append({
                        "country_hint": item.get("country") or "follow_up", "mode": item["mode"],
                        "title": result_item.title, "url": result_item.url,
                        "summary": result_item.summary or "", "evidence_gap": item["gap"],
                        "research_round": round_number,
                        "published_at": result_item.published_at,
                        "language": result_item.language,
                        "search_locale": (result_item.raw_metadata or {}).get("search_locale"),
                        "search_query": (result_item.raw_metadata or {}).get("query"),
                        "search_engine": (result_item.raw_metadata or {}).get("engine"),
                    })
        unique_sources = _merge_source_records(sources)
        signal_sets = _signal_sets(unique_sources)
        if round_number < research_rounds:
            new_targets = await _extract_research_targets(
                unique_sources, countries, model, expert_prompt,
            )
            target_keys = {
                (item["country"], _normalized_entity_text(item["company_name"]), item["role"])
                for item in research_targets
            }
            for target in new_targets:
                key = (
                    target["country"], _normalized_entity_text(target["company_name"]), target["role"],
                )
                if key not in target_keys:
                    research_targets.append(target)
                    target_keys.add(key)
        round_traces.append({
            "round": round_number, "queries": followups,
            "new_sources": len(unique_sources) - before,
            "research_targets": len(research_targets),
        })

    semaphore = asyncio.Semaphore(6)

    async def enrich(source: dict[str, Any]) -> dict[str, Any]:
        if source.get("content"):
            return source
        async with semaphore:
            try:
                document = await read_document(source["url"])
                text = document.get("text") or document.get("content") or ""
                return {**source, "content": str(text)[:8000]}
            except Exception as exc:
                return {**source, "content": "", "read_error": str(exc)}

    # Prefer readable HTML/news with snippets; PDFs remain in the mix but no longer
    # crowd out every source when publishers block automated PDF retrieval.
    ranked = sorted(unique_sources, key=_source_priority)[:40]
    enriched = await asyncio.gather(*(enrich(source) for source in ranked))
    enriched_by_url = {item["url"]: item for item in enriched}
    evidence_source_records = [
        enriched_by_url.get(item["url"], item) for item in unique_sources
    ]
    deterministic_trade_records = _extract_structured_trade_records(
        evidence_source_records, countries, as_of=as_of,
        import_record_window_days=import_record_window_days,
    )
    deterministic_trade_records = _attach_deterministic_contract_evidence(
        deterministic_trade_records, evidence_source_records,
    )
    evidence_payload = [
        {key: value for key, value in source.items() if key != "read_error"}
        for source in enriched
    ]
    prompt = f"""
【供应链专家长期指令】
{expert_prompt}

【当前阶段：候选供应链证据审核】
你是供应链开源情报分析员。只能依据下面本次互联网搜索及原文读取结果提取线索，不得编造公司、合同号、提单号、产品或 URL。

需要识别两类证据：
1. 合同证据：政府、军方、主承包商或可信官方材料，证明目标企业获得国防合同或进入军工项目；
2. 贸易证据：贸易记录、提单索引、企业披露或可信报道，证明目标企业从中国进口相关产品。

优先返回两类证据均已找到且 URL 不同的完整链。如果目前只找到其中一类，也必须作为待补证线索返回，另一类 URL 填 null，并在 limitations 中说明缺口。只有合同证据时，exporter_name 可填 null；只有贸易证据时，contract_title 可填 null。不得声称具体批次进入武器装备，除非来源直接证明。

时间规则：合同或军工项目可以早于进口记录，不因合同较早而丢弃；但贸易证据必须给出 trade_date，且日期在 {trade_cutoff.date().isoformat()} 至 {as_of.date().isoformat()} 之间。若证据是明确报道目标企业“自中国进口”，trade_date_basis 填 report_publication，并使用该报道发布日期；若是提单/海关记录，填 shipment_record，并使用运输或报关日期。缺少可核验日期的来源不能作为贸易证据。

角色规则：importer_name 必须是获得军工合同且接收中国货物的企业，不能是国防部、军种、海关或其他采购机关；exporter_name 必须是中国出口商。必须确认流向为“中国出口商 → 目标国家进口企业”，不得把目标企业向中国出口、在中国销售、泛称中国供应链或仅有中国关键词的报道算作进口证据。

目标国家：{json.dumps(countries, ensure_ascii=False)}
最多返回：{max_candidates}
中国来源信号集：{json.dumps(signal_sets['china_trade_signals'], ensure_ascii=False)}
军事用途信号集：{json.dumps(signal_sets['military_use_signals'], ensure_ascii=False)}
可读取的检索证据：{json.dumps(evidence_payload, ensure_ascii=False)}
程序已从公开贸易表格逐字段抽取并校验的近期记录：{json.dumps(deterministic_trade_records, ensure_ascii=False)}

按三条路径发现新链：
A. 贸易优先：从 2026 年中国出口、目标企业进口、提单或供应商记录反查进口企业的军工合同；
B. 军事优先：从军方合同、政府采购和主承包商名单反查其中国供应商与进口记录；
C. 桥接发现：用企业法定名称/别名、地址、产品型号/料号、合同与运输时间窗做跨来源交叉。

逐边验证：分别检查“中国企业→进口企业”和“进口企业→军事项目”。排查同名企业、经销商转售、贸易日期超出所选窗口、产品过于宽泛、新闻转述无原始来源等反证。合同与近期进口记录不要求在同一年；如果合同仍在履约、续约或证明该企业长期承担该军工项目，可以与近期进口事实形成候选，但不得据此声称具体批次已进入装备。完整链必须有两个独立 URL；单边线索只能标为待补证，不得表述为已闭合。

产品、合同标题、项目名称等描述字段必须使用中文。企业名称保留来源中的英文法定名称，后续展示层会转换为“中文名（英文原名）”。
只返回 JSON 数组。每项字段：
country, importer_name, exporter_name, product, contract_title, contracting_agency,
importer_aliases, exporter_aliases, target_program, contract_reference, contract_date,
contract_excerpt, contract_evidence_url, trade_reference, trade_date, trade_date_basis,
trade_excerpt, trade_evidence_url, supporting_urls,
confidence_score（完整链 60-95，单类证据 45-75）, limitations（字符串数组）。
所有 URL 必须来自检索证据中的 url 字段。
程序确定性记录中的进口商、出口商、产品、提单号和日期不得遗漏或改写；找不到合同证据时也要原样返回为单边待补证线索。
""".strip()
    allowed_urls = {item["url"] for item in unique_sources}
    try:
        result = await call_llm(
            model, prompt, timeout_seconds=240, minimum_content_length=2,
        )
        model_content = result["content"]
    except Exception as exc:
        errors = [*errors, f"candidate review: {type(exc).__name__}: {exc}"]
        model_content = "[]"
    model_candidates = qualify_candidates(
        model_content, allowed_urls, set(countries), allow_partial=True,
        source_records=evidence_source_records,
        import_record_window_days=import_record_window_days,
        as_of=as_of,
    )
    deterministic_candidates = qualify_candidates(
        json.dumps(deterministic_trade_records, ensure_ascii=False),
        allowed_urls, set(countries), allow_partial=True,
        source_records=evidence_source_records,
        import_record_window_days=import_record_window_days,
        as_of=as_of,
    )
    candidates = _merge_candidate_evidence(
        model_candidates, deterministic_candidates, limit=max_candidates,
    )
    candidates = await _localize_candidates(candidates, model)
    return {
        "candidates": candidates,
        "sources_found": len(unique_sources),
        "sources_read": sum(1 for item in enriched if item.get("content")),
        "errors": errors,
        "research_trace": {
            "configured_rounds": research_rounds,
            "initial_searches": len(searches),
            "configured_searches": len(configured_searches),
            "configured_search_providers": [
                str(config.id) for config in (search_configs or [])
            ],
            "follow_up_queries": all_followups,
            "rounds": round_traces,
            "sources_found": len(unique_sources),
            "sources_read": sum(1 for item in enriched if item.get("content")),
            "method": "multi_round_online_evidence_research",
            "prompt_template_id": prompt_template_id,
            "discovery_paths": ["trade_to_defense", "defense_to_trade", "identity_product_time_bridge"],
            "trade_year_priority": 2026,
            "as_of_date": as_of.date().isoformat(),
            "import_record_window_days": import_record_window_days,
            "import_record_cutoff": trade_cutoff.date().isoformat(),
            "contract_time_policy": "合同可早于贸易记录；近期贸易事实仍需单独验证",
            "search_locales": sorted({
                item.get("search_locale") for item in unique_sources if item.get("search_locale")
            }),
            "research_targets": research_targets,
            "deep_china_trade_search": deep_trade_enabled,
            "direct_trade_index_sources": len(direct_trade_sources),
            "structured_trade_records": len(deterministic_trade_records),
            "china_trade_signal_count": len(signal_sets["china_trade_signals"]),
            "military_use_signal_count": len(signal_sets["military_use_signals"]),
            "candidate_threshold": "双源闭合优先；单边强来源仅作为C级待补证线索",
        },
    }
