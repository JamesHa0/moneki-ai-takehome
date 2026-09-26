<script setup>
import { computed } from "vue"
import { formatMoney, formatCount, formatAov } from "../utils/format"

const props = defineProps({
  /** { loading, error, data }，data 为 /api/metrics/summary 的响应。 */
  state: { type: Object, required: true },
})

defineEmits(["retry"])

/** 每张卡直接由接口字段渲染，不在组件里写死值。 */
const cards = computed(() => {
  const data = props.state.data || {}
  return [
    { label: "净营业额", value: formatMoney(data.net_revenue) },
    { label: "退款金额", value: formatMoney(data.refund_amount) },
    { label: "有效订单数", value: formatCount(data.orders) },
    { label: "客单价", value: formatAov(data.aov) },
    { label: "销量", value: formatCount(data.qty) },
  ]
})
</script>

<template>
  <el-card shadow="never" class="metric-cards" v-loading="state.loading">
    <el-alert
      v-if="state.error"
      type="error"
      :closable="false"
      :title="`指标加载失败：${state.error}`"
    >
      <el-button size="small" @click="$emit('retry')">重试</el-button>
    </el-alert>
    <el-row v-else-if="state.data" :gutter="12">
      <el-col v-for="card in cards" :key="card.label" :xs="12" :sm="12" :md="4" :lg="4">
        <div class="metric-card">
          <div class="metric-label">{{ card.label }}</div>
          <div class="metric-value">{{ card.value }}</div>
        </div>
      </el-col>
    </el-row>
    <el-empty v-else-if="!state.loading" description="暂无数据" :image-size="60" />
  </el-card>
</template>

<style scoped>
.metric-cards {
  margin-bottom: 12px;
}
.metric-card {
  padding: 8px 4px;
  text-align: center;
}
.metric-label {
  color: #909399;
  font-size: 13px;
  margin-bottom: 6px;
}
.metric-value {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
</style>
