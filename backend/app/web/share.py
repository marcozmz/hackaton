"""Compartilhar no WhatsApp: mensagem curta, pronta, com fonte e link.

No campo a informação circula pelo WhatsApp (vizinhos, cooperativa, técnico da Emater).
O link wa.me só abre o WhatsApp do próprio usuário com o texto: nada é enviado sem ele confirmar.
Sem dado pessoal na mensagem (só cultura, município e a orientação).
"""
from __future__ import annotations

from urllib.parse import quote

MAX_LEN = 700


def share_link(text: str, url: str | None = None) -> str:
    msg = text.strip()
    if url:
        msg = f"{msg}\n{url}"
    return "https://wa.me/?text=" + quote(msg[:MAX_LEN])


def recommendation_text(rec: dict) -> str:
    """'🌱 Milho em Araraquara-SP: Ainda não é hora…' + melhor dia + 1ª ação + fonte."""
    loc = rec["location"]
    lines = [f'🌱 {rec["crop"]["name"]} em {loc["name"]}-{loc["uf"]}: {rec["title"]}.', rec["summary"]]
    bd = rec.get("best_day") or {}
    if bd.get("status") == "ok":
        lines.append(f'⭐ Melhor dia para semear: {bd["label"]}.')
    if rec.get("actions"):
        lines.append(f'👉 {rec["actions"][0]}')
    lines.append("Fonte: calendário oficial ZARC (MAPA). Via Plant+Facil.")
    return "\n".join(lines)
