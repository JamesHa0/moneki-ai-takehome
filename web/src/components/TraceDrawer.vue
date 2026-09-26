<script setup>
import { computed, ref, watch } from "vue"
import { getTrace } from "../api"
import { formatMs, inlineSummary, prettyJson } from "../utils/format"

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  traceId: { type: String, default: "" },
  /** 来自 /api/health 的 llm_mode，用于模型调用为空时区分空态文案。 */
  llmMode: { type: String, default: "" },
})

const emit = defineEmits(["update:modelValue"])

const loading = ref(false)
const error = ref("")
const trace = ref(null)

async function load() {
  if (!props.traceId) return
  loading.value = true
  error.value = ""
  trace.value = null
  try {
    const payload = await getTrace(props.traceId)
    trace.value = payload && typeof payload === "object" ? payload : null
  } catch (err) {
    error.value = err && err.message ? err.message : "加载失败"
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.modelValue, props.traceId],
  ([visible]) => {
    if (visible) load()
  },
)

function close(value) {
  emit("update:modelValue", value)
}

/* ── 防御式解析：任何字段缺失、类型不符、空数组都不许抛异常 ── */

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null
}
function asArray(value) {
  return Array.isArray(value) ? value : []
}

const steps = computed(() => asArray(trace.value && trace.value.steps).filter((s) => asObject(s)))
const llmCalls = computed(() => asArray(trace.value && trace.value.llm_calls).filter((c) => asObject(c)))
const errors = computed(() => asArray(trace.value && trace.value.errors).filter((e) => asObject(e)))

const llmEmptyText = computed(() =>
  props.llmMode === "mock" ? "当前为降级模式，无模型调用记录" : "本次未产生模型调用",
)

/** 检索类步骤的已知字段（doc_id / chunk_id / score / 过滤原因），在 detail 或步骤本体上找。 */
function retrievalFields(step) {
  const detail = asObject(step.detail) || {}
  const merged = { ...detail, ...pickKnown(step) }
  const fields = []
  if (merged.doc_id) fields.push(["doc_id", merged.doc_id])
  if (merged.chunk_id) fields.push(["chunk_id", merged.chunk_id])
  if (typeof merged.score === "number") fields.push(["score", merged.score])
  const reason = merged.filter_reason || merged.filtered_reason || merged.drop_reason
  if (reason) fields.push(["过滤原因", reason])
  return fields
}

function pickKnown(obj) {
  const out = {}
  for (const key of ["doc_id", "chunk_id", "score", "filter_reason", "filtered_reason", "drop_reason"]) {
    if (obj && obj[key] !== undefined) out[key] = obj[key]
  }
  return out
}

/** 工具步骤的已知字段（工具名 / 参数 / 结果摘要 / 错误）。 */
function toolFields(step) {
  const detail = asObject(step.detail) || {}
  const merged = { ...detail, ...pickTool(step) }
  const fields = []
  const name = merged.tool || merged.tool_name || merged.name
  if (name && step.step !== name) fields.push(["工具", name])
  if (merged.params !== undefined) fields.push(["参数", inlineSummary(merged.params)])
  if (merged.result !== undefined) fields.push(["结果摘要", summarize(merged.result)])
  if (merged.error) fields.push(["错误", typeof merged.error === "string" ? merged.error : inlineSummary(merged.error)])
  return fields
}

function pickTool(obj) {
  const out = {}
  for (const key of ["tool", "tool_name", "params", "result", "error"]) {
    if (obj && obj[key] !== undefined) out[key] = obj[key]
  }
  return out
}

function summarize(result) {
  const text = inlineSummary(result)
  return text.length > 200 ? `${text.slice(0, 200)}…` : text
}

function stepName(step, index) {
  return step.step || step.name || `step ${index + 1}`
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="处理过程"
    size="680px"
    destroy-on-close
    @update:model-value="close"
  >
    <div v-if="loading" class="state">加载中…</div>
    <div v-else-if="error" class="state">
      <el-alert type="error" :closable="false" :title="`trace 加载失败：${error}`" />
      <el-button size="small" class="retry" @click="load">重试</el-button>
    </div>
    <template v-else-if="trace">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="trace_id">{{ trace.trace_id || "—" }}</el-descriptions-item>
        <el-descriptions-item label="总耗时">{{ formatMs(trace.total_ms) }}</el-descriptions-item>
        <el-descriptions-item label="session_id">{{ trace.session_id || "—" }}</el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ trace.started_at || "—" }}</el-descriptions-item>
        <el-descriptions-item label="问题" :span="2">{{ trace.question || "—" }}</el-descriptions-item>
      </el-descriptions>

      <h3>步骤</h3>
      <el-empty v-if="!steps.length" description="无步骤记录" :image-size="60" />
      <div v-for="(step, index) in steps" :key="index" class="step">
        <div class="step-head">
          <el-tag size="small">{{ stepName(step, index) }}</el-tag>
          <span class="step-ms">开始 {{ formatMs(step.at_ms) }} · 耗时 {{ formatMs(step.took_ms) }}</span>
        </div>
        <div v-if="retrievalFields(step).length" class="kv">
          <div v-for="[label, value] in retrievalFields(step)" :key="label" class="kv-row">
            <span class="kv-label">{{ label }}</span><span>{{ value }}</span>
          </div>
        </div>
        <div v-if="toolFields(step).length" class="kv">
          <div v-for="[label, value] in toolFields(step)" :key="label" class="kv-row">
            <span class="kv-label">{{ label }}</span><span class="kv-value">{{ value }}</span>
          </div>
        </div>
        <details v-if="asObject(step.detail)" class="json-block">
          <summary>detail</summary>
          <pre>{{ prettyJson(step.detail) }}</pre>
        </details>
      </div>

      <h3>模型调用</h3>
      <el-empty v-if="!llmCalls.length" :description="llmEmptyText" :image-size="60" />
      <el-collapse v-else>
        <el-collapse-item
          v-for="(call, index) in llmCalls"
          :key="index"
          :title="`调用 ${index + 1} · finish_reason: ${call.finish_reason || '—'} · ${formatMs(call.took_ms)}`"
        >
          <h4>prompt</h4>
          <pre class="wrap">{{ call.prompt || "（空）" }}</pre>
          <h4>raw_reasoning</h4>
          <pre class="wrap">{{ call.raw_reasoning || "（无）" }}</pre>
          <h4>raw_content</h4>
          <pre class="wrap">{{ call.raw_content || "（空）" }}</pre>
          <h4>usage</h4>
          <pre>{{ prettyJson(call.usage) || "（无）" }}</pre>
        </el-collapse-item>
      </el-collapse>

      <h3>错误</h3>
      <el-empty v-if="!errors.length" description="无错误" :image-size="60" />
      <div v-for="(item, index) in errors" :key="index" class="error-item">
        <el-alert
          type="error"
          :closable="false"
          :title="`${item.where || '未知位置'} · ${item.type || 'Error'}：${item.message || ''}`"
        />
        <details v-if="item.traceback" class="json-block">
          <summary>traceback</summary>
          <pre>{{ item.traceback }}</pre>
        </details>
      </div>
    </template>
    <el-empty v-else description="无 trace 数据" :image-size="60" />
  </el-drawer>
</template>

<style scoped>
.state {
  padding: 16px 0;
}
.retry {
  margin-top: 8px;
}
h3 {
  margin: 20px 0 10px;
  font-size: 14px;
  color: #303133;
}
h4 {
  margin: 10px 0 4px;
  font-size: 13px;
  color: #606266;
}
.step {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.step-ms {
  color: #909399;
  font-size: 12px;
}
.kv {
  margin-top: 6px;
}
.kv-row {
  font-size: 12px;
  line-height: 1.8;
}
.kv-label {
  display: inline-block;
  min-width: 64px;
  color: #909399;
}
.kv-value {
  word-break: break-all;
}
.json-block {
  margin-top: 6px;
}
.json-block summary {
  cursor: pointer;
  color: #409eff;
  font-size: 12px;
}
pre {
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.wrap {
  white-space: pre-wrap;
}
.error-item {
  margin-bottom: 10px;
}
</style>
