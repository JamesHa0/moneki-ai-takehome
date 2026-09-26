<script setup>
import { ref } from "vue"
import { useChat } from "../composables/useChat"
import { inlineSummary, prettyJson } from "../utils/format"
import TraceDrawer from "./TraceDrawer.vue"

const props = defineProps({
  /** 来自 /api/health 的 llm_mode；"mock" 时顶部显示降级提示。 */
  llmMode: { type: String, default: "" },
})

const { messages, sending, send, retry } = useChat()

const draft = ref("")
const traceVisible = ref(false)
const activeTraceId = ref("")

function submit() {
  const text = draft.value.trim()
  if (!text || sending.value) return
  draft.value = ""
  send(text)
}

function openTrace(traceId) {
  activeTraceId.value = traceId
  traceVisible.value = true
}

function paramsSummary(params) {
  return inlineSummary(params)
}

function hasResult(ev) {
  return ev && ev.result !== undefined && ev.result !== null
}
</script>

<template>
  <el-card shadow="never" class="chat-panel">
    <template #header>经营问答</template>

    <el-alert
      v-if="llmMode === 'mock'"
      type="warning"
      :closable="false"
      title="当前为降级模式（未配置大模型），回答由模板生成。"
      class="mock-tip"
    />

    <div class="messages">
      <el-empty v-if="!messages.length && !sending" description="试着问：S03 六月第二周营业额为什么低" :image-size="60" />
      <div v-for="(message, index) in messages" :key="index" :class="['msg', message.role]">
        <div class="msg-body">
          <p class="msg-text">{{ message.content }}</p>

          <div v-if="message.error" class="msg-error">
            <el-button size="small" type="primary" :disabled="sending" @click="retry(message)">
              重新发送
            </el-button>
          </div>

          <template v-if="message.citations && message.citations.length">
            <div class="sub-title">引用</div>
            <div v-for="(citation, i) in message.citations" :key="i" class="citation">
              <el-tag size="small">{{ citation.doc_id }}</el-tag>
              <span class="quote">{{ citation.quote }}</span>
            </div>
          </template>

          <template v-if="message.dataEvidence && message.dataEvidence.length">
            <div class="sub-title">数据依据</div>
            <div v-for="(ev, i) in message.dataEvidence" :key="i" class="evidence">
              <el-tag size="small" type="success">{{ ev.tool }}</el-tag>
              <span class="params">{{ paramsSummary(ev.params) }}</span>
              <details v-if="hasResult(ev)" class="result-block">
                <summary>查看结果</summary>
                <pre>{{ prettyJson(ev.result) }}</pre>
              </details>
            </div>
          </template>

          <el-button
            v-if="message.traceId"
            size="small"
            text
            type="primary"
            class="trace-link"
            @click="openTrace(message.traceId)"
          >
            查看处理过程
          </el-button>
        </div>
      </div>
      <div v-if="sending" class="msg assistant">
        <div class="msg-body thinking">思考中…</div>
      </div>
    </div>

    <div class="input-row">
      <el-input
        v-model="draft"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="输入经营问题，Enter 发送"
        :disabled="sending"
        @keydown.enter.exact.prevent="submit"
      />
      <el-button
        type="primary"
        :loading="sending"
        :disabled="sending || !draft.trim()"
        @click="submit"
      >
        发送
      </el-button>
    </div>

    <trace-drawer v-model="traceVisible" :trace-id="activeTraceId" :llm-mode="llmMode" />
  </el-card>
</template>

<style scoped>
.chat-panel {
  margin-bottom: 12px;
}
.mock-tip {
  margin-bottom: 10px;
}
.messages {
  max-height: 480px;
  overflow-y: auto;
  margin-bottom: 12px;
}
.msg {
  display: flex;
  margin-bottom: 10px;
}
.msg.user {
  justify-content: flex-end;
}
.msg-body {
  max-width: 82%;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f4f4f5;
  font-size: 14px;
  line-height: 1.7;
}
.msg.user .msg-body {
  background: #ecf5ff;
}
.msg-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-error {
  margin-top: 8px;
}
.thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
}
.sub-title {
  font-size: 12px;
  color: #909399;
  margin: 10px 0 4px;
}
.citation {
  display: flex;
  gap: 6px;
  align-items: baseline;
  margin-bottom: 4px;
}
.quote {
  font-size: 13px;
  color: #606266;
}
.evidence {
  margin-bottom: 6px;
  font-size: 13px;
}
.params {
  margin-left: 6px;
  color: #606266;
  font-size: 12px;
  word-break: break-all;
}
.result-block {
  margin-top: 4px;
}
.result-block summary {
  cursor: pointer;
  color: #409eff;
  font-size: 12px;
}
.result-block pre {
  background: #fff;
  border: 1px solid #ebeef5;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow-y: auto;
}
.trace-link {
  margin-top: 6px;
  padding: 0;
}
.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.input-row :deep(.el-textarea) {
  flex: 1;
}
</style>
