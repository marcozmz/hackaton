"""IA para simplificar o texto da recomendação (desejável).

Dados oficiais → regras → contexto estruturado → IA → guard → texto. Falhou em qualquer
ponto (sem provider, timeout, cota, guard reprovou) → texto do template. Nunca no caminho
crítico: a recomendação sai sem IA; isto é chamado sob demanda (botão "explicar mais simples").
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from flask import current_app

from app.domain.narrative import guard
from app.errors import UpstreamUnavailable
from app.extensions import cache
from app.providers.registry import provider

log = logging.getLogger(__name__)
PROMPT = Path(__file__).resolve().parent.parent / "domain" / "narrative" / "prompts" / "simplify_pt_BR.md"
PROMPT_VERSION = "simplify-1"


def build_context(rec: dict) -> dict:
    """Contexto ENXUTO e sem identificação pessoal (só o que o texto pode usar)."""
    w = rec.get("recommended_window") or {}
    ctx = {
        "cultura": rec["crop"]["name"],
        "municipio": f'{rec["location"]["name"]}/{rec["location"]["uf"]}',
        "decisao": rec["title"],
        "resumo": rec["summary"],
        "risco": rec["risk_level"],
        "janela_de_plantio": {"de": w.get("start"), "ate": w.get("end"), "texto": w.get("label")} if w else None,
        "motivos": [r["text"] for r in rec["explanation"]["why"]][:5],
        "o_que_fazer": rec["actions"][:4],
    }
    if (f := rec.get("forecast") or {}).get("summary"):
        ctx["previsao"] = f["summary"]
    if (i := rec.get("insurance") or {}).get("text"):
        ctx["seguro"] = i["text"]
    return ctx


def template_text(rec: dict) -> str:
    parts = [rec["title"] + ".", rec["summary"]]
    if rec["actions"]:
        parts.append(rec["actions"][0])
    return " ".join(parts)


class SimplifyService:
    def simplify(self, rec: dict, level: str = "simple") -> dict:
        context = build_context(rec)
        fallback = {"text": template_text(rec), "generated_by": "template", "model": None}
        llm = provider("llm")
        if llm is None:
            return {**fallback, "fallback_reason": "ia_desligada"}

        key = "llm:" + hashlib.sha256(
            json.dumps([context, level, llm.model, PROMPT_VERSION], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:32]
        if (hit := cache.get(key)) is not None:
            return hit

        system = PROMPT.read_text(encoding="utf-8").replace("{level}", level)
        try:
            res = llm.complete(
                system=system,
                user=json.dumps(context, ensure_ascii=False),
                max_tokens=current_app.config["LLM_MAX_TOKENS"],
                timeout=current_app.config["LLM_TIMEOUT"],
            )
        except UpstreamUnavailable:
            return {**fallback, "fallback_reason": "ia_indisponivel"}

        text = res.text.replace("**", "").strip()  # negrito de markdown não tem uso no texto falado/lido
        check = guard.check(text, context)
        # Log sem o texto (pode conter conteúdo do usuário no futuro chat): só métricas.
        log.info("llm model=%s latency_ms=%s out_tokens=%s guard_passed=%s",
                 res.model, res.latency_ms, res.output_tokens, check.ok)
        if not check.ok:
            return {**fallback, "fallback_reason": "guard_reprovou", "guard_problems": check.problems}

        out = {"text": text, "generated_by": "llm", "model": res.model, "prompt_version": PROMPT_VERSION}
        cache.set(key, out, timeout=current_app.config["LLM_CACHE_TTL"])
        return out
