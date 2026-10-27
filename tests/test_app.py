from datetime import date

from app.cache import ExtremesCache
from app.main import create_app
from app.tides import TideService
from fastapi.testclient import TestClient

from .conftest import StubProvider


def test_index_lists_beihai_stations(client):
    r = client.get("/")
    assert r.status_code == 200
    for name in ("北海", "涠洲岛", "铁山港"):
        assert name in r.text


def test_station_day_page(client):
    r = client.get("/tides/beihai?date=2026-10-24")
    assert r.status_code == 200
    assert "北海潮汐表" in r.text and "农历九月十五" in r.text
    assert "?date=2026-10-23" in r.text and "?date=2026-10-25" in r.text
    assert "04:00" in r.text and "4.00 m" in r.text


def test_api_full_day_curve(client):
    j = client.get("/api/tides/beihai?date=2026-10-24").json()
    assert len(j["hourly"]) == 25 and len(j["curve"]) == 145
    # 有前后两天的数据，0 点和 24 点都能插值出来
    assert j["hourly"][0]["height"] is not None and j["hourly"][-1]["height"] is not None
    assert j["astro"]["tide_period"] in ("大潮", "中潮", "小潮")


def test_cache_avoids_refetch(client, provider):
    client.get("/api/tides/beihai?date=2026-10-24")
    first = provider.calls
    client.get("/api/tides/beihai?date=2026-10-24")
    assert provider.calls == first == 3


def test_unknown_station_404(client):
    assert client.get("/tides/nowhere").status_code == 404


def test_provider_failure_shows_error_not_fake_data():
    p = StubProvider(fail_days={date(2026, 10, 24)})
    c = TestClient(create_app(TideService(p, ExtremesCache(":memory:", 30))))
    r = c.get("/tides/beihai?date=2026-10-24")
    assert r.status_code == 502 and "暂时取不到潮汐数据" in r.text
    assert c.get("/api/tides/beihai?date=2026-10-24").json() == {"error": "stub failure"}
