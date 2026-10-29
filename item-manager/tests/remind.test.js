// 云函数 remind：用内存数据库和假的 wx-server-sdk 跑一遍
const test = require('node:test')
const assert = require('node:assert/strict')
const Module = require('module')
const path = require('path')
const { createDatabase } = require('./helpers/wx-mock')
const { today, addDays } = require('../miniprogram/utils/predict')

const fnDir = path.join(__dirname, '../cloudfunctions/remind')

function loadRemind({ sendError } = {}) {
  const database = createDatabase({ limit: 100 })
  const sent = []
  const fakeSdk = {
    DYNAMIC_CURRENT_ENV: 'env',
    init() {},
    database: () => database,
    openapi: {
      subscribeMessage: {
        async send(msg) {
          if (sendError) throw sendError
          sent.push(msg)
        },
      },
    },
  }
  const originalLoad = Module._load
  Module._load = function (request, ...rest) {
    if (request === 'wx-server-sdk') return fakeSdk
    return originalLoad.call(this, request, ...rest)
  }
  for (const f of ['index.js', 'template.js']) delete require.cache[path.join(fnDir, f)]
  try {
    const fn = require(path.join(fnDir, 'index.js'))
    require(path.join(fnDir, 'template.js')).templateId = 'TPL'
    return { fn, database, sent }
  } finally {
    Module._load = originalLoad
  }
}

async function seed(database, item, instances) {
  const { _id } = await database.collection('items').add({ data: { lastRemindedFor: '', ...item } })
  for (const inst of instances) await database.collection('instances').add({ data: { itemId: _id, ...inst } })
  return _id
}

test('进入提醒期且已订阅才发，发完不重复', async () => {
  const { fn, database, sent } = loadRemind()
  const t = today()
  const base = { tags: ['消耗品'], defaultDays: 30, remindDaysBefore: 3 }
  const due = await seed(database, { ...base, name: '洗衣液', remindSubscribed: true }, [{ startDate: addDays(t, -28), endDate: null }])
  await seed(database, { ...base, name: '没订阅', remindSubscribed: false }, [{ startDate: addDays(t, -28), endDate: null }])
  await seed(database, { ...base, name: '还早', remindSubscribed: true }, [{ startDate: t, endDate: null }])

  const res = await fn.main()
  assert.deepEqual(res, { checked: 2, sent: 1, failed: 0 })
  assert.equal(sent[0].touser, 'user1')
  assert.equal(sent[0].page, `pages/item/item?id=${due}`)
  assert.deepEqual(sent[0].data, {
    thing1: { value: '洗衣液' },
    date2: { value: addDays(t, 2) },
    thing3: { value: '还剩约 2 天，记得补货' },
  })

  const item = (await database.collection('items').doc(due).get()).data
  assert.equal(item.remindSubscribed, false)
  assert.equal(item.lastRemindedFor, addDays(t, 2))

  // 用户再次订阅，但还是同一轮（用完日期没变）→ 不重复发
  await database.collection('items').doc(due).update({ data: { remindSubscribed: true } })
  assert.equal((await fn.main()).sent, 0)
})

test('用户拒收时取消订阅标记', async () => {
  const { fn, database } = loadRemind({ sendError: Object.assign(new Error('no quota'), { errCode: 43101 }) })
  const id = await seed(database, { tags: ['消耗品'], name: '牙膏', remindSubscribed: true }, [{ startDate: '2026-01-01', endDate: '2026-01-10' }])
  const res = await fn.main()
  assert.equal(res.failed, 1)
  assert.equal((await database.collection('items').doc(id).get()).data.remindSubscribed, false)
})
