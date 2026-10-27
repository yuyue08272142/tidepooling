"""预取所有站点今天起可取范围内的高低潮，写入缓存。

建议每天凌晨跑一次（如 cron: 10 0 * * *）。这样：
- 用户打开页面时直接命中缓存，不用等抓取；
- 第二天 tidescn 不再提供“昨天”时，缓存里仍有，曲线 0 点前后能接上。
已缓存的日期会跳过，所以每天实际只新增一两次请求/站。

    python -m app.prefetch
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import config
from .cache import ExtremesCache
from .providers import ProviderError
from .providers.tidescn import TidescnProvider
from .stations import all_stations
from .tides import TideService


def main() -> None:
    provider = TidescnProvider()
    service = TideService(provider, ExtremesCache(config.CACHE_PATH, config.CACHE_TTL_DAYS))
    today = datetime.now(config.TZ).date()
    failures = 0
    for station in all_stations():
        for offset in range(provider.available_days + 1):
            day = today + timedelta(days=offset)
            try:
                service.extremes(station, day)
            except ProviderError as e:
                failures += 1
                print(f"{station.name} {day}: {e}")
    print(f"完成，失败 {failures} 条")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
