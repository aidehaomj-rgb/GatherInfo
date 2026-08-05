"""Deterministic text-language quality checks used before Chinese publication."""
from __future__ import annotations

import re
import unicodedata


_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def is_substantially_chinese(
    value: object,
    *,
    minimum_han: int = 2,
    minimum_ratio: float = 0.50,
) -> bool:
    """Require enough Han characters and reject text that remains mostly Latin."""
    text = str(value or "").strip()
    han_count = len(_HAN_RE.findall(text))
    letter_count = sum(unicodedata.category(char).startswith("L") for char in text)
    if han_count < minimum_han or letter_count == 0:
        return False
    return han_count / letter_count >= minimum_ratio


__all__ = ["is_substantially_chinese"]
