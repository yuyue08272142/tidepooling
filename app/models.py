from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    map_label: str = "right"  # 首页地图上站名标签的方向：right / left / top / bottom


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


@dataclass(frozen=True)
class DayWeather:
    """单日天气风浪预报。各字段取不到时为 None / 空串。"""

    sky: str = ""  # 晴、多云、小雨、雷阵雨……
    air_temp: float | None = None  # °C
    water_temp: float | None = None  # °C
    pressure: float | None = None  # hPa
    wind_level: int | None = None  # 蒲福风级
    wind_kmh: float | None = None
    wind_dir: str = ""
    wave_m: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> DayWeather:
        return cls(**d)


@dataclass(frozen=True)
class DayPage:
    """数据源一次取回的单日数据。"""

    extremes: list[TideExtreme]
    weather: DayWeather | None = None


@dataclass(frozen=True)
class Suggestion:
    """当天的赶海建议（取当天最适合的一次低潮）。"""

    score: int  # 0~100
    stars: int  # 1~5
    verdict: str
    low: TideExtreme
    window_start: datetime  # 最佳时段
    window_end: datetime  # 到点开始往回走
    leave_by: datetime  # 潮水涨回下滩时的水位，最晚离开滩涂
    night: bool
    reasons: list[str]
    warnings: list[str]


@dataclass
class DayTides:
    station: Station
    day: date
    source: str
    extremes: list[TideExtreme]  # 仅当天
    hourly: list[tuple[datetime, float | None]]  # 0~24 时整点
    curve: list[tuple[datetime, float | None]]  # 细粒度曲线，用于画图
    astro: dict = field(default_factory=dict)
    weather: DayWeather | None = None
    weather_time: datetime | None = None  # 天气抓取时间
    suggestion: Suggestion | None = None
