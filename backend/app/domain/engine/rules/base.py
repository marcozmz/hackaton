from __future__ import annotations

from typing import Protocol

from app.domain.context import AgroContext
from app.domain.engine.finding import Finding


class Rule(Protocol):
    id: str
    version: str

    def applies(self, ctx: AgroContext) -> bool: ...

    def evaluate(self, ctx: AgroContext) -> list[Finding]: ...
