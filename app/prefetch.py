"""预取所有站点今天起可取范围内的高低潮和天气，写入缓存。

建议每 6 小时跑一次（如 cron: 10 */6 * * *）。这样：
- 用户打开页面、日历时直接命中缓存，不用等抓取；
- 第二天 tidescn 不再提供“昨天”时，缓存里仍有，曲线 0 点前后能接上；
- 天气预报保持在 6 小时内更新（WEATHER_TTL_HOURS）。
潮汐已缓存且天气未过期的日期会跳过。

    python -m app.prefetch
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import config
from .cache import PageCache
from .providers import ProviderError
from .providers.tidescn import TidescnProvider
from .stations import all_stations
from .tides import TideService


def prefetch(service: TideService, days: int) -> tuple[int, list[str]]:
    """返回（实际请求数, 失败信息）。"""
    today = datetime.now(config.TZ).date()
    fetched, failures = 0, []
    for station in all_stations():
        for offset in range(days + 1):
            day = today + timedelta(days=offset)
            cached = service.cache.get(service.provider.name, station.id, day)
            if cached is not None and not service.weather_is_stale(*cached):
                continue
            try:
                service.fetch(station, day)
                fetched += 1
            except ProviderError as e:
                failures.append(f"{station.name} {day}: {e}")
    return fetched, failures


def main() -> None:
    provider = TidescnProvider()
    service = TideService(provider, PageCache(config.CACHE_PATH, config.CACHE_TTL_DAYS))
    fetched, failures = prefetch(service, provider.available_days)
    for line in failures:
        print(line)
    print(f"完成：请求 {fetched} 次，失败 {len(failures)} 条")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
