"""Models do MVP essencial. Tabelas desejáveis/futuras (forecast, farmer,
advisory, media) estão desenhadas em files/03-database.md e entram depois."""
from app.models.catalog import Crop, CropAlias, CropVariety, SoilType, VarietyZone
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
    "Municipality",
    "SoilType",
    "State",
    "VarietyZone",
    "ZarcWindow",
    "ZarcZone",
]
