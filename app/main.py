from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config
from .cache import ExtremesCache
from .models import DayTides
from .providers import ProviderError
from .providers.tidescn import TidescnProvider
from .stations import all_stations, get_station
from .tides import TideService

_HERE = Path(__file__).parent
templates = Jinja2Templates(directory=_HERE / "templates")
templates.env.filters["hm"] = lambda t: t.strftime("%H:%M") if t else "--"
_WEEKDAYS = "一二三四五六日"
templates.env.filters["weekday"] = lambda d: "周" + _WEEKDAYS[d.weekday()]


def _iso(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


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
    }


def create_app(service: TideService | None = None) -> FastAPI:
    app = FastAPI(title="北海赶海潮汐")
    app.state.service = service or TideService(
        TidescnProvider(), ExtremesCache(config.CACHE_PATH, config.CACHE_TTL_DAYS)
    )
    app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")

    def lookup(station_id: str):
        station = get_station(station_id)
        if station is None:
            raise HTTPException(404, "未找到该潮汐站")
        return station

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(
            request, "index.html", {"stations": all_stations(), "today": datetime.now(config.TZ).date()}
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
                "data": data,
                "payload": serialize(data) if data else None,
                "error": error,
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
