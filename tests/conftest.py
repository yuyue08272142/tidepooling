from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.cache import ExtremesCache
from app.config import TZ
from app.main import create_app
from app.models import Station, TideExtreme
from app.providers import ProviderError
from app.tides import TideService


class StubProvider:
    """测试用数据源：每天 04:00 低潮 0.5m、16:00 高潮 4.0m（全日潮形态）。"""

    name = "stub"

    def __init__(self, fail_days=()):
        self.calls = 0
        self.fail_days = set(fail_days)

    def fetch_extremes(self, station: Station, day: date):
        self.calls += 1
        if day in self.fail_days:
            raise ProviderError("stub failure")
        base = datetime(day.year, day.month, day.day, tzinfo=TZ)
        return [
            TideExtreme(base + timedelta(hours=4), 0.5, "low"),
            TideExtreme(base + timedelta(hours=16), 4.0, "high"),
        ]


@pytest.fixture
def provider():
    return StubProvider()


@pytest.fixture
def service(provider):
    return TideService(provider, ExtremesCache(":memory:", ttl_days=30))


@pytest.fixture
def client(service):
    return TestClient(create_app(service))
