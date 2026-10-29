const db = require('../../utils/db')
const { predictionText } = require('../../utils/format')
const { toast, confirm, prompt, withLoading } = require('../../utils/ui')

Page({
  data: {
    loading: true,
    groups: [],
    reminders: [],
  },

  onShow() {
    this.load()
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh())
  },

  async load() {
    try {
      const [groups, reminders] = await Promise.all([db.listGroups(), db.listReminders()])
      this.setData({
        loading: false,
        groups,
        reminders: reminders.map(({ item, prediction }) => ({
          id: item._id,
          name: item.name,
          cover: (item.photos || [])[0] || '',
          state: prediction.state,
          text: predictionText(prediction),
        })),
      })
    } catch (e) {
      console.error(e)
      this.setData({ loading: false })
      toast('加载失败，请检查云开发环境')
    }
  },

  openGroup(e) {
    const { id, name } = e.currentTarget.dataset
    wx.navigateTo({ url: `/pages/group/group?id=${id}&name=${encodeURIComponent(name)}` })
  },

  openItem(e) {
    wx.navigateTo({ url: `/pages/item/item?id=${e.currentTarget.dataset.id}` })
  },

  async addGroup() {
    const name = await prompt('新建分组', '', '例如：厨房、卫生间、书房')
    if (!name) return
    await withLoading('保存中', () => db.addGroup(name))
    this.load()
  },

  groupActions(e) {
    const { id, name } = e.currentTarget.dataset
    wx.showActionSheet({
      itemList: ['重命名', '删除'],
      success: async ({ tapIndex }) => {
        if (tapIndex === 0) {
          const newName = await prompt('重命名分组', name)
          if (!newName || newName === name) return
          await withLoading('保存中', () => db.renameGroup(id, newName))
        } else {
          if (!(await confirm(`确定删除分组“${name}”？`))) return
          await withLoading('删除中', () => db.removeGroup(id))
        }
        this.load()
      },
    })
  },
})
