import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
TZ = ZoneInfo("Asia/Shanghai")

TIDESCN_BASE_URL = os.environ.get("TIDESCN_BASE_URL", "http://www.tidescn.com").rstrip("/")
# 两次请求 tidescn 之间的最小间隔（秒），避免给对方站点造成压力
TIDESCN_MIN_INTERVAL = float(os.environ.get("TIDESCN_MIN_INTERVAL", "2"))
HTTP_TIMEOUT = float(os.environ.get("HTTP_TIMEOUT", "15"))
USER_AGENT = os.environ.get("USER_AGENT", "tidepooling/0.1 (personal tide viewer)")

CACHE_PATH = Path(os.environ.get("CACHE_PATH", ROOT / "var" / "cache.sqlite3"))
# 潮汐预报是天文推算结果，基本不变，缓存可以放久一些
CACHE_TTL_DAYS = float(os.environ.get("CACHE_TTL_DAYS", "30"))
