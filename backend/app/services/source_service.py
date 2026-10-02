from __future__ import annotations

from app.repositories import source_repo


def version_ref(dataset_code: str, name: str, version) -> dict:
    return {
        "id": dataset_code,
        "name": name,
        "version": version.version_label if version else None,
        "extracted_at": version.extracted_at.isoformat() if version else None,
    }


def forecast_ref(fc) -> dict:
    return {
        "id": "open_meteo",
        "name": "Open-Meteo (previsão do tempo)",
        "version": fc.provider,
        "fetched_at": fc.fetched_at.isoformat(timespec="seconds"),
        "extracted_at": fc.fetched_at.date().isoformat(),
    }


class SourceService:
    def list(self) -> list[dict]:
        out = []
        for ds, src, v in source_repo.datasets_with_current_version():
            out.append(
                {
                    "id": ds.code,
                    "name": ds.name,
                    "organization": src.organization or src.name,
                    "license": src.license,
                    "format": ds.format,
                    "url": ds.methodology_url or src.homepage_url,
                    "version": v.version_label if v else None,
                    "extracted_at": v.extracted_at.isoformat() if v else None,
                    "row_count": v.row_count if v else 0,
                    "status": "live" if ds.format == "api" else ("loaded" if v else "not_loaded"),
                }
            )
        return out
