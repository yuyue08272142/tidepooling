const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const path = require('path')
const {
  today, addDays, diffDays, instanceStatus, averageUsageDays, predict, remindDaysOf,
} = require('../miniprogram/utils/predict')

const T = '2026-10-29'
const finished = (startDate, endDate) => ({ startDate, endDate })
const using = startDate => ({ startDate, endDate: null })
const stock = () => ({ startDate: null, endDate: null })

test('today 按北京时间算', () => {
  // UTC 10-28 17:00 = 北京 10-29 01:00
  assert.equal(today(Date.UTC(2026, 9, 28, 17)), '2026-10-29')
  assert.equal(today(Date.UTC(2026, 9, 28, 15)), '2026-10-28')
})

test('日期加减跨月跨年', () => {
  assert.equal(addDays('2026-12-30', 3), '2027-01-02')
  assert.equal(addDays('2028-03-01', -1), '2028-02-29')
  assert.equal(diffDays('2026-10-01', '2026-10-31'), 30)
})

test('对象状态', () => {
  assert.equal(instanceStatus(stock()), 'stock')
  assert.equal(instanceStatus(using('2026-10-01')), 'using')
  assert.equal(instanceStatus(finished('2026-10-01', '2026-10-02')), 'finished')
})

test('平均使用天数：最近的权重大，只看最近 5 次', () => {
  const history = [
    finished('2026-01-01', '2026-01-11'), // 10 天，第 6 新，不算
    finished('2026-02-01', '2026-03-03'), // 30
    finished('2026-03-03', '2026-04-02'), // 30
    finished('2026-04-02', '2026-05-02'), // 30
    finished('2026-05-02', '2026-06-01'), // 30
    finished('2026-06-01', '2026-06-21'), // 20，最新，权重 5
  ]
  const { days, samples } = averageUsageDays(history)
  assert.equal(samples, 5)
  // (20*5 + 30*4 + 30*3 + 30*2 + 30*1) / 15
  assert.equal(days, 26.7)
})

test('同一天开始同一天用完按 1 天算', () => {
  assert.equal(averageUsageDays([finished(T, T)]).days, 1)
})

test('没有对象：none，不提醒', () => {
  const p = predict({}, [], T)
  assert.equal(p.state, 'none')
  assert.equal(p.needRemind, false)
})

test('没有历史也没有默认天数：unknown', () => {
  const p = predict({}, [using('2026-10-20')], T)
  assert.equal(p.state, 'unknown')
  assert.equal(p.needRemind, false)
})

test('没有历史时用默认天数', () => {
  const p = predict({ defaultDays: 30, remindDaysBefore: 3 }, [using('2026-10-20')], T)
  assert.equal(p.basis, 'default')
  assert.equal(p.runOutDate, '2026-11-19')
  assert.equal(p.daysLeft, 21)
  assert.equal(p.state, 'ok')
  assert.equal(p.remindDate, '2026-11-16')
})

test('有历史时优先用历史，库存依次接上', () => {
  const instances = [finished('2026-09-01', '2026-09-11'), using('2026-10-25'), stock(), stock()]
  const p = predict({ defaultDays: 100 }, instances, T)
  assert.equal(p.basis, 'history')
  assert.equal(p.cycleDays, 10)
  // 当前这个 11-04 用完，再加 2 个库存各 10 天
  assert.equal(p.runOutDate, '2026-11-24')
  assert.equal(p.stockCount, 2)
})

test('进入提醒期：soon', () => {
  const p = predict({ remindDaysBefore: 3 }, [finished('2026-09-01', '2026-09-11'), using('2026-10-21')], T)
  assert.equal(p.runOutDate, '2026-10-31')
  assert.equal(p.daysLeft, 2)
  assert.equal(p.state, 'soon')
  assert.equal(p.needRemind, true)
})

test('当前对象超期且没有库存：out', () => {
  const p = predict({}, [finished('2026-09-01', '2026-09-11'), using('2026-10-01')], T)
  assert.equal(p.runOutDate, T)
  assert.equal(p.state, 'out')
  assert.equal(p.needRemind, true)
})

test('超期但还有库存：从今天开始算库存', () => {
  const p = predict({}, [finished('2026-09-01', '2026-09-11'), using('2026-10-01'), stock()], T)
  assert.equal(p.runOutDate, '2026-11-08')
})

test('同时在用多个：以最晚用完的为准', () => {
  const p = predict({ defaultDays: 10 }, [using('2026-10-20'), using('2026-10-25')], T)
  assert.equal(p.runOutDate, '2026-11-04')
})

test('只有库存：从今天开始算', () => {
  const p = predict({ defaultDays: 7 }, [stock()], T)
  assert.equal(p.runOutDate, '2026-11-05')
})

test('全部用完：empty，用最后用完的日期去重', () => {
  const p = predict({}, [finished('2026-09-01', '2026-09-11'), finished('2026-09-11', '2026-10-02')], T)
  assert.equal(p.state, 'empty')
  assert.equal(p.runOutDate, '2026-10-02')
  assert.equal(p.needRemind, true)
})

test('提前提醒天数：0 有效，空值用默认 3', () => {
  assert.equal(remindDaysOf({ remindDaysBefore: 0 }), 0)
  assert.equal(remindDaysOf({ remindDaysBefore: '' }), 3)
  assert.equal(remindDaysOf({ remindDaysBefore: null }), 3)
  assert.equal(remindDaysOf({}), 3)
  assert.equal(remindDaysOf({ remindDaysBefore: 'abc' }), 3)
})

test('云函数里的 predict.js 与小程序里的一致（改完请 npm run sync）', () => {
  const root = path.join(__dirname, '..')
  assert.equal(
    fs.readFileSync(path.join(root, 'cloudfunctions/remind/predict.js'), 'utf8'),
    fs.readFileSync(path.join(root, 'miniprogram/utils/predict.js'), 'utf8'),
  )
})
