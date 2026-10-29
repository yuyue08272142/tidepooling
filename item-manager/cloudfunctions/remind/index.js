// 定时触发（每天 9 点，见 config.json）：找出已订阅提醒、进入提醒期的消耗品，发订阅消息。
// 一次性订阅每同意一次只能发一条，发完把 remindSubscribed 置回 false，用户下次在物品页重新订阅。
// lastRemindedFor 记下这次提醒对应的用完日期，同一轮不会重复提醒。

const cloud = require('wx-server-sdk')
const { predict, today } = require('./predict')
const template = require('./template')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const db = cloud.database()
const PAGE = 100
const CONSUMABLE_TAG = '消耗品'
// 用户拒收或订阅次数已用完
const NO_QUOTA_ERRORS = [43101, 43107]

async function fetchAll(query) {
  const all = []
  for (;;) {
    const { data } = await query.skip(all.length).limit(PAGE).get()
    all.push(...data)
    if (data.length < PAGE) return all
  }
}

exports.main = async () => {
  if (!template.templateId) return { error: '请先在 template.js 里填写订阅消息模板 ID' }

  const t = today()
  const items = await fetchAll(db.collection('items').where({ tags: CONSUMABLE_TAG, remindSubscribed: true }))
  const summary = { checked: items.length, sent: 0, failed: 0 }

  for (const item of items) {
    const instances = await fetchAll(db.collection('instances').where({ itemId: item._id }))
    const p = predict(item, instances, t)
    if (!p.needRemind || item.lastRemindedFor === p.runOutDate) continue

    try {
      await cloud.openapi.subscribeMessage.send({
        touser: item._openid,
        templateId: template.templateId,
        page: `pages/item/item?id=${item._id}`,
        data: template.buildData(item, p),
        miniprogramState: template.miniprogramState,
      })
      await db.collection('items').doc(item._id).update({
        data: { remindSubscribed: false, lastRemindedFor: p.runOutDate },
      })
      summary.sent += 1
    } catch (e) {
      console.error('发送失败', item._id, e)
      summary.failed += 1
      if (NO_QUOTA_ERRORS.includes(e.errCode)) {
        await db.collection('items').doc(item._id).update({ data: { remindSubscribed: false } })
      }
    }
  }

  console.log(summary)
  return summary
}
