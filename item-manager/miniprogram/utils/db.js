// 云数据库读写。三个集合，权限都设为“仅创建者可读写”：
//   groups     分组    { name, createdAt }
//   items      物品类  { groupId, name, photos[], tags[], note, defaultDays, remindDaysBefore,
//                       remindSubscribed, lastRemindedFor, createdAt }
//   instances  物品对象 { itemId, note, startDate, endDate, createdAt }

const { CONSUMABLE_TAG, isConsumable } = require('./tags')
const { predict, today } = require('./predict')

// 小程序端单次查询最多返回 20 条
const PAGE = 20
const IN_CHUNK = 50

function db() {
  return wx.cloud.database()
}

function col(name) {
  return db().collection(name)
}

async function fetchAll(query) {
  const all = []
  for (;;) {
    const { data } = await query.skip(all.length).limit(PAGE).get()
    all.push(...data)
    if (data.length < PAGE) return all
  }
}

// ---------- 分组 ----------

async function listGroups() {
  const groups = await fetchAll(col('groups').orderBy('createdAt', 'asc'))
  const counts = await Promise.all(groups.map(g => col('items').where({ groupId: g._id }).count()))
  return groups.map((g, i) => ({ ...g, itemCount: counts[i].total }))
}

function addGroup(name) {
  return col('groups').add({ data: { name, createdAt: db().serverDate() } })
}

function renameGroup(id, name) {
  return col('groups').doc(id).update({ data: { name } })
}

async function removeGroup(id) {
  const { total } = await col('items').where({ groupId: id }).count()
  if (total > 0) throw new Error(`分组里还有 ${total} 种物品，请先移走或删除`)
  return col('groups').doc(id).remove()
}

// ---------- 物品 ----------

async function getItem(id) {
  const { data } = await col('items').doc(id).get()
  return data
}

function listItems(groupId) {
  return fetchAll(col('items').where({ groupId }).orderBy('createdAt', 'desc'))
}

async function saveItem(id, data) {
  if (id) {
    await col('items').doc(id).update({ data })
    return id
  }
  const { _id } = await col('items').add({
    data: {
      remindSubscribed: false,
      lastRemindedFor: '',
      ...data,
      createdAt: db().serverDate(),
    },
  })
  return _id
}

async function removeItem(item) {
  const instances = await listInstances(item._id)
  await Promise.all(instances.map(i => col('instances').doc(i._id).remove()))
  if (item.photos && item.photos.length) {
    await wx.cloud.deleteFile({ fileList: item.photos }).catch(() => {})
  }
  return col('items').doc(item._id).remove()
}

// ---------- 对象 ----------

function listInstances(itemId) {
  return fetchAll(col('instances').where({ itemId }).orderBy('createdAt', 'asc'))
}

// 一次取多个物品的全部对象，返回 { itemId: [instance] }
async function instancesByItem(itemIds) {
  const _ = db().command
  const map = {}
  itemIds.forEach(id => { map[id] = [] })
  for (let i = 0; i < itemIds.length; i += IN_CHUNK) {
    const chunk = itemIds.slice(i, i + IN_CHUNK)
    const rows = await fetchAll(col('instances').where({ itemId: _.in(chunk) }).orderBy('createdAt', 'asc'))
    rows.forEach(r => map[r.itemId].push(r))
  }
  return map
}

async function getInstance(id) {
  const { data } = await col('instances').doc(id).get()
  return data
}

// count > 1 时一次建多个相同的对象（比如一次买了 6 卷纸）
async function addInstances(itemId, data, count = 1) {
  for (let i = 0; i < count; i++) {
    await col('instances').add({ data: { itemId, ...data, createdAt: db().serverDate() } })
  }
}

function updateInstance(id, data) {
  return col('instances').doc(id).update({ data })
}

function removeInstance(id) {
  return col('instances').doc(id).remove()
}

// ---------- 提醒 ----------

// 首页“即将用完”：所有进入提醒期的消耗品，按剩余天数排序
async function listReminders() {
  const items = await fetchAll(col('items').where({ tags: CONSUMABLE_TAG }))
  if (!items.length) return []
  const byItem = await instancesByItem(items.map(i => i._id))
  const t = today()
  return items
    .filter(isConsumable)
    .map(item => ({ item, prediction: predict(item, byItem[item._id], t) }))
    .filter(r => r.prediction.needRemind)
    .sort((a, b) => a.prediction.daysLeft - b.prediction.daysLeft)
}

module.exports = {
  listGroups,
  addGroup,
  renameGroup,
  removeGroup,
  getItem,
  listItems,
  saveItem,
  removeItem,
  listInstances,
  instancesByItem,
  getInstance,
  addInstances,
  updateInstance,
  removeInstance,
  listReminders,
}
