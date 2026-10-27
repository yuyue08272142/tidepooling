"""由高低潮时刻和潮高插值出连续潮汐曲线。

相邻高低潮之间用半个余弦波连接，这是潮汐表常用的近似方法，
误差一般在几厘米到十几厘米。
"""
from __future__ import annotations

import bisect
import math
from datetime import datetime, timedelta

from .models import TideExtreme


def height_at(extremes: list[TideExtreme], t: datetime) -> float | None:
    """extremes 需按时间排序；t 不在覆盖范围内时返回 None。"""
    times = [e.time for e in extremes]
    i = bisect.bisect_right(times, t)
    if i == 0 or i == len(extremes):
        return extremes[-1].height if extremes and t == times[-1] else None
    a, b = extremes[i - 1], extremes[i]
    frac = (t - a.time) / (b.time - a.time)
    return a.height + (b.height - a.height) * (1 - math.cos(math.pi * frac)) / 2


def sample(
    extremes: list[TideExtreme], start: datetime, end: datetime, step: timedelta
) -> list[tuple[datetime, float | None]]:
    out = []
    t = start
    while t <= end:
        h = height_at(extremes, t)
        out.append((t, None if h is None else round(h, 2)))
        t += step
    return out
