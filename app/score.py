"""赶海指数、最佳时段和返回时间。

对当天每一次低潮打分，取分最高的一次：
- 低潮有多低（40%）：潮高基准面大致是当地最低潮位，所以低潮潮高越接近 0，露出的滩涂越多。
  0.4 米及以下满分，2.0 米及以上 0 分。
- 是否白天（20%）：最佳时段落在日出前半小时到日落后半小时之间的比例。
- 天气风浪（25%）：风力、浪高、天况各打分取最低项；雷雨、6 级以上大风、1.5 米以上浪直接判不宜。
- 潮差（15%）：上一次高潮到这次低潮的落差，落差大说明退得远。1 米 0 分，3.5 米满分。

时段：低潮前 2 小时到低潮后 1 小时为最佳时段，到点开始往回走；
潮水涨回到下滩时（时段开始）的水位，就必须离开滩涂。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .interp import height_at
from .models import DayWeather, Suggestion, TideExtreme

BEFORE_LOW = timedelta(hours=2)
AFTER_LOW = timedelta(hours=1)
TWILIGHT = timedelta(minutes=30)
WEIGHTS = {"depth": 40, "daylight": 20, "weather": 25, "range": 15}
VETO_CAP = 20  # 被一票否决时总分上限
NO_WEATHER = 0.7  # 没有天气数据时天气项按 0.7 计


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def depth_score(low_height: float) -> float:
    return _clamp((2.0 - low_height) / (2.0 - 0.4))


def range_score(tidal_range: float | None) -> float:
    return 0.5 if tidal_range is None else _clamp((tidal_range - 1.0) / (3.5 - 1.0))


def daylight_score(start: datetime, end: datetime, sunrise: datetime, sunset: datetime) -> float:
    light_start, light_end = sunrise - TWILIGHT, sunset + TWILIGHT
    overlap = min(end, light_end) - max(start, light_start)
    return _clamp(overlap / (end - start))


def weather_score(w: DayWeather | None) -> tuple[float, str | None]:
    """返回（0~1 分数, 一票否决原因）。"""
    if w is None:
        return NO_WEATHER, None
    if "雷" in w.sky:
        return 0.0, f"{w.sky}，雷雨天不要下滩"
    if any(k in w.sky for k in ("暴雨", "大雨", "台风")):
        return 0.0, f"{w.sky}，不宜赶海"
    if w.wind_level is not None and w.wind_level >= 6:
        return 0.0, f"{w.wind_level} 级大风，不宜赶海"
    if w.wave_m is not None and w.wave_m >= 1.5:
        return 0.0, f"浪高 {w.wave_m} 米，不宜赶海"

    parts = [1.0]
    if w.wind_level is not None:
        parts.append({4: 0.7, 5: 0.35}.get(w.wind_level, 1.0))
    if w.wave_m is not None:
        parts.append(1.0 if w.wave_m <= 0.5 else 0.7 if w.wave_m <= 1.0 else 0.4)
    if "雨" in w.sky:
        parts.append(0.4)
    return min(parts), None


def stars_for(score: int) -> int:
    return 5 if score >= 80 else 4 if score >= 65 else 3 if score >= 50 else 2 if score >= 35 else 1


def verdict_for(score: int, veto: str | None) -> str:
    if veto:
        return "不宜赶海"
    return ("非常适合赶海", "适合赶海", "可以去看看", "一般", "不太适合")[5 - stars_for(score)]


def _previous_high(low: TideExtreme, context: list[TideExtreme]) -> TideExtreme | None:
    before = [e for e in context if e.kind == "high" and e.time < low.time]
    if before:
        return before[-1]
    after = [e for e in context if e.kind == "high" and e.time > low.time]
    return after[0] if after else None


def _leave_by(low: TideExtreme, start: datetime, context: list[TideExtreme]) -> datetime:
    """低潮后潮水涨回 start 时刻水位的时间；取不到曲线时按低潮后 2 小时。"""
    level = height_at(context, start)
    if level is not None:
        t = low.time + AFTER_LOW
        while t <= low.time + timedelta(hours=6):
            h = height_at(context, t)
            if h is None:
                break
            if h >= level:
                return t
            t += timedelta(minutes=5)
    return low.time + timedelta(hours=2)


def _evaluate(low, context, sunrise, sunset, weather) -> Suggestion:
    start, end = low.time - BEFORE_LOW, low.time + AFTER_LOW
    leave_by = max(_leave_by(low, start, context), end)
    high = _previous_high(low, context)
    tidal_range = high.height - low.height if high else None

    d = depth_score(low.height)
    light = daylight_score(start, end, sunrise, sunset)
    w, veto = weather_score(weather)
    r = range_score(tidal_range)
    score = round(
        WEIGHTS["depth"] * d + WEIGHTS["daylight"] * light + WEIGHTS["weather"] * w + WEIGHTS["range"] * r
    )
    if veto:
        score = min(score, VETO_CAP)
    night = light < 0.5

    reasons = [
        f"低潮 {low.height:.2f} 米，"
        + ("滩涂露出多" if d >= 0.75 else "露滩一般" if d >= 0.4 else "低潮偏高，露滩少"),
    ]
    if tidal_range is not None:
        reasons.append(f"潮差 {tidal_range:.1f} 米，" + ("退得远" if r >= 0.6 else "退得不远"))
    reasons.append(
        "低潮在白天" if light >= 0.99 else "低潮在夜间，需要照明" if night else "部分时段天还没亮或已天黑"
    )
    if weather:
        wind = f"{weather.wind_dir} {weather.wind_level} 级".strip() if weather.wind_level is not None else ""
        wave = f"浪 {weather.wave_m:g} 米" if weather.wave_m is not None else ""
        reasons.append("，".join(x for x in (weather.sky, wind, wave) if x))
    else:
        reasons.append("暂无天气预报")

    warnings = []
    if veto:
        warnings.append(veto)
    warnings.append("涨潮后第 3、4 小时水位上涨最快，看到潮水回涨就往岸上走")
    if leave_by > sunset:
        warnings.append(f"离开时间晚于日落（{sunset:%H:%M}），带好头灯")
    if night:
        warnings.append("夜间赶海务必结伴、带照明，提前看好上岸路线")

    return Suggestion(
        score=score,
        stars=stars_for(score),
        verdict=verdict_for(score, veto),
        low=low,
        window_start=start,
        window_end=end,
        leave_by=leave_by,
        night=night,
        reasons=reasons,
        warnings=warnings,
    )


def suggest(
    day_extremes: list[TideExtreme],
    context: list[TideExtreme],
    sunrise: datetime,
    sunset: datetime,
    weather: DayWeather | None,
) -> Suggestion | None:
    """day_extremes：当天高低潮；context：含前后两天、按时间排序，用于算潮差和曲线。当天没有低潮返回 None。"""
    lows = [e for e in day_extremes if e.kind == "low"]
    if not lows:
        return None
    return max((_evaluate(low, context, sunrise, sunset, weather) for low in lows), key=lambda s: s.score)
