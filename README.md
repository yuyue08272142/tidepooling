# 北海赶海潮汐

面向赶海的潮汐查询 H5 网页。第一版覆盖广西北海市：北海港、金海湾、涠洲岛、营盘港、铁山港。

## 功能

- **首页** `/`：今天各站的赶海星级和最佳时段、赶海地点地图（标记颜色按今天的星级，点开看时段和详情）、未来 7 天各站赶海指数总览
- **站点日页** `/tides/{站点}?date=YYYY-MM-DD`：
  - 赶海建议：星级/分数、最佳时段、开始返回时间、最晚离开滩涂时间、理由和安全提醒
  - 农历、潮汛（大/中/小潮）、月相、高低潮表
  - 24 小时潮汐曲线（最佳时段、最晚离开线、夜间阴影、“现在”标线）
  - 天气风浪（天况、风向风力、浪高、气温、水温、气压）、日出日落/月出月落、逐时潮高
- **赶海日历** `/calendar/{站点}`：未来 15 天（今天 + 14 天）每天的星级、时段、低潮、潮汛和天气
- JSON 接口 `/api/tides/{站点}?date=YYYY-MM-DD`（含 `weather`、`suggestion`）

首页和日历只读缓存，不会触发抓取，需要先跑 `app.prefetch`。

## 赶海指数

`app/score.py`。对当天每次低潮打分（满分 100），取最高的一次：

| 维度 | 权重 | 规则 |
|---|---|---|
| 低潮有多低 | 40% | 潮高 ≤0.4 米满分，≥2.0 米 0 分（潮高基准面大致是当地最低潮位） |
| 是否白天 | 20% | 最佳时段落在日出前 30 分钟到日落后 30 分钟之间的比例 |
| 天气风浪 | 25% | 风 ≤3 级满分、4 级 0.7、5 级 0.35；浪 ≤0.5 米满分、≤1 米 0.7；有雨 0.4；取最低项 |
| 潮差 | 15% | 上一次高潮到这次低潮的落差，1 米 0 分、3.5 米满分 |

雷雨、暴雨/大雨/台风、6 级以上大风、1.5 米以上浪：直接判“不宜赶海”（最多 20 分）。
星级：≥80 五星、≥65 四星、≥50 三星、≥35 二星。

时段：低潮前 2 小时到低潮后 1 小时为最佳时段，到点开始往回走；
潮水涨回到下滩时的水位（按插值曲线计算），就是最晚离开滩涂的时间。

## 运行

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m app.prefetch          # 预取各站未来 14 天潮汐和天气（首次约 3 分钟），建议每 6 小时用 cron 跑一次
uvicorn app.main:app --reload --port 8000   # --reload：改了 Python 代码自动重启
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
- 天气风浪和高低潮在同一页面，一起解析。天气缓存超过 6 小时（`WEATHER_TTL_HOURS`）预取时会重抓；
  页面结构变化导致天气解析不出时只缺天气，不影响潮汐。
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
| `WEATHER_TTL_HOURS` | `6` |
| `MAP_TILES` | `osm`（OpenStreetMap，免 key）；设为 `tianditu` 改用天地图 |
| `TIANDITU_KEY` | 天地图 key（在天地图官网免费申请“浏览器端”key）；`MAP_TILES=tianditu` 但没配 key 时仍用 OpenStreetMap |

地图坐标都用 WGS-84（GPS 坐标），OpenStreetMap 和天地图都能直接用，不需要偏移换算。
站点经纬度是大致位置，可在 `app/data/stations.json` 里修正；`map_label` 控制地图上站名标签的方向。

## 目录

```
app/
  main.py            路由（页面 + API）
  tides.py           取数、缓存、插值、打分的组装
  score.py           赶海指数、最佳时段、返回时间
  prefetch.py        定时预取
  providers/         数据源（tidescn 抓取）
  interp.py          余弦插值
  astro.py           日月、农历、潮汛
  cache.py           SQLite 缓存
  data/stations.json 站点配置
  templates/ static/ 页面（static/vendor 内：ECharts 5.5.1 Apache-2.0、Leaflet 1.9.4 BSD-2-Clause）
tests/
```
