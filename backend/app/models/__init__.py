"""Models: MVP essencial, previsão, seguro, contas/propriedades. Advisory/media ainda futuras
(files/03-database.md)."""
from app.models.catalog import Crop, CropAlias, CropVariety, SoilType, VarietyZone
from app.models.climate import ForecastDaily, ForecastRun
from app.models.farmer import Farm, Planting, User
from app.models.insurance import InsuranceStat
from app.models.provenance import DataSource, Dataset, DatasetVersion
from app.models.territory import Municipality, State
from app.models.zarc import ZarcWindow, ZarcZone

__all__ = [
    "Crop",
    "CropAlias",
    "CropVariety",
    "DataSource",
    "Dataset",
    "DatasetVersion",
    "Farm",
    "ForecastDaily",
    "ForecastRun",
    "InsuranceStat",
    "Municipality",
    "Planting",
    "SoilType",
    "State",
    "User",
    "VarietyZone",
    "ZarcWindow",
    "ZarcZone",
]
