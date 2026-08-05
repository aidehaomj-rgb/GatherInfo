import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.connectors.base import FetchItem
from app.connectors.ai_research import AIResearchCollector
from app.connectors.tavily_search import (
    _extract_date_hint, _extract_url_date_hint, _parse_search_query,
)
from app.connectors.official_enforcement_search import (
    _extract_portuguese_date,
    _looks_like_enforcement,
)
from app.connectors.rss_collector import _parse_published_at
from app.enforcement_review import (
    _is_allowed_overseas_candidate, _is_verifiable_inclusion,
    enrich_enforcement_review_metadata,
    prioritize_enforcement_candidates, review_enforcement_candidates,
)
from app.engine import (
    CollectionEngine, _filter_items_by_window, _topic_collection_keywords,
)
from app.research_planner import build_research_queries


def test_enforcement_fallback_queries_are_multilingual_and_overseas(monkeypatch):
    monkeypatch.setattr(
        "app.research_planner.call_llm",
        AsyncMock(side_effect=RuntimeError("offline")),
    )
    topic = SimpleNamespace(
        id="weekly-enforcement-intelligence",
        name="执法信息周报",
        description="境外进出口执法案例",
        keywords=["走私", "查获"],
    )

    queries = asyncio.run(build_research_queries(
        topic, "", None, max_queries=12, window_days=30,
        today=date(2026, 7, 28),
    ))

    assert len(queries) == 12
    assert any("aduanas" in query for query in queries)
    assert any("alfandega" in query for query in queries)
    assert all("-site:customs.gov.cn" in query for query in queries)
    assert len({query.split("||", 1)[0] for query in queries}) == 12


def test_enforcement_full_plan_covers_codex_multilingual_discovery_regions(monkeypatch):
    monkeypatch.setattr(
        "app.research_planner.call_llm",
        AsyncMock(side_effect=RuntimeError("offline")),
    )
    topic = SimpleNamespace(
        id="weekly-enforcement-intelligence",
        name="执法信息周报",
        description="境外进出口执法案例",
        keywords=["走私", "查获"],
    )

    queries = asyncio.run(build_research_queries(
        topic, "", None, max_queries=40, window_days=30,
        today=date(2026, 7, 28),
    ))
    query_text = "\n".join(queries)

    assert len(queries) >= 35
    assert "jurisdiction=Portugal" in query_text
    assert "jurisdiction=India" in query_text
    assert "jurisdiction=Pakistan" in query_text
    assert "ศุลกากร" in query_text
    assert "Bea Cukai" in query_text
    assert "税関" in query_text
    assert "세관" in query_text
    assert "جمارك" in query_text
    assert "China Chinese mainland China-origin" not in query_text


def test_ai_research_uses_deep_source_content_for_enforcement_plan():
    config = SimpleNamespace(
        id="ai-research",
        api_key="test-key",
        api_key_ref=None,
        base_url=None,
        api_endpoint=None,
        auth_config={},
        default_keywords=[],
        default_categories=[],
        timeout_seconds=30,
        rate_limit_rps=1,
    )
    collector = AIResearchCollector(config)
    queries = [
        f"jurisdiction=Country {index} || customs seizure {index}"
        for index in range(36)
    ]

    assert len(collector._resolve_queries(queries)) == 36
    provider_config = collector._provider_config(
        "tavily", "test-key", is_enforcement_plan=True,
    )
    assert provider_config.auth_config["include_raw_content"] is True
    assert provider_config.auth_config["search_depth"] == "advanced"


def test_enforcement_topic_expands_rss_discovery_stems():
    topic = SimpleNamespace(
        id="weekly-enforcement-intelligence",
        keywords=["走私", "seizure"],
    )

    keywords = _topic_collection_keywords(topic)

    assert "走私" in keywords
    assert "seizure" in keywords
    assert "seiz" in keywords
    assert "intercept" in keywords
    assert len(keywords) == len({keyword.casefold() for keyword in keywords})


def test_rss_publication_time_is_converted_to_utc():
    published = _parse_published_at("Tue, 28 Jul 2026 13:54:11 -0400")

    assert published == "2026-07-28T17:54:11+00:00"


def test_search_directives_are_not_sent_as_query_text():
    query, directives = _parse_search_query(
        "jurisdiction=Brazil;country=brazil || Receita Federal apreensao"
    )

    assert query == "Receita Federal apreensao"
    assert directives == {"jurisdiction": "Brazil", "country": "brazil"}


def test_enforcement_candidates_are_round_robined_by_jurisdiction():
    items = [
        FetchItem(
            title=f"Hong Kong Customs seized drugs {index}",
            content="Customs officers seized drugs.",
            url=f"https://www.customs.gov.hk/news/{index}",
            raw_metadata={"search_jurisdiction": "Hong Kong"},
        )
        for index in range(10)
    ]
    items.extend([
        FetchItem(
            title="CBP seized cocaine",
            content="CBP officers seized cocaine.",
            url="https://www.cbp.gov/news/one",
            raw_metadata={"search_jurisdiction": "United States"},
        ),
        FetchItem(
            title="CBSA seized methamphetamine",
            content="CBSA officers seized methamphetamine.",
            url="https://www.canada.ca/news/two",
            raw_metadata={"search_jurisdiction": "Canada"},
        ),
    ])

    selected = prioritize_enforcement_candidates(items, max_items=6)
    jurisdictions = [
        item.raw_metadata["search_jurisdiction"] for item in selected
    ]

    assert jurisdictions[:3] == ["Hong Kong", "United States", "Canada"]
    assert jurisdictions.count("Hong Kong") < len(jurisdictions)


def test_enforcement_candidates_prioritize_low_coverage_jurisdictions():
    items = [
        FetchItem(
            title="ABF officers seized 400 prohibited weapons",
            content="Australian Border Force seized 400 prohibited weapons.",
            url="https://www.abf.gov.au/news/one",
            raw_metadata={"search_jurisdiction": "Australia"},
        ),
        FetchItem(
            title="Receita Federal retém 477 kg de maconha",
            content="Receita Federal localizou 477 kg de maconha.",
            url="https://www.gov.br/news/two",
            raw_metadata={"search_jurisdiction": "Brazil"},
        ),
        FetchItem(
            title="CBSA seizes 26 kg of methamphetamine",
            content="CBSA officers seized 26 kg of methamphetamine.",
            url="https://www.canada.ca/news/three",
            raw_metadata={"search_jurisdiction": "Canada"},
        ),
    ]

    selected = prioritize_enforcement_candidates(
        items,
        max_items=3,
        existing_counts={"Australia": 5, "Brazil": 3, "Canada": 2},
    )

    assert [
        item.raw_metadata["search_jurisdiction"] for item in selected
    ] == ["Canada", "Brazil", "Australia"]


def test_enforcement_portfolio_reaches_30_without_one_region_dominating():
    db = SimpleNamespace()
    db.query = lambda *_args: SimpleNamespace(
        filter=lambda *_conditions: SimpleNamespace(all=lambda: []),
    )
    engine = CollectionEngine(db)
    jurisdictions = (
        ("Hong Kong", 16),
        ("United States", 8),
        ("Canada", 8),
        ("Brazil", 8),
        ("Australia", 8),
    )
    items = [
        FetchItem(
            title=f"{jurisdiction} customs seized contraband {index}",
            content="Customs officers seized a major contraband shipment.",
            url=f"https://example.gov/{jurisdiction.casefold().replace(' ', '-')}/{index}",
            relevance_score=0.9,
            raw_metadata={"search_jurisdiction": jurisdiction},
        )
        for jurisdiction, count in jurisdictions
        for index in range(count)
    ]

    selected, skipped = engine._select_enforcement_portfolio(
        items, None, target_total=30,
    )
    counts = {}
    for item in selected:
        jurisdiction = item.raw_metadata["search_jurisdiction"]
        counts[jurisdiction] = counts.get(jurisdiction, 0) + 1

    assert len(selected) == 30
    assert skipped == len(items) - 30
    assert counts["Hong Kong"] == 10
    assert len(counts) == 5
    assert max(counts.values()) / len(selected) <= 1 / 3


def test_existing_monthly_items_do_not_block_new_enforcement_candidates():
    stored = [
        SimpleNamespace(
            url=f"https://stored.example/{index}",
            title=f"Stored case {index}",
            content="",
            summary="",
            raw_metadata={
                "enforcement_review": {"jurisdiction": "United States"},
            },
        )
        for index in range(30)
    ]
    db = SimpleNamespace()
    db.query = lambda *_args: SimpleNamespace(
        filter=lambda *_conditions: SimpleNamespace(all=lambda: stored),
    )
    engine = CollectionEngine(db)
    candidates = [
        FetchItem(
            title=f"CBP seizes shipment from China {index}",
            content=(
                f"The shipment was sent from China. CBP officers seized "
                f"{index + 1} cartons of restricted goods."
            ),
            url=f"https://www.cbp.gov/newsroom/new-case-{index}",
            relevance_score=0.9,
            raw_metadata={"search_jurisdiction": "United States"},
        )
        for index in range(6)
    ]

    selected, skipped = engine._select_enforcement_portfolio(
        candidates, None, target_total=30,
    )

    assert len(selected) == 6
    assert skipped == 0


def test_historical_enforcement_review_metadata_is_enriched():
    item = FetchItem(
        title="香港海关检获怀疑受管制属濒危物种活蜥蜴",
        content="香港海关检获怀疑受管制属濒危物种活蜥蜴。",
        url="https://www.customs.gov.hk/sc/news/example.html",
        raw_metadata={
            "enforcement_review": {
                "decision": "approve",
                "evidence_quote": "香港海关检获怀疑受管制属濒危物种活蜥蜴",
            },
        },
    )

    review = enrich_enforcement_review_metadata(item)

    assert review["jurisdiction"] == "Hong Kong"
    assert review["authority"] == "Hong Kong Customs and Excise Department"
    assert review["case_type"] == "wildlife"
    assert review["source_domain"] == "www.customs.gov.hk"


def test_generic_listing_page_is_not_an_enforcement_case():
    item = FetchItem(
        title="Hong Kong Customs and Excise Department - Press Release -",
        content="Customs seized drugs in one of several listed stories.",
        url="https://www.customs.gov.hk/en/customs-announcement/press-release/index.html",
    )

    assert _is_allowed_overseas_candidate(item) is False


def test_gdelt_seen_time_is_not_accepted_as_publication_date():
    evidence = "customs officers seized 25 kilograms of cocaine"
    item = FetchItem(
        title="Customs officers seize cocaine",
        content=f"On 20 July 2026, {evidence}.",
        url="https://example.com/customs-case",
        published_at="2026-07-20T00:00:00+00:00",
        raw_metadata={
            "engine": "gdelt",
            "date_verification": "search_index_only",
        },
    )

    assert _is_verifiable_inclusion(
        item,
        f"{item.title} {item.content}",
        evidence,
        "major_enforcement",
    ) is False

    item.raw_metadata["date_verification"] = "source_page"
    assert _is_verifiable_inclusion(
        item,
        f"{item.title} {item.content}",
        evidence,
        "major_enforcement",
    ) is True


def test_window_filter_accepts_english_and_chinese_dates():
    items = [
        FetchItem(
            title="15 July 2026 Notice of Seizure",
            content="Official customs seizure notice",
            url="https://example.gov/notice/1",
        ),
        FetchItem(
            title="海关于2026年7月18日查获违禁品",
            content="海关采取扣押措施",
            url="https://example.gov/notice/2",
        ),
    ]
    accepted, rejected = _filter_items_by_window(
        items,
        datetime(2026, 7, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 28, tzinfo=timezone.utc),
    )

    assert rejected == 0
    assert len(accepted) == 2
    assert accepted[0].published_at.startswith("2026-07-15")
    assert accepted[1].published_at.startswith("2026-07-18")


def test_search_and_url_date_helpers_cover_official_formats():
    assert _extract_date_hint("Published 15 July 2026")
    assert _extract_date_hint("Published July 15 2026")
    assert _extract_url_date_hint(
        "https://www.info.gov.hk/gia/general/202607/19/P2026071900709.htm"
    ).startswith("2026-07-19")


def test_official_search_detects_portuguese_and_spanish_enforcement_titles():
    assert _looks_like_enforcement(
        "Receita Federal apreende caminhão com contrabando",
        "",
    )
    assert _looks_like_enforcement(
        "Aduanas incautó cinco kilos de cocaína",
        "",
    )
    assert _extract_portuguese_date(
        '<span class="documentPublished">'
        '<span class="value">14/07/2026 09h24</span></span>'
    ) == "2026-07-14T12:24:00+00:00"


def test_major_drug_case_does_not_require_china_nexus(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":95,
            "basis":"major cross-border drug seizure",
            "inclusion_basis":"major_enforcement",
            "evidence_quote":"officers seized 25 kilograms of cocaine",
            "mainland_nexus_evidence":"",
            "enforcement_action":"seizure of cocaine"
        }]}"""}),
    )
    item = FetchItem(
        title="Customs officers seize cocaine at international port",
        content=(
            "On 20 July 2026, customs officers seized 25 kilograms of cocaine "
            "from a container and arrested two suspects."
        ),
        url="https://customs.example.gov/news/cocaine-seizure",
        published_at="2026-07-20T00:00:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    assert approved == [item]
    assert item.raw_metadata["enforcement_review"]["inclusion_basis"] == "major_enforcement"
    assert (
        item.raw_metadata["enforcement_review"]["china_relevance_level"]
        == "major_non_china"
    )


def test_strong_china_nexus_is_verified_and_classified(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":96,
            "basis":"shipment originated in mainland China",
            "inclusion_basis":"strong_china_nexus",
            "evidence_quote":"officers seized 10,412 tablets",
            "mainland_nexus_evidence":"The shipment originated from China",
            "enforcement_action":"seized unapproved medicines"
        }]}"""}),
    )
    item = FetchItem(
        title="Customs intercepts unapproved medicines",
        content=(
            "The shipment originated from China and was destined for New York. "
            "Customs officers seized 10,412 tablets of unapproved medicines."
        ),
        url="https://www.cbp.gov/newsroom/china-shipment",
        published_at="2026-07-20T00:00:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    review = item.raw_metadata["enforcement_review"]
    assert approved == [item]
    assert review["inclusion_basis"] == "strong_china_nexus"
    assert review["china_relevance_level"] == "strong"
    assert review["china_relevance_label"] == "强涉华关联"


def test_weak_china_nexus_is_verified_and_classified(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":90,
            "basis":"seized shipment contained Chinese-made products",
            "inclusion_basis":"weak_china_nexus",
            "evidence_quote":"customs seized counterfeit electronics",
            "mainland_nexus_evidence":"the shipment contained Chinese-made electronics",
            "enforcement_action":"seized counterfeit electronics"
        }]}"""}),
    )
    item = FetchItem(
        title="Customs seizes counterfeit electronics",
        content=(
            "Customs seized counterfeit electronics at the port; "
            "the shipment contained Chinese-made electronics."
        ),
        url="https://customs.example.gov/news/electronics",
        published_at="2026-07-20T00:00:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    review = item.raw_metadata["enforcement_review"]
    assert approved == [item]
    assert review["inclusion_basis"] == "weak_china_nexus"
    assert review["china_relevance_level"] == "weak"


def test_missing_model_nexus_quote_is_recovered_from_source(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":93,
            "basis":"China-linked shipment",
            "inclusion_basis":"strong_china_nexus",
            "evidence_quote":"CBP officers seized the parcel",
            "mainland_nexus_evidence":"",
            "enforcement_action":"seized the parcel"
        }]}"""}),
    )
    item = FetchItem(
        title="CBP intercepts restricted parcel",
        content=(
            "The parcel was shipped from China to California. "
            "CBP officers seized the parcel at the airport."
        ),
        url="https://www.cbp.gov/newsroom/restricted-parcel",
        published_at="2026-07-20T00:00:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    review = item.raw_metadata["enforcement_review"]
    assert approved == [item]
    assert review["china_relevance_level"] == "strong"
    assert "shipped from China" in review["mainland_nexus_evidence"]


def test_major_case_allows_action_quote_when_contraband_is_elsewhere_in_source(
    monkeypatch, tmp_path,
):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":95,
            "basis":"official tobacco enforcement operation",
            "inclusion_basis":"major_enforcement",
            "evidence_quote":"21 warrants executed on eight retail outlets",
            "mainland_nexus_evidence":"",
            "enforcement_action":"executed 21 warrants"
        }]}"""}),
    )
    item = FetchItem(
        title="Customs operation targets illicit tobacco network",
        content=(
            "Customs investigated an illicit tobacco network. "
            "21 warrants executed on eight retail outlets and six homes."
        ),
        url="https://customs.example.gov/news/tobacco-operation",
        published_at="2026-07-20T00:00:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    assert approved == [item]


def test_major_case_accepts_chinese_action_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":94,
            "basis":"境外海关实施具体毒品查获行动",
            "inclusion_basis":"major_enforcement",
            "evidence_quote":"该国海关在港口查获约三百公斤毒品",
            "mainland_nexus_evidence":"",
            "enforcement_action":"查获约三百公斤毒品"
        }]}"""}),
    )
    item = FetchItem(
        title="境外海关查获一批走私毒品",
        content="该国海关在港口查获约三百公斤毒品，案件正在进一步调查。",
        url="https://customs.example.gov/news/drug-seizure",
        published_at="2026-07-20T00:00:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    assert approved == [item]


def test_major_case_accepts_portuguese_customs_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":92,
            "basis":"巴西海关实施大宗毒品查获行动",
            "inclusion_basis":"major_enforcement",
            "evidence_quote":"Receita Federal retém 600 kg de substância análoga à maconha",
            "mainland_nexus_evidence":"",
            "enforcement_action":"retenção de 600 kg de maconha"
        }]}"""}),
    )
    item = FetchItem(
        title="Receita Federal retém 600 kg de substância análoga à maconha",
        content=(
            "Receita Federal retém 600 kg de substância análoga à maconha "
            "na Aduana da Ponte Internacional da Amizade."
        ),
        url="https://www.gov.br/receitafederal/noticias/operacao",
        published_at="2026-07-14T12:24:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    assert approved == [item]


def test_major_case_accepts_punctuation_normalized_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":91,
            "basis":"澳大利亚边防部门查获大量非法烟草",
            "inclusion_basis":"regional_jurisdiction",
            "evidence_quote":"ABF seized over 2,300 tonnes of illicit tobacco",
            "mainland_nexus_evidence":"",
            "enforcement_action":"seized illicit tobacco"
        }]}"""}),
    )
    item = FetchItem(
        title="Record seizures highlight crackdown on illicit tobacco",
        content="ABF seized over 2 300 tonnes of illicit tobacco during operations.",
        url="https://www.abf.gov.au/newsroom/tobacco",
        published_at="2026-07-19T14:00:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    assert approved == [item]
    assert (
        item.raw_metadata["enforcement_review"]["inclusion_basis"]
        == "major_enforcement"
    )


def test_major_case_accepts_portuguese_located_drugs_evidence(
    monkeypatch, tmp_path,
):
    monkeypatch.setattr(
        "app.enforcement_review.QUEUE_FILE",
        tmp_path / "review.json",
    )
    monkeypatch.setattr(
        "app.enforcement_review.call_llm",
        AsyncMock(return_value={"content": """{"decisions":[{
            "index":0,
            "decision":"approve",
            "confidence":93,
            "basis":"巴西海关发现大宗毒品",
            "inclusion_basis":"major_enforcement",
            "evidence_quote":"foi localizado um compartimento oculto com 477,80 kg de substância análoga à maconha",
            "mainland_nexus_evidence":"",
            "enforcement_action":"localização e retenção de 477,80 kg"
        }]}"""}),
    )
    item = FetchItem(
        title="Operação conjunta retém 477,80 kg de maconha",
        content=(
            "Durante a fiscalização, foi localizado um compartimento oculto "
            "com 477,80 kg de substância análoga à maconha."
        ),
        url="https://www.gov.br/receitafederal/noticias/operacao-477",
        published_at="2026-07-09T12:04:00+00:00",
    )
    model = SimpleNamespace(is_active=True, api_key="configured", model_name="test")

    approved = asyncio.run(review_enforcement_candidates([item], model))

    assert approved == [item]
