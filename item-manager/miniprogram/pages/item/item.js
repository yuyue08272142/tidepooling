const db = require('../../utils/db')
const config = require('../../config')
const { predict, today, remindDaysOf } = require('../../utils/predict')
const { isConsumable } = require('../../utils/tags')
const { predictionText, basisText, instanceView } = require('../../utils/format')
const { toast, confirm, withLoading } = require('../../utils/ui')

const TEMPLATE_ID = config.SUBSCRIBE_TEMPLATE_ID

Page({
  data: {
    id: '',
    item: null,
    instances: [],
    consumable: false,
    prediction: null,
    predictionText: '',
    basisText: '',
    remindDays: 0,
    canSubscribe: !!TEMPLATE_ID,
  },

  onLoad(options) {
    this.setData({ id: options.id })
  },

  onShow() {
    this.load()
  },

  async load() {
    try {
      const [item, instances] = await Promise.all([db.getItem(this.data.id), db.listInstances(this.data.id)])
      wx.setNavigationBarTitle({ title: item.name })
      const t = today()
      const consumable = isConsumable(item)
      const p = predict(item, instances, t)
      this.setData({
        item,
        consumable,
        prediction: consumable ? p : null,
        predictionText: consumable ? predictionText(p) : '',
        basisText: consumable ? basisText(p) : '',
        remindDays: remindDaysOf(item),
        instances: instances.map((inst, i) => instanceView(inst, i, p.cycleDays, t)).reverse(),
      })
    } catch (e) {
      console.error(e)
      toast('加载失败')
    }
  },

  previewPhoto(e) {
    wx.previewImage({ urls: this.data.item.photos, current: e.currentTarget.dataset.src })
  },

  edit() {
    wx.navigateTo({ url: `/pages/item-edit/item-edit?id=${this.data.id}` })
  },

  async remove() {
    const { item } = this.data
    if (!(await confirm(`删除“${item.name}”以及它的全部对象和照片？`))) return
    await withLoading('删除中', () => db.removeItem(item))
    wx.navigateBack()
  },

  addInstance() {
    wx.navigateTo({ url: `/pages/instance-edit/instance-edit?itemId=${this.data.id}` })
  },

  openInstance(e) {
    wx.navigateTo({ url: `/pages/instance-edit/instance-edit?id=${e.currentTarget.dataset.id}` })
  },

  async startUse(e) {
    await withLoading('保存中', () => db.updateInstance(e.currentTarget.dataset.id, { startDate: today() }))
    this.load()
  },

  async finishUse(e) {
    await withLoading('保存中', () => db.updateInstance(e.currentTarget.dataset.id, { endDate: today() }))
    this.load()
  },

  // 一次性订阅：每同意一次，云函数才能发一条提醒，发完需要重新订阅
  subscribe() {
    wx.requestSubscribeMessage({
      tmplIds: [TEMPLATE_ID],
      success: async res => {
        if (res[TEMPLATE_ID] !== 'accept') {
          toast('没有订阅，可以在右上角“设置”里打开通知')
          return
        }
        await withLoading('保存中', () => db.saveItem(this.data.id, { remindSubscribed: true }))
        toast('已订阅，快用完时会通知你', 'success')
        this.load()
      },
      fail: err => {
        console.error(err)
        toast('订阅失败')
      },
    })
  },
})
