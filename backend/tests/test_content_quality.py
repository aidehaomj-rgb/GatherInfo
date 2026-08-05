"""Tests for the article-quality gate used before intelligence is persisted."""
import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.connectors.base import FetchItem
from app.content_quality import (
    _build_intelligence_profile,
    curate_article_candidates,
    review_persisted_items,
    rule_rejection_reason,
)


def _llm_approved_source() -> SimpleNamespace:
    return SimpleNamespace(
        is_active=True,
        is_configured=True,
        verification_status="verified",
        robots_status="allowed",
        terms_status="allowed",
        llm_ingest_allowed=True,
    )


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
def test_quality_gate_rejects_english_text_falsely_labelled_as_chinese(monkeypatch) -> None:
    item = FetchItem(
        title="Customs authority publishes trade control update",
        url="https://example.gov/news/english-only",
        content=(
            "The customs authority published a detailed trade control update with "
            "dates, covered products, documentation requirements and enforcement guidance. "
        ) * 4,
        language="en",
    )
    response = {"content": json.dumps({"reviews": [{
        "index": 0,
        "decision": "approve",
        "confidence": 95,
        "independence_score": 95,
        "completeness_score": 95,
        "customs_value_score": 95,
        "reason": "Complete article",
        "title_zh": "Customs authority publishes trade control update",
        "summary_zh": "The customs authority published a detailed update for importers and enforcement teams.",
        "content_zh": (
            "The authority published a complete policy update covering affected products, "
            "implementation dates, documentation requirements and enforcement guidance. " * 3
        ),
    }]})}
    monkeypatch.setattr("app.content_quality.call_llm", AsyncMock(return_value=response))

    approved, rejected = asyncio.run(curate_article_candidates(
        [item], SimpleNamespace(is_active=True, model_name="test-model"),
    ))

    assert approved == []
    assert rejected


def test_quality_gate_adds_clean_structured_intelligence_profile(monkeypatch) -> None:
    item = FetchItem(
        title="USTR extends tariff exclusions for battery materials",
        url="https://ustr.gov/example/structured-article",
        content=(
            "The United States Trade Representative extended tariff exclusions for "
            "battery materials imported from China. The notice names covered products, "
            "effective dates, import routes, and filing requirements for importers. "
        ) * 2,
        language="en",
        category="旧分类",
        entities={"countries": ["既有国家"], "years": ["2026"]},
        relevance_score=0.42,
        raw_metadata={"connector": "test"},
    )
    response = {
        "content": json.dumps({
            "reviews": [{
                "index": 0,
                "decision": "approve",
                "confidence": 94,
                "independence_score": 92,
                "completeness_score": 91,
                "customs_value_score": 89,
                "topic_relevance_score": 87,
                "reason": "事实、主体和影响完整。",
                "title_zh": "美国延长部分电池材料关税排除措施",
                "summary_zh": "美国贸易代表办公室延长部分电池材料的关税排除安排，并明确适用产品、执行期限和进口申报要求。",
                "content_zh": (
                    "美国贸易代表办公室发布通知，延长部分源自中国的电池材料关税排除安排。"
                    "通知列明适用产品、执行期限、进口路径和申报要求。海关关员可据此核验"
                    "相关税则商品的原产地、排除资格与证明材料，并关注政策到期带来的征管风险。"
                ),
                "business_category": "  关税与贸易救济  ",
                "risk_type": "  关税政策 调整  ",
                "countries": ["美国", " 美国 ", "中国", 123, ""],
                "products": ["锂离子电池材料", "锂离子电池材料"],
                "actors": ["美国贸易代表办公室", None],
                "routes": ["中国 → 美国"],
                "china_relevance": 88,
                "priority": " HIGH ",
                "key_facts": ["排除期限延长。", " 排除期限延长。 ", "适用产品以通知清单为准。"],
                "evidence_quotes": ["The notice names covered products"],
                "publishability": 96,
                "original_language": " en-US ",
            }],
        }, ensure_ascii=False),
    }
    llm_mock = AsyncMock(return_value=response)
    monkeypatch.setattr("app.content_quality.call_llm", llm_mock)
    model = SimpleNamespace(is_active=True, model_name="test-model")

    approved, rejected = asyncio.run(curate_article_candidates([item], model))

    assert not rejected
    assert item.category == "旧分类"
    assert item.entities == {"countries": ["既有国家"], "years": ["2026"]}
    assert item.relevance_score == 0.42
    curated = approved[0]
    assert curated.category == "关税与贸易救济"
    assert curated.entities == {
        "countries": ["既有国家", "美国", "中国"],
        "years": ["2026"],
        "products": ["锂离子电池材料"],
        "actors": ["美国贸易代表办公室"],
        "routes": ["中国 → 美国"],
    }
    assert curated.entities["years"] is not item.entities["years"]
    assert curated.relevance_score == 0.88
    assert curated.raw_metadata["connector"] == "test"
    assert curated.raw_metadata["intelligence_profile"] == {
        "business_category": "关税与贸易救济",
        "risk_type": "关税政策 调整",
        "countries": ["美国", "中国"],
        "products": ["锂离子电池材料"],
        "actors": ["美国贸易代表办公室"],
        "routes": ["中国 → 美国"],
        "china_relevance": 88,
        "priority": "high",
        "key_facts": ["排除期限延长。", "适用产品以通知清单为准。"],
        "evidence_quotes": ["The notice names covered products"],
        "publishability": 96,
        "original_language": "en-US",
    }
    prompt = llm_mock.await_args.args[1]
    assert '"business_category"' in prompt
    assert '"publishability"' in prompt
    assert '"original_language"' in prompt
    assert "不可信外部数据" in prompt


def test_quality_gate_rejects_timeline_when_primary_event_is_outside_window(
    monkeypatch,
) -> None:
    item = FetchItem(
        title="EU-China relations after the elections: a timeline",
        url="https://example.org/eu-china-timeline",
        published_at="2026-08-03T08:00:00Z",
        content=(
            "This timeline was updated in August. The substantive anti-dumping decision "
            "was adopted on May 5, 2026 and affected adipic acid imports from China. "
        ) * 3,
        language="en",
    )
    response = {
        "content": json.dumps({
            "reviews": [{
                "index": 0, "decision": "approve", "confidence": 95,
                "independence_score": 90, "completeness_score": 90,
                "customs_value_score": 90, "topic_relevance_score": 90,
                "title_zh": "欧盟对华己二酸反倾销措施时间线更新",
                "summary_zh": "文章汇总欧盟对华经贸关系进展，其中反倾销决定实际发生于五月，并非本周新增措施。",
                "content_zh": "文章以时间线形式回顾欧盟对华经贸关系。核心反倾销决定发生于五月五日，涉及中国己二酸产品。该页面虽然于八月更新，但没有提供本周新发生的独立监管事件，因此不能作为本周新增情报。" * 2,
                "business_category": "贸易救济", "risk_type": "反倾销",
                "countries": ["欧盟", "中国"], "products": ["己二酸"],
                "actors": ["欧盟委员会"], "routes": ["中国 → 欧盟"],
                "china_relevance": 90, "priority": "high",
                "key_facts": ["决定发生于2026年5月5日"],
                "evidence_quotes": ["adopted on May 5, 2026"],
                "publishability": 90, "original_language": "en",
                "artifact_type": "timeline", "primary_event_date": "2026-05-05",
            }],
        }, ensure_ascii=False),
    }
    monkeypatch.setattr("app.content_quality.call_llm", AsyncMock(return_value=response))
    model = SimpleNamespace(is_active=True, model_name="test-model")

    approved, rejected = asyncio.run(curate_article_candidates(
        [item], model,
        topic_context={
            "topic_id": "global-trade",
            "collection_window_start": "2026-08-02T16:00:00+00:00",
            "collection_window_end": "2026-08-04T12:00:00+00:00",
        },
    ))

    assert approved == []
    assert [entry.reason for entry in rejected] == ["主事件日期不在本次采集窗口内"]


def test_quality_gate_keeps_single_event_with_in_window_primary_date(
    monkeypatch,
) -> None:
    item = FetchItem(
        title="Customs authority issues a new import control notice",
        url="https://example.org/new-notice",
        published_at="2026-08-03T08:00:00Z",
        content=(
            "The customs authority issued a new import control notice on August 3, 2026. "
            "It identifies affected goods, filing requirements and the effective date. "
        ) * 3,
        language="en",
    )
    review = {
        "index": 0, "decision": "approve", "confidence": 95,
        "independence_score": 90, "completeness_score": 90,
        "customs_value_score": 90, "topic_relevance_score": 90,
        "title_zh": "海关发布新的进口管制公告",
        "summary_zh": "海关于八月三日发布进口管制公告，明确适用商品、申报材料和生效日期。",
        "content_zh": "海关于八月三日发布新的进口管制公告，列明适用商品、申报材料和正式生效日期。海关关员可据此核验申报要素、证明文件以及政策生效后的货物适用范围。" * 2,
        "business_category": "进口监管", "risk_type": "监管调整",
        "countries": ["美国"], "products": ["进口商品"],
        "actors": ["海关"], "routes": [], "china_relevance": 70,
        "priority": "medium", "key_facts": ["公告于八月三日发布"],
        "evidence_quotes": ["issued a new import control notice on August 3, 2026"],
        "publishability": 90, "original_language": "en",
        "artifact_type": "single_event", "primary_event_date": "2026-08-03",
    }
    monkeypatch.setattr(
        "app.content_quality.call_llm",
        AsyncMock(return_value={"content": json.dumps({"reviews": [review]}, ensure_ascii=False)}),
    )
    model = SimpleNamespace(is_active=True, model_name="test-model")

    approved, rejected = asyncio.run(curate_article_candidates(
        [item], model,
        topic_context={
            "topic_id": "global-trade",
            "collection_window_start": "2026-08-02T16:00:00+00:00",
            "collection_window_end": "2026-08-04T12:00:00+00:00",
        },
    ))

    assert not rejected
    assert approved[0].raw_metadata["intelligence_profile"]["artifact_type"] == "single_event"
    assert approved[0].raw_metadata["intelligence_profile"]["primary_event_date"] == "2026-08-03"


def test_topic_quality_gate_rejects_item_below_weekly_publishability(monkeypatch) -> None:
    item = FetchItem(
        title="Customs authority issues a trade notice",
        url="https://example.gov/trade-notice",
        content=(
            "The customs authority issued a detailed trade notice covering products, "
            "dates, filing requirements and enforcement implications. "
        ) * 4,
        language="en",
    )
    review = {
        "index": 0, "decision": "approve", "confidence": 92,
        "independence_score": 91, "completeness_score": 90,
        "customs_value_score": 88, "topic_relevance_score": 86,
        "title_zh": "海关发布新的贸易监管公告",
        "summary_zh": "海关发布新的贸易监管公告，明确相关商品、实施日期、申报资料和执法要求。",
        "content_zh": (
            "海关发布新的贸易监管公告，明确相关商品、实施日期、申报资料和执法要求。"
            "该公告可用于核验商品适用范围、企业申报资料以及措施生效后的监管要求。"
        ) * 2,
        "china_relevance": 80, "publishability": 65,
        "artifact_type": "single_event", "primary_event_date": "2026-08-03",
    }
    monkeypatch.setattr(
        "app.content_quality.call_llm",
        AsyncMock(return_value={"content": json.dumps({"reviews": [review]}, ensure_ascii=False)}),
    )

    approved, rejected = asyncio.run(curate_article_candidates(
        [item], SimpleNamespace(is_active=True, model_name="test-model"),
        topic_context={"topic_id": "global-trade", "name": "全球贸易风险"},
    ))

    assert approved == []
    assert [entry.reason for entry in rejected] == ["发布适用性评分低于周报门槛"]


def test_topic_quality_uses_topic_relevance_without_requiring_china_focus(
    monkeypatch,
) -> None:
    item = FetchItem(
        title="Brazil updates customs filing requirements",
        url="https://example.gov/brazil-customs",
        content=(
            "Brazil updated customs filing requirements for importers, including "
            "covered goods, effective dates and documentary evidence. "
        ) * 4,
        language="pt",
    )
    review = {
        "index": 0, "decision": "approve", "confidence": 94,
        "independence_score": 92, "completeness_score": 91,
        "customs_value_score": 89, "topic_relevance_score": 88,
        "title_zh": "巴西更新进口海关申报要求",
        "summary_zh": "巴西海关更新进口申报要求，明确适用商品、生效日期以及企业应提交的证明材料。",
        "content_zh": (
            "巴西海关更新进口申报要求，明确适用商品、生效日期以及企业应提交的证明材料。"
            "海关关员可据此了解巴西进口监管变化，并核验申报材料和商品适用范围。"
        ) * 2,
        "countries": ["巴西"], "china_relevance": 25,
        "publishability": 90, "artifact_type": "single_event",
        "primary_event_date": "2026-08-03",
    }
    monkeypatch.setattr(
        "app.content_quality.call_llm",
        AsyncMock(return_value={"content": json.dumps({"reviews": [review]}, ensure_ascii=False)}),
    )

    approved, rejected = asyncio.run(curate_article_candidates(
        [item], SimpleNamespace(is_active=True, model_name="test-model"),
        topic_context={"topic_id": "global-trade", "name": "全球贸易风险"},
    ))

    assert not rejected
    assert approved[0].relevance_score == 0.88
    assert approved[0].quality_score == 0.89
    assert approved[0].raw_metadata["intelligence_profile"]["china_relevance"] == 25


def test_quality_gate_ignores_invalid_new_fields_and_keeps_legacy_values(monkeypatch) -> None:
    item = FetchItem(
        title="Autoridad aduanera publica nuevas medidas de control",
        url="https://example.gov/news/legacy-compatible",
        content=(
            "La autoridad aduanera publicó medidas de control comercial con fechas, "
            "productos cubiertos, documentación exigida y pautas de aplicación. "
        ) * 3,
        language="zh",
        category="既有分类",
        entities={"companies": ["既有机构"]},
        relevance_score=0.61,
        raw_metadata={
            "source_snapshot": {"language": "es", "title": "Título original"},
            "intelligence_profile": {"original_language": "es"},
        },
    )
    response = {
        "content": json.dumps({
            "reviews": [{
                "index": 0,
                "decision": "approve",
                "confidence": 90,
                "independence_score": 90,
                "completeness_score": 90,
                "customs_value_score": 85,
                "reason": "旧版合同仍提供完整中文整理稿。",
                "title_zh": "海关部门发布新的贸易监管措施",
                "summary_zh": "有关海关部门发布新的贸易监管措施，明确适用商品、执行日期、申报资料以及现场执行要求。",
                "content_zh": (
                    "有关海关部门发布新的贸易监管措施，明确适用商品、执行日期、申报资料和"
                    "现场执行要求。该措施为进出口企业准备申报材料提供依据，也便于海关关员"
                    "核验商品范围、实施时间和单证要求，及时识别申报不完整或适用条件错误。"
                ),
                "business_category": ["错误类型"],
                "countries": "西班牙",
                "products": [123, None],
                "actors": {"name": "机构"},
                "routes": False,
                "china_relevance": "88",
                "priority": "urgent",
                "key_facts": "不是数组",
                "evidence_quotes": [{"quote": "错误类型"}],
                "publishability": 101,
                "original_language": ["es"],
            }],
        }, ensure_ascii=False),
    }
    monkeypatch.setattr("app.content_quality.call_llm", AsyncMock(return_value=response))
    model = SimpleNamespace(is_active=True, model_name="test-model")

    approved, rejected = asyncio.run(curate_article_candidates([item], model))

    assert not rejected
    curated = approved[0]
    assert curated.category == "既有分类"
    assert curated.entities == {"companies": ["既有机构"]}
    assert curated.relevance_score == 0.61
    assert curated.raw_metadata["intelligence_profile"] == {"original_language": "es"}
    assert curated.raw_metadata["source_snapshot"] == {
        "language": "es", "title": "Título original",
    }
    assert curated.raw_metadata["quality_review"]["method"] == "llm"
    assert curated.raw_metadata["translation_zh"]["status"] == "curated"


def test_intelligence_profile_enforces_text_and_collection_limits() -> None:
    raw_profile = {
        "business_category": f"<b>{'类' * 150}</b>",
        "countries": [f"国家{index}" for index in range(20)],
        "key_facts": ["事实" * 400],
        "evidence_quotes": ["e" * 900],
    }

    profile = _build_intelligence_profile(raw_profile, "zh")

    assert profile["business_category"] == "类" * 100
    assert profile["countries"] == [f"国家{index}" for index in range(12)]
    assert len(profile["key_facts"][0]) == 500
    assert len(profile["evidence_quotes"][0]) == 700
    assert profile["original_language"] == "zh"


def test_historical_review_persists_structured_classification(monkeypatch) -> None:
    row = SimpleNamespace(
        id="item-1",
        title="Original title",
        content="Original article body " * 15,
        summary="Original summary",
        url="https://example.gov/item-1",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        language="en",
        category="旧分类",
        quality_score=0.7,
        relevance_score=0.4,
        entities={"years": ["2026"]},
        raw_metadata={"connector": "test"},
        source=_llm_approved_source(),
    )

    class QueryStub:
        def order_by(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def all(self):
            return [row]

    db = SimpleNamespace(
        query=lambda _model: QueryStub(),
        delete=lambda _row: None,
        commit=lambda: None,
    )

    async def curate_stub(items, _model):
        curated = replace(
            items[0],
            title="中文标题",
            summary="中文摘要",
            content="中文正文",
            language="zh",
            category="关税政策",
            entities={"years": ["2026"], "countries": ["美国"]},
            quality_score=0.9,
            relevance_score=0.88,
            raw_metadata={
                **(items[0].raw_metadata or {}),
                "intelligence_profile": {"business_category": "关税政策"},
            },
        )
        return [curated], []

    monkeypatch.setattr("app.content_quality.curate_article_candidates", curate_stub)
    model = SimpleNamespace(is_active=True, model_name="test-model")

    result = asyncio.run(review_persisted_items(db, model))

    assert result == {"reviewed": 1, "curated": 1, "deleted": 0, "retained": 1}
    assert row.category == "关税政策"
    assert row.entities == {"years": ["2026"], "countries": ["美国"]}
    assert row.relevance_score == 0.4
    assert row.raw_metadata == {
        "connector": "test",
        "intelligence_profile": {"business_category": "关税政策"},
    }


def test_historical_review_never_sends_unapproved_source_to_llm(monkeypatch) -> None:
    row = SimpleNamespace(
        id="item-policy-blocked",
        title="Restricted source article",
        content="Complete trade intelligence article body. " * 15,
        summary="Restricted source summary",
        url="https://restricted.example/item",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        language="en",
        category="旧分类",
        quality_score=0.8,
        relevance_score=0.8,
        entities={},
        raw_metadata={},
        source=SimpleNamespace(
            is_active=True,
            is_configured=True,
            verification_status="legacy_unverified",
            robots_status="unverified",
            terms_status="unverified",
            llm_ingest_allowed=False,
        ),
    )

    class QueryStub:
        def order_by(self, *_args):
            return self

        def limit(self, _limit):
            return self

        def all(self):
            return [row]

    db = SimpleNamespace(
        query=lambda _model: QueryStub(),
        delete=lambda _row: None,
        commit=lambda: None,
    )
    curate_mock = AsyncMock()
    monkeypatch.setattr("app.content_quality.curate_article_candidates", curate_mock)

    result = asyncio.run(review_persisted_items(
        db,
        SimpleNamespace(is_active=True, model_name="test-model"),
    ))

    assert result == {"reviewed": 1, "curated": 0, "deleted": 0, "retained": 1}
    curate_mock.assert_not_awaited()
