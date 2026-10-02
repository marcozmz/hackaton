"""Seguro rural ("proteja sua safra") a partir dos agregados do SISSER/PSR.

Privacidade: célula com menos de K apólices não é exibida no nível do município
(poderia expor um produtor) — sobe para o agregado do estado.
"""
from __future__ import annotations

from app.domain.context import CropRef, InsuranceFacts, MunicipalityRef
from app.repositories import insurance_repo

K_ANONYMITY = 3


def _with_rates(stat: dict) -> dict:
    premium, amount, subsidy = stat["premium_total"], stat["insured_amount"], stat["subsidy_total"]
    return {
        **stat,
        "avg_premium_rate_pct": round(100 * premium / amount, 1) if amount else None,
        "subsidy_share_pct": round(100 * subsidy / premium, 1) if premium else None,
    }


class InsuranceService:
    def facts(self, m: MunicipalityRef, crop: CropRef) -> InsuranceFacts | None:
        version = insurance_repo.current()
        if version is None:
            return None
        year = insurance_repo.latest_year(version.id)
        if year is None:
            return None

        crop_mun = insurance_repo.municipality_stat(version.id, m.ibge_code, crop.id, year)
        if crop_mun and crop_mun["policies_count"] >= K_ANONYMITY:
            scope, stat, about_crop = "municipality", crop_mun, True
        else:
            crop_uf = insurance_repo.uf_stat(version.id, m.uf, crop.id, year)
            all_mun = insurance_repo.municipality_stat(version.id, m.ibge_code, None, year)
            if crop_uf and crop_uf["policies_count"] >= K_ANONYMITY:
                scope, stat, about_crop = "uf", crop_uf, True
            elif all_mun and all_mun["policies_count"] >= K_ANONYMITY:
                scope, stat, about_crop = "municipality", all_mun, False
            else:
                scope, stat, about_crop = "none", None, False

        return InsuranceFacts(
            dataset_version_id=version.id,
            version_label=version.version_label,
            year=year,
            scope=scope,
            about_crop=about_crop,
            stat=_with_rates(stat) if stat else None,
        )

    def present(self, facts: InsuranceFacts | None, m: MunicipalityRef, text: str | None) -> dict:
        if facts is None:
            return {"status": "unavailable", "source_id": "sisser"}
        if facts.stat is None:
            return {"status": "no_data", "year": facts.year, "text": text, "source_id": "sisser"}
        s = facts.stat
        return {
            "status": "ok",
            "year": facts.year,
            "scope": facts.scope,  # municipality | uf
            "scope_name": m.name if facts.scope == "municipality" else m.uf,
            "about_crop": facts.about_crop,
            "policies_count": s["policies_count"],
            "insured_area_ha": round(s["insured_area_ha"]),
            "avg_premium_rate_pct": s["avg_premium_rate_pct"],
            "subsidy_share_pct": s["subsidy_share_pct"],
            "text": text,
            "notes": [
                "Dados agregados do Programa de Subvenção ao Seguro Rural (PSR/MAPA).",
                "A base aberta não traz informações de sinistros.",
            ],
            "source_id": "sisser",
        }
