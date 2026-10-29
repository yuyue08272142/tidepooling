const db = require('../../utils/db')
const { today } = require('../../utils/predict')
const { toast, confirm, withLoading } = require('../../utils/ui')

Page({
  data: {
    id: '',
    itemId: '',
    note: '',
    startDate: '',
    endDate: '',
    count: '1',
    today: today(),
  },

  async onLoad(options) {
    if (options.id) {
      wx.setNavigationBarTitle({ title: '编辑对象' })
      try {
        const inst = await db.getInstance(options.id)
        this.setData({
          id: inst._id,
          itemId: inst.itemId,
          note: inst.note || '',
          startDate: inst.startDate || '',
          endDate: inst.endDate || '',
        })
      } catch (e) {
        console.error(e)
        toast('加载失败')
      }
    } else {
      wx.setNavigationBarTitle({ title: '添加对象' })
      this.setData({ itemId: options.itemId })
    }
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value })
  },

  onDateChange(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value })
  },

  clearDate(e) {
    const field = e.currentTarget.dataset.field
    // 清掉开始日期时结束日期也没有意义了
    this.setData(field === 'startDate' ? { startDate: '', endDate: '' } : { endDate: '' })
  },

  async save() {
    const { id, itemId, note, startDate, endDate, count } = this.data
    if (endDate && !startDate) return toast('请先选择开始使用日期')
    if (endDate && endDate < startDate) return toast('用完日期不能早于开始日期')
    const data = { note: note.trim(), startDate: startDate || null, endDate: endDate || null }
    if (id) {
      await withLoading('保存中', () => db.updateInstance(id, data))
    } else {
      const n = Math.min(99, Math.max(1, parseInt(count, 10) || 1))
      await withLoading('保存中', () => db.addInstances(itemId, data, n))
    }
    wx.navigateBack()
  },

  async remove() {
    if (!(await confirm('确定删除这个对象？'))) return
    await withLoading('删除中', () => db.removeInstance(this.data.id))
    wx.navigateBack()
  },
})
