from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config
from .cache import PageCache
from .models import DayTides, Suggestion
from .providers import ProviderError
from .providers.tidescn import TidescnProvider
from .stations import all_stations, get_station
from .tides import TideService

_HERE = Path(__file__).parent
templates = Jinja2Templates(directory=_HERE / "templates")
templates.env.filters["hm"] = lambda t: t.strftime("%H:%M") if t else "--"
_WEEKDAYS = "一二三四五六日"
templates.env.filters["weekday"] = lambda d: "周" + _WEEKDAYS[d.weekday()]
templates.env.filters["stars"] = lambda n: "★" * n + "☆" * (5 - n)


def _iso(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def serialize_suggestion(s: Suggestion | None) -> dict | None:
    if s is None:
        return None
    return {
        "score": s.score,
        "stars": s.stars,
        "verdict": s.verdict,
        "low": s.low.to_dict(),
        "window_start": s.window_start.isoformat(),
        "window_end": s.window_end.isoformat(),
        "leave_by": s.leave_by.isoformat(),
        "night": s.night,
        "reasons": s.reasons,
        "warnings": s.warnings,
    }


def serialize(d: DayTides) -> dict:
    s = d.station
    return {
        "station": {"id": s.id, "name": s.name, "region": s.region, "lat": s.lat, "lon": s.lon},
        "date": d.day.isoformat(),
        "source": d.source,
        "unit": "m",
        "extremes": [e.to_dict() for e in d.extremes],
        "hourly": [{"time": t.isoformat(), "height": h} for t, h in d.hourly],
        "curve": [[t.isoformat(), h] for t, h in d.curve],
        "astro": {k: _iso(v) for k, v in d.astro.items()},
        "weather": d.weather.to_dict() if d.weather else None,
        "weather_time": _iso(d.weather_time),
        "suggestion": serialize_suggestion(d.suggestion),
    }


_TIANDITU = (
    "https://t{s}.tianditu.gov.cn/{layer}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
    "&LAYER={layer}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles"
    "&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}&tk={key}"
)


def map_tiles() -> list[dict]:
    """首页地图的底图图层。天地图需要 key，没配 key 时退回 OpenStreetMap。"""
    if config.MAP_TILES == "tianditu" and config.TIANDITU_KEY:
        return [
            {
                "url": _TIANDITU.format(s="{s}", layer=layer, key=config.TIANDITU_KEY),
                "subdomains": "01234567",
                "attribution": "&copy; 天地图" if layer == "vec" else "",
                "maxZoom": 18,
            }
            for layer in ("vec", "cva")  # 矢量底图 + 中文注记
        ]
    return [
        {
            "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "subdomains": "",
            "attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> 贡献者',
            "maxZoom": 19,
        }
    ]


def map_points(rows, day: date) -> list[dict]:
    """首页地图上的站点标记：位置 + 当天赶海建议（没缓存时只有位置）。"""
    points = []
    for s, d in rows:
        sg = d.suggestion if d else None
        points.append(
            {
                "id": s.id,
                "name": s.name,
                "lat": s.lat,
                "lon": s.lon,
                "label": s.map_label,
                "url": f"/tides/{s.id}?date={day.isoformat()}",
                "calendar": f"/calendar/{s.id}",
                "period": d.astro["tide_period"] if d else None,
                "suggestion": serialize_suggestion(sg),
            }
        )
    return points


def create_app(service: TideService | None = None) -> FastAPI:
    app = FastAPI(title="北海赶海潮汐")
    app.state.service = service or TideService(
        TidescnProvider(), PageCache(config.CACHE_PATH, config.CACHE_TTL_DAYS)
    )
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")

    def lookup(station_id: str):
        station = get_station(station_id)
        if station is None:
            raise HTTPException(404, "未找到该潮汐站")
        return station

    def available_days() -> int:
        return getattr(app.state.service.provider, "available_days", 14)

    def cached_day(station, day) -> DayTides | None:
        # 首页和日历只读缓存（由 app.prefetch 预先填好），避免一次打开触发几十次抓取
        try:
            return app.state.service.day(station, day, fetch=False)
        except ProviderError:
            return None

    def station_rows(day):
        """各站某天的数据（只读缓存），用于首页和日页侧栏。"""
        return [(s, cached_day(s, day)) for s in all_stations()]

    def week(station, start):
        """某站从 start 起 7 天（只读缓存）。"""
        return [(d, cached_day(station, d)) for d in (start + timedelta(days=i) for i in range(7))]

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        today = datetime.now(config.TZ).date()
        days = [today + timedelta(days=i) for i in range(7)]
        matrix = [(s, [d for _, d in week(s, today)]) for s in all_stations()]
        rows = station_rows(today)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "rows": rows,
                "today": today,
                "days": days,
                "matrix": matrix,
                "map_data": {"tiles": map_tiles(), "points": map_points(rows, today)},
            },
        )

    @app.get("/calendar/{station_id}", response_class=HTMLResponse)
    def calendar(request: Request, station_id: str):
        station = lookup(station_id)
        today = datetime.now(config.TZ).date()
        last = today + timedelta(days=available_days())
        # 按周排成日历：从今天所在周的周一排到最后一天所在周的周日，范围外的格子留空
        start = today - timedelta(days=today.weekday())
        end = last + timedelta(days=6 - last.weekday())
        cells = []
        d = start
        while d <= end:
            in_range = today <= d <= last
            cells.append((d, in_range, cached_day(station, d) if in_range else None))
            d += timedelta(days=1)
        weeks = [cells[i : i + 7] for i in range(0, len(cells), 7)]
        return templates.TemplateResponse(
            request,
            "calendar.html",
            {
                "station": station,
                "stations": all_stations(),
                "weeks": weeks,
                "today": today,
                "last": last,
            },
        )

    @app.get("/tides/{station_id}", response_class=HTMLResponse)
    def station_day(request: Request, station_id: str, date: date | None = None):
        station = lookup(station_id)
        now = datetime.now(config.TZ)
        day = date or now.date()
        data, error = None, None
        try:
            data = app.state.service.day(station, day)
        except ProviderError as e:
            error = str(e)
        return templates.TemplateResponse(
            request,
            "station_day.html",
            {
                "station": station,
                "stations": all_stations(),
                "day": day,
                "prev": day - timedelta(days=1),
                "next": day + timedelta(days=1),
                "is_today": day == now.date(),
                "min_date": now.date(),
                "max_date": now.date() + timedelta(days=available_days()),
                "data": data,
                "payload": serialize(data) if data else None,
                "error": error,
                "week": week(station, now.date()),
            },
            status_code=200 if data else 502,
        )

    @app.get("/api/tides/{station_id}")
    def api_station_day(station_id: str, date: date | None = None):
        station = lookup(station_id)
        day = date or datetime.now(config.TZ).date()
        try:
            return serialize(app.state.service.day(station, day))
        except ProviderError as e:
            return JSONResponse({"error": str(e)}, status_code=502)

    return app


app = create_app()
