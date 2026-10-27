from datetime import date, datetime, timedelta

from app.astro import day_astro, tide_period
from app.config import TZ
from app.interp import height_at, sample
from app.models import TideExtreme
from app.stations import get_station

T0 = datetime(2026, 10, 24, tzinfo=TZ)
EX = [TideExtreme(T0 + timedelta(hours=4), 0.5, "low"), TideExtreme(T0 + timedelta(hours=16), 4.0, "high")]


def test_interpolation_hits_extremes_and_midpoint():
    assert height_at(EX, EX[0].time) == 0.5
    assert height_at(EX, EX[1].time) == 4.0
    assert abs(height_at(EX, T0 + timedelta(hours=10)) - 2.25) < 1e-9


def test_interpolation_outside_range_is_none():
    pts = sample(EX, T0, T0 + timedelta(days=1), timedelta(hours=1))
    assert pts[0][1] is None and pts[-1][1] is None
    assert pts[4][1] == 0.5


def test_beihai_astro_plausible():
    a = day_astro(get_station("beihai"), date(2026, 10, 24))
    assert 6 <= a["sunrise"].hour <= 7 and 17 <= a["sunset"].hour <= 18
    assert a["lunar"]["text"] == "农历九月十五"


def test_tide_period_follows_moon_declination():
    # 2026-10-16 前后月赤纬约 -28°（大潮），10-24 前后月亮过赤道（小潮）
    assert tide_period(date(2026, 10, 16)) == "大潮"
    assert tide_period(date(2026, 10, 24)) == "小潮"
