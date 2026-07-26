export const FALLBACK_NOTICE = '当前图片由备用模型生成，效果可能与所选模型不同。如有问题，请联系管理员查看原因。'

export function fallbackNotice(item) {
  if (!item?.degraded && !(item?.degraded_count > 0)) return ''
  return FALLBACK_NOTICE
}

export function countDegradedItems(items) {
  return (items || []).filter(item => item?.degraded).length
}
