<script setup>
import { onMounted, reactive, ref, watch } from "vue"
import FilterBar from "./components/FilterBar.vue"
import MetricCards from "./components/MetricCards.vue"
import TrendChart from "./components/TrendChart.vue"
import TopProducts from "./components/TopProducts.vue"
import DataQuality from "./components/DataQuality.vue"
import ChatPanel from "./components/ChatPanel.vue"
import {
  getDataQuality,
  getHealth,
  getStores,
  getProducts,
  getSummary,
  getDaily,
  getTopProducts,
} from "./api"

/* ── 筛选条件：日期初值来自 /api/data_quality 的 data_period，不写死 ── */
const filters = reactive({ range: [], storeId: "", productId: "" })

/** 日期初值加载完成前为 false：禁用筛选控件，且不允许发出其他业务请求。 */
const ready = ref(false)
const basicsError = ref("")

const llmMode = ref("")
const stores = ref([])
const products = ref([])
const optionsError = ref("")

/* ── 每个数据块独立的 loading / error / data：一块失败不清空其他块 ── */
const summary = reactive({ loading: false, error: "", data: null })
const daily = reactive({ loading: false, error: "", data: null })
const topProducts = reactive({ loading: false, error: "", data: null })
const dataQuality = reactive({ loading: false, error: "", data: null })

/* 递增 request id：快速连续切换筛选时，旧响应不得覆盖新响应 */
const reqIds = { summary: 0, daily: 0, top: 0 }

async function loadBlock(state, key, fetcher) {
  const id = ++reqIds[key]
  state.loading = true
  state.error = ""
  try {
    const data = await fetcher()
    if (id === reqIds[key]) state.data = data
  } catch (err) {
    if (err && err.name === "AbortError") return
    if (id === reqIds[key]) state.error = err && err.message ? err.message : "加载失败"
  } finally {
    if (id === reqIds[key]) state.loading = false
  }
}

function baseParams() {
  const [start, end] = filters.range || []
  return { start, end, store_id: filters.storeId || undefined }
}

function loadSummary() {
  if (!ready.value) return
  loadBlock(summary, "summary", () =>
    getSummary({ ...baseParams(), product_id: filters.productId || undefined }),
  )
}

function loadDaily() {
  if (!ready.value) return
  loadBlock(daily, "daily", () =>
    getDaily({ ...baseParams(), product_id: filters.productId || undefined }),
  )
}

/** Top10 只随日期与门店变化；不接收 product_id，商品筛选变化时不重新请求。 */
function loadTopProducts() {
  if (!ready.value) return
  loadBlock(topProducts, "top", () => getTopProducts(baseParams()))
}

/* ── 初始化：data_quality 是硬依赖（提供日期初值），失败则全局可重试、控件禁用 ── */
async function init() {
  basicsError.value = ""
  optionsError.value = ""
  dataQuality.loading = true
  dataQuality.error = ""
  try {
    const dq = await getDataQuality()
    dataQuality.data = dq
    const period = dq && dq.data_period
    if (period && period.start && period.end) {
      filters.range = [period.start, period.end]
      ready.value = true
    } else {
      basicsError.value = "数据区间为空，无法初始化筛选"
      ready.value = false
    }
  } catch (err) {
    const message = err && err.message ? err.message : "加载失败"
    basicsError.value = message
    dataQuality.error = message
    ready.value = false
  } finally {
    dataQuality.loading = false
  }

  // health / stores / products 是独立块，各自失败不影响主流程
  getHealth()
    .then((health) => {
      llmMode.value = health && health.llm_mode ? health.llm_mode : ""
    })
    .catch(() => {})
  Promise.all([getStores(), getProducts()])
    .then(([storeList, productList]) => {
      stores.value = Array.isArray(storeList) ? storeList : []
      products.value = Array.isArray(productList) ? productList : []
    })
    .catch((err) => {
      optionsError.value = err && err.message ? err.message : "门店 / 商品列表加载失败"
    })
}

/* 日期或门店变化：刷新指标卡、趋势图、Top10 */
watch([() => filters.range, () => filters.storeId], () => {
  loadSummary()
  loadDaily()
  loadTopProducts()
})

/* 商品变化：只刷新指标卡与趋势图；Top10 保持原结果 */
watch(
  () => filters.productId,
  () => {
    loadSummary()
    loadDaily()
  },
)

onMounted(init)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <h1>门店经营看板</h1>
    </header>

    <el-alert v-if="basicsError" type="error" :closable="false" class="fatal">
      <template #title>
        数据区间加载失败：{{ basicsError }}
        <el-button size="small" class="fatal-retry" @click="init">重试</el-button>
      </template>
    </el-alert>

    <filter-bar
      :range="filters.range"
      :store-id="filters.storeId"
      :product-id="filters.productId"
      :stores="stores"
      :products="products"
      :disabled="!ready"
      @update:range="filters.range = $event"
      @update:store-id="filters.storeId = $event"
      @update:product-id="filters.productId = $event"
    />
    <el-alert
      v-if="optionsError"
      type="error"
      :closable="false"
      class="options-error"
      :title="`筛选选项加载失败：${optionsError}`"
    >
      <el-button size="small" @click="init">重试</el-button>
    </el-alert>

    <metric-cards :state="summary" @retry="loadSummary" />
    <trend-chart :state="daily" @retry="loadDaily" />
    <top-products :state="topProducts" @retry="loadTopProducts" />
    <data-quality :state="dataQuality" @retry="init" />
    <chat-panel :llm-mode="llmMode" />
  </div>
</template>

<style>
body {
  margin: 0;
  background: #f5f7fa;
  font-family: "Helvetica Neue", Helvetica, "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
}
.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 16px 16px 40px;
}
.page-header h1 {
  font-size: 20px;
  color: #303133;
  margin: 8px 0 16px;
}
.fatal,
.options-error {
  margin-bottom: 12px;
}
.fatal-retry {
  margin-left: 8px;
}
</style>
