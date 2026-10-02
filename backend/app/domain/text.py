"""Normalização de nomes (busca por município, cultura, alias)."""
from __future__ import annotations

import re

from unidecode import unidecode

_SPACES = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def normalize_name(value: str) -> str:
    """'Feijão-de-Corda ' -> 'feijao de corda'."""
    s = unidecode(value or "").lower()
    s = _PUNCT.sub(" ", s)
    return _SPACES.sub(" ", s).strip()
