"""Narrator: códigos do engine → texto simples, por nível de linguagem.

Determinístico e testável. A IA (desejável) só reescreve o resultado daqui.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from app.domain.context import AgroContext
from app.domain.decendio import MONTHS_FULL
from app.domain.engine.engine import EngineResult
from app.domain.risk import Status

MESSAGES = Path(__file__).parent / "messages" / "pt_BR.yaml"
FALLBACK = {"technical": ("technical", "standard", "simple"), "standard": ("standard", "simple"), "simple": ("simple",)}


class SafeDict(dict):
    def __missing__(self, key):  # variável ausente não quebra o texto
        return "—"


@lru_cache(maxsize=1)
def load_messages() -> dict:
    with open(MESSAGES, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def date_text(iso: str | None) -> str:
    if not iso:
        return "—"
    d = date.fromisoformat(iso)
    return f"{d.day} de {MONTHS_FULL[d.month - 1]}"


@dataclass
class Narrative:
    title: str
    summary: str
    reason: str
    actions: list[str]
    reasons: list[dict]  # [{code, severity, text, source_id}]
    assumptions: list[str]
    gaps: list[str]


class Narrator:
    def __init__(self, messages: dict | None = None):
        self.m = messages or load_messages()

    def _pick(self, entry, level: str) -> str:
        if isinstance(entry, str):
            return entry
        for lv in FALLBACK.get(level, ("simple",)):
            if lv in entry:
                return entry[lv]
        return next(iter(entry.values()))

    def _fmt(self, template: str, params: dict) -> str:
        return template.format_map(SafeDict(params))

    def _params(self, ctx: AgroContext, result: EngineResult, extra: dict | None = None) -> dict:
        p = {
            "crop": ctx.crop.name.lower(),
            "municipality": ctx.municipality.name,
            "uf": ctx.municipality.uf,
            "risk_word": self.m["risk_words"].get(result.risk_level.value, ""),
        }
        p.update(result.window or {})
        p.update(extra or {})
        p["crop"] = ctx.crop.name.lower()
        for key in ("window_start", "window_end", "better_start"):
            if key in p:
                p[f"{key}_text"] = date_text(p[key])
        if "options_open" in p:
            p["options_open_text"] = ", ".join(p["options_open"])
        return p

    def narrate(self, ctx: AgroContext, result: EngineResult) -> Narrative:
        level = ctx.language_level
        base = self._params(ctx, result)

        status_key = result.status.value
        if result.status == Status.UNFAVORABLE and not result.window:
            status_key = "unfavorable_no_window"
        title = self._fmt(self.m["titles"][result.status.value], base)
        summary = self._fmt(self._pick(self.m["summaries"][status_key], level), base)

        reasons = []
        for f in result.findings:
            tpl = self.m["findings"].get(f.code)
            if not tpl:
                continue
            reasons.append(
                {
                    "code": f.code,
                    "severity": f.severity.name.lower(),
                    "text": self._fmt(self._pick(tpl, level), self._params(ctx, result, f.params)),
                    "source_id": f.evidence.source_id if f.evidence.source_id != "engine" else None,
                }
            )

        actions = []
        for code in result.actions:
            tpl = self.m["actions"].get(code)
            if not tpl:
                continue
            owner = next((f for f in result.findings if code in f.actions), None)
            actions.append(self._fmt(tpl, self._params(ctx, result, owner.params if owner else None)))

        return Narrative(
            title=title,
            summary=summary,
            reason=reasons[0]["text"] if reasons else summary,
            actions=actions,
            reasons=reasons,
            assumptions=[self.m["assumptions"].get(a, a) for a in result.assumptions],
            gaps=[self.m["gaps"].get(g, g) for g in result.gaps],
        )
