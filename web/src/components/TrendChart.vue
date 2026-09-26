<script>
import * as echarts from "echarts/core"
import { LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import { formatMoney, formatCount } from "../utils/format"

// 按模块引入 ECharts（控制构建体积，不依赖运行时 CDN）
echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

/**
 * 由 /api/metrics/daily 的响应纯函数生成 chart option。
 * tooltip 同时展示日期、净营业额、订单数、客单价；aov 为 null 显示「无数据」。
 */
export function buildTrendOption(data) {
  const days = data && Array.isArray(data.days) ? data.days : []
  return {
    grid: { left: 80, right: 24, top: 32, bottom: 40 },
    tooltip: {
      trigger: "axis",
      formatter(params) {
        const first = Array.isArray(params) && params.length ? params[0] : null
        const raw = first && first.data && first.data.raw ? first.data.raw : {}
        const aov = raw.aov === null || raw.aov === undefined ? "无数据" : formatMoney(raw.aov)
        return [
          raw.date || "",
          `净营业额：${formatMoney(raw.net_revenue)}`,
          `订单数：${formatCount(raw.orders ?? 0)}`,
          `客单价：${aov}`,
        ].join("<br/>")
      },
    },
    xAxis: {
      type: "category",
      data: days.map((day) => day.date),
      boundaryGap: false,
    },
    yAxis: { type: "value", name: "净营业额（元）" },
    series: [
      {
        type: "line",
        name: "净营业额",
        smooth: true,
        showSymbol: false,
        data: days.map((day) => ({ value: day.net_revenue, raw: day })),
      },
    ],
  }
}
</script>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import * as echarts from "echarts/core"

const props = defineProps({
  /** { loading, error, data }，data 为 /api/metrics/daily 的响应。 */
  state: { type: Object, required: true },
})

defineEmits(["retry"])

const hasDays = computed(() => {
  const data = props.state.data
  return !!(data && Array.isArray(data.days) && data.days.length)
})

const chartEl = ref(null)
let chart = null

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(buildTrendOption(props.state.data), { notMerge: true })
}

function resize() {
  if (chart) chart.resize()
}

onMounted(() => {
  render()
  window.addEventListener("resize", resize)
})

watch(
  () => props.state.data,
  () => render(),
)

onBeforeUnmount(() => {
  window.removeEventListener("resize", resize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<template>
  <el-card shadow="never" class="trend-chart" v-loading="state.loading">
    <template #header>营业额趋势</template>
    <el-alert
      v-if="state.error"
      type="error"
      :closable="false"
      :title="`趋势加载失败：${state.error}`"
    >
      <el-button size="small" @click="$emit('retry')">重试</el-button>
    </el-alert>
    <template v-else>
      <div v-show="hasDays" ref="chartEl" class="chart"></div>
      <el-empty v-if="!state.loading && !hasDays" description="区间内无数据" :image-size="60" />
    </template>
  </el-card>
</template>

<style scoped>
.trend-chart {
  margin-bottom: 12px;
}
.chart {
  width: 100%;
  height: 320px;
}
</style>
