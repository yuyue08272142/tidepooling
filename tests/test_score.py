from dataclasses import replace
from datetime import datetime, timedelta

from app.config import TZ
from app.models import TideExtreme
from app.score import depth_score, suggest, weather_score

from .conftest import FINE

D = datetime(2026, 10, 28, tzinfo=TZ)
SUNRISE, SUNSET = D.replace(hour=6, minute=44), D.replace(hour=18, minute=10)


def tides(low_hour, low_h=0.5, high_h=4.8):
    """前一天傍晚低潮、当天高潮、当天低潮、次日高潮的全日潮序列。"""
    low = D + timedelta(hours=low_hour)
    return [
        TideExtreme(low - timedelta(hours=24), low_h, "low"),
        TideExtreme(low - timedelta(hours=9), high_h, "high"),
        TideExtreme(low, low_h, "low"),
        TideExtreme(low + timedelta(hours=14), high_h, "high"),
    ]


def run(ctx, weather=FINE):
    day = [e for e in ctx if e.time.date() == D.date()]
    return suggest(day, ctx, SUNRISE, SUNSET, weather)


def test_good_afternoon_low_is_top_rated():
    s = run(tides(15))
    assert s.stars == 5 and s.verdict == "非常适合赶海" and not s.night
    assert s.window_start == D.replace(hour=13) and s.window_end == D.replace(hour=16)
    # 潮水涨回 13:00 的水位才算最晚离开。这组数据落潮 9 小时、涨潮 14 小时，涨得慢，约 3 小时才涨回
    assert D.replace(hour=18) <= s.leave_by <= D.replace(hour=18, minute=15)
    assert any("滩涂露出多" in r for r in s.reasons)


def test_night_low_scores_lower_and_warns():
    s = run(tides(23))
    assert s.night and s.score < run(tides(15)).score
    assert any("夜间" in w for w in s.warnings)


def test_high_low_tide_is_poor():
    s = run(tides(15, low_h=2.1, high_h=3.5))
    assert s.stars <= 3 and any("露滩少" in r for r in s.reasons)


def test_thunderstorm_vetoes():
    s = run(tides(15), replace(FINE, sky="雷阵雨"))
    assert s.verdict == "不宜赶海" and s.score <= 20 and s.stars == 1
    assert "雷雨" in s.warnings[0]


def test_strong_wind_and_waves_veto():
    assert weather_score(replace(FINE, wind_level=6))[1]
    assert weather_score(replace(FINE, wave_m=1.6))[1]
    assert weather_score(replace(FINE, wind_level=4))[0] == 0.7


def test_missing_weather_is_neutral():
    s = run(tides(15), None)
    assert "暂无天气预报" in s.reasons and s.verdict != "不宜赶海"


def test_picks_best_of_two_lows():
    low_night = D.replace(hour=2)
    low_day = D.replace(hour=14)
    ctx = [
        TideExtreme(D - timedelta(hours=4), 3.0, "high"),
        TideExtreme(low_night, 1.0, "low"),
        TideExtreme(D.replace(hour=8), 3.2, "high"),
        TideExtreme(low_day, 1.2, "low"),
        TideExtreme(D.replace(hour=20), 3.4, "high"),
    ]
    assert run(ctx).low.time == low_day


def test_no_low_tide_returns_none():
    ctx = [TideExtreme(D.replace(hour=5), 4.5, "high")]
    assert run(ctx) is None


def test_depth_score_bounds():
    assert depth_score(0.2) == 1 and depth_score(2.5) == 0
