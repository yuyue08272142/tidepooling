from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import astro
from .cache import ExtremesCache
from .config import TZ
from .interp import sample
from .models import DayTides, Station, TideExtreme
from .providers import ProviderError, TideProvider


class TideService:
    def __init__(self, provider: TideProvider, cache: ExtremesCache):
        self.provider = provider
        self.cache = cache

    def extremes(self, station: Station, day: date) -> list[TideExtreme]:
        cached = self.cache.get(self.provider.name, station.id, day)
        if cached is not None:
            return cached
        result = self.provider.fetch_extremes(station, day)
        self.cache.put(self.provider.name, station.id, day, result)
        return result

    def day(self, station: Station, day: date) -> DayTides:
        today = self.extremes(station, day)
        # 0 点之前和 24 点之后的曲线需要用到前后两天的潮位；取不到就让两端留空
        around: list[TideExtreme] = []
        for d in (day - timedelta(days=1), day + timedelta(days=1)):
            try:
                around += self.extremes(station, d)
            except ProviderError:
                pass
        everything = sorted({e.time: e for e in today + around}.values(), key=lambda e: e.time)

        start = datetime.combine(day, time(0), TZ)
        end = start + timedelta(days=1)
        return DayTides(
            station=station,
            day=day,
            source=self.provider.name,
            extremes=today,
            hourly=sample(everything, start, end, timedelta(hours=1)),
            curve=sample(everything, start, end, timedelta(minutes=10)),
            astro=astro.day_astro(station, day),
        )
