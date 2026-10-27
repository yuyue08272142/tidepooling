from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

TideKind = Literal["high", "low"]


@dataclass(frozen=True)
class Station:
    id: str  # 本站 URL 用的 slug，如 "beihai"
    name: str
    region: str
    lat: float
    lon: float
    tidescn_id: int | None = None
    note: str = ""


@dataclass(frozen=True)
class TideExtreme:
    time: datetime  # 带时区（Asia/Shanghai）
    height: float  # 米，相对当地潮高基准面
    kind: TideKind

    def to_dict(self) -> dict:
        return {"time": self.time.isoformat(), "height": self.height, "kind": self.kind}

    @classmethod
    def from_dict(cls, d: dict) -> TideExtreme:
        return cls(datetime.fromisoformat(d["time"]), float(d["height"]), d["kind"])


@dataclass
class DayTides:
    station: Station
    day: date
    source: str
    extremes: list[TideExtreme]  # 仅当天
    hourly: list[tuple[datetime, float | None]]  # 0~24 时整点
    curve: list[tuple[datetime, float | None]]  # 细粒度曲线，用于画图
    astro: dict = field(default_factory=dict)
