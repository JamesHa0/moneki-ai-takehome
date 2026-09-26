<script setup>
defineProps({
  /** [start, end]，初值来自 /api/data_quality 的 data_period，不在代码里写死。 */
  range: { type: Array, default: () => [] },
  storeId: { type: String, default: "" },
  productId: { type: String, default: "" },
  stores: { type: Array, default: () => [] },
  products: { type: Array, default: () => [] },
  /** 日期初值加载完成前为 true，所有控件禁用。 */
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(["update:range", "update:storeId", "update:productId"])

function onRange(value) {
  emit("update:range", Array.isArray(value) ? value : [])
}
function onStore(value) {
  emit("update:storeId", value || "")
}
function onProduct(value) {
  emit("update:productId", value || "")
}
</script>

<template>
  <el-card class="filter-bar" shadow="never">
    <el-form inline @submit.prevent>
      <el-form-item label="日期范围">
        <el-date-picker
          :model-value="range"
          type="daterange"
          value-format="YYYY-MM-DD"
          :clearable="false"
          :disabled="disabled"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          @update:model-value="onRange"
        />
      </el-form-item>
      <el-form-item label="门店">
        <el-select
          :model-value="storeId"
          clearable
          placeholder="全部门店"
          :disabled="disabled"
          class="filter-select"
          @update:model-value="onStore"
        >
          <el-option
            v-for="store in stores"
            :key="store.store_id"
            :label="store.store_name"
            :value="store.store_id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="商品">
        <el-select
          :model-value="productId"
          clearable
          filterable
          placeholder="全部商品"
          :disabled="disabled"
          class="filter-select"
          @update:model-value="onProduct"
        >
          <el-option
            v-for="product in products"
            :key="product.product_id"
            :label="product.product_name"
            :value="product.product_id"
          />
        </el-select>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.filter-bar {
  margin-bottom: 12px;
}
.filter-bar :deep(.el-form-item) {
  margin-bottom: 0;
}
.filter-select {
  width: 200px;
}

@media (max-width: 640px) {
  .filter-bar :deep(.el-form--inline) {
    display: block;
  }
  .filter-bar :deep(.el-form-item) {
    display: block;
    width: 100%;
    margin: 0 0 10px;
  }
  .filter-bar :deep(.el-form-item:last-child) {
    margin-bottom: 0;
  }
  .filter-bar :deep(.el-form-item__label) {
    display: block;
    text-align: left;
  }
  .filter-bar :deep(.el-form-item__content) {
    width: 100%;
    min-width: 0;
  }
  .filter-bar :deep(.el-date-editor) {
    width: 100%;
    min-width: 0;
  }
  .filter-bar :deep(.el-range-input) {
    font-size: 12px;
  }
  .filter-select {
    width: 100%;
  }
}
</style>
