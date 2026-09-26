<script setup>
import { computed } from "vue"
import { formatCount } from "../utils/format"

const props = defineProps({
  /** { loading, error, data }，data 为 /api/data_quality 的响应。 */
  state: { type: Object, required: true },
})

defineEmits(["retry"])

/** 六项剔除计数的规范键；响应里键缺失时显示 0。 */
const REMOVED_KEYS = [
  "1_unparseable_date",
  "2_empty_amount",
  "3_qty_le_zero",
  "4_store_not_in_stores",
  "5_product_not_in_products",
  "6_duplicate_row",
]

const report = computed(() => {
  const data = props.state.data
  return data && data.cleaning_report && typeof data.cleaning_report === "object"
    ? data.cleaning_report
    : null
})

const removedRows = computed(() => {
  const removed = report.value && typeof report.value.removed === "object" && report.value.removed
    ? report.value.removed
    : {}
  const keys = [...REMOVED_KEYS]
  for (const key of Object.keys(removed)) {
    if (!keys.includes(key)) keys.push(key)
  }
  return keys.map((key) => ({ key, count: Number(removed[key]) || 0 }))
})

const warnings = computed(() => {
  const data = props.state.data
  return data && Array.isArray(data.kb_warnings) ? data.kb_warnings : []
})

const period = computed(() => {
  const data = props.state.data
  return data && data.data_period && typeof data.data_period === "object" ? data.data_period : null
})
</script>

<template>
  <el-card shadow="never" class="data-quality" v-loading="state.loading">
    <template #header>数据质量</template>
    <el-alert
      v-if="state.error"
      type="error"
      :closable="false"
      :title="`数据质量加载失败：${state.error}`"
    >
      <el-button size="small" @click="$emit('retry')">重试</el-button>
    </el-alert>
    <template v-else-if="report">
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="原始行数">{{ formatCount(report.raw_rows) }}</el-descriptions-item>
        <el-descriptions-item label="保留行数">{{ formatCount(report.kept_rows) }}</el-descriptions-item>
        <el-descriptions-item label="数据区间">
          <span v-if="period">{{ period.start }} ~ {{ period.end }}</span>
          <span v-else>—</span>
        </el-descriptions-item>
      </el-descriptions>
      <div class="removed">
        <div class="sub-title">清洗剔除明细</div>
        <el-row :gutter="8">
          <el-col v-for="row in removedRows" :key="row.key" :xs="12" :sm="8" :md="4">
            <div class="removed-item">
              <div class="removed-count">{{ formatCount(row.count) }}</div>
              <div class="removed-key">{{ row.key }}</div>
            </div>
          </el-col>
        </el-row>
      </div>
      <div class="warnings">
        <div class="sub-title">知识库警告</div>
        <template v-if="warnings.length">
          <el-alert
            v-for="(warning, index) in warnings"
            :key="index"
            type="warning"
            :closable="false"
            :title="String(warning)"
            class="warning-item"
          />
        </template>
        <span v-else class="no-warning">无警告</span>
      </div>
    </template>
    <el-empty v-else-if="!state.loading" description="暂无数据" :image-size="60" />
  </el-card>
</template>

<style scoped>
.data-quality {
  margin-bottom: 12px;
}
.sub-title {
  font-size: 13px;
  color: #909399;
  margin: 12px 0 8px;
}
.removed-item {
  text-align: center;
  padding: 6px 0;
}
.removed-count {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
.removed-key {
  font-size: 12px;
  color: #909399;
  word-break: break-all;
}
.warning-item {
  margin-bottom: 6px;
}
.no-warning {
  color: #67c23a;
  font-size: 13px;
}
</style>
