// 把小程序里的预测逻辑复制到云函数目录（云函数不能引用 miniprogram/ 下的文件）
const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const src = path.join(root, 'miniprogram/utils/predict.js')
const dest = path.join(root, 'cloudfunctions/remind/predict.js')

fs.copyFileSync(src, dest)
console.log(`已同步 ${path.relative(root, src)} → ${path.relative(root, dest)}`)
