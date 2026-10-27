"""从 tidescn.com 抓取单站单日的高低潮。

页面结构（2026-10 核对）：
- 日期在 `.tide_tile h1 span`，如“2026年10月24日 星期六”
- 每条高低潮一个 `div.tide2`，文字如“05:23 满潮 2.6米”
- 天气在 `.column3`（`.skycon` 天况，“气温28.33°C”“水温29.75°C”“气压1009hpa”），
  风浪在 `.column6`（`.wind2`“2级”，`.wind1`“10.4km/h”，`.wind3`“西北风”“0.21米浪”）
- 曲线的逐时数据是加密的，不使用；曲线由高低潮插值得到

注意：只提供今天起 14 天内的数据。超出范围的日期不会报错，而是返回别的日期的页面，
所以必须校验页面上的日期。

调试：python -m app.providers.tidescn 945 2026-10-24 --save var/html
"""
from __future__ import annotations

import argparse
import re
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .. import config
from ..models import DayPage, DayWeather, Station, TideExtreme
from . import ProviderError

AVAILABLE_DAYS = 14  # 页面日期选择器到 +15 天，但第 15 天页面没有数据（2026-10 核对）
_KIND = {"满潮": "high", "高潮": "high", "干潮": "low", "低潮": "low"}
_PAGE_DATE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_ENTRY = re.compile(r"(\d{1,2})\s*[:：]\s*(\d{2})\s*(满潮|高潮|干潮|低潮)\s*(-?\d+(?:\.\d+)?)\s*(米|m|厘米|cm)?")


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


def _extremes(soup: BeautifulSoup, day: date) -> list[TideExtreme]:
    title = soup.select_one(".tide_tile h1")
    m = _PAGE_DATE.search(title.get_text() if title else "")
    if not m:
        raise ProviderError("tidescn 页面结构有变化：找不到页面日期")
    page_day = date(*map(int, m.groups()))
    if page_day != day:
        raise ProviderError(f"tidescn 没有 {day} 的数据（返回的是 {page_day}），只提供今天起 {AVAILABLE_DAYS} 天内的潮汐")

    midnight = datetime(day.year, day.month, day.day, tzinfo=config.TZ)
    extremes = []
    for div in soup.select("div.tide2"):
        m = _ENTRY.search(div.get_text(" ", strip=True))
        if not m:
            raise ProviderError(f"tidescn 页面结构有变化：无法解析“{div.get_text(' ', strip=True)}”")
        hh, mm, kind, value, unit = m.groups()
        height = float(value) / (100 if unit in ("厘米", "cm") else 1)
        t = midnight + timedelta(hours=int(hh), minutes=int(mm))
        extremes.append(TideExtreme(t, round(height, 2), _KIND[kind]))

    extremes.sort(key=lambda e: e.time)
    if not extremes:
        raise ProviderError("tidescn 页面上没有高低潮数据")
    return extremes


def _number(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def _weather(soup: BeautifulSoup) -> DayWeather | None:
    """天气是附加信息：页面结构变了就返回 None，不影响潮汐。"""
    sky = soup.select_one(".calendarlist .value .skycon")
    wind = soup.select_one(".calendarlist .value .column6")
    if sky is None and wind is None:
        return None
    sky_box = sky.parent.get_text(" ", strip=True) if sky else ""
    wind_level = _number(r"(\d+)\s*级", wind.get_text(" ", strip=True)) if wind else None
    wind_dir, wave = "", None
    for el in wind.select(".wind3") if wind else []:
        text = el.get_text(strip=True)
        if text.endswith("浪"):
            wave = _number(r"(\d+(?:\.\d+)?)\s*米", text)
        elif "风" in text:
            wind_dir = text
    return DayWeather(
        sky=sky.get_text(strip=True) if sky else "",
        air_temp=_number(r"气温\s*(-?\d+(?:\.\d+)?)", sky_box),
        water_temp=_number(r"水温\s*(-?\d+(?:\.\d+)?)", sky_box),
        pressure=_number(r"气压\s*(\d+(?:\.\d+)?)", sky_box),
        wind_level=int(wind_level) if wind_level is not None else None,
        wind_kmh=_number(r"(\d+(?:\.\d+)?)\s*km/h", wind.get_text(" ", strip=True)) if wind else None,
        wind_dir=wind_dir,
        wave_m=wave,
    )


def parse_page(html: str, day: date) -> DayPage:
    soup = BeautifulSoup(html, "html.parser")
    return DayPage(_extremes(soup, day), _weather(soup))


def parse_extremes(html: str, day: date) -> list[TideExtreme]:
    return parse_page(html, day).extremes


class TidescnProvider:
    name = "tidescn.com"
    label = "tidescn.com（数据源自国家海洋信息中心）"
    available_days = AVAILABLE_DAYS

    def __init__(self, base_url: str = config.TIDESCN_BASE_URL, client: httpx.Client | None = None):
        self.base_url = base_url
        self._client = client or httpx.Client(
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
            follow_redirects=True,
        )
        self._lock = threading.Lock()
        self._last_request = 0.0

    def available(self, day: date) -> bool:
        today = datetime.now(config.TZ).date()
        return today <= day <= today + timedelta(days=AVAILABLE_DAYS)

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

    def fetch_day(self, station: Station, day: date) -> DayPage:
        if station.tidescn_id is None:
            raise ProviderError(f"{station.name} 还没有配置 tidescn 站点编号")
        if not self.available(day):
            raise ProviderError(f"tidescn 只提供今天起 {AVAILABLE_DAYS} 天内的潮汐，{day} 不在范围内")
        return parse_page(self.fetch_html(station.tidescn_id, day), day)


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
    page = parse_page(html, args.date)
    for e in page.extremes:
        print(f"{e.time:%H:%M}  {'高潮' if e.kind == 'high' else '低潮'}  {e.height:.2f} m")
    print(page.weather)


if __name__ == "__main__":
    main()
