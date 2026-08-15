from types import SimpleNamespace

from app.research_graph import _canonical


def test_entity_canonicalization_merges_spacing_and_punctuation():
    assert _canonical("ABC Logistics, Ltd.") == _canonical("ABC Logistics Ltd")
