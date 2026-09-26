import { ref } from "vue"
import { postChat } from "../api"

/** 会话 ID：优先 crypto.randomUUID()，旧环境降级为时间戳 + 随机串。 */
function createSessionId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

/**
 * 对话状态：消息列表 + 唯一 session_id + 发送中标记。
 * 发送期间禁止重复提交；失败的消息带 retryQuestion，提供重新发送入口。
 */
export function useChat() {
  const sessionId = createSessionId()
  const messages = ref([])
  const sending = ref(false)

  async function send(question, { echo = true } = {}) {
    const text = String(question || "").trim()
    if (!text || sending.value) return
    if (echo) messages.value.push({ role: "user", content: text })
    sending.value = true
    try {
      const resp = await postChat({ session_id: sessionId, question: text })
      messages.value.push({
        role: "assistant",
        content: resp && typeof resp.answer === "string" ? resp.answer : "",
        answerType: resp && resp.answer_type ? resp.answer_type : "",
        citations: resp && Array.isArray(resp.citations) ? resp.citations : [],
        dataEvidence: resp && Array.isArray(resp.data_evidence) ? resp.data_evidence : [],
        traceId: resp && resp.trace_id ? resp.trace_id : "",
      })
    } catch (err) {
      messages.value.push({
        role: "assistant",
        error: true,
        content: err && err.message ? err.message : "请求失败",
        retryQuestion: text,
        citations: [],
        dataEvidence: [],
        traceId: "",
      })
    } finally {
      sending.value = false
    }
  }

  /** 重新发送失败的那条问题：移除失败消息，复用原用户气泡（不再重复上屏）。 */
  function retry(message) {
    const index = messages.value.indexOf(message)
    const question = message && message.retryQuestion
    if (index >= 0) messages.value.splice(index, 1)
    if (question) send(question, { echo: false })
  }

  return { sessionId, messages, sending, send, retry }
}
