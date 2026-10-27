from __future__ import annotations

from datetime import date
from typing import Protocol

from ..models import Station, TideExtreme


class ProviderError(Exception):
    """数据源取数或解析失败。"""


class TideProvider(Protocol):
    name: str  # 缓存 key；可另设 label 作为页面上显示的数据来源

    def fetch_extremes(self, station: Station, day: date) -> list[TideExtreme]:
        """返回该站当天（本地时间 0~24 时）的高低潮，按时间排序。"""
        ...
