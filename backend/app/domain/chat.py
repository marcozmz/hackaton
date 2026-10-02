"""Entendimento de mensagens do assistente (puro, determinístico).

A IA nunca decide a intenção nem os fatos: regras simples escolhem a "ferramenta"
(recomendação, previsão, cultivares, seguro, glossário) e os dados vêm dos services.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.text import normalize_name

INTENTS = {
    # ordem importa: a primeira que casar vence
    "out_of_scope_pests": r"\b(praga|pragas|lagarta|lagartas|pulgao|inseto|insetos|doenca|fungo|agrotox\w*|veneno|defensivo\w*|herbicida|inseticida|fungicida|adubo|adubacao|fertiliz\w*)\b",
    "glossary": r"\b(o que (e|eh|significa|quer dizer)|que (e|eh) (o|a)|significa|explica(r)?|definicao)\b",
    "insurance": r"\b(seguro|psr|subvencao|proagro|apolice)\b",
    "varieties": r"\b(semente|sementes|cultivar|cultivares|variedade|variedades)\b",
    "weather": r"\b(chuva|chover|chove|previsao|tempo|temperatura|frio|calor|geada|seca|clima|vai chover)\b",
    "planting": r"\b(plantar|planto|plantio|semear|semeio|semeadura|epoca|janela|quando|posso|devo|hora de|risco)\b",
    "greeting": r"\b(oi|ola|bom dia|boa tarde|boa noite|ajuda|ajudar|o que voce faz)\b",
}
_COMPILED = {k: re.compile(v) for k, v in INTENTS.items()}
# "em/no/na <lugar>" no fim da frase (o service confirma se é mesmo um município).
_PLACE_RE = re.compile(r"\b(?:em|no|na)\s+([a-zà-ú' ]{3,40}?)(?:\s*[-/,]?\s*([a-z]{2}))?\s*(?:[?.!,]|$)", re.IGNORECASE)


@dataclass
class Parsed:
    intent: str
    text_norm: str
    crop_hint: str | None = None
    place_hint: str | None = None
    glossary_key: str | None = None
    extras: dict = field(default_factory=dict)


def detect_intent(text_norm: str) -> str:
    for name, rx in _COMPILED.items():
        if rx.search(text_norm):
            return name
    return "unknown"


def find_alias(text_norm: str, aliases: list[str]) -> str | None:
    """Maior alias que aparece como palavra(s) inteira(s) no texto ("feijao de corda" vence "feijao")."""
    padded = f" {text_norm} "
    for a in sorted(aliases, key=len, reverse=True):
        if len(a) >= 3 and f" {a} " in padded:
            return a
    return None


def find_glossary(text_norm: str, glossary: list[dict]) -> str | None:
    best, best_len = None, 0
    padded = f" {text_norm} "
    for t in glossary:
        for k in t["keys"]:
            kn = normalize_name(k)
            if f" {kn} " in padded and len(kn) > best_len:
                best, best_len = t["slug"], len(kn)
    return best


def find_place(raw_text: str) -> str | None:
    """'posso plantar milho em Araraquara SP?' → 'Araraquara SP'. Heurística; o service valida."""
    m = None
    for m in _PLACE_RE.finditer(raw_text):
        pass  # último "em X" costuma ser o lugar
    if not m:
        return None
    name = m.group(1).strip()
    if normalize_name(name) in {"casa", "agosto", "setembro", "outubro", "novembro", "dezembro", "janeiro",
                                "fevereiro", "marco", "abril", "maio", "junho", "julho", "minha regiao",
                                "minha roca", "minha terra", "semana", "esta semana", "essa semana"}:
        return None
    uf = m.group(2)
    return f"{name} {uf.upper()}" if uf else name


def parse(raw_text: str, crop_aliases: list[str], glossary: list[dict]) -> Parsed:
    norm = normalize_name(raw_text)
    intent = detect_intent(norm)
    crop = find_alias(norm, crop_aliases)
    gloss = find_glossary(norm, glossary) if intent in ("glossary", "unknown") else None
    if intent == "unknown" and crop:
        intent = "planting"  # "e o milho?" → segue o assunto plantio
    if intent == "unknown" and gloss:
        intent = "glossary"
    return Parsed(intent, norm, crop, find_place(raw_text), gloss)
