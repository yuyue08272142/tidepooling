module.exports = {
  // 云开发环境 ID，留空则使用开发者工具里选中的默认环境
  CLOUD_ENV: '',
  // 订阅消息模板 ID（公众平台 → 订阅消息 → 我的模板），留空则不显示“订阅用完提醒”按钮。
  // 云函数 cloudfunctions/remind/template.js 里也要填同一个。
  SUBSCRIBE_TEMPLATE_ID: '',
}
