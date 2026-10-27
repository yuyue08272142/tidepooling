import json
from functools import lru_cache
from pathlib import Path

from .models import Station

_DATA = Path(__file__).parent / "data" / "stations.json"


@lru_cache
def all_stations() -> tuple[Station, ...]:
    with _DATA.open(encoding="utf-8") as f:
        return tuple(Station(**s) for s in json.load(f))


def get_station(station_id: str) -> Station | None:
    return next((s for s in all_stations() if s.id == station_id), None)
