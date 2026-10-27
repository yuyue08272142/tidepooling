"""按（数据源, 站点, 日期）缓存单日数据（高低潮 + 天气）的 SQLite 小缓存。"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import date, datetime
from pathlib import Path

from .config import TZ
from .models import DayPage, DayWeather, TideExtreme


class PageCache:
    def __init__(self, path: Path | str, ttl_days: float):
        self.ttl = ttl_days * 86400
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS extremes ("
                " source TEXT, station TEXT, day TEXT, payload TEXT, fetched_at REAL,"
                " PRIMARY KEY (source, station, day))"
            )

    def get(self, source: str, station: str, day: date) -> tuple[DayPage, datetime] | None:
        """返回（数据, 抓取时间）；没有或已过期返回 None。"""
        with self._lock:
            row = self._db.execute(
                "SELECT payload, fetched_at FROM extremes WHERE source=? AND station=? AND day=?",
                (source, station, day.isoformat()),
            ).fetchone()
        if not row or time.time() - row[1] > self.ttl:
            return None
        payload = json.loads(row[0])
        if isinstance(payload, list):  # M1 的缓存只存了高低潮列表
            payload = {"extremes": payload, "weather": None}
        page = DayPage(
            [TideExtreme.from_dict(d) for d in payload["extremes"]],
            DayWeather.from_dict(payload["weather"]) if payload.get("weather") else None,
        )
        return page, datetime.fromtimestamp(row[1], TZ)

    def put(self, source: str, station: str, day: date, page: DayPage) -> None:
        payload = json.dumps(
            {
                "extremes": [e.to_dict() for e in page.extremes],
                "weather": page.weather.to_dict() if page.weather else None,
            },
            ensure_ascii=False,
        )
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO extremes VALUES (?, ?, ?, ?, ?)",
                (source, station, day.isoformat(), payload, time.time()),
            )
