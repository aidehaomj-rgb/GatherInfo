"""Tests for the article-quality gate used before intelligence is persisted."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.connectors.base import FetchItem
from app.content_quality import curate_article_candidates, rule_rejection_reason


def test_rule_gate_rejects_gambling_tag_page() -> None:
    item = FetchItem(
        title="查获_【环球博讯】",
        url="https://m.wgi888.com/tag/%E6%9F%A5%E8%8E%B7",
        content="BOSS体育 U存U取 编辑推荐 SIDE1 招租 Copyright 环球博彩资讯门户网",
    )

    assert rule_rejection_reason(item) == "非独立文章或低价值推广/聚合页面"


def test_quality_gate_rejects_uncurated_article_without_active_model() -> None:
    item = FetchItem(
        title="贸易主管部门发布进口监管新规",
        url="https://example.gov/news/1",
        content="该部门发布进口监管新规，明确适用商品、实施日期、企业申报材料和海关执法衔接要求。" * 6,
    )

    approved, rejected = asyncio.run(curate_article_candidates([item], None))

    assert not approved
    assert rejected[0].reason == "未配置有效模型，无法完成信息质量整理"


def test_quality_gate_keeps_only_model_approved_complete_article(monkeypatch) -> None:
    item = FetchItem(
        title="USTR updates tariff exclusions for battery materials",
        url="https://ustr.gov/example/article",
        content=(
            "The United States Trade Representative announced an update to tariff "
            "exclusions affecting battery material imports. The notice identifies the "
            "covered products, effective date, and filing requirements for importers."
        ),
        language="en",
    )
    response = {
        "content": """{
          "reviews": [{
            "index": 0,
            "decision": "approve",
            "confidence": 91,
            "independence_score": 92,
            "completeness_score": 89,
            "customs_value_score": 86,
            "reason": "来源为美国贸易代表办公室，政策措施、适用对象和执行时间明确。",
            "title_zh": "美国更新电池材料关税排除措施",
            "summary_zh": "美国贸易代表办公室更新部分电池材料进口关税排除措施，明确适用产品、执行日期和申报要求。",
            "content_zh": "美国贸易代表办公室发布通知，更新部分电池材料进口关税排除措施。通知明确列明适用产品、实施日期及进口申报要求。海关关员可据此关注相关税则商品的排除资格、有效期限和企业申报材料，避免因适用条件变化产生征管风险。"
          }]
        }""",
    }
    monkeypatch.setattr("app.content_quality.call_llm", AsyncMock(return_value=response))
    model = SimpleNamespace(is_active=True, model_name="test-model")

    approved, rejected = asyncio.run(curate_article_candidates([item], model))

    assert not rejected
    assert len(approved) == 1
    assert approved[0].language == "zh"
    assert approved[0].title == "美国更新电池材料关税排除措施"
    assert approved[0].raw_metadata["quality_review"]["method"] == "llm"
    assert approved[0].raw_metadata["translation_zh"]["content_zh"].startswith("美国贸易代表办公室")


def test_quality_gate_rejects_incomplete_model_output(monkeypatch) -> None:
    item = FetchItem(
        title="Trade authority publishes update",
        url="https://example.gov/news/1",
        content=(
            "The authority published a detailed trade update with measures, dates, "
            "covered importers, and implementation instructions. The publication also "
            "describes documentation requirements, product scope, and the contact point "
            "for businesses seeking clarification on the new customs procedures."
        ),
    )
    monkeypatch.setattr(
        "app.content_quality.call_llm",
        AsyncMock(return_value={"content": '{"reviews":[{"index":0,"decision":"approve","confidence":95,"independence_score":95,"completeness_score":40,"customs_value_score":90}]}' }),
    )
    model = SimpleNamespace(is_active=True, model_name="test-model")

    approved, rejected = asyncio.run(curate_article_candidates([item], model))

    assert not approved
    assert rejected[0].reason == "大模型未确认文章完整性或海关业务价值"


def test_customs_hotspot_uses_conservative_rule_fallback_without_model() -> None:
    item = FetchItem(
        title="Fuel shortage raises China border smuggling concerns after refinery attacks",
        url="https://example.com/energy/shortage",
        content=(
            "Refinery attacks caused a regional diesel and gasoline shortage and a sharp price increase. "
            "China border authorities warned that customs inspections would focus on fuel smuggling, auxiliary "
            "vehicle tanks and false export declarations. The disruption changed import and export routes "
            "and created a black market price differential across the border. "
        ) * 3,
        summary="Fuel supply disruption created a cross-border price gap and customs enforcement concern.",
    )
    context = {"topic_id": "weekly-trade-current-affairs"}

    approved, rejected = asyncio.run(curate_article_candidates([item], None, context))

    assert not rejected
    assert len(approved) == 1
    review = approved[0].raw_metadata["customs_hotspot_review"]
    assert review["method"] == "rule_fallback"
    assert "边境走私" in review["customs_risk"]
    assert review["is_inference"] is True
