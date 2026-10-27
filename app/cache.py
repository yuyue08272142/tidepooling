"""按（数据源, 站点, 日期）缓存高低潮数据的 SQLite 小缓存。"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import date
from pathlib import Path

from .models import TideExtreme


class ExtremesCache:
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

    def get(self, source: str, station: str, day: date) -> list[TideExtreme] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT payload, fetched_at FROM extremes WHERE source=? AND station=? AND day=?",
                (source, station, day.isoformat()),
            ).fetchone()
        if not row or time.time() - row[1] > self.ttl:
            return None
        return [TideExtreme.from_dict(d) for d in json.loads(row[0])]

    def put(self, source: str, station: str, day: date, extremes: list[TideExtreme]) -> None:
        payload = json.dumps([e.to_dict() for e in extremes], ensure_ascii=False)
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO extremes VALUES (?, ?, ?, ?, ?)",
                (source, station, day.isoformat(), payload, time.time()),
            )
