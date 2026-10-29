// 测试用：内存版云数据库 + 最小的 wx / Page 全局对象，让 utils/db.js 和页面逻辑能在 node 里跑

const path = require('path')

const CLIENT_LIMIT = 20

function createDatabase({ limit = CLIENT_LIMIT, openid = 'user1' } = {}) {
  const store = {}
  let seq = 0
  const serverDate = () => ({ $serverDate: true })
  const command = { in: values => ({ $in: values }) }

  function matches(doc, cond) {
    return Object.entries(cond).every(([key, expected]) => {
      const actual = doc[key]
      if (expected && expected.$in) return expected.$in.includes(actual)
      if (Array.isArray(actual)) return actual.includes(expected)
      return actual === expected
    })
  }

  function query(name, state = {}) {
    const rows = () => {
      let list = (store[name] || []).filter(d => matches(d, state.where || {}))
      if (state.orderBy) {
        const [field, dir] = state.orderBy
        list = [...list].sort((a, b) => (a[field] < b[field] ? -1 : a[field] > b[field] ? 1 : 0) * (dir === 'desc' ? -1 : 1))
      }
      return list
    }
    return {
      where: cond => query(name, { ...state, where: cond }),
      orderBy: (field, dir) => query(name, { ...state, orderBy: [field, dir] }),
      skip: n => query(name, { ...state, skip: n }),
      limit: n => query(name, { ...state, limit: Math.min(n, limit) }),
      async get() {
        const start = state.skip || 0
        return { data: clone(rows().slice(start, start + (state.limit || limit))) }
      },
      async count() {
        return { total: rows().length }
      },
    }
  }

  function resolve(data) {
    const out = {}
    for (const [k, v] of Object.entries(data)) out[k] = v && v.$serverDate ? ++seq : v
    return out
  }

  return {
    store,
    serverDate,
    command,
    collection(name) {
      store[name] = store[name] || []
      return {
        ...query(name),
        async add({ data }) {
          const _id = `${name}-${++seq}`
          store[name].push({ _id, _openid: openid, ...resolve(data) })
          return { _id }
        },
        doc(id) {
          const find = () => store[name].find(d => d._id === id)
          return {
            async get() {
              const doc = find()
              if (!doc) throw new Error(`document ${id} not found`)
              return { data: clone(doc) }
            },
            async update({ data }) {
              Object.assign(find(), resolve(data))
              return { stats: { updated: 1 } }
            },
            async remove() {
              store[name] = store[name].filter(d => d._id !== id)
              return { stats: { removed: 1 } }
            },
          }
        },
      }
    },
  }
}

function clone(v) {
  return JSON.parse(JSON.stringify(v))
}

// 装好 wx / Page 全局对象，返回调用记录
function installWx(database) {
  const calls = { navigateTo: [], navigateBack: 0, redirectTo: [], toast: [], deleteFile: [] }
  global.wx = {
    cloud: {
      database: () => database,
      deleteFile: async ({ fileList }) => { calls.deleteFile.push(...fileList) },
      uploadFile: async ({ cloudPath }) => ({ fileID: `cloud://env/${cloudPath}` }),
    },
    showLoading() {},
    hideLoading() {},
    showToast: ({ title }) => calls.toast.push(title),
    showModal: ({ success }) => success({ confirm: true }),
    setNavigationBarTitle() {},
    navigateTo: ({ url }) => calls.navigateTo.push(url),
    navigateBack: () => { calls.navigateBack += 1 },
    redirectTo: ({ url }) => calls.redirectTo.push(url),
    stopPullDownRefresh() {},
  }
  return calls
}

// 加载一个页面，返回一个可以直接调用方法的页面实例
function loadPage(name) {
  const file = path.join(__dirname, '../../miniprogram/pages', name, `${name}.js`)
  delete require.cache[require.resolve(file)]
  let def
  global.Page = d => { def = d }
  require(file)
  const page = Object.create(def)
  page.data = clone(def.data)
  page.setData = function (patch) {
    for (const [k, v] of Object.entries(patch)) this.data[k] = v
  }
  return page
}

module.exports = { createDatabase, installWx, loadPage }
