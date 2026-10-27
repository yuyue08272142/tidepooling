"""日出日落、月出月落、月相、农历和潮汛。"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from astral import LocationInfo, moon
from astral.julian import julianday
from astral.sun import sun
from lunar_python import Solar

from .config import TZ
from .models import Station

_PHASES = [
    (1.0, "新月"), (6.0, "蛾眉月"), (8.0, "上弦月"), (13.0, "盈凸月"),
    (15.5, "满月"), (20.5, "亏凸月"), (22.5, "下弦月"), (27.0, "残月"), (28.0, "新月"),
]


def _observer(station: Station):
    return LocationInfo(station.name, "China", str(TZ), station.lat, station.lon).observer


def _safe(fn, *args, **kwargs) -> datetime | None:
    # 某些日期没有月出/月落，astral 会抛 ValueError
    try:
        return fn(*args, **kwargs)
    except ValueError:
        return None


def moon_phase_name(day: date) -> str:
    p = moon.phase(day)
    return next(name for limit, name in _PHASES if p < limit)


def moon_declination(t: datetime) -> float:
    """月球赤纬（度）。"""
    jd2000 = julianday(t.astimezone(TZ).replace(tzinfo=None) - timedelta(hours=8)) - 2451545.0
    return math.degrees(moon.moon_position(jd2000).declination)


def tide_period(day: date) -> str:
    """大潮 / 中潮 / 小潮。

    北部湾（北海）以全日潮为主，大小潮由月球赤纬决定（回归潮）：
    月亮赤纬最大时潮差最大，月亮过赤道时潮差最小，与月相（初一、十五）关系不大。
    这里用当天正午月赤纬绝对值与前后半个月内最大值的比值来划分。
    """
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=TZ)
    decl = abs(moon_declination(noon))
    peak = max(abs(moon_declination(noon + timedelta(days=d))) for d in range(-14, 15))
    ratio = decl / peak
    if ratio >= 0.75:
        return "大潮"
    if ratio <= 0.35:
        return "小潮"
    return "中潮"


def lunar_info(day: date) -> dict:
    lunar = Solar.fromYmd(day.year, day.month, day.day).getLunar()
    return {
        "text": f"农历{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
        "year": f"{lunar.getYearInGanZhi()}（{lunar.getYearShengXiao()}）年",
        "jieqi": lunar.getJieQi() or "",
    }


def day_astro(station: Station, day: date) -> dict:
    obs = _observer(station)
    s = sun(obs, date=day, tzinfo=TZ)
    return {
        "dawn": s["dawn"],
        "sunrise": s["sunrise"],
        "sunset": s["sunset"],
        "dusk": s["dusk"],
        "moonrise": _safe(moon.moonrise, obs, day, tzinfo=TZ),
        "moonset": _safe(moon.moonset, obs, day, tzinfo=TZ),
        "moon_phase": moon_phase_name(day),
        "tide_period": tide_period(day),
        "lunar": lunar_info(day),
    }
