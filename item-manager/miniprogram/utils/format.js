// 把物品、对象、预测结果整理成页面直接显示的文字（纯函数，方便测试）

const { instanceStatus, usageDays, diffDays, expectedEnd, today } = require('./predict')

const STATUS_TEXT = { stock: '库存', using: '使用中', finished: '已用完' }

function predictionText(p) {
  switch (p.state) {
    case 'none':
      return '还没有记录，先添加一个'
    case 'unknown':
      return '用完一个后就能预测，也可以在编辑里设置“默认可用天数”'
    case 'empty':
      return '已经用完了，记得补货'
    case 'out':
      return '预计已经用完'
    default:
      return `预计 ${p.daysLeft} 天后用完（${p.runOutDate}）`
  }
}

function basisText(p) {
  if (p.basis === 'history') return `按最近 ${p.samples} 次平均每个用 ${p.cycleDays} 天估算`
  if (p.basis === 'default') return `按默认每个用 ${p.cycleDays} 天估算`
  return ''
}

// 列表里一行的数量概况，例如“使用中 1 · 库存 2 · 已用完 5”
function countsText(instances) {
  const counts = { using: 0, stock: 0, finished: 0 }
  instances.forEach(i => { counts[instanceStatus(i)] += 1 })
  const parts = []
  if (counts.using) parts.push(`使用中 ${counts.using}`)
  if (counts.stock) parts.push(`库存 ${counts.stock}`)
  if (counts.finished) parts.push(`已用完 ${counts.finished}`)
  return parts.join(' · ') || '暂无对象'
}

// 物品详情页里对象列表的一行
function instanceView(inst, index, cycleDays, todayStr = today()) {
  const status = instanceStatus(inst)
  let detail = ''
  if (status === 'finished') {
    detail = inst.startDate
      ? `${inst.startDate} 至 ${inst.endDate}，用了 ${usageDays(inst)} 天`
      : `${inst.endDate} 用完`
  } else if (status === 'using') {
    const used = Math.max(0, diffDays(inst.startDate, todayStr))
    const end = expectedEnd(inst, cycleDays)
    detail = `${inst.startDate} 开始，已用 ${used} 天` + (end ? `，预计 ${end} 用完` : '')
  } else {
    detail = '还没开始用'
  }
  return {
    ...inst,
    no: index + 1,
    status,
    statusText: STATUS_TEXT[status],
    detail,
  }
}

module.exports = { STATUS_TEXT, predictionText, basisText, countsText, instanceView }
