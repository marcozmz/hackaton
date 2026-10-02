"""Explicação detalhada — responde à visão §10:
o que foi recomendado · por quê · quais dados · qual período · qual fonte · qual confiança · qual ação.

Puro: recebe contexto, resultado do engine, narrativa e metadados das fontes (vindos do service).
"""
from __future__ import annotations

import re

from app.domain import decendio as dec
from app.domain.context import AgroContext
from app.domain.engine.engine import EngineResult
from app.domain.narrative.narrator import Narrative, Narrator, SafeDict, date_text
from app.domain.risk import Severity


_PORTARIA = re.compile(r"Port\.?\s*(\d+)\D+(\d{2})-(\d{2})-(\d{4})")


def portaria_text(raw: str) -> str:
    """'Port.21_de_16-03-2026' → 'Portaria nº 21, de 16/03/2026'."""
    m = _PORTARIA.search(raw or "")
    return f"Portaria nº {m.group(1)}, de {m.group(2)}/{m.group(3)}/{m.group(4)}" if m else raw


def _soil_code_name(code: int) -> str:
    return {1: "arenoso", 2: "textura média", 3: "argiloso"}.get(code, f"AD{code - 10}" if code >= 11 else str(code))


class Explainer:
    def __init__(self, narrator: Narrator | None = None):
        self.n = narrator or Narrator()
        self.m = self.n.m

    def _fmt(self, tpl: str, params: dict) -> str:
        return tpl.format_map(SafeDict(params))

    def _finding_params(self, ctx: AgroContext, result: EngineResult, f) -> dict:
        p = self.n._params(ctx, result, f.params)
        p.update({k: v for k, v in f.evidence.data.items() if k not in p})
        p["portarias_text"] = "; ".join(portaria_text(x) for x in p.get("portarias") or []) or "—"
        if isinstance(p.get("threshold"), (int, float)):
            p["threshold_int"] = round(p["threshold"])
        p["soil_codes_text"] = ", ".join(_soil_code_name(c) for c in p.get("soil_codes", []))
        p["resolved_by_text"] = self.m["resolved_by"].get(ctx.municipality.resolved_by, ctx.municipality.resolved_by)
        if "date" in p and isinstance(p["date"], str):
            p["date_text"] = date_text(p["date"])
        return p

    def explain(self, ctx: AgroContext, result: EngineResult, narrative: Narrative, sources: dict[str, dict]) -> dict:
        level = ctx.language_level
        ex = self.m["explanation"]
        risk_word = self.m["risk_words"].get(result.risk_level.value, "")

        # --- por quê: um motivo por achado, com dados usados e fonte ---------
        why = []
        texts = {r["code"]: r["text"] for r in narrative.reasons}
        for f in result.findings:
            if f.code not in texts:
                continue
            params = self._finding_params(ctx, result, f)
            src = f.evidence.source_id if f.evidence.source_id != "engine" else None
            why.append(
                {
                    "code": f.code,
                    "severity": f.severity.name.lower(),
                    "text": texts[f.code],
                    "data_used": [self._fmt(t, params) for t in self.m["evidence"].get(f.code, [])],
                    "source": sources.get(src) if src else None,
                    "rule": {"id": f.rule_id, "version": f.rule_version},
                }
            )

        # --- manchete: pior achado + o melhor argumento a favor --------------
        main = why[0] if why else None
        headline = self._fmt(
            self.n._pick(ex["headline"], level),
            {"risk_word": risk_word, "risk_level": result.risk_level.value,
             "main": main["text"] if main else narrative.summary, "main_code": main["code"] if main else "—"},
        )
        favor = next(
            (w for w in why[1:] if w["severity"] == Severity.OK.name.lower()),
            None,
        )
        if favor:
            headline += " " + self._fmt(ex["in_favor"], {"text": favor["text"]})

        # --- dados considerados ---------------------------------------------
        dc = self.m["data_considered"]
        m = ctx.municipality
        considered = [
            self._fmt(dc["location"], {"municipality": m.name, "uf": m.uf,
                                       "resolved_by_text": self.m["resolved_by"].get(m.resolved_by, m.resolved_by)}),
            self._fmt(dc["crop"], {"crop_name": ctx.crop.name,
                                   "matched_text": f" (você escreveu “{ctx.crop.matched_as}”)" if ctx.crop.matched_as
                                   and ctx.crop.matched_as.lower() != ctx.crop.name.lower() else ""}),
            self._fmt(dc["soil"], {"soil": ctx.soil.name}) if ctx.soil else dc["soil_none"],
            dc["management"],
        ]
        if "zarc_tabua_risco" in sources:
            considered.append(self._fmt(dc["zarc"], {"version": sources["zarc_tabua_risco"].get("version")}))
        if (v := ctx.facts.get("varieties")) is not None:
            considered.append(self._fmt(dc["varieties"], {"count": len(v.items), "uf": m.uf}))
        if (fc := ctx.facts.get("forecast")) is not None:
            considered.append(self._fmt(dc["forecast"], {
                "provider": "Open-Meteo",
                "fetched_at_text": fc.fetched_at.astimezone().strftime("%d/%m %H:%M"),
            }))

        # --- período analisado ----------------------------------------------
        today_dec = dec.from_date(ctx.as_of)
        start, end = dec.bounds(today_dec, ctx.as_of.year)
        period = {
            "as_of": ctx.as_of.isoformat(),
            "text": self._fmt(ex["period"], {
                "today": date_text(ctx.as_of.isoformat()),
                "decendio_label": f"{start.day} a {date_text(end.isoformat())}",
            }),
            "recommended_window": (result.window or {}).get("window_label"),
            "valid_until": result.valid_until.isoformat(timespec="seconds"),
        }
        if (fc := ctx.facts.get("forecast")) is not None:
            period["forecast_text"] = self._fmt(ex["forecast_horizon"], {"n_days": len(fc.upcoming(ctx.as_of, 7))})

        # --- opções de plantio do ZARC (para quem quer o detalhe) -----------
        options = []
        zfinding = next((f for f in result.findings if f.code.startswith("zarc_") and "options" in f.evidence.data), None)
        if zfinding:
            options = zfinding.evidence.data["options"]

        # --- confiança explicada --------------------------------------------
        reduced_items = narrative.gaps + narrative.assumptions
        reduced = self._fmt(ex["reduced_by"], {"items": "; ".join(reduced_items)}) if reduced_items else ex["not_reduced"]
        confidence_text = self._fmt(
            self.n._pick(ex["confidence"], level),
            {"confidence_word": self.m["confidence_words"][result.confidence_level.value],
             "score": f"{result.confidence_score:.2f}".replace(".", ","), "reduced": reduced},
        )

        return {
            "headline": headline,
            "what": {"title": narrative.title, "summary": narrative.summary},
            "why": why,
            "reasons": [{k: w[k] for k in ("code", "severity", "text")} | {"source_id": (w["source"] or {}).get("id")}
                        for w in why],  # formato curto (compatível)
            "data_considered": considered,
            "period": period,
            "planting_options": options,
            "confidence_text": confidence_text,
            "actions": narrative.actions,
        }
