// 用内存版云数据库跑数据层和页面逻辑
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const path = require('path')
const { createDatabase, installWx, loadPage } = require('./helpers/wx-mock')
const { today, addDays } = require('../miniprogram/utils/predict')

const db = require('../miniprogram/utils/db')

function setup() {
  const database = createDatabase()
  const calls = installWx(database)
  return { database, calls }
}

test('app.json 里的页面文件都存在', () => {
  const root = path.join(__dirname, '../miniprogram')
  const { pages } = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8'))
  for (const page of pages) {
    for (const ext of ['js', 'json', 'wxml', 'wxss']) {
      assert.ok(fs.existsSync(path.join(root, `${page}.${ext}`)), `${page}.${ext}`)
    }
  }
})

test('分组显示物品种类数量，非空分组不能删', async () => {
  setup()
  const { _id: kitchen } = await db.addGroup('厨房')
  const { _id: bath } = await db.addGroup('卫生间')
  await db.saveItem('', { groupId: kitchen, name: '洗洁精', tags: [] })
  await db.saveItem('', { groupId: kitchen, name: '保鲜膜', tags: [] })

  const groups = await db.listGroups()
  assert.deepEqual(groups.map(g => [g.name, g.itemCount]), [['厨房', 2], ['卫生间', 0]])

  await assert.rejects(db.removeGroup(kitchen), /还有 2 种物品/)
  await db.removeGroup(bath)
  assert.equal((await db.listGroups()).length, 1)
})

test('超过 20 条时分页取全', async () => {
  setup()
  const itemId = await db.saveItem('', { groupId: 'g', name: '卷纸', tags: [] })
  await db.addInstances(itemId, { startDate: null, endDate: null }, 45)
  assert.equal((await db.listInstances(itemId)).length, 45)
  assert.equal((await db.instancesByItem([itemId]))[itemId].length, 45)
})

test('删除物品同时删掉对象和照片', async () => {
  const { database, calls } = setup()
  const id = await db.saveItem('', { groupId: 'g', name: '牙膏', tags: [], photos: ['cloud://a.jpg'] })
  await db.addInstances(id, { startDate: null, endDate: null }, 3)
  await db.removeItem(await db.getItem(id))
  assert.equal(database.store.items.length, 0)
  assert.equal(database.store.instances.length, 0)
  assert.deepEqual(calls.deleteFile, ['cloud://a.jpg'])
})

test('首页提醒只列出进入提醒期的消耗品', async () => {
  setup()
  const t = today()
  const soon = await db.saveItem('', { groupId: 'g', name: '洗衣液', tags: ['消耗品'], defaultDays: 30, remindDaysBefore: 3 })
  await db.addInstances(soon, { startDate: addDays(t, -28), endDate: null })
  const fine = await db.saveItem('', { groupId: 'g', name: '洗发水', tags: ['消耗品'], defaultDays: 30, remindDaysBefore: 3 })
  await db.addInstances(fine, { startDate: t, endDate: null })
  const notConsumable = await db.saveItem('', { groupId: 'g', name: '剪刀', tags: ['日用'], defaultDays: 1 })
  await db.addInstances(notConsumable, { startDate: addDays(t, -10), endDate: null })

  const reminders = await db.listReminders()
  assert.deepEqual(reminders.map(r => [r.item.name, r.prediction.daysLeft]), [['洗衣液', 2]])
})

test('首页页面：加载分组和提醒', async () => {
  setup()
  const { _id: g } = await db.addGroup('卫生间')
  const id = await db.saveItem('', { groupId: g, name: '卷纸', tags: ['消耗品'], photos: ['cloud://p.jpg'] })
  await db.addInstances(id, { startDate: '2026-01-01', endDate: '2026-01-02' })

  const page = loadPage('index')
  await page.load()
  assert.deepEqual(page.data.groups.map(x => x.itemCount), [1])
  assert.equal(page.data.reminders.length, 1)
  assert.equal(page.data.reminders[0].cover, 'cloud://p.jpg')
  assert.equal(page.data.reminders[0].text, '已经用完了，记得补货')
})

test('分组页面：按标签筛选', async () => {
  setup()
  await db.saveItem('', { groupId: 'g', name: '洗衣液', tags: ['消耗品', '日用'] })
  await db.saveItem('', { groupId: 'g', name: '吹风机', tags: ['电子产品'] })
  const page = loadPage('group')
  page.onLoad({ id: 'g', name: '卫生间' })
  await page.load()
  assert.equal(page.data.shown.length, 2)
  assert.deepEqual(page.data.allTags.sort(), ['日用', '消耗品', '电子产品'].sort())
  page.toggleTag({ currentTarget: { dataset: { tag: '电子产品' } } })
  assert.deepEqual(page.data.shown.map(i => i.name), ['吹风机'])
  page.toggleTag({ currentTarget: { dataset: { tag: '电子产品' } } })
  assert.equal(page.data.shown.length, 2)
})

test('物品页面：开始用 / 用完了 之后有了预测', async () => {
  setup()
  const id = await db.saveItem('', { groupId: 'g', name: '洗洁精', tags: ['消耗品'] })
  await db.addInstances(id, { startDate: null, endDate: null }, 2)
  const page = loadPage('item')
  page.onLoad({ id })
  await page.load()
  assert.equal(page.data.prediction.state, 'unknown')

  const [first] = await db.listInstances(id)
  await page.startUse({ currentTarget: { dataset: { id: first._id } } })
  await page.load()
  assert.equal(page.data.instances.find(i => i._id === first._id).status, 'using')
  await page.finishUse({ currentTarget: { dataset: { id: first._id } } })
  await page.load()
  // 同一天开始同一天用完算 1 天；剩下 1 个库存
  assert.equal(page.data.prediction.basis, 'history')
  assert.equal(page.data.prediction.runOutDate, addDays(today(), 1))
})

test('物品编辑页面：新建物品带照片和标签', async () => {
  const { database, calls } = setup()
  const { _id: g } = await db.addGroup('厨房')
  const page = loadPage('item-edit')
  await page.onLoad({ groupId: g })
  assert.equal(page.data.groupIndex, 0)
  page.setData({ name: '  酱油 ', photos: ['cloud://x.jpg'], customTag: '调料' })
  page.addCustomTag()
  page.toggleTag({ currentTarget: { dataset: { tag: '消耗品' } } })
  assert.equal(page.data.consumable, true)
  page.setData({ defaultDays: '60', remindDaysBefore: '0' })
  await page.save()

  const [item] = database.store.items
  assert.equal(item.name, '酱油')
  assert.deepEqual(item.tags, ['调料', '消耗品'])
  assert.equal(item.defaultDays, 60)
  assert.equal(item.remindDaysBefore, 0)
  assert.equal(item.remindSubscribed, false)
  assert.deepEqual(calls.redirectTo, [`/pages/item/item?id=${item._id}`])
})

test('对象编辑页面：用完日期不能早于开始日期，可批量添加', async () => {
  const { database, calls } = setup()
  const page = loadPage('instance-edit')
  await page.onLoad({ itemId: 'item-x' })
  page.setData({ startDate: '2026-10-10', endDate: '2026-10-01' })
  await page.save()
  assert.deepEqual(calls.toast, ['用完日期不能早于开始日期'])

  page.setData({ startDate: '', endDate: '', count: '6' })
  await page.save()
  assert.equal(database.store.instances.length, 6)
  assert.equal(calls.navigateBack, 1)
})
