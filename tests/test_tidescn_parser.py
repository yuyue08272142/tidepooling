from datetime import date
from pathlib import Path

import pytest

from app.providers import ProviderError
from app.providers.tidescn import decode_html, parse_extremes

DAY = date(2026, 10, 24)


def test_parses_synthetic_table():
    html = (Path(__file__).parent / "fixtures" / "synthetic_day.html").read_text(encoding="utf-8")
    ex = parse_extremes(html, DAY)
    assert [(e.time.strftime("%H:%M"), e.kind, e.height) for e in ex] == [
        ("03:12", "low", 0.58),
        ("17:45", "high", 4.21),
    ]


def test_metres_and_time_first_layout():
    html = "<div>02:30 0.45m 低潮</div><div>15:05 3.90m 高潮</div>"
    ex = parse_extremes(html, DAY)
    assert [(e.kind, e.height) for e in ex] == [("low", 0.45), ("high", 3.9)]


def test_rejects_page_without_tides():
    with pytest.raises(ProviderError):
        parse_extremes("<p>日出 06:42 日落 18:12</p>", DAY)


def test_rejects_non_alternating():
    html = "<p>高潮 01:00 300cm</p><p>高潮 13:00 310cm</p>"
    with pytest.raises(ProviderError):
        parse_extremes(html, DAY)


def test_decodes_gbk():
    raw = '<meta charset="gbk"><p>低潮</p>'.encode("gbk")
    assert "低潮" in decode_html(raw)
