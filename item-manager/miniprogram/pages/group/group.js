const db = require('../../utils/db')
const { predict, today } = require('../../utils/predict')
const { isConsumable } = require('../../utils/tags')
const { predictionText, countsText } = require('../../utils/format')
const { toast } = require('../../utils/ui')

Page({
  data: {
    groupId: '',
    loading: true,
    items: [],
    shown: [],
    allTags: [],
    activeTag: '',
  },

  onLoad(options) {
    const name = decodeURIComponent(options.name || '')
    this.setData({ groupId: options.id })
    if (name) wx.setNavigationBarTitle({ title: name })
  },

  onShow() {
    this.load()
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh())
  },

  async load() {
    try {
      const items = await db.listItems(this.data.groupId)
      const byItem = await db.instancesByItem(items.map(i => i._id))
      const t = today()
      const tagSet = new Set()
      const views = items.map(item => {
        const instances = byItem[item._id]
        ;(item.tags || []).forEach(tag => tagSet.add(tag))
        const view = {
          id: item._id,
          name: item.name,
          cover: (item.photos || [])[0] || '',
          tags: item.tags || [],
          counts: countsText(instances),
          consumable: isConsumable(item),
        }
        if (view.consumable) {
          const p = predict(item, instances, t)
          view.state = p.state
          view.predictionText = predictionText(p)
        }
        return view
      })
      this.setData({ loading: false, items: views, allTags: [...tagSet] })
      this.applyFilter()
    } catch (e) {
      console.error(e)
      this.setData({ loading: false })
      toast('加载失败')
    }
  },

  applyFilter() {
    const { items, activeTag } = this.data
    this.setData({ shown: activeTag ? items.filter(i => i.tags.includes(activeTag)) : items })
  },

  toggleTag(e) {
    const tag = e.currentTarget.dataset.tag
    this.setData({ activeTag: this.data.activeTag === tag ? '' : tag })
    this.applyFilter()
  },

  openItem(e) {
    wx.navigateTo({ url: `/pages/item/item?id=${e.currentTarget.dataset.id}` })
  },

  addItem() {
    wx.navigateTo({ url: `/pages/item-edit/item-edit?groupId=${this.data.groupId}` })
  },
})
