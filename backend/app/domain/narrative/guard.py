"""Validação pós-geração do texto da IA (files/08-ai.md §3).

A IA só pode reescrever: todo número e mês citados precisam existir no contexto,
sem termos proibidos (promessas, defensivos) e dentro do tamanho máximo.
Falhou → o chamador usa o texto do template.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

MAX_CHARS = 700
MONTHS = {
    "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "março": 3, "marco": 3, "mar": 3, "abril": 4, "abr": 4,
    "maio": 5, "mai": 5, "junho": 6, "jun": 6, "julho": 7, "jul": 7, "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9, "outubro": 10, "out": 10, "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12,
}
BANNED = (
    "garant", "com certeza", "sem risco", "risco zero", "agrotóx", "agrotox", "veneno", "defensivo",
    "inseticida", "herbicida", "fungicida", "http", "www.",
)
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_WORD = re.compile(r"[a-zà-ú]+", re.IGNORECASE)


@dataclass
class GuardResult:
    ok: bool
    problems: list[str] = field(default_factory=list)


def _numbers(text: str) -> set[str]:
    out: set[str] = set()
    for raw in _NUM.findall(text):
        out.add(raw.replace(".", "").replace(",", ""))  # 1.250 → 1250 · 39,8 → 398
        out.update(re.split(r"[.,]", raw))  # partes: 39 e 8; 2026-10-05 já vem separado
        out.add(raw.split(",")[0].replace(".", ""))  # parte inteira: 39,8 → 39
    return {n.lstrip("0") or "0" for n in out if n}


def _months(text: str) -> set[int]:
    return {MONTHS[w] for w in (m.lower() for m in _WORD.findall(text)) if w in MONTHS}


def allowed_from_context(context: dict) -> tuple[set[str], set[int]]:
    dumped = json.dumps(context, ensure_ascii=False)
    numbers = _numbers(dumped)
    months = _months(dumped) | {int(m) for m in re.findall(r"\d{4}-(\d{2})-\d{2}", dumped)}
    return numbers, months


def check(text: str, context: dict) -> GuardResult:
    problems: list[str] = []
    if not text or not text.strip():
        return GuardResult(False, ["vazio"])
    if len(text) > MAX_CHARS:
        problems.append(f"longo demais ({len(text)} > {MAX_CHARS})")
    lower = text.lower()
    problems += [f"termo proibido: {b}" for b in BANNED if b in lower]
    allowed_nums, allowed_months = allowed_from_context(context)
    invented = sorted(_numbers(text) - allowed_nums)
    if invented:
        problems.append(f"números fora do contexto: {', '.join(invented[:5])}")
    bad_months = sorted(_months(text) - allowed_months)
    if bad_months:
        problems.append(f"meses fora do contexto: {bad_months}")
    if re.search(r"^\s*#|\*\*|\[.+\]\(", text, re.MULTILINE):
        problems.append("formatação markdown")
    return GuardResult(not problems, problems)
