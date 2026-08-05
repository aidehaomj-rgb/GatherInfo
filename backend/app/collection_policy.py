"""Pure compliance policy for deciding how deeply a source may be collected."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ContentDepth = Literal["metadata", "excerpt", "full"]

_DENIED_TOKENS = frozenset({"blocked", "denied", "prohibited"})
_ALLOWED_ROBOTS_PREFIXES = ("allowed", "api_required")
_ALLOWED_TERMS_PREFIXES = (
    "allowed",
    "public_domain",
    "government_conditions",
    "linking_allowed",
    "open_government",
    "us_government",
    "cc_by",
)


@dataclass(frozen=True, slots=True)
class CollectionPolicyDecision:
    """Immutable collection permissions derived from a source profile."""

    automated_fetch_allowed: bool
    llm_ingest_allowed: bool
    content_depth: ContentDepth
    reason: str


def evaluate_collection_policy(source: object) -> CollectionPolicyDecision:
    """Evaluate collection permissions without changing the source or global state."""
    if not bool(getattr(source, "is_active", False)):
        return _reject("来源未启用，禁止自动采集。")
    if not bool(getattr(source, "is_configured", False)):
        return _reject("来源未完成配置，禁止自动采集。")

    verification = _normalize_status(getattr(source, "verification_status", None))
    robots = _normalize_status(getattr(source, "robots_status", None))
    terms = _normalize_status(getattr(source, "terms_status", None))

    if _is_denied(verification):
        return _reject("来源核验状态明确为 blocked/denied，禁止采集。")
    if _is_denied(robots):
        return _reject("robots 状态明确拒绝自动访问，禁止采集。")
    if _is_denied(terms):
        return _reject("来源条款明确拒绝自动使用，禁止采集。")

    if verification == "legacy_unverified":
        return CollectionPolicyDecision(
            automated_fetch_allowed=True,
            llm_ingest_allowed=False,
            content_depth="excerpt",
            reason="旧来源兼容模式：仅允许现有连接器采集元数据或短摘录。",
        )
    if not _is_verified(verification):
        return _reject("来源尚未核验，不允许自动采集。")
    if not _has_allowed_prefix(robots, _ALLOWED_ROBOTS_PREFIXES):
        return _reject("robots 未明确允许自动访问，禁止采集。")
    if not _has_allowed_prefix(terms, _ALLOWED_TERMS_PREFIXES):
        return _reject("来源条款未明确允许自动使用，禁止采集。")

    if not bool(getattr(source, "llm_ingest_allowed", False)):
        return CollectionPolicyDecision(
            automated_fetch_allowed=True,
            llm_ingest_allowed=False,
            content_depth="excerpt",
            reason="允许自动采集元数据和短摘录，但来源未授权 LLM 全文处理。",
        )
    return CollectionPolicyDecision(
        automated_fetch_allowed=True,
        llm_ingest_allowed=True,
        content_depth="full",
        reason="来源、robots、条款及 LLM 使用许可均已核验并明确允许。",
    )


def _reject(reason: str) -> CollectionPolicyDecision:
    return CollectionPolicyDecision(
        automated_fetch_allowed=False,
        llm_ingest_allowed=False,
        content_depth="metadata",
        reason=reason,
    )


def _normalize_status(value: object) -> str:
    raw_value = getattr(value, "value", value)
    return str(raw_value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _is_denied(status: str) -> bool:
    return any(token in _DENIED_TOKENS for token in status.split("_"))


def _is_verified(status: str) -> bool:
    return status == "verified" or status.startswith("verified_")


def _has_allowed_prefix(status: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        status == prefix or status.startswith(f"{prefix}_")
        for prefix in prefixes
    )


__all__ = [
    "CollectionPolicyDecision",
    "ContentDepth",
    "evaluate_collection_policy",
]
