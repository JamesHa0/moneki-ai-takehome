/** 展示层格式化工具；api.js 里不允许混入这些逻辑。 */

export function isBlank(value) {
  return value === null || value === undefined || Number.isNaN(Number(value))
}

/** 金额：¥1,234.56；null / 非法值显示「无数据」（不允许出现 NaN）。 */
export function formatMoney(value) {
  if (isBlank(value)) return "无数据"
  return `¥${Number(value).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** 整数计数：12,345；null / 非法值显示「无数据」。 */
export function formatCount(value) {
  if (isBlank(value)) return "无数据"
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 0 })
}

/** 客单价：为 null 时显示「无数据」。 */
export function formatAov(value) {
  return formatMoney(value)
}

/** 耗时毫秒：1234.5 -> "1234.5 ms"；null -> "—"。 */
export function formatMs(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—"
  return `${Number(value).toFixed(1)} ms`
}

/** 对象的紧凑单行摘要（用于 params 这类小对象）。 */
export function inlineSummary(value) {
  if (value === null || value === undefined) return ""
  if (typeof value !== "object") return String(value)
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

/** 对象的多行格式化（用于折叠区域）。 */
export function prettyJson(value) {
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
