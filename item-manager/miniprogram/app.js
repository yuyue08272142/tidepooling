const config = require('./config')

App({
  onLaunch() {
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力')
      return
    }
    wx.cloud.init(config.CLOUD_ENV ? { env: config.CLOUD_ENV, traceUser: true } : { traceUser: true })
  },
})
