// 带“消耗品”标签的物品会做消耗预测和用完提醒
const CONSUMABLE_TAG = '消耗品'

const PRESET_TAGS = [CONSUMABLE_TAG, '食品', '药品', '日用', '电子产品', '衣物', '证件', '贵重']

function isConsumable(item) {
  return Array.isArray(item.tags) && item.tags.includes(CONSUMABLE_TAG)
}

module.exports = { CONSUMABLE_TAG, PRESET_TAGS, isConsumable }
