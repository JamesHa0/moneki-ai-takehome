<script setup>
import { computed } from "vue"
import { formatMoney, formatCount } from "../utils/format"

const props = defineProps({
  /** { loading, error, data }，data 为 /api/top_products 的响应。 */
  state: { type: Object, required: true },
})

defineEmits(["retry"])

const rows = computed(() => {
  const data = props.state.data
  return data && Array.isArray(data.products) ? data.products : []
})
</script>

<template>
  <el-card shadow="never" class="top-products" v-loading="state.loading">
    <template #header>
      <div class="header">
        <span>商品 Top10</span>
        <span class="note">按当前日期与门店统计的商品 Top10，不受商品筛选影响</span>
      </div>
    </template>
    <el-alert
      v-if="state.error"
      type="error"
      :closable="false"
      :title="`Top10 加载失败：${state.error}`"
    >
      <el-button size="small" @click="$emit('retry')">重试</el-button>
    </el-alert>
    <template v-else>
      <el-table v-if="rows.length" :data="rows" size="small">
        <el-table-column prop="product_name" label="商品名" min-width="180" />
        <el-table-column label="净营业额" width="140" align="right">
          <template #default="{ row }">{{ formatMoney(row.net_revenue) }}</template>
        </el-table-column>
        <el-table-column label="销量" width="100" align="right">
          <template #default="{ row }">{{ formatCount(row.qty) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="!state.loading" description="区间内无商品数据" :image-size="60" />
    </template>
  </el-card>
</template>

<style scoped>
.top-products {
  margin-bottom: 12px;
}
.header {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.note {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}
</style>
