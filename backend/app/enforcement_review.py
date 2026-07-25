"""LLM gate for overseas customs enforcement intelligence."""
from __future__ import annotations

import json
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.connectors.base import FetchItem
from app.llm_client import call_llm
from app.models import ModelConfig

logger = logging.getLogger(__name__)
QUEUE_FILE = Path(__file__).resolve().parents[2] / "data" / "enforcement_review_queue.json"
REVIEW_SEMAPHORE = asyncio.Semaphore(2)


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
    items = [item for item in items if _is_allowed_overseas_candidate(item)][:30]
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

    prompt = """You review candidates for an overseas customs enforcement weekly report.
Use two decisions only:
- approve: a concrete overseas enforcement action is clear, the publication date is supportable, and one of the inclusion routes below is met;
- reject: policy commentary, generic trade news, no concrete enforcement action, obvious mainland-China enforcement, an unreliable/reposted source, or an unverified date.

The overseas authority may be customs, border, police, prosecutors, courts, port authorities, or another official enforcement body outside mainland China. Apply these inclusion routes:
1) Hong Kong, Taiwan, or Macao customs/official enforcement cases: a concrete seizure, arrest, interception, investigation, prosecution, or penalty is enough; mainland-China nexus is not required.
2) Other countries and regions: require an explicit mainland-China nexus such as mainland China/PRC, China-origin goods, shipment from/to China, Chinese mainland person/company, Chinese nationality, or a China-linked logistics route.
3) Any country or region: major cross-border enforcement involving firearms, ammunition, explosives, weapons, violent crime, drugs, narcotics, wildlife, endangered species, tobacco, counterfeit goods, or other serious contraband may be included without a China nexus, provided the concrete action and date are supported by the source.
Do not infer a nexus from a Hong Kong address, a Chinese-language page, a generic Chinese brand, the fact that the authority is Hong Kong Customs, or background knowledge. For every approval, copy a short exact quote from the supplied title/content into evidence_quote. The quote must support either the regional-jurisdiction route, the mainland-China route, or the major-enforcement route and must not be invented. Set inclusion_basis to one of regional_jurisdiction, mainland_nexus, or major_enforcement. If no exact quote can be copied, reject.
Return JSON only: {"decisions":[{"index":0,"decision":"approve|reject","confidence":0-100,"basis":"short Chinese evidence-based reason","inclusion_basis":"regional_jurisdiction|mainland_nexus|major_enforcement","evidence_quote":"exact source quote or empty","mainland_nexus_evidence":"exact mainland quote or empty","enforcement_action":"..."}]}.

CANDIDATES:\n""" + json.dumps([
        {
            "index": index,
            "title": item.title,
            "url": item.url,
            "published_at": item.published_at,
            "content": (item.content or item.summary or "")[:1800],
        }
        for index, item in enumerate(items)
    ], ensure_ascii=False)

    try:
        async with REVIEW_SEMAPHORE:
            response = await asyncio.wait_for(call_llm(model, prompt), timeout=90)
        text = response["content"].strip()
        if "```" in text:
            text = text.replace("```json", "").replace("```", "").strip()
        decisions = json.loads(text).get("decisions", [])
    except Exception as exc:
        logger.warning("Enforcement review unavailable; candidates queued: %s", exc)
        _write_queue(records)
        return []

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
            evidence = str(
                decision.get("evidence_quote")
                or decision.get("mainland_nexus_evidence")
                or ""
            ).strip()
            source_text = " ".join(
                str(value or "") for value in (items[index].title, items[index].content, items[index].summary)
            )
            basis = str(decision.get("inclusion_basis") or "").strip()
            if not _is_verifiable_inclusion(items[index], source_text, evidence, basis):
                decision["decision"] = "reject"
                decision["basis"] = "原文未提供可核验的港澳台、涉中国大陆或重大跨境执法证据"
                records[index]["status"] = "reject"
                records[index]["review"] = decision
                continue
            metadata = dict(items[index].raw_metadata or {})
            metadata["enforcement_review"] = decision
            items[index].raw_metadata = metadata
            approved.append(items[index])
    _write_queue(records)
    return approved


def _has_verifiable_mainland_evidence(source_text: str, evidence: str) -> bool:
    """Require an exact source quote that explicitly links the case to mainland China."""
    if len(evidence) < 6:
        return False
    normalized_source = " ".join(source_text.casefold().split())
    normalized_evidence = " ".join(evidence.casefold().split())
    if normalized_evidence not in normalized_source:
        return False
    mainland_markers = (
        "mainland china", "chinese mainland", "people's republic of china", "prc",
        "china-origin", "originating in china", "from china", "to china",
        "destination china", "shipped from china", "chinese national", "chinese citizen",
        "chinese company", "china-based", "china-linked", "中国大陆", "中国内地",
        "中华人民共和国", "中国产", "来自中国", "运往中国", "中国籍", "中国公民",
        "中国企业", "中国公司", "中国制造", "中国来源", "中国目的地", "经中国转运",
        "中国港口", "中国路线",
    )
    return any(marker in normalized_evidence for marker in mainland_markers)


def _is_special_china_jurisdiction(item: FetchItem) -> bool:
    """Hong Kong, Taiwan, and Macao cases do not require a mainland nexus."""
    host = urlparse((item.url or "").strip()).netloc.casefold()
    return (
        host.endswith(".gov.hk")
        or host.endswith(".gov.tw")
        or host.endswith(".gov.mo")
        or "customs.gov.hk" in host
        or "customs.gov.tw" in host
    )


def _has_major_enforcement_evidence(evidence: str) -> bool:
    normalized = evidence.casefold()
    markers = (
        "firearm", "gun", "pistol", "rifle", "ammunition", "explosive", "weapon",
        "violent", "armed robbery", "drug", "narcotic", "cocaine", "heroin", "meth",
        "fentanyl", "wildlife", "endangered", "ivory", "pangolin", "tobacco",
        "cigarette", "counterfeit", "contraband", "枪", "弹药", "爆炸物", "武器",
        "暴力", "毒品", "毒品", "麻醉品", "野生动物", "濒危", "象牙", "穿山甲",
        "烟草", "香烟", "假冒", "侵权", "违禁品",
    )
    return any(marker in normalized for marker in markers)


def _is_verifiable_inclusion(
    item: FetchItem, source_text: str, evidence: str, basis: str,
) -> bool:
    """Verify the model's route and require the supporting quote in the source."""
    normalized_source = " ".join(source_text.casefold().split())
    normalized_evidence = " ".join(evidence.casefold().split())
    if len(normalized_evidence) < 6 or normalized_evidence not in normalized_source:
        return False
    if basis == "regional_jurisdiction":
        return _is_special_china_jurisdiction(item)
    if basis == "mainland_nexus":
        return _has_verifiable_mainland_evidence(source_text, evidence)
    if basis == "major_enforcement":
        return _has_major_enforcement_evidence(evidence)
    return False


def _is_allowed_overseas_candidate(item: FetchItem) -> bool:
    """Remove only obvious domestic or low-quality candidates before the LLM."""
    url = (item.url or "").strip()
    host = urlparse(url).netloc.lower()
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
