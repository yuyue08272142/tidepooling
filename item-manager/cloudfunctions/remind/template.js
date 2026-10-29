// 订阅消息模板配置。
// 在公众平台 → 订阅消息 → 公共模板库 里选一个提醒类模板（例如“物品到期提醒”“库存不足提醒”），
// 把模板 ID 填到这里和 miniprogram/config.js，再按模板的字段名改 buildData 里的 key。
// thing 类字段最多 20 个字，date 类字段要是日期格式。

function clip(text, max = 20) {
  return text.length > max ? text.slice(0, max - 1) + '…' : text
}

module.exports = {
  templateId: '',
  // 开发版 developer、体验版 trial、正式版 formal：决定点开通知后跳到哪个版本
  miniprogramState: 'formal',

  buildData(item, prediction) {
    const tip = prediction.state === 'empty' || prediction.state === 'out'
      ? '已经用完了，记得补货'
      : `还剩约 ${prediction.daysLeft} 天，记得补货`
    return {
      thing1: { value: clip(item.name) },
      date2: { value: prediction.runOutDate },
      thing3: { value: clip(tip) },
    }
  },
}
