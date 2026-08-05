"""LLM gate for overseas customs enforcement intelligence."""
from __future__ import annotations

import json
import logging
import asyncio
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.connectors.base import FetchItem
from app.llm_client import call_llm
from app.models import ModelConfig

logger = logging.getLogger(__name__)
QUEUE_FILE = Path(__file__).resolve().parents[2] / "data" / "enforcement_review_queue.json"
REVIEW_SEMAPHORE = asyncio.Semaphore(1)
REVIEW_BATCH_SIZE = 2
MAX_REVIEW_CANDIDATES = 45
REVIEW_RETRY_DELAYS = (12, 24)


def _write_queue(records: list[dict]) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if QUEUE_FILE.exists():
        try:
            existing = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read enforcement review queue; creating a new queue")
    existing.extend(records)
    QUEUE_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


async def review_enforcement_candidates(
    items: list[FetchItem], model: ModelConfig | None,
) -> list[FetchItem]:
    """Return model-approved items and keep every candidate for traceability."""
    items = prioritize_enforcement_candidates(items, MAX_REVIEW_CANDIDATES)
    if not items:
        return []

    now = datetime.now(timezone.utc).isoformat()
    records = [{
        "title": item.title,
        "url": item.url,
        "published_at": item.published_at,
        "content": (item.content or item.summary or "")[:1800],
        "source_metadata": item.raw_metadata or {},
        "queued_at": now,
        "status": "pending_model",
        "review": None,
    } for item in items]

    if not model or not model.is_active or not model.api_key:
        _write_queue(records)
        return []

    prompt_prefix = """You review candidates for an overseas customs enforcement weekly report.
Use two decisions only:
- approve: a concrete overseas enforcement action is clear, the publication date is supportable, and one of the inclusion routes below is met;
- reject: policy commentary, generic trade news, no concrete enforcement action, obvious mainland-China enforcement, an unreliable/reposted source, or an unverified date.

The overseas authority may be customs, border, police, prosecutors, courts, port authorities, or another official enforcement body outside mainland China. Apply these inclusion routes:
1) strong_china_nexus: the source explicitly connects the case to mainland China through origin/destination, shipment or transit route, a PRC/Chinese national, a mainland Chinese company/exporter/importer, or another direct case-specific relationship.
2) weak_china_nexus: the source supports a broader but still case-specific China relationship, such as Chinese-made/China-origin goods, a Chinese product or brand involved in the seized shipment, a route through Hong Kong/Macao/Taiwan, or an official Hong Kong/Macao/Taiwan enforcement case. Do not classify a case as weak merely because the page is in Chinese.
3) major_enforcement: a major cross-border case involving firearms, ammunition, explosives, weapons, violent crime, drugs, narcotics, regulated medicines or pharmaceuticals, wildlife, endangered species, tobacco, counterfeit goods, high-value smuggled cargo, or other serious contraband. It may be included without a China nexus when the source supports a concrete customs/border action and a meaningful quantity, value, arrest, prosecution, or organized-crime dimension.
For this report, "overseas" means outside mainland China. An Australian, Brazilian, Canadian, or other foreign authority acting inside its own country is still overseas enforcement and must not be rejected merely because the action was domestic to that authority.
For every approval, copy a short exact source quote supporting the enforcement action into evidence_quote. For strong or weak China nexus, also copy the exact case-specific China relationship into mainland_nexus_evidence. For major_enforcement, prefer a quote containing the action and contraband type, quantity, value, arrest, or prosecution. Quotes must come from the supplied title/content and must not be invented. Set inclusion_basis to strong_china_nexus, weak_china_nexus, or major_enforcement. Prefer a China-nexus route over major_enforcement whenever the source supports one. If no exact supporting quote can be copied, reject.
For approved cases also identify:
- jurisdiction: standardized country or region name;
- authority: the overseas customs, border, police, prosecution, court or port authority;
- case_type: drugs, firearms, wildlife, tobacco, counterfeit, trade compliance, export control, or other;
- subject: the people, company, shipment or goods acted upon;
- source_name: the publishing authority or media outlet.
Return JSON only: {"decisions":[{"index":0,"decision":"approve|reject","confidence":0-100,"basis":"short Chinese evidence-based reason","inclusion_basis":"strong_china_nexus|weak_china_nexus|major_enforcement","evidence_quote":"exact action quote or empty","mainland_nexus_evidence":"exact China-nexus quote or empty","enforcement_action":"...","jurisdiction":"...","authority":"...","case_type":"...","subject":"...","source_name":"..."}]}.
"""

    indexed_items = list(enumerate(items))
    batches = [
        indexed_items[offset:offset + REVIEW_BATCH_SIZE]
        for offset in range(0, len(indexed_items), REVIEW_BATCH_SIZE)
    ]
    batch_results = await asyncio.gather(
        *[_review_batch(model, prompt_prefix, batch) for batch in batches],
        return_exceptions=True,
    )
    decisions: list[dict] = []
    for batch, batch_result in zip(batches, batch_results):
        if isinstance(batch_result, Exception):
            logger.warning(
                "Enforcement review batch unavailable; retrying %d candidates individually: %s",
                len(batch), batch_result,
            )
            for candidate in batch:
                try:
                    decisions.extend(
                        await _review_batch(model, prompt_prefix, [candidate])
                    )
                except Exception as exc:
                    logger.warning(
                        "Enforcement review candidate remains queued (%s): %s",
                        candidate[1].title[:80],
                        exc,
                    )
            continue
        decisions.extend(batch_result)

    approved: list[FetchItem] = []
    for decision in decisions:
        index = decision.get("index")
        if not isinstance(index, int) or not 0 <= index < len(items):
            continue
        records[index]["review"] = decision
        normalized = decision.get("decision", "reject")
        if normalized not in {"approve", "reject"}:
            normalized = "reject"
        records[index]["status"] = normalized
        decision["decision"] = normalized
        if decision.get("decision") == "approve" and int(decision.get("confidence", 0)) >= 75:
            source_text = " ".join(
                str(value or "") for value in (items[index].title, items[index].content, items[index].summary)
            )
            basis = str(decision.get("inclusion_basis") or "").strip()
            nexus_evidence = str(
                decision.get("mainland_nexus_evidence") or ""
            ).strip()
            if not nexus_evidence:
                nexus_evidence = _extract_china_nexus_evidence(source_text)
                if nexus_evidence:
                    decision["mainland_nexus_evidence"] = nexus_evidence
            evidence = str(decision.get("evidence_quote") or "").strip()
            if basis in {
                "strong_china_nexus", "weak_china_nexus", "mainland_nexus",
                "regional_jurisdiction",
            }:
                evidence = nexus_evidence or evidence
            verified_basis = _resolve_verifiable_inclusion(
                items[index], source_text, evidence, basis
            )
            if not verified_basis:
                decision["decision"] = "reject"
                decision["basis"] = "原文未提供可核验的港澳台、涉中国大陆或重大跨境执法证据"
                records[index]["status"] = "reject"
                records[index]["review"] = decision
                continue
            decision["inclusion_basis"] = verified_basis
            relevance_level = _china_relevance_level(
                items[index], source_text, nexus_evidence, verified_basis,
            )
            decision["china_relevance_level"] = relevance_level
            decision["china_relevance_label"] = {
                "strong": "强涉华关联",
                "weak": "弱涉华关联",
                "major_non_china": "重大案件（不涉华）",
            }[relevance_level]
            metadata = dict(items[index].raw_metadata or {})
            decision["jurisdiction"] = (
                str(decision.get("jurisdiction") or "").strip()
                or infer_enforcement_jurisdiction(items[index])
            )
            decision["source_domain"] = urlparse(items[index].url or "").netloc.casefold()
            metadata["enforcement_review"] = decision
            items[index].raw_metadata = metadata
            approved.append(items[index])
    _write_queue(records)
    return approved


async def _review_batch(
    model: ModelConfig,
    prompt_prefix: str,
    batch: list[tuple[int, FetchItem]],
) -> list[dict]:
    prompt = prompt_prefix + "\nCANDIDATES:\n" + json.dumps([
        {
            "index": index,
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at,
            "content": (item.content or item.summary or "")[:1500],
            "search_jurisdiction": (
                item.raw_metadata.get("search_jurisdiction")
                if isinstance(item.raw_metadata, dict) else None
            ),
        }
        for index, item in batch
    ], ensure_ascii=False)
    async with REVIEW_SEMAPHORE:
        for attempt in range(len(REVIEW_RETRY_DELAYS) + 1):
            try:
                response = await asyncio.wait_for(
                    call_llm(
                        model,
                        prompt,
                        max_tokens_override=3000,
                        timeout_seconds=150,
                    ),
                    timeout=160,
                )
                await asyncio.sleep(3)
                break
            except Exception as exc:
                if attempt >= len(REVIEW_RETRY_DELAYS) or not _is_rate_limit(exc):
                    raise
                delay = REVIEW_RETRY_DELAYS[attempt]
                logger.warning(
                    "Enforcement review rate limited; retrying in %d seconds",
                    delay,
                )
                await asyncio.sleep(delay)
    text = str(response.get("content") or "").strip()
    if "```" in text:
        text = text.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(text)
    decisions = parsed.get("decisions", []) if isinstance(parsed, dict) else []
    return [decision for decision in decisions if isinstance(decision, dict)]


def prioritize_enforcement_candidates(
    items: list[FetchItem],
    max_items: int = MAX_REVIEW_CANDIDATES,
    existing_counts: dict[str, int] | None = None,
) -> list[FetchItem]:
    """Round-robin candidates by jurisdiction before the model sees them."""
    groups: dict[str, list[FetchItem]] = {}
    seen: set[str] = set()
    for item in items:
        if not _is_allowed_overseas_candidate(item):
            continue
        key = (item.url or item.title or "").strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        jurisdiction = infer_enforcement_jurisdiction(item)
        bucket = groups.setdefault(jurisdiction, [])
        per_jurisdiction_limit = 8 if jurisdiction != "Unknown" else 5
        if len(bucket) < per_jurisdiction_limit:
            bucket.append(item)

    for bucket in groups.values():
        bucket.sort(key=_candidate_review_priority, reverse=True)

    ordered: list[FetchItem] = []
    jurisdictions = list(groups)
    if existing_counts is not None:
        jurisdictions.sort(
            key=lambda jurisdiction: (
                existing_counts.get(jurisdiction, 0),
                jurisdiction == "Unknown",
            )
        )
    while jurisdictions and len(ordered) < max_items:
        next_round: list[str] = []
        for jurisdiction in jurisdictions:
            bucket = groups[jurisdiction]
            if bucket:
                ordered.append(bucket.pop(0))
                if len(ordered) >= max_items:
                    break
            if bucket:
                next_round.append(jurisdiction)
        jurisdictions = next_round
    return ordered


def _candidate_review_priority(item: FetchItem) -> tuple[int, int, float]:
    text = " ".join(
        str(value or "") for value in (item.title, item.content, item.summary)
    )
    return (
        int(_has_concrete_action_evidence(text))
        + int(_has_major_enforcement_evidence(text)),
        int(bool(re.search(r"\b\d+(?:[.,]\d+)?\b", text))),
        float(item.relevance_score or 0),
    )


def infer_enforcement_jurisdiction(item: FetchItem) -> str:
    metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
    review = metadata.get("enforcement_review")
    reviewed = (
        str(review.get("jurisdiction") or "").strip()
        if isinstance(review, dict) else ""
    )
    if reviewed:
        return reviewed
    planned = str(metadata.get("search_jurisdiction") or "").strip()
    if planned:
        return planned

    host = urlparse((item.url or "").strip()).netloc.casefold()
    host_markers = (
        ("gov.hk", "Hong Kong"), ("gov.mo", "Macao"), ("gov.tw", "Taiwan"),
        ("cbp.gov", "United States"), ("canada.ca", "Canada"),
        ("customs.govt.nz", "New Zealand"), ("abf.gov.au", "Australia"),
        ("customs.gov.ph", "Philippines"), ("customs.gov.sg", "Singapore"),
        ("douane.gouv.fr", "France"), ("gov.br", "Brazil"),
        ("aduana.cl", "Chile"), ("dian.gov.co", "Colombia"),
        ("sunat.gob.pe", "Peru"), ("kra.go.ke", "Kenya"),
        ("customs.gov.ng", "Nigeria"), ("sars.gov.za", "South Africa"),
    )
    for marker, jurisdiction in host_markers:
        if marker in host:
            return jurisdiction
    return "Unknown"


def enrich_enforcement_review_metadata(item: FetchItem) -> dict | None:
    """Fill structured fields added after older enforcement items were stored."""
    metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
    existing = metadata.get("enforcement_review")
    if not isinstance(existing, dict):
        return None

    review = dict(existing)
    jurisdiction = infer_enforcement_jurisdiction(item)
    authority_by_jurisdiction = {
        "Hong Kong": "Hong Kong Customs and Excise Department",
        "Macao": "Macao Customs Service",
        "Taiwan": "Taiwan Customs Administration",
        "United States": "U.S. Customs and Border Protection",
        "Canada": "Canada Border Services Agency",
        "Australia": "Australian Border Force",
        "New Zealand": "New Zealand Customs Service",
        "Brazil": "Receita Federal do Brasil",
        "Philippines": "Bureau of Customs Philippines",
    }
    text = _normalize_evidence_text(
        " ".join(str(value or "") for value in (
            item.title, item.summary, item.content,
        ))
    )
    case_markers = (
        ("drugs", (
            "drug", "narcotic", "cocaine", "heroin", "meth", "fentanyl",
            "cannabis", "maconha", "毒品", "海洛因", "可卡因", "冰毒", "大麻",
        )),
        ("firearms", (
            "firearm", "weapon", "ammunition", "pistol", "rifle",
            "枪", "武器", "弹药",
        )),
        ("wildlife", (
            "wildlife", "endangered", "animal", "parrot", "turtle", "lizard",
            "濒危", "野生动物", "活龟", "蜥蜴", "动物",
        )),
        ("tobacco", (
            "tobacco", "cigarette", "vape", "私烟", "香烟", "吸烟产品", "电子烟",
        )),
        ("counterfeit", ("counterfeit", "fake goods", "冒牌", "假冒", "侵权")),
        ("currency", ("currency", "cash", "unreported money", "货币", "现金")),
    )
    case_type = next(
        (
            label for label, markers in case_markers
            if any(marker in text for marker in markers)
        ),
        "other",
    )
    host = urlparse((item.url or "").strip()).netloc.casefold()

    review.setdefault("jurisdiction", jurisdiction)
    review.setdefault(
        "authority",
        authority_by_jurisdiction.get(jurisdiction, jurisdiction),
    )
    review.setdefault("case_type", case_type)
    review.setdefault("source_name", review.get("authority"))
    review.setdefault("source_domain", host)
    source_text = " ".join(str(value or "") for value in (
        item.title, item.summary, item.content,
    ))
    nexus_evidence = str(review.get("mainland_nexus_evidence") or "").strip()
    if not nexus_evidence:
        nexus_evidence = _extract_china_nexus_evidence(source_text)
        if nexus_evidence:
            review["mainland_nexus_evidence"] = nexus_evidence
    relevance_level = _china_relevance_level(
        item,
        source_text,
        nexus_evidence,
        str(review.get("inclusion_basis") or ""),
    )
    review.setdefault("china_relevance_level", relevance_level)
    review.setdefault("china_relevance_label", {
        "strong": "强涉华关联",
        "weak": "弱涉华关联",
        "major_non_china": "重大案件（不涉华）",
    }[relevance_level])
    return review


STRONG_CHINA_NEXUS_MARKERS = (
    "mainland china", "chinese mainland", "people s republic of china", "prc",
    "from china", "to china", "destination china", "shipped from china",
    "exported from china", "imported from china", "originating in china",
    "chinese national", "chinese citizen", "chinese company", "china based",
    "china linked logistics", "中国大陆", "中国内地", "中华人民共和国",
    "来自中国", "从中国", "运往中国", "发往中国", "中国籍", "中国公民",
    "中国企业", "中国公司", "经中国转运", "中国港口", "中国路线",
)

WEAK_CHINA_NEXUS_MARKERS = (
    "china origin", "china-origin", "made in china", "chinese made",
    "chinese-made", "chinese goods", "chinese product", "chinese brand",
    "china cargo", "goods of chinese origin", "manufactured in china",
    "hong kong transit", "via hong kong", "macao transit", "via macao",
    "taiwan transit", "via taiwan", "中国产", "中国制造", "中国来源",
    "中国货物", "中国商品", "中国品牌", "中国生产", "香港转运",
    "经香港", "澳门转运", "经澳门", "台湾转运", "经台湾",
)


def _has_verifiable_china_evidence(
    source_text: str, evidence: str, level: str,
) -> bool:
    """Require an exact source quote supporting the requested China relationship."""
    if len(evidence) < 6:
        return False
    normalized_source = _normalize_evidence_text(source_text)
    normalized_evidence = _normalize_evidence_text(evidence)
    if normalized_evidence not in normalized_source:
        return False
    markers = (
        STRONG_CHINA_NEXUS_MARKERS
        if level == "strong"
        else STRONG_CHINA_NEXUS_MARKERS + WEAK_CHINA_NEXUS_MARKERS
    )
    return any(
        _normalize_evidence_text(marker) in normalized_evidence
        for marker in markers
    )


def _has_verifiable_mainland_evidence(source_text: str, evidence: str) -> bool:
    """Backward-compatible verifier for any explicit China nexus."""
    return _has_verifiable_china_evidence(source_text, evidence, "weak")


def _extract_china_nexus_evidence(source_text: str) -> str:
    """Return a short exact source fragment containing a case-specific China marker."""
    text = str(source_text or "").strip()
    if not text:
        return ""
    fragments = [
        fragment.strip()
        for fragment in re.split(r"(?<=[.!?。！？；;])\s*", text)
        if fragment.strip()
    ]
    markers = STRONG_CHINA_NEXUS_MARKERS + WEAK_CHINA_NEXUS_MARKERS
    for fragment in fragments:
        normalized = _normalize_evidence_text(fragment)
        if any(_normalize_evidence_text(marker) in normalized for marker in markers):
            return fragment[:500]
    return ""


def _china_relevance_level(
    item: FetchItem,
    source_text: str,
    nexus_evidence: str,
    inclusion_basis: str,
) -> str:
    """Classify an approved case for portfolio balancing and report display."""
    if nexus_evidence and _has_verifiable_china_evidence(
        source_text, nexus_evidence, "strong",
    ):
        return "strong"
    if (
        nexus_evidence
        and _has_verifiable_china_evidence(source_text, nexus_evidence, "weak")
    ):
        return "weak"
    if inclusion_basis in {"strong_china_nexus", "mainland_nexus"}:
        return "strong"
    if (
        inclusion_basis in {"weak_china_nexus", "regional_jurisdiction"}
        or _is_special_china_jurisdiction(item, source_text)
    ):
        return "weak"
    return "major_non_china"


def infer_candidate_china_relevance(item: FetchItem) -> str:
    """Best-effort pre-review classification used only to order candidates."""
    source_text = " ".join(str(value or "") for value in (
        item.title, item.summary, item.content,
    ))
    evidence = _extract_china_nexus_evidence(source_text)
    if evidence and _has_verifiable_china_evidence(
        source_text, evidence, "strong",
    ):
        return "strong"
    if (
        evidence
        and _has_verifiable_china_evidence(source_text, evidence, "weak")
    ) or _is_special_china_jurisdiction(item, source_text):
        return "weak"
    return "major_non_china"


def _is_special_china_jurisdiction(item: FetchItem, source_text: str) -> bool:
    """Hong Kong, Taiwan, and Macao cases do not require a mainland nexus."""
    host = urlparse((item.url or "").strip()).netloc.casefold()
    if (
        host.endswith(".gov.hk")
        or host.endswith(".gov.tw")
        or host.endswith(".gov.mo")
        or "customs.gov.hk" in host
        or "customs.gov.tw" in host
    ):
        return True
    return infer_enforcement_jurisdiction(item) in {
        "Hong Kong", "Taiwan", "Macao", "Macau",
    }


def _has_major_enforcement_evidence(evidence: str) -> bool:
    normalized = _normalize_evidence_text(evidence)
    markers = (
        "firearm", "gun", "pistol", "rifle", "ammunition", "explosive", "weapon",
        "violent", "armed robbery", "drug", "narcotic", "cocaine", "heroin", "meth",
        "fentanyl", "wildlife", "endangered", "ivory", "pangolin", "tobacco",
        "cigarette", "counterfeit", "contraband", "枪", "弹药", "爆炸物", "武器",
        "暴力", "毒品", "毒品", "麻醉品", "野生动物", "濒危", "象牙", "穿山甲",
        "烟草", "香烟", "假冒", "侵权", "违禁品",
    )
    markers = markers + (
        "droga", "narcotrafico", "cocaina", "heroina", "metanfetamina",
        "arma", "municion", "explosivo", "fauna silvestre", "especie protegida",
        "tabaco", "cigarrillo", "falsificacion",
        "cigarro", "cannabis", "maconha", "contrabando", "medicamento",
        "remedio", "ampola", "pharmaceutical", "medicine", "produto proibido",
        "drogue", "stupefiant", "cocaine", "heroine", "arme", "munition",
        "explosif", "espece protegee", "contrefacon",
    )
    return any(marker in normalized for marker in markers)


def _has_concrete_action_evidence(evidence: str) -> bool:
    normalized = _normalize_evidence_text(evidence)
    markers = (
        "seiz", "intercept", "confiscat", "arrest", "detain", "charge",
        "convict", "sentenc", "warrant", "raid", "investigat", "prosecut",
        "incaut", "decomis", "apreens", "apreend", "retem", "retiv",
        "localiz", "encontr",
        "saisie", "sequestro",
        "查获", "查扣", "扣押", "没收", "逮捕", "拘捕", "截获", "起诉",
        "判刑", "查缉", "侦破", "侦办", "调查", "处罚",
    )
    return any(marker in normalized for marker in markers)


def _is_verifiable_inclusion(
    item: FetchItem, source_text: str, evidence: str, basis: str,
) -> bool:
    """Verify the model's route and require the supporting quote in the source."""
    metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
    if (
        metadata.get("engine") == "gdelt"
        and metadata.get("date_verification") != "source_page"
    ):
        return False
    normalized_source = _normalize_evidence_text(source_text)
    normalized_evidence = _normalize_evidence_text(evidence)
    if len(normalized_evidence) < 6 or normalized_evidence not in normalized_source:
        return False
    if basis == "regional_jurisdiction":
        return _is_special_china_jurisdiction(item, source_text)
    if basis in {"mainland_nexus", "strong_china_nexus"}:
        return _has_verifiable_china_evidence(source_text, evidence, "strong")
    if basis == "weak_china_nexus":
        return (
            _is_special_china_jurisdiction(item, source_text)
            or _has_verifiable_china_evidence(source_text, evidence, "weak")
        )
    if basis == "major_enforcement":
        return (
            _has_concrete_action_evidence(evidence)
            and _has_major_enforcement_evidence(source_text)
        )
    return False


def _resolve_verifiable_inclusion(
    item: FetchItem, source_text: str, evidence: str, requested_basis: str,
) -> str | None:
    """Keep the model's route when valid, otherwise recover another evidenced route."""
    routes = [
        requested_basis,
        "strong_china_nexus",
        "weak_china_nexus",
        "major_enforcement",
    ]
    for basis in dict.fromkeys(route for route in routes if route):
        if _is_verifiable_inclusion(item, source_text, evidence, basis):
            return basis
    return None


def _normalize_evidence_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    normalized = "".join(
        char if char.isalnum() else " " for char in normalized
    )
    return " ".join(normalized.split())


def _is_rate_limit(exc: Exception) -> bool:
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    text = str(exc).casefold()
    return status_code == 429 or "429" in text or "too many requests" in text


def _is_allowed_overseas_candidate(item: FetchItem) -> bool:
    """Remove only obvious domestic or low-quality candidates before the LLM."""
    url = (item.url or "").strip()
    parsed_url = urlparse(url)
    host = parsed_url.netloc.lower()
    if host.endswith("customs.gov.cn") or ".customs.gov.cn" in host:
        return False

    blocked_hosts = (
        "renrendoc.com", "doc88.com", "wenku.baidu.com", "mbalib.com",
        "sohu.com", "163.com", "toutiao.com", "baijiahao.baidu.com",
        "inside.com.tw", "sina.com.cn",
    )
    if any(host.endswith(blocked) for blocked in blocked_hosts):
        return False

    text = f"{item.title} {item.content or ''} {item.summary or ''}"
    lowered_text = text.lower()
    normalized_title = " ".join((item.title or "").casefold().split()).strip(" -|")
    if normalized_title in {
        "complete list of latest news",
        "hong kong customs and excise department - press release",
        "hong kong customs and excise department press release",
        "press releases",
        "media releases",
        "newsroom",
    }:
        return False
    if parsed_url.path.casefold().endswith(("/index.html", "/default.aspx")) and (
        "press release" in normalized_title or normalized_title in {"news", "newsroom"}
    ):
        return False
    if "海关总署" in text or "中华人民共和国海关" in text:
        return False

    domestic_action_patterns = (
        "china has detained", "china detained", "chinese authorities detained",
        "chinese police", "china customs", "chinese customs",
        "中国拘留", "中国执法机关", "中国海关", "中方拘留",
    )
    if any(pattern in lowered_text for pattern in domestic_action_patterns):
        return False

    allowed_signals = (
        ".gov", "customs", "border", "police", "justice", "prosecut",
        "court", "europa.eu", "interpol", "unodc", "reuters.com",
        "apnews.com", "bloomberg.com", "bbc.", "cnn.", "theguardian.com",
        "infobae.com", "eldiario.ec", "vistazo.com", "dailymirror.lk",
        "pib.gov.in", "gov.in", "pna.gov.ph",
    )
    enforcement_terms = (
        "seizure", "seized", "intercept", "intercepted", "confiscat",
        "arrest", "detain", "investigat", "prosecut", "charged", "penalt",
        "smuggl", "扣押", "查获", "没收", "逮捕", "调查", "走私",
        "incaut", "decomis", "confisc", "aprehens", "arrestad", "detenid",
        "contraband", "allanamiento", "investigación", "incautação", "apreens",
        "prisão", "detido", "saisie", "interpellé", "sequestro",
    )
    # Preserve credible-looking leads even when the host name does not expose
    # its official status; the model or a human can make the final decision.
    if not any(signal in host for signal in allowed_signals) and not any(
        term in lowered_text for term in enforcement_terms
    ):
        return False
    return True
