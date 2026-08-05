"""Chinese publication checks must count every Unicode script."""
from app.language_quality import is_substantially_chinese


def test_accepts_chinese_text_with_limited_latin_acronyms() -> None:
    assert is_substantially_chinese(
        "欧盟EU发布进口电池监管新规，海关应核验商品范围和申报材料。",
        minimum_han=10,
    )


def test_rejects_japanese_text_with_kanji_but_dominant_kana() -> None:
    text = "税関輸入規制" + "についてのお知らせをこうしんしました" * 8
    assert is_substantially_chinese(text) is False


def test_rejects_cyrillic_or_arabic_dominant_mixed_text() -> None:
    cyrillic = "海关监管风险政策措施涉及商品" + "Таможенное регулирование" * 20
    arabic = "海关监管风险政策措施涉及商品" + "التنظيم الجمركي والتجارة" * 20

    assert is_substantially_chinese(cyrillic) is False
    assert is_substantially_chinese(arabic) is False
