"""从 tidescn.com 抓取单站单日的高低潮。

注意：开发环境暂时无法访问 tidescn.com，下面的解析规则是按潮汐表页面的常见写法
（“高潮/低潮 + 时间 + 潮高”）写的通用规则，尚未用真实页面校验。
拿到真实页面后用本模块的命令行保存 HTML，再按实际结构收紧解析逻辑：

    python -m app.providers.tidescn 945 2026-10-24 --save tests/fixtures
"""
from __future__ import annotations

import argparse
import re
import threading
import time
from datetime import date, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .. import config
from ..models import Station, TideExtreme
from . import ProviderError

_KIND = {"高潮": "high", "满潮": "high", "低潮": "low", "干潮": "low"}
_TIME = r"([01]?\d|2[0-3])\s*[:：]\s*([0-5]\d)"
_HEIGHT = r"(-?\d+(?:\.\d+)?)\s*(cm|CM|厘米|m|M|米)?"
_KIND_FIRST = re.compile(rf"(高潮|满潮|低潮|干潮)\D{{0,12}}?{_TIME}\D{{0,12}}?{_HEIGHT}")
_TIME_FIRST = re.compile(rf"{_TIME}\D{{0,12}}?{_HEIGHT}\s*\D{{0,6}}?(高潮|满潮|低潮|干潮)")


def decode_html(content: bytes, content_type: str = "") -> str:
    m = re.search(r"charset=([\w-]+)", content_type, re.I) or re.search(
        rb"<meta[^>]+charset=[\"']?([\w-]+)", content[:2048], re.I
    )
    charset = m.group(1) if m else "utf-8"
    if isinstance(charset, bytes):
        charset = charset.decode("ascii")
    if charset.lower() in ("gb2312", "gbk"):
        charset = "gb18030"
    try:
        return content.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return content.decode("gb18030", errors="replace")


def _to_metres(value: str, unit: str | None) -> float:
    v = float(value)
    if unit in ("cm", "CM", "厘米") or (unit is None and abs(v) > 15):
        v /= 100
    return round(v, 2)


def _collect(text: str, day: date, kind_first: bool) -> list[TideExtreme]:
    found: dict[datetime, TideExtreme] = {}
    for m in (_KIND_FIRST if kind_first else _TIME_FIRST).finditer(text):
        g = m.groups()
        kind, hh, mm, val, unit = g if kind_first else (g[4], *g[:4])
        t = datetime(day.year, day.month, day.day, int(hh), int(mm), tzinfo=config.TZ)
        found.setdefault(t, TideExtreme(t, _to_metres(val, unit), _KIND[kind]))
    return sorted(found.values(), key=lambda e: e.time)


def parse_extremes(html: str, day: date) -> list[TideExtreme]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    # 两种写法分开解析：混在一起时“低潮”可能被错配到下一条记录的时间上
    candidates = [_collect(text, day, kind_first) for kind_first in (True, False)]
    candidates = [c for c in candidates if len(c) >= 2]
    if not candidates:
        raise ProviderError("页面中未识别到高低潮数据（解析规则可能需要按页面结构调整）")
    for extremes in candidates:
        if all(a.kind != b.kind for a, b in zip(extremes, extremes[1:])):
            return extremes
    raise ProviderError("识别出的高低潮不是交替出现，页面里可能混入了其他日期的数据")


class TidescnProvider:
    name = "tidescn.com"

    def __init__(self, base_url: str = config.TIDESCN_BASE_URL, client: httpx.Client | None = None):
        self.base_url = base_url
        self._client = client or httpx.Client(
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
            follow_redirects=True,
        )
        self._lock = threading.Lock()
        self._last_request = 0.0

    def url(self, tidescn_id: int, day: date) -> str:
        return f"{self.base_url}/Tides/{tidescn_id}.html?date={day.isoformat()}"

    def fetch_html(self, tidescn_id: int, day: date) -> str:
        with self._lock:  # 串行 + 限速
            wait = config.TIDESCN_MIN_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self._client.get(self.url(tidescn_id, day))
                resp.raise_for_status()
            except httpx.HTTPError as e:
                raise ProviderError(f"请求 tidescn 失败：{e}") from e
            finally:
                self._last_request = time.monotonic()
        return decode_html(resp.content, resp.headers.get("content-type", ""))

    def fetch_extremes(self, station: Station, day: date) -> list[TideExtreme]:
        if station.tidescn_id is None:
            raise ProviderError(f"{station.name} 还没有配置 tidescn 站点编号")
        return parse_extremes(self.fetch_html(station.tidescn_id, day), day)


def main() -> None:
    ap = argparse.ArgumentParser(description="抓取并解析 tidescn 单日页面（调试用）")
    ap.add_argument("tidescn_id", type=int)
    ap.add_argument("date", type=date.fromisoformat)
    ap.add_argument("--save", type=Path, help="把原始 HTML 保存到该目录")
    args = ap.parse_args()

    html = TidescnProvider().fetch_html(args.tidescn_id, args.date)
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)
        out = args.save / f"tidescn_{args.tidescn_id}_{args.date}.html"
        out.write_text(html, encoding="utf-8")
        print(f"已保存 {out}")
    for e in parse_extremes(html, args.date):
        print(f"{e.time:%H:%M}  {'高潮' if e.kind == 'high' else '低潮'}  {e.height:.2f} m")


if __name__ == "__main__":
    main()
