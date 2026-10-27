from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.cache import PageCache
from app.config import TZ
from app.main import create_app
from app.models import DayPage, DayWeather, Station, TideExtreme
from app.providers import ProviderError
from app.tides import TideService

FINE = DayWeather(sky="多云", air_temp=27.0, water_temp=29.0, pressure=1018, wind_level=3,
                  wind_kmh=13.2, wind_dir="东风", wave_m=0.78)


class StubProvider:
    """测试用数据源：每天 04:00 高潮 4.5m、14:00 低潮 0.5m（全日潮形态），天气多云 3 级。"""

    name = "stub"
    available_days = 14

    def __init__(self, fail_days=(), weather=FINE):
        self.calls = 0
        self.fail_days = set(fail_days)
        self.weather = weather

    def fetch_day(self, station: Station, day: date) -> DayPage:
        self.calls += 1
        if day in self.fail_days:
            raise ProviderError("stub failure")
        base = datetime(day.year, day.month, day.day, tzinfo=TZ)
        return DayPage(
            [
                TideExtreme(base + timedelta(hours=4), 4.5, "high"),
                TideExtreme(base + timedelta(hours=14), 0.5, "low"),
            ],
            self.weather,
        )


@pytest.fixture
def provider():
    return StubProvider()


@pytest.fixture
def service(provider):
    return TideService(provider, PageCache(":memory:", ttl_days=30))


@pytest.fixture
def client(service):
    return TestClient(create_app(service))
