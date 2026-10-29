const db = require('../../utils/db')
const { CONSUMABLE_TAG, PRESET_TAGS } = require('../../utils/tags')
const { DEFAULT_REMIND_DAYS } = require('../../utils/predict')
const { toast, withLoading } = require('../../utils/ui')

const MAX_PHOTOS = 9

Page({
  data: {
    id: '',
    groups: [],
    groupIndex: -1,
    name: '',
    photos: [],
    tags: [],
    tagOptions: PRESET_TAGS.map(name => ({ name, active: false })),
    customTag: '',
    note: '',
    defaultDays: '',
    remindDaysBefore: String(DEFAULT_REMIND_DAYS),
    consumable: false,
    maxPhotos: MAX_PHOTOS,
  },

  async onLoad(options) {
    // 本次新上传、还没保存的照片，放弃编辑时要删掉；已保存过、本次被移除的照片，保存后再删
    this.uploaded = []
    this.removed = []
    this.saved = false
    wx.setNavigationBarTitle({ title: options.id ? '编辑物品' : '添加物品' })
    try {
      const groups = await db.listGroups()
      let groupId = options.groupId
      if (options.id) {
        const item = await db.getItem(options.id)
        groupId = item.groupId
        this.setData({
          id: options.id,
          name: item.name,
          photos: item.photos || [],
          tags: item.tags || [],
          note: item.note || '',
          defaultDays: item.defaultDays ? String(item.defaultDays) : '',
          remindDaysBefore: item.remindDaysBefore === undefined ? String(DEFAULT_REMIND_DAYS) : String(item.remindDaysBefore),
        })
      }
      this.setData({ groups, groupIndex: groups.findIndex(g => g._id === groupId) })
      this.refreshTags()
    } catch (e) {
      console.error(e)
      toast('加载失败')
    }
  },

  onUnload() {
    if (!this.saved && this.uploaded.length) {
      wx.cloud.deleteFile({ fileList: this.uploaded }).catch(() => {})
    }
  },

  onInput(e) {
    this.setData({ [e.currentTarget.dataset.field]: e.detail.value })
  },

  onGroupChange(e) {
    this.setData({ groupIndex: Number(e.detail.value) })
  },

  // ---------- 照片 ----------

  choosePhoto() {
    wx.chooseMedia({
      count: MAX_PHOTOS - this.data.photos.length,
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: async ({ tempFiles }) => {
        const fileIDs = await withLoading('上传中', () => Promise.all(tempFiles.map(f => upload(f.tempFilePath))))
        this.uploaded.push(...fileIDs)
        this.setData({ photos: [...this.data.photos, ...fileIDs] })
      },
    })
  },

  previewPhoto(e) {
    wx.previewImage({ urls: this.data.photos, current: e.currentTarget.dataset.src })
  },

  removePhoto(e) {
    const src = e.currentTarget.dataset.src
    if (this.uploaded.includes(src)) {
      this.uploaded = this.uploaded.filter(f => f !== src)
      wx.cloud.deleteFile({ fileList: [src] }).catch(() => {})
    } else {
      this.removed.push(src)
    }
    this.setData({ photos: this.data.photos.filter(f => f !== src) })
  },

  // ---------- 标签 ----------

  refreshTags() {
    const { tags } = this.data
    const options = [...PRESET_TAGS, ...tags.filter(t => !PRESET_TAGS.includes(t))]
    this.setData({
      tagOptions: options.map(name => ({ name, active: tags.includes(name) })),
      consumable: tags.includes(CONSUMABLE_TAG),
    })
  },

  toggleTag(e) {
    const tag = e.currentTarget.dataset.tag
    const { tags } = this.data
    this.setData({ tags: tags.includes(tag) ? tags.filter(t => t !== tag) : [...tags, tag] })
    this.refreshTags()
  },

  addCustomTag() {
    const tag = this.data.customTag.trim()
    if (!tag) return
    if (!this.data.tags.includes(tag)) this.setData({ tags: [...this.data.tags, tag] })
    this.setData({ customTag: '' })
    this.refreshTags()
  },

  // ---------- 保存 ----------

  async save() {
    const { id, name, groups, groupIndex, photos, tags, note, defaultDays, remindDaysBefore } = this.data
    if (!name.trim()) return toast('请填写名称')
    if (groupIndex < 0) return toast('请选择分组')
    const data = {
      name: name.trim(),
      groupId: groups[groupIndex]._id,
      photos,
      tags,
      note: note.trim(),
      defaultDays: Number(defaultDays) > 0 ? Number(defaultDays) : null,
      remindDaysBefore: Number(remindDaysBefore) >= 0 && remindDaysBefore !== '' ? Number(remindDaysBefore) : DEFAULT_REMIND_DAYS,
    }
    const newId = await withLoading('保存中', () => db.saveItem(id, data))
    this.saved = true
    if (this.removed.length) wx.cloud.deleteFile({ fileList: this.removed }).catch(() => {})
    if (id) {
      wx.navigateBack()
    } else {
      wx.redirectTo({ url: `/pages/item/item?id=${newId}` })
    }
  },
})

async function upload(path) {
  const ext = (path.match(/\.\w+$/) || ['.jpg'])[0]
  const cloudPath = `items/${Date.now()}-${Math.random().toString(36).slice(2, 8)}${ext}`
  const { fileID } = await wx.cloud.uploadFile({ cloudPath, filePath: path })
  return fileID
}
