// 常用的弹窗封装

function toast(title, icon = 'none') {
  wx.showToast({ title, icon })
}

function confirm(content, title = '提示') {
  return new Promise(resolve => {
    wx.showModal({ title, content, success: res => resolve(res.confirm), fail: () => resolve(false) })
  })
}

// 带输入框的弹窗，取消返回 null
function prompt(title, value = '', placeholderText = '') {
  return new Promise(resolve => {
    wx.showModal({
      title,
      editable: true,
      content: value,
      placeholderText,
      success: res => resolve(res.confirm ? (res.content || '').trim() : null),
      fail: () => resolve(null),
    })
  })
}

// 包一层 loading，出错时提示错误信息并继续抛出（中断后续操作）
async function withLoading(title, fn) {
  wx.showLoading({ title, mask: true })
  let result
  try {
    result = await fn()
  } catch (e) {
    console.error(e)
    wx.hideLoading()
    toast(e.message || e.errMsg || '出错了')
    throw e
  }
  wx.hideLoading()
  return result
}

module.exports = { toast, confirm, prompt, withLoading }
