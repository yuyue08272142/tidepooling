// 消耗预测：根据已用完的对象的使用时长，估算当前这一批什么时候用完。
//
// 本文件同时被小程序和云函数 remind 使用，cloudfunctions/remind/predict.js 是它的副本，
// 改完这里请运行 `npm run sync` 同步（测试会检查两份是否一致）。
//
// 日期统一用 'YYYY-MM-DD' 字符串，按北京时间算“今天”，
// 避免云函数（UTC）和手机时区不一致导致差一天。

const DAY_MS = 24 * 60 * 60 * 1000
const BEIJING_OFFSET_MS = 8 * 60 * 60 * 1000
// 只看最近几次的使用时长，越近权重越大，习惯变了预测能跟上
const HISTORY_SAMPLES = 5
const DEFAULT_REMIND_DAYS = 3

function today(now = Date.now()) {
  return new Date(now + BEIJING_OFFSET_MS).toISOString().slice(0, 10)
}

function toDayNumber(date) {
  const [y, m, d] = date.split('-').map(Number)
  return Date.UTC(y, m - 1, d) / DAY_MS
}

function addDays(date, days) {
  return new Date((toDayNumber(date) + Math.round(days)) * DAY_MS).toISOString().slice(0, 10)
}

function diffDays(from, to) {
  return toDayNumber(to) - toDayNumber(from)
}

// stock：还没开始用（库存）；using：使用中；finished：已用完
function instanceStatus(inst) {
  if (inst.endDate) return 'finished'
  if (inst.startDate) return 'using'
  return 'stock'
}

// 同一天开始同一天用完也算用了 1 天
function usageDays(inst) {
  return Math.max(1, diffDays(inst.startDate, inst.endDate))
}

// 最近 HISTORY_SAMPLES 次的加权平均使用天数，最近一次权重最大
function averageUsageDays(instances) {
  const recent = instances
    .filter(i => instanceStatus(i) === 'finished' && i.startDate)
    .sort((a, b) => (a.endDate < b.endDate ? 1 : a.endDate > b.endDate ? -1 : 0))
    .slice(0, HISTORY_SAMPLES)
  if (!recent.length) return { days: 0, samples: 0 }
  let sum = 0
  let weights = 0
  recent.forEach((inst, i) => {
    const w = recent.length - i
    sum += usageDays(inst) * w
    weights += w
  })
  return { days: Math.round((sum / weights) * 10) / 10, samples: recent.length }
}

function remindDaysOf(item) {
  const v = item.remindDaysBefore
  if (v === null || v === undefined || v === '') return DEFAULT_REMIND_DAYS
  const n = Number(v)
  return n >= 0 ? n : DEFAULT_REMIND_DAYS
}

/**
 * 预测某个物品什么时候用完。
 *
 * 规则：
 * - 每个对象的可用天数 = 历史加权平均；没有历史时用物品上设置的 defaultDays
 * - 使用中的对象各自从开始日期算起；已经超期的视为今天用完
 * - 同时在用的几个按并行消耗处理，以最晚用完的为准，之后再依次拆库存
 * - 用完日期前 remindDaysBefore 天开始提醒
 *
 * state：
 * - none     还没有任何对象
 * - unknown  没有历史也没有默认天数，无法预测
 * - empty    之前的都用完了，也没有库存
 * - out      预计今天（或已经）用完
 * - soon     进入提醒期
 * - ok       充足
 */
function predict(item, instances, todayStr = today()) {
  const using = instances.filter(i => instanceStatus(i) === 'using')
  const stock = instances.filter(i => instanceStatus(i) === 'stock')
  const finished = instances.filter(i => instanceStatus(i) === 'finished')
  const history = averageUsageDays(instances)
  const remindDays = remindDaysOf(item)

  let cycleDays = 0
  let basis = null
  if (history.samples) {
    cycleDays = history.days
    basis = 'history'
  } else if (Number(item.defaultDays) > 0) {
    cycleDays = Number(item.defaultDays)
    basis = 'default'
  }

  const result = {
    state: 'ok',
    basis,
    cycleDays,
    samples: history.samples,
    usingCount: using.length,
    stockCount: stock.length,
    finishedCount: finished.length,
    runOutDate: null,
    daysLeft: null,
    remindDate: null,
    needRemind: false,
  }

  if (!instances.length) return { ...result, state: 'none' }

  if (!using.length && !stock.length) {
    // 用最后一次用完的日期，保证同一次“用完”只提醒一次
    const lastEnd = finished.map(i => i.endDate).sort().pop()
    return {
      ...result,
      state: 'empty',
      runOutDate: lastEnd,
      daysLeft: 0,
      remindDate: lastEnd,
      needRemind: true,
    }
  }

  if (!cycleDays) return { ...result, state: 'unknown' }

  let currentEnd = todayStr
  for (const inst of using) {
    const end = addDays(inst.startDate, cycleDays)
    if (end > currentEnd) currentEnd = end
  }
  const runOutDate = addDays(currentEnd, stock.length * cycleDays)
  const daysLeft = diffDays(todayStr, runOutDate)
  const remindDate = addDays(runOutDate, -remindDays)
  const needRemind = todayStr >= remindDate

  return {
    ...result,
    state: daysLeft <= 0 ? 'out' : needRemind ? 'soon' : 'ok',
    runOutDate,
    daysLeft,
    remindDate,
    needRemind,
  }
}

// 某个使用中的对象预计哪天用完
function expectedEnd(inst, cycleDays) {
  if (!inst.startDate || !cycleDays) return null
  return addDays(inst.startDate, cycleDays)
}

module.exports = {
  DEFAULT_REMIND_DAYS,
  today,
  addDays,
  diffDays,
  instanceStatus,
  usageDays,
  averageUsageDays,
  remindDaysOf,
  predict,
  expectedEnd,
}
