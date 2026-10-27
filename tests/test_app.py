import json
import time
from dataclasses import replace
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app.cache import PageCache
from app.config import TZ
from app.main import create_app
from app.models import DayPage
from app.prefetch import prefetch
from app.tides import TideService

from .conftest import FINE, StubProvider


def test_index_lists_beihai_stations_with_cached_scores(client, service):
    r = client.get("/")
    assert r.status_code == 200
    for name in ("北海港", "金海湾", "涠洲岛", "营盘港", "铁山港"):
        assert name in r.text
    assert "★" not in r.text  # 没缓存时首页不触发抓取
    prefetch(service, days=1)
    assert "★★★★★" in client.get("/").text


def test_station_day_page(client):
    r = client.get("/tides/beihai?date=2026-10-24")
    assert r.status_code == 200
    assert "北海港潮汐表" in r.text and "农历九月十五" in r.text
    assert "?date=2026-10-23" in r.text and "?date=2026-10-25" in r.text
    assert "14:00" in r.text and "0.50 m" in r.text
    # 赶海建议和天气
    assert "最佳时段" in r.text and "12:00 – 15:00" in r.text and "最晚离开滩涂" in r.text
    assert "东风 3级" in r.text and "0.78 m" in r.text


def test_api_full_day_curve_and_suggestion(client):
    j = client.get("/api/tides/beihai?date=2026-10-24").json()
    assert len(j["hourly"]) == 25 and len(j["curve"]) == 145
    assert j["hourly"][0]["height"] is not None and j["hourly"][-1]["height"] is not None
    assert j["astro"]["tide_period"] in ("大潮", "中潮", "小潮")
    assert j["weather"]["wind_dir"] == "东风"
    assert j["suggestion"]["stars"] == 5 and j["suggestion"]["window_start"].startswith("2026-10-24T12:00")


def test_cache_avoids_refetch(client, provider):
    client.get("/api/tides/beihai?date=2026-10-24")
    first = provider.calls
    client.get("/api/tides/beihai?date=2026-10-24")
    assert provider.calls == first == 3


def test_calendar_reads_cache_only(client, provider, service):
    r = client.get("/calendar/beihai")
    assert r.status_code == 200 and provider.calls == 0
    assert r.text.count("数据未缓存") == 15
    prefetch(service, days=14)
    r = client.get("/calendar/beihai")
    assert "数据未缓存" not in r.text and r.text.count("★★★★★") == 15


def test_unknown_station_404(client):
    assert client.get("/tides/nowhere").status_code == 404
    assert client.get("/calendar/nowhere").status_code == 404


def test_provider_failure_shows_error_not_fake_data():
    p = StubProvider(fail_days={date(2026, 10, 24)})
    c = TestClient(create_app(TideService(p, PageCache(":memory:", 30))))
    r = c.get("/tides/beihai?date=2026-10-24")
    assert r.status_code == 502 and "暂时取不到潮汐数据" in r.text
    assert c.get("/api/tides/beihai?date=2026-10-24").json() == {"error": "stub failure"}


def test_prefetch_skips_fresh_and_refreshes_stale_weather(service, provider):
    fetched, failures = prefetch(service, days=1)
    assert fetched == 10 and not failures  # 5 站 × 2 天
    assert prefetch(service, days=1)[0] == 0
    # 把一条记录的抓取时间改到 7 小时前：天气过期，需要重抓
    today = datetime.now(TZ).date()
    service.cache._db.execute(
        "UPDATE extremes SET fetched_at=? WHERE station='beihai' AND day=?",
        (time.time() - 7 * 3600, today.isoformat()),
    )
    assert prefetch(service, days=1)[0] == 1


def test_cache_reads_m1_payload():
    cache = PageCache(":memory:", 30)
    cache._db.execute(
        "INSERT INTO extremes VALUES ('stub', 'beihai', '2026-10-24', ?, ?)",
        (json.dumps([{"time": "2026-10-24T14:00:00+08:00", "height": 0.5, "kind": "low"}]), time.time()),
    )
    page, _ = cache.get("stub", "beihai", date(2026, 10, 24))
    assert page.weather is None and page.extremes[0].height == 0.5


def test_day_page_sidebars(client, service):
    prefetch(service, days=6)
    today = datetime.now(TZ).date()
    r = client.get(f"/tides/jinhaiwan?date={today.isoformat()}")
    assert "今天各站" in r.text and "金海湾 · 近 7 天" in r.text
    # 侧栏 7 天都来自缓存，且当前站在“今天各站”里高亮
    assert r.text.count("未缓存") == 0
    assert '<li class="current">' in r.text


def test_index_seven_day_matrix(client, service):
    prefetch(service, days=6)
    r = client.get("/")
    assert "未来 7 天各站赶海指数" in r.text
    assert r.text.count('class="heat-5') == 5 * 7  # stub 数据每天都是 5 星
