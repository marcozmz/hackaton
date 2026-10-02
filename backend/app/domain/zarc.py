"""Interpretação pura das zonas ZARC: combina solos, ciclos e variantes numa janela.

Regras de combinação (documentadas em files/06-recommendation-engine.md):
- **Solo** (vários códigos para o mesmo grupo, ou solo não informado) e **nível de
  manejo** (NM1–NM4 da soja, que o agricultor não informa): conservador —
  o decêndio só vale se valer em todos os solos considerados, com o maior risco.
- **Ciclo / variante / clima** (ex.: Milho 1ª e 2ª safra, Grupo I e II): opções
  diferentes para o agricultor — o decêndio vale se valer em pelo menos uma, com o menor risco.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.domain.context import ZoneFacts
from app.domain.decendio import Segment, segments

CYCLE_LABELS = {
    13: "Perene",
    19: "Semiperene",
    20: "Grupo I",
    21: "Grupo II",
    22: "Grupo III",
    24: "Grupo IV",
    25: "Grupo V",
    26: "Grupo VI",
}
CYCLE_GROUP_NUMBER = {20: "1", 21: "2", 22: "3", 24: "4", 25: "5", 26: "6"}
MANAGEMENT_LABELS = {1: "Sequeiro", 2: "Irrigado", 3: "Irrigado com controle de geada"}


@dataclass(frozen=True)
class PlantingOption:
    zarc_crop_name: str
    cycle_code: int
    climate_code: int
    windows: dict[int, int]

    @property
    def cycle_label(self) -> str:
        return CYCLE_LABELS.get(self.cycle_code, f"Ciclo {self.cycle_code}")

    @property
    def segments(self) -> list[Segment]:
        return segments(self.windows)


@dataclass(frozen=True)
class CombinedWindow:
    windows: dict[int, int]  # decêndio → menor risco entre as opções
    options: tuple[PlantingOption, ...]
    soil_codes: tuple[int, ...]

    @property
    def segments(self) -> list[Segment]:
        return segments(self.windows)

    def options_open_at(self, decendio: int) -> list[PlantingOption]:
        return [o for o in self.options if decendio in o.windows]

    def segment_containing(self, decendio: int) -> Segment | None:
        return next((s for s in self.segments if decendio in s), None)

    def next_segment(self, decendio: int) -> Segment | None:
        future = [s for s in self.segments if decendio not in s]
        return min(future, key=lambda s: s.distance_from(decendio), default=None)


def _conservative(windows_list: list[dict[int, int]]) -> dict[int, int]:
    common = set.intersection(*(set(w) for w in windows_list)) if windows_list else set()
    return {d: max(w[d] for w in windows_list) for d in common}


def combine(zones: list[ZoneFacts] | tuple[ZoneFacts, ...]) -> CombinedWindow:
    by_option: dict[tuple, list[ZoneFacts]] = defaultdict(list)
    for z in zones:
        by_option[(z.zarc_crop_name, z.cycle_code, z.climate_code)].append(z)

    options: list[PlantingOption] = []
    for (name, cycle, climate), zs in sorted(by_option.items()):
        merged = _conservative([z.windows for z in zs])
        options.append(PlantingOption(name, cycle, climate, merged))

    combined: dict[int, int] = {}
    for o in options:
        for d, r in o.windows.items():
            combined[d] = min(r, combined.get(d, 100))
    soil_codes = tuple(sorted({z.soil_code for z in zones}))
    return CombinedWindow(combined, tuple(options), soil_codes)
