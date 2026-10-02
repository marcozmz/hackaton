"""Fixtures: app em SQLite de memória com um mini-ZARC sintético (sem rede, sem arquivos reais)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import insert, select

from app import create_app
from app.domain.text import normalize_name
from app.extensions import db
from app.ingestion import base, catalog_seed
from app.models import (
    Crop,
    CropVariety,
    Municipality,
    SoilType,
    State,
    VarietyZone,
    ZarcWindow,
    ZarcZone,
)
from app.errors import UpstreamUnavailable
from app.providers.weather.base import DailyWeatherDTO, ForecastDTO
from app.repositories import territory_repo

ARARAQUARA, ARARAS, CAMPINAS = 3503208, 3503307, 3509502
DAY0 = date(2026, 10, 2)


class FakeWeather:
    """Provider controlável: `rain` = mm por dia a partir de DAY0; `down=True` simula queda."""

    name = "fake"

    def __init__(self):
        self.rain = [3.0] * 10
        self.down = False
        self.calls = 0

    def forecast(self, lat, lon, days=10):
        self.calls += 1
        if self.down:
            raise UpstreamUnavailable("fora do ar")
        out = tuple(
            DailyWeatherDTO(DAY0 + timedelta(days=i), 18.0, 29.0, mm, 60, 12.0, 4.0)
            for i, mm in enumerate(self.rain[:days])
        )
        return ForecastDTO(self.name, lat, lon, None, out, None)


def _seed_minimal():
    catalog_seed.seed_sources()
    catalog_seed.seed_soils()
    catalog_seed.seed_crops()
    db.session.add(State(uf="SP", ibge_code=35, name="São Paulo", macro_region="Sudeste"))
    db.session.add(State(uf="MG", ibge_code=31, name="Minas Gerais", macro_region="Sudeste"))
    db.session.add(State(uf="RS", ibge_code=43, name="Rio Grande do Sul", macro_region="Sul"))
    db.session.add(State(uf="PI", ibge_code=22, name="Piauí", macro_region="Nordeste"))
    for code, name, uf, lat, lon in [
        (ARARAQUARA, "Araraquara", "SP", -21.7845, -48.178),
        (ARARAS, "Araras", "SP", -22.3572, -47.3842),
        (CAMPINAS, "Campinas", "SP", -22.9053, -47.0659),
        (3100104, "Abadia dos Dourados", "MG", -18.4831, -47.3916),
        (3550308, "São Paulo", "SP", -23.5329, -46.6395),
        (4302303, "Bom Jesus", "RS", -28.6697, -50.4295),
        (2201903, "Bom Jesus", "PI", -9.07124, -44.359),
    ]:
        db.session.add(Municipality(ibge_code=code, name=name, name_normalized=normalize_name(name),
                                    uf=uf, centroid_lat=lat, centroid_lon=lon))
    db.session.commit()

    crops = {c.slug: c.id for c in db.session.scalars(select(Crop))}
    soils = {s.zarc_code: s.id for s in db.session.scalars(select(SoilType))}

    zv = base.start_version(base.get_dataset("zarc_tabua_risco"), "Safra 2026/2027", [], "sha-zarc", date(2026, 10, 1))
    zones = [
        # milho em Araraquara: solo 2 com janela 27–30 (risco 20/20/30/40), solo 3 com 28–29
        dict(id=1, crop="milho", name="Milho 1ª Safra", soil=2, w={27: 20, 28: 20, 29: 30, 30: 40}),
        dict(id=2, crop="milho", name="Milho 1ª Safra", soil=3, w={28: 30, 29: 20}),
        # mandioca em Araraquara: janela já passou (decêndios 1–6)
        dict(id=3, crop="mandioca", name="Mandioca", soil=2, w={d: 20 for d in range(1, 7)}),
        # feijão em Araraquara: zona sem nenhuma janela
        dict(id=4, crop="feijao", name="Feijão", soil=2, w={}),
    ]
    for z in zones:
        db.session.execute(insert(ZarcZone), [dict(
            id=z["id"], dataset_version_id=zv.id, crop_id=crops[z["crop"]], zarc_crop_name=z["name"],
            municipality_ibge=ARARAQUARA, soil_type_id=soils[z["soil"]], cycle_code=20, management_code=1,
            climate_code=0, management_level=0, portaria="Port.1", season_label="2026/2027",
        )])
        if z["w"]:
            db.session.execute(insert(ZarcWindow), [dict(zone_id=z["id"], decendio=d, risk_pct=r) for d, r in z["w"].items()])
    base.activate(zv, len(zones))

    cv = base.start_version(base.get_dataset("zarc_cultivares"), "Cultivares 2026-2027", [], "sha-cult", date(2026, 10, 1))
    v = CropVariety(crop_id=crops["milho"], name="BRS 1010", name_normalized="brs 1010", holder="Embrapa")
    db.session.add(v)
    db.session.flush()
    db.session.add(VarietyZone(dataset_version_id=cv.id, variety_id=v.id, zarc_crop_name="Milho", uf="SP", group_code="1"))
    base.activate(cv, 1)


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        _seed_minimal()
        app.extensions["providers"]["weather"] = FakeWeather()
        territory_repo.all_light.cache_clear()
        yield app
        db.session.remove()
        db.drop_all()
        territory_repo.all_light.cache_clear()


@pytest.fixture()
def weather(app) -> FakeWeather:
    return app.extensions["providers"]["weather"]


@pytest.fixture()
def client(app):
    return app.test_client()
