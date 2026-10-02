"""Assistente Plant+Facil: pergunta → intenção (regras) → ferramenta determinística → resposta.

Ferramentas = os mesmos services da aplicação (recomendação, previsão, cultivares, seguro,
glossário). A IA (opcional) só reescreve a resposta da recomendação, com guard.
O servidor NÃO guarda as conversas (o histórico fica no navegador).
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from flask import url_for

from app.domain import chat as chat_domain
from app.domain.context import MunicipalityRef
from app.errors import AppError, LocationAmbiguous
from app.models import User
from app.repositories import catalog_repo
from app.services.crop_service import CropService
from app.services.location_service import LocationService
from app.services.recommendation_service import RecommendationService
from app.services.simplify_service import SimplifyService
from app.services.weather_service import WeatherService

GLOSSARY = Path(__file__).resolve().parent.parent / "seeds" / "glossary.yaml"
DEFAULT_SUGGESTIONS = [
    "Quando plantar milho na minha região?",
    "Vai chover nos próximos dias?",
    "Quais sementes de feijão são indicadas?",
    "O que é o ZARC?",
]


@lru_cache(maxsize=1)
def glossary() -> list[dict]:
    return yaml.safe_load(GLOSSARY.read_text(encoding="utf-8"))["terms"]


def _aliases() -> list[str]:
    return sorted({a[1] for a in catalog_repo.all_aliases()})


class ChatService:
    def __init__(self):
        self.locations = LocationService()
        self.crops = CropService()

    # --- contexto: lugar, cultura, solo ------------------------------------
    def _location(self, parsed, ctx: dict, user: User | None):
        """(MunicipalityRef | None, pergunta_de_esclarecimento | None)."""
        if parsed.place_hint:
            try:
                return self.locations.by_text(parsed.place_hint).municipality, None
            except LocationAmbiguous as e:
                options = [f'{c["name"]} {c["uf"]}' for c in e.details.get("candidates", [])][:5]
                return None, {"text": "Achei mais de um lugar com esse nome. Qual deles?", "suggestions": options}
            except AppError:
                pass  # "em casa", "na minha roça"... não era município
        if ctx.get("municipality"):
            try:
                return self.locations.by_ibge(int(ctx["municipality"])).municipality, None
            except (AppError, ValueError):
                pass
        if user and user.farm:
            return self.locations.by_ibge(user.farm.municipality_ibge).municipality, None
        return None, None

    def _crop(self, parsed, ctx: dict, user: User | None, uf: str | None):
        for term in (parsed.crop_hint, ctx.get("crop")):
            if term:
                try:
                    return self.crops.resolve(term, uf)
                except AppError:
                    continue
        if user and user.farm and user.farm.plantings:
            c = catalog_repo.crop_by_id(user.farm.plantings[0].crop_id)
            return self.crops.resolve(c.slug, uf)
        return None

    @staticmethod
    def _soil(user: User | None, m: MunicipalityRef | None) -> str | None:
        if user and user.farm and m and user.farm.municipality_ibge == m.ibge_code and user.farm.soil_group:
            return str(user.farm.soil_group)
        return None

    # --- entrada -------------------------------------------------------------
    def reply(self, text: str, ctx: dict | None, user: User | None) -> dict:
        ctx = dict(ctx or {})
        parsed = chat_domain.parse(text, _aliases(), glossary())
        handler = getattr(self, f"_on_{parsed.intent}", self._on_unknown)
        out = handler(parsed, ctx, user)
        out.setdefault("intent", parsed.intent)
        out.setdefault("suggestions", [])
        out.setdefault("context", ctx)
        out.setdefault("generated_by", "template")
        return out

    # --- intenções -------------------------------------------------------------
    def _ask_place(self, ctx, user, why="") -> dict:
        tip = "" if user else " Se você entrar na sua conta e cadastrar a propriedade, eu lembro da sua cidade."
        return {"text": f"Em qual município fica a sua roça?{why}{tip}",
                "suggestions": ["Em Araraquara SP", "Em Chapecó SC", "Em Sobral CE"], "context": ctx,
                "needs": "place"}

    def _on_planting(self, parsed, ctx, user) -> dict:
        m, clarify = self._location(parsed, ctx, user)
        if clarify:
            return {**clarify, "context": ctx}
        crop = self._crop(parsed, ctx, user, m.uf if m else None)
        if crop:
            ctx["crop"] = crop.slug
        if m is None:
            return self._ask_place(ctx, user)
        ctx["municipality"] = m.ibge_code
        if crop is None:
            names = [c.official_name for c in catalog_repo.list_crops()]
            return {"text": "O que você quer plantar?", "suggestions": [f"E {n.lower()}?" for n in names[:6]],
                    "context": ctx, "needs": "crop"}
        level = user.language_level if user else "simple"
        rec = RecommendationService().planting_advice(
            municipality=m.ibge_code, crop=crop.slug, soil=self._soil(user, m), level=level
        )
        simple = SimplifyService().simplify(rec, level)
        w = rec.get("recommended_window") or {}
        return {
            "text": simple["text"],
            "generated_by": simple["generated_by"],
            "card": {
                "type": "planting",
                "title": rec["title"],
                "status": rec["status"],
                "risk_level": rec["risk_level"],
                "crop": rec["crop"]["name"],
                "place": f'{rec["location"]["name"]} - {rec["location"]["uf"]}',
                "window": w.get("label"),
                "soil": rec["soil"]["name"] if rec.get("soil") else "Não informado (período mais seguro)",
                "varieties": rec["varieties"]["count"],
                "link": url_for("web.clima", municipality=m.ibge_code, crop=crop.slug,
                                soil=self._soil(user, m) or ""),
                "source": "ZARC – Tábua de Risco (MAPA)",
            },
            "suggestions": [f"Vai chover em {m.name}?", f"Quais sementes de {crop.name.lower()}?",
                            "Tem seguro com ajuda do governo?"],
            "context": ctx,
        }

    def _on_weather(self, parsed, ctx, user) -> dict:
        m, clarify = self._location(parsed, ctx, user)
        if clarify:
            return {**clarify, "context": ctx}
        if m is None:
            return self._ask_place(ctx, user)
        ctx["municipality"] = m.ibge_code
        svc = WeatherService()
        try:
            fc = svc.forecast(m)
        except AppError:
            return {"text": "Não consegui ver a previsão do tempo agora. Tente de novo daqui a pouco.", "context": ctx}
        view = svc.present(fc, date.today(), user.language_level if user else "simple")
        heavy = [d for d in view["days"] if d["condition"] == "heavy_rain"]
        alert = (f' Atenção: chuva forte prevista na {heavy[0]["weekday"]} ({round(heavy[0]["precip_mm"])} mm).'
                 if heavy else "")
        return {
            "text": f'Em {m.name}: {view["summary"]}{alert}',
            "card": {"type": "weather", "place": f"{m.name} - {m.uf}", "days": view["days"], "source": "Open-Meteo"},
            "suggestions": ["Posso plantar agora?", "O que é o ZARC?"],
            "context": ctx,
        }

    def _on_varieties(self, parsed, ctx, user) -> dict:
        m, clarify = self._location(parsed, ctx, user)
        if clarify:
            return {**clarify, "context": ctx}
        crop = self._crop(parsed, ctx, user, m.uf if m else None)
        if m is None:
            if crop:
                ctx["crop"] = crop.slug
            return self._ask_place(ctx, user, " As sementes indicadas mudam de estado para estado.")
        ctx["municipality"] = m.ibge_code
        if crop is None:
            return {"text": "De qual cultura você quer saber as sementes indicadas?", "context": ctx,
                    "suggestions": ["Sementes de milho", "Sementes de feijão", "Sementes de feijão de corda"]}
        ctx["crop"] = crop.slug
        v = self.crops.varieties(crop.slug, m.uf)
        names = [i["name"] for i in v["items"]]
        if not names:
            text = (f"Não encontrei na lista oficial (ZARC – Cultivares) sementes de {crop.name.lower()} "
                    f"indicadas para {m.uf}. Vale perguntar a um técnico da Emater/ATER.")
        else:
            text = (f"Para {m.uf}, a lista oficial do ZARC indica {len(names)} cultivares de {crop.name.lower()}, "
                    f"por exemplo: {', '.join(names[:6])}. Confira com o técnico ou na loja qual se adapta à sua roça.")
        return {"text": text, "suggestions": [f"Quando plantar {crop.name.lower()}?"], "context": ctx,
                "card": {"type": "list", "title": f"Cultivares de {crop.name} ({m.uf})", "items": names[:20],
                         "source": "ZARC – Cultivares (MAPA)"}}

    def _on_insurance(self, parsed, ctx, user) -> dict:
        m, _ = self._location(parsed, ctx, user)
        crop = self._crop(parsed, ctx, user, m.uf if m else None)
        base = next(t for t in glossary() if t["slug"] == "psr")["text"]
        if m and crop:
            rec = RecommendationService().planting_advice(municipality=m.ibge_code, crop=crop.slug)
            ins = rec.get("insurance") or {}
            if ins.get("text"):
                return {"text": f'{ins["text"]} {base}', "context": {**ctx, "municipality": m.ibge_code,
                                                                       "crop": crop.slug},
                        "suggestions": [f"Quando plantar {crop.name.lower()}?"]}
        return {"text": base, "suggestions": ["O que é o ZARC?", "Quando plantar milho na minha região?"]}

    def _on_glossary(self, parsed, ctx, user) -> dict:
        slug = parsed.glossary_key or chat_domain.find_glossary(parsed.text_norm, glossary())
        term = next((t for t in glossary() if t["slug"] == slug), None)
        if term is None:
            return {"text": "Ainda não tenho uma explicação oficial para esse termo. Posso explicar: ZARC, decêndio, "
                            "risco, cultivar, sequeiro, janela de plantio, tipo de solo e seguro rural.",
                    "suggestions": ["O que é o ZARC?", "O que é decêndio?", "O que é cultivar?"]}
        return {"text": f'{term["term"]}: {term["text"]}', "source": term["source"],
                "suggestions": ["Quando plantar milho na minha região?", "O que é cultivar?"]}

    def _on_out_of_scope_pests(self, parsed, ctx, user) -> dict:
        return {"text": "Sobre pragas, doenças, adubos e defensivos eu ainda não tenho dados oficiais, então não vou "
                        "te indicar produto nem dose. Procure a assistência técnica da sua região (Emater/ATER) ou um "
                        "agrônomo. Posso ajudar com época de plantio, chuva, sementes indicadas e seguro rural.",
                "suggestions": DEFAULT_SUGGESTIONS[:3]}

    def _on_greeting(self, parsed, ctx, user) -> dict:
        who = f", {user.display_name.split()[0]}" if user else ""
        return {"text": f"Olá{who}! Eu consulto o calendário oficial de plantio (ZARC), a previsão do tempo, as "
                        "sementes indicadas e o seguro rural para te ajudar a decidir. Pergunte do seu jeito.",
                "suggestions": DEFAULT_SUGGESTIONS}

    def _on_unknown(self, parsed, ctx, user) -> dict:
        return {"text": "Não entendi bem. Eu sei responder sobre quando plantar, chuva nos próximos dias, sementes "
                        "indicadas, seguro rural e termos como ZARC. Tente uma destas:",
                "suggestions": DEFAULT_SUGGESTIONS}
