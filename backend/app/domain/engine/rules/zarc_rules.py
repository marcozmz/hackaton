"""Regras do ZARC: cobertura e janela de plantio."""
from __future__ import annotations

from datetime import datetime, time, timezone

from app.domain import decendio as dec
from app.domain.context import AgroContext, ZarcFacts
from app.domain.engine import thresholds as th
from app.domain.engine.finding import Evidence, Finding
from app.domain.risk import Severity, zarc_risk_severity
from app.domain.zarc import CombinedWindow, combine

SOURCE = "zarc_tabua_risco"


def _zarc(ctx: AgroContext) -> ZarcFacts | None:
    return ctx.facts.get("zarc")


def _end_of_decendio_utc(ctx: AgroContext) -> datetime:
    return datetime.combine(dec.end_of_decendio(ctx.as_of), time(23, 59), tzinfo=timezone.utc)


class ZarcCoverageRule:
    """Sem zoneamento para (município, cultura) ⇒ no_data. Nunca 'risco alto'."""

    id, version = "zarc_coverage", "1.0"

    def applies(self, ctx: AgroContext) -> bool:
        return True

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        z = _zarc(ctx)
        if z and z.zones:
            if not z.is_current_season:
                return [
                    Finding(
                        "zarc_old_season", Severity.INFO, 0.3,
                        Evidence(SOURCE, z.dataset_version_id, {"version": z.version_label}),
                        self.id, self.version,
                        params={"version": z.version_label},
                        confidence_penalty=th.CONFIDENCE_PENALTY["zarc_old_season"],
                        gap="zarc_old_season",
                    )
                ]
            return []
        return [
            Finding(
                "zarc_no_coverage", Severity.INFO, 1.0,
                Evidence(SOURCE, z.dataset_version_id if z else None, {}),
                self.id, self.version,
                params={"crop": ctx.crop.name, "municipality": ctx.municipality.name},
                actions=("seek_technical_assistance",),
                blocks_recommendation=True,
            )
        ]


class ZarcWindowRule:
    """Hoje está dentro/fora da janela oficial; risco do decêndio; próxima janela."""

    id, version = "zarc_window", "1.0"

    def applies(self, ctx: AgroContext) -> bool:
        z = _zarc(ctx)
        return bool(z and z.zones)

    def evaluate(self, ctx: AgroContext) -> list[Finding]:
        z = _zarc(ctx)
        assert z is not None
        cw = combine(z.zones)
        today = dec.from_date(ctx.as_of)
        valid_until = _end_of_decendio_utc(ctx)
        base_data = {
            "decendio_today": today,
            "portarias": sorted({zz.portaria for zz in z.zones if zz.portaria}),
            "season": z.version_label,
            "soil_codes": list(cw.soil_codes),
            "options": [
                {
                    "variant": o.zarc_crop_name,
                    "cycle": o.cycle_label,
                    "windows": [s.label() for s in o.segments],
                }
                for o in cw.options
            ],
        }

        def ev(extra: dict) -> Evidence:
            return Evidence(SOURCE, z.dataset_version_id, {**base_data, **extra}, valid_until)

        if not cw.windows:
            return [
                Finding(
                    "zarc_no_window", Severity.BLOCKING, 1.0, ev({}), self.id, self.version,
                    params={"crop": ctx.crop.name},
                    actions=("seek_technical_assistance",),
                )
            ]

        seg = cw.segment_containing(today)
        if seg:
            return self._inside(ctx, cw, seg, today, ev)
        return self._outside(ctx, cw, today, ev)

    def _window_params(self, ctx: AgroContext, seg: dec.Segment) -> dict:
        start, end = seg.dates(ctx.as_of)
        return {
            "window_label": seg.label(),
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
        }

    def _inside(self, ctx, cw: CombinedWindow, seg, today, ev) -> list[Finding]:
        risk = cw.windows[today]
        open_opts = cw.options_open_at(today)
        params = {
            **self._window_params(ctx, seg),
            "risk_pct": risk,
            "crop": ctx.crop.name,
            "options_open": sorted({f"{o.zarc_crop_name} ({o.cycle_label})" for o in open_opts}),
        }
        findings = [
            Finding(
                "zarc_in_window", zarc_risk_severity(risk), 1.0, ev({"risk_pct": risk}),
                self.id, self.version, params=params,
                actions=("prepare_soil", "plant_in_window"),
            )
        ]
        remaining = len(seg.decendios) - 1 - seg.decendios.index(today)
        if remaining < th.WINDOW_CLOSING_DECENDIOS + 1:
            findings.append(
                Finding(
                    "zarc_window_closing", Severity.INFO, 0.8, ev({"remaining_decendios": remaining}),
                    self.id, self.version, params=params, actions=("plant_soon",),
                )
            )
        if risk > 20:
            better = [d for d, r in cw.windows.items() if r < risk and d != today]
            if better:
                best_seg = min(
                    dec.segments(better), key=lambda s: s.distance_from(today)
                )
                start, end = best_seg.dates(ctx.as_of)
                findings.append(
                    Finding(
                        "zarc_lower_risk_period", Severity.INFO, 0.5,
                        ev({"lower_risk_decendios": sorted(better)}),
                        self.id, self.version,
                        params={
                            **params,
                            "better_label": best_seg.label(),
                            "better_start": start.isoformat(),
                            "better_risk_pct": min(cw.windows[d] for d in best_seg.decendios),
                        },
                        actions=("consider_lower_risk_period",),
                    )
                )
        return findings

    def _outside(self, ctx, cw: CombinedWindow, today, ev) -> list[Finding]:
        nxt = cw.next_segment(today)
        assert nxt is not None
        distance = nxt.distance_from(today)
        params = {
            **self._window_params(ctx, nxt),
            "crop": ctx.crop.name,
            "risk_pct": min(cw.windows[d] for d in nxt.decendios),
            "decendios_until": distance,
            "soon": distance <= th.NEXT_WINDOW_SOON_DECENDIOS,
        }
        actions = ("prepare_for_next_window",) if params["soon"] else ("wait_window",)
        return [
            Finding(
                "zarc_out_of_window", Severity.HIGH, 1.0, ev({"next_decendios": list(nxt.decendios)}),
                self.id, self.version, params=params, actions=actions,
            )
        ]
