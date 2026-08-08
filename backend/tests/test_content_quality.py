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


def test_customs_hotspot_rejects_foreign_trade_remedy_without_china_customs_action(monkeypatch) -> None:
    item = FetchItem(
        title="US starts solar circumvention inquiry involving Ethiopia and Vietnam",
        url="https://example.gov/solar-inquiry",
        content=(
            "The United States opened a circumvention inquiry into solar products made in Ethiopia "
            "and Vietnam with Chinese components. The proceeding determines US antidumping duties "
            "for American importers and does not create a Chinese customs control measure. "
        ) * 4,
    )
    decision = {
        "index": 0, "decision": "approve", "confidence": 95,
        "independence_score": 95, "completeness_score": 95,
        "customs_value_score": 88, "topic_relevance_score": 82,
        "china_customs_score": 45, "transmission_evidence_score": 70,
        "executable_check_score": 68, "foreign_enforcement_only": True,
        "china_customs_stage": "无直接落点",
        "transmission_chain": "美国反规避调查影响美国进口商缴税，未形成中国海关直接监管动作。",
        "title_zh": "美国启动光伏反规避调查",
        "summary_zh": "美国对使用中国零部件并经埃塞俄比亚和越南加工的光伏产品启动反规避调查，主要影响美国进口执法。",
        "content_zh": "美国主管部门启动光伏产品反规避调查，审查使用中国零部件并经埃塞俄比亚和越南加工后输美的产品。该措施主要确定美国进口环节反倾销及反补贴税适用，不直接形成中国海关进境、出境、口岸、保税或出口管制核查任务。",
        "data_checks": "核查美国进口商申报和美国税款，缺少中国海关可执行动作。",
    }
    monkeypatch.setattr(
        "app.content_quality.call_llm",
        AsyncMock(return_value={"content": __import__("json").dumps({"reviews": [decision]}, ensure_ascii=False)}),
    )
    model = SimpleNamespace(is_active=True, model_name="test-model")

    approved, rejected = asyncio.run(curate_article_candidates(
        [item], model, {"topic_id": "weekly-trade-current-affairs"},
    ))

    assert not approved
    assert "外国海关" in rejected[0].reason


def test_customs_hotspot_accepts_indirect_event_with_actionable_china_customs_chain(monkeypatch) -> None:
    item = FetchItem(
        title="Russian refinery outages widen regional diesel price gaps",
        url="https://example.com/russia-diesel",
        content=(
            "Repeated refinery outages reduced diesel supply in eastern Russia and widened the price "
            "gap with neighbouring markets. Fuel traders reported rerouting cargo and rising roadside sales. "
        ) * 5,
    )
    decision = {
        "index": 0, "decision": "approve", "confidence": 92,
        "independence_score": 90, "completeness_score": 90,
        "customs_value_score": 90, "topic_relevance_score": 90,
        "china_customs_score": 88, "transmission_evidence_score": 84,
        "executable_check_score": 90, "foreign_enforcement_only": False,
        "china_customs_stage": "中外陆路边境",
        "transmission_chain": "俄罗斯远东柴油短缺扩大边境价差，可能提高经中俄陆路口岸车辆油箱、罐车及替代品名向俄异常出境的利润。",
        "title_zh": "俄罗斯炼厂停产扩大柴油价差并抬升中俄边境异常出境风险",
        "summary_zh": "俄罗斯炼厂停产压缩柴油供应并扩大区域价差，可能提高中俄边境利用车辆油箱、罐车或替代品名异常运输燃油的利润。",
        "content_zh": "原文显示俄罗斯炼厂停产导致柴油供应下降和区域价差扩大。结合中俄陆路相邻及成品油跨境运输条件，相关变化可能提高利用车辆油箱、罐车或将柴油申报为润滑油、溶剂油异常出境的利润。该风险属于分析推演，须由口岸数据验证。",
        "source_type": "通讯社报道", "facts": "俄罗斯炼厂停产导致柴油供应下降和区域价差扩大。",
        "customs_risk": "可能出现车辆油箱夹带、罐车异常出境及油品品名错报。",
        "data_checks": "调取满洲里、绥芬河等口岸报关单和车辆进出境记录；筛查HS 2710项下近20日数量、价格、车辆频次及润滑油和溶剂油税号迁移；对异常企业开展单证和货物查验。",
        "risk_level": "高",
    }
    monkeypatch.setattr(
        "app.content_quality.call_llm",
        AsyncMock(return_value={"content": __import__("json").dumps({"reviews": [decision]}, ensure_ascii=False)}),
    )
    model = SimpleNamespace(is_active=True, model_name="test-model")

    approved, rejected = asyncio.run(curate_article_candidates(
        [item], model, {"topic_id": "weekly-trade-current-affairs"},
    ))

    assert not rejected
    assert len(approved) == 1
    review = approved[0].raw_metadata["customs_hotspot_review"]
    assert review["china_customs_stage"] == "中外陆路边境"
    assert review["executable_check_score"] == 90
