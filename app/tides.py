from __future__ import annotations

from datetime import date, datetime, time, timedelta

from . import astro
from .cache import PageCache
from .config import TZ, WEATHER_TTL_HOURS
from .interp import sample
from .models import DayPage, DayTides, Station
from .providers import ProviderError, TideProvider
from .score import suggest


class TideService:
    def __init__(self, provider: TideProvider, cache: PageCache):
        self.provider = provider
        self.cache = cache

    def fetch(self, station: Station, day: date) -> tuple[DayPage, datetime]:
        """强制从数据源取一次并写入缓存。"""
        result = self.provider.fetch_day(station, day)
        self.cache.put(self.provider.name, station.id, day, result)
        return result, datetime.now(TZ)

    def page(self, station: Station, day: date, fetch: bool = True) -> tuple[DayPage, datetime]:
        """优先读缓存；fetch=False 时只读缓存，没有就报错。"""
        cached = self.cache.get(self.provider.name, station.id, day)
        if cached is not None:
            return cached
        if not fetch:
            raise ProviderError(f"{station.name} {day} 的数据还没有缓存")
        return self.fetch(station, day)

    def weather_is_stale(self, page: DayPage, fetched_at: datetime) -> bool:
        return page.weather is None or datetime.now(TZ) - fetched_at > timedelta(hours=WEATHER_TTL_HOURS)

    def day(self, station: Station, day: date, fetch: bool = True) -> DayTides:
        today, fetched_at = self.page(station, day, fetch)
        # 0 点之前和 24 点之后的曲线、潮差需要用到前后两天的潮位；取不到就让两端留空
        around = []
        for d in (day - timedelta(days=1), day + timedelta(days=1)):
            try:
                around += self.page(station, d, fetch)[0].extremes
            except ProviderError:
                pass
        context = sorted({e.time: e for e in today.extremes + around}.values(), key=lambda e: e.time)

        start = datetime.combine(day, time(0), TZ)
        end = start + timedelta(days=1)
        day_astro = astro.day_astro(station, day)
        return DayTides(
            station=station,
            day=day,
            source=getattr(self.provider, "label", self.provider.name),
            extremes=today.extremes,
            hourly=sample(context, start, end, timedelta(hours=1)),
            curve=sample(context, start, end, timedelta(minutes=10)),
            astro=day_astro,
            weather=today.weather,
            weather_time=fetched_at if today.weather else None,
            suggestion=suggest(
                today.extremes, context, day_astro["sunrise"], day_astro["sunset"], today.weather
            ),
        )
