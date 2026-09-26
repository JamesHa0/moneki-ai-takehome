/**
 * 请求层：只做 transport。
 * - 全部走同源相对路径，不配置后端 base URL。
 * - 统一解析 JSON；非 2xx 抛 ApiError（保留 status / payload / message）。
 * - 不设置超时：fetch 默认无超时，正好覆盖 /api/chat 契约规定的 180 秒预算。
 * - AbortController 只用于筛选切换或组件卸载时取消过期请求，不拿来冒充业务超时。
 */

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.payload = payload
  }
}

async function request(path, { method = "GET", body, signal } = {}) {
  let resp
  try {
    resp = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (err) {
    if (err && err.name === "AbortError") throw err
    throw new ApiError(err && err.message ? err.message : "网络请求失败", 0, null)
  }
  const text = await resp.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }
  if (!resp.ok) {
    let message = payload && (payload.error || payload.detail)
    if (message && typeof message !== "string") message = JSON.stringify(message)
    throw new ApiError(message || `请求失败（HTTP ${resp.status}）`, resp.status, payload)
  }
  return payload
}

function withQuery(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ""
}

export function getStores(options = {}) {
  return request("/api/stores", options)
}

export function getProducts(options = {}) {
  return request("/api/products", options)
}

export function getHealth(options = {}) {
  return request("/api/health", options)
}

export function getDataQuality(options = {}) {
  return request("/api/data_quality", options)
}

export function getSummary(params, options = {}) {
  return request(`/api/metrics/summary${withQuery(params)}`, options)
}

export function getDaily(params, options = {}) {
  return request(`/api/metrics/daily${withQuery(params)}`, options)
}

export function getTopProducts(params, options = {}) {
  return request(`/api/top_products${withQuery(params)}`, options)
}

export function postChat(body, options = {}) {
  return request("/api/chat", { ...options, method: "POST", body })
}

export function getTrace(traceId, options = {}) {
  return request(`/api/trace/${encodeURIComponent(traceId)}`, options)
}
