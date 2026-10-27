# 北海赶海潮汐（M1）

面向赶海的潮汐查询 H5 网页。第一版覆盖广西北海市：北海港、金海湾、涠洲岛、营盘港、铁山港。

## 功能（M1）

- 站点日页 `/tides/{站点}?date=YYYY-MM-DD`：前一天/后一天和日期选择、农历、潮汛（大/中/小潮）、月相、
  高低潮表、24 小时潮汐曲线（夜间阴影、“现在”标线）、日出日落/月出月落、逐时潮高
- JSON 接口 `/api/tides/{站点}?date=YYYY-MM-DD`
- 首页：站点列表

## 运行

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m app.prefetch          # 预取各站未来 14 天数据（约 3 分钟），建议每天凌晨用 cron 跑一次
uvicorn app.main:app --port 8000
# 打开 http://127.0.0.1:8000/
pytest -q
```

## 数据来源

高低潮从 tidescn.com 抓取（页面注明数据来自国家海洋信息中心），代码在 `app/providers/tidescn.py`。
曲线和逐时潮高由相邻高低潮按余弦插值得到；tidescn 页面上的曲线数据是加密的，不使用。

- **只能取到今天起 14 天内的数据**。超出范围时 tidescn 不报错，而是返回别的日期的页面，
  所以解析时会校验页面日期，对不上就报错，不会存错数据。
- 抓取是串行的，请求间隔至少 2 秒，结果缓存在 SQLite（`var/cache.sqlite3`，30 天）。
  查看一天要用到前后 3 天的数据；昨天的数据 tidescn 已不提供，靠 `app.prefetch` 前一天存下的缓存补上，
  否则当天 0 点到第一个高低潮之间的曲线会留空。
- 取不到数据时页面显示错误提示，不会用估算数据冒充。
- 站点配置在 `app/data/stations.json`。经纬度是大致位置，只用于计算日出日落和月出月落。
  tidescn 上北海市还有高沙（1166）、廉江（1167）两站，暂未加入。
- 调试单页：`python -m app.providers.tidescn 945 2026-10-28 --save var/html`

## 潮汛的判断

北部湾以全日潮为主，大小潮由月球赤纬决定（回归潮）：月亮赤纬最大时潮差最大，过赤道时最小，
与初一、十五关系不大。`app/astro.py` 用当天月赤纬与前后半个月最大值的比值划分大/中/小潮。

例：2026-10-24（农历十五）tidescn 按农历标为“大潮”，但北海港当天潮差只有 1.4 米、出现 4 次高低潮；
10-27、10-28 月赤纬接近最大，潮差达 3.6~4.3 米。本站分别判为小潮和大潮。

## 配置（环境变量）

| 变量 | 默认值 |
|---|---|
| `TIDESCN_BASE_URL` | `https://www.tidescn.com` |
| `TIDESCN_MIN_INTERVAL` | `2`（秒） |
| `HTTP_TIMEOUT` | `30`（秒） |
| `CACHE_PATH` | `var/cache.sqlite3` |
| `CACHE_TTL_DAYS` | `30` |

## 目录

```
app/
  main.py            路由（页面 + API）
  tides.py           取数、缓存、插值的组装
  prefetch.py        每日预取
  providers/         数据源（tidescn 抓取）
  interp.py          余弦插值
  astro.py           日月、农历、潮汛
  cache.py           SQLite 缓存
  data/stations.json 站点配置
  templates/ static/ 页面（ECharts 5.5.1 放在 static/vendor，Apache-2.0）
tests/
```
