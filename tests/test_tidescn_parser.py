from datetime import date
from pathlib import Path

import pytest

from app.providers import ProviderError
from app.providers.tidescn import TidescnProvider, decode_html, parse_extremes
from app.stations import get_station

FIXTURES = Path(__file__).parent / "fixtures"


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parses_real_page_structure():
    ex = parse_extremes(read("tidescn_945_2026-10-24.html"), date(2026, 10, 24))
    assert [(e.time.strftime("%H:%M"), e.kind, e.height) for e in ex] == [
        ("05:23", "high", 2.6),
        ("09:54", "low", 2.2),
        ("16:50", "high", 3.5),
        ("23:50", "low", 2.1),
    ]
    assert all(e.time.date() == date(2026, 10, 24) for e in ex)


def test_rejects_page_for_another_date():
    # tidescn 对范围外日期不报错，而是返回别的日期，必须拦下来
    with pytest.raises(ProviderError, match="2026-11-11"):
        parse_extremes(read("tidescn_945_out_of_range.html"), date(2026, 12, 30))
    with pytest.raises(ProviderError, match="2026-10-24"):
        parse_extremes(read("tidescn_945_2026-10-24.html"), date(2026, 10, 25))


def test_rejects_unknown_structure():
    with pytest.raises(ProviderError, match="结构"):
        parse_extremes("<html><body>维护中</body></html>", date(2026, 10, 24))


def test_unparseable_entry_is_an_error_not_skipped():
    html = read("tidescn_945_2026-10-24.html").replace("2.6米", "--")
    with pytest.raises(ProviderError, match="无法解析"):
        parse_extremes(html, date(2026, 10, 24))


def test_out_of_range_day_is_not_requested():
    class NoNetwork:
        def get(self, *a, **k):
            raise AssertionError("不应发出请求")

    p = TidescnProvider(client=NoNetwork())
    with pytest.raises(ProviderError, match="14 天"):
        p.fetch_extremes(get_station("beihai"), date(2000, 1, 1))


def test_decodes_gbk():
    raw = '<meta charset="gbk"><p>干潮</p>'.encode("gbk")
    assert "干潮" in decode_html(raw)
