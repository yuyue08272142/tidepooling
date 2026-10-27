# 北海赶海潮汐（M1）

面向赶海的潮汐查询 H5 网页。第一版覆盖广西北海市：北海、涠洲岛、铁山港。

## 功能（M1）

- 站点日页 `/tides/{站点}?date=YYYY-MM-DD`：前一天/后一天和日期选择、农历、潮汛（大/中/小潮）、月相、
  高低潮表、24 小时潮汐曲线（夜间阴影、“现在”标线）、日出日落/月出月落、逐时潮高
- JSON 接口 `/api/tides/{站点}?date=YYYY-MM-DD`
- 首页：站点列表

## 运行

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# 打开 http://127.0.0.1:8000/
pytest -q
```

## 数据来源

高低潮数据从 tidescn.com 抓取（`app/providers/tidescn.py`），曲线和逐时潮高由相邻高低潮按余弦插值得到。

- 抓取是串行的，请求间隔至少 `TIDESCN_MIN_INTERVAL` 秒（默认 2 秒），结果缓存在 SQLite（`var/cache.sqlite3`，默认 30 天）。
  查看一天会用到前后共 3 天的数据，缓存命中后不再请求。
- **解析规则尚未用真实页面校验**（开发环境无法访问 tidescn.com）。在能访问的机器上运行：

  ```bash
  python -m app.providers.tidescn 945 2026-10-24 --save tests/fixtures
  ```

  会打印解析结果并保存原始 HTML，用它来收紧解析规则、补充测试。
- 站点和 tidescn 编号在 `app/data/stations.json`。目前只有北海填了 945（取自参考链接，待确认），
  涠洲岛、铁山港的编号待补充。
- 取不到数据时页面显示错误提示，不会用估算数据冒充。

## 潮汛的判断

北部湾以全日潮为主，大小潮由月球赤纬决定（回归潮）：月亮赤纬最大时潮差最大，过赤道时最小，
与初一、十五关系不大。`app/astro.py` 用当天月赤纬与前后半个月最大值的比值划分大/中/小潮。

## 配置（环境变量）

| 变量 | 默认值 |
|---|---|
| `TIDESCN_BASE_URL` | `http://www.tidescn.com` |
| `TIDESCN_MIN_INTERVAL` | `2` |
| `CACHE_PATH` | `var/cache.sqlite3` |
| `CACHE_TTL_DAYS` | `30` |

## 目录

```
app/
  main.py            路由（页面 + API）
  tides.py           取数、缓存、插值的组装
  providers/         数据源（tidescn 抓取）
  interp.py          余弦插值
  astro.py           日月、农历、潮汛
  cache.py           SQLite 缓存
  data/stations.json 站点配置
  templates/ static/ 页面（ECharts 5.5.1 放在 static/vendor，Apache-2.0）
tests/
```
