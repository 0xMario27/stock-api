<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, computed } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts";
import { getKlines, getQuote } from "@/api";
import type { AssetClass, Kline, KlineAdjust, KlinePeriod, Quote, SourceName } from "@/types";

const props = defineProps<{ code: string; assetClass: AssetClass }>();
const router = useRouter();

const quote = ref<Quote | null>(null);
const klines = ref<Kline[]>([]);
const loading = ref(false);
const period = ref<KlinePeriod>("day");
const adjust = ref<KlineAdjust>("none");
const source = ref<SourceName>("auto");
const chartContainer = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let refreshTimer: number | null = null;

const isCrypto = computed(() => props.assetClass === "crypto");

function formatPrice(price: number): string {
  if (price >= 1000) return price.toFixed(2);
  if (price >= 1) return price.toFixed(3);
  if (price >= 0.01) return price.toFixed(5);
  return price.toFixed(8);
}

function percentClass(percent: number): string {
  if (percent > 0) return "text-up";
  if (percent < 0) return "text-down";
  return "text-flat";
}

function formatPercent(percent: number): string {
  return `${(percent * 100).toFixed(2)}%`;
}

async function loadQuote(): Promise<void> {
  try {
    quote.value = await getQuote(props.code, source.value, props.assetClass);
  } catch {
    // keep last
  }
}

async function loadKlines(): Promise<void> {
  loading.value = true;
  try {
    klines.value = await getKlines(
      props.code,
      { period: period.value, adjust: adjust.value, count: 120, source: source.value },
      props.assetClass
    );
    renderChart();
  } finally {
    loading.value = false;
  }
}

function renderChart(): void {
  if (!chartContainer.value || klines.value.length === 0) return;
  if (!chart) {
    chart = echarts.init(chartContainer.value);
  }
  const data = klines.value.map((k) => ({
    value: [k.open, k.close, k.low, k.high],
    volume: k.volume ?? 0,
  }));
  const dates = klines.value.map((k) => k.date);
  const volumes = klines.value.map((k) => k.volume ?? 0);

  chart.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
    legend: { data: ["K线", "成交量"], top: 0 },
    grid: [
      { left: "8%", right: "4%", top: "12%", height: "58%" },
      { left: "8%", right: "4%", top: "76%", height: "16%" },
    ],
    xAxis: [
      { type: "category", data: dates, scale: true, boundaryGap: false, axisLine: { onZero: false } },
      { type: "category", gridIndex: 1, data: dates, scale: true, boundaryGap: false, show: false },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: data.map((d) => d.value),
        itemStyle: {
          color: "#f56c6c",
          color0: "#67c23a",
          borderColor: "#f56c6c",
          borderColor0: "#67c23a",
        },
      },
      {
        name: "成交量",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: data[i].value[1] >= data[i].value[0] ? "#f56c6c" : "#67c23a" },
        })),
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 60, end: 100 },
      { show: true, type: "slider", xAxisIndex: [0, 1], top: "94%", start: 60, end: 100 },
    ],
  });
}

function startAutoRefresh(): void {
  stopAutoRefresh();
  refreshTimer = window.setInterval(() => loadQuote(), 15000);
}

function stopAutoRefresh(): void {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

watch(() => props.code, () => {
  loadQuote();
  loadKlines();
});

watch([period, adjust, source], () => loadKlines());

onMounted(() => {
  loadQuote();
  loadKlines();
  startAutoRefresh();
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  stopAutoRefresh();
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
  chart = null;
});

function handleResize(): void {
  chart?.resize();
}

function goInspect(): void {
  router.push(`/inspect/${props.code}?asset_class=${props.assetClass}`);
}
</script>

<template>
  <div class="detail-view" v-loading="loading">
    <el-page-header @back="router.push('/')" class="page-header">
      <template #content>
        <span class="header-content">
          <span class="code">{{ code }}</span>
          <span v-if="quote" class="name">{{ quote.name }}</span>
          <el-tag v-if="quote" size="small" type="info">{{ quote.source }}</el-tag>
        </span>
      </template>
    </el-page-header>

    <el-card v-if="quote" shadow="never" class="quote-card">
      <div class="quote-grid">
        <div class="quote-item">
          <div class="label">最新价</div>
          <div class="value">{{ formatPrice(quote.now) }}</div>
        </div>
        <div class="quote-item">
          <div class="label">涨跌幅</div>
          <div class="value" :class="percentClass(quote.percent)">
            {{ formatPercent(quote.percent) }}
          </div>
        </div>
        <div class="quote-item">
          <div class="label">最高</div>
          <div class="value">{{ formatPrice(quote.high) }}</div>
        </div>
        <div class="quote-item">
          <div class="label">最低</div>
          <div class="value">{{ formatPrice(quote.low) }}</div>
        </div>
        <div class="quote-item">
          <div class="label">昨收</div>
          <div class="value">{{ formatPrice(quote.yesterday) }}</div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="kline-card">
      <template #header>
        <div class="kline-header">
          <span>K 线图</span>
          <div class="kline-controls">
            <el-radio-group v-model="period" size="small">
              <el-radio-button label="day">日K</el-radio-button>
              <el-radio-button label="week">周K</el-radio-button>
              <el-radio-button label="month">月K</el-radio-button>
            </el-radio-group>
            <el-radio-group v-if="!isCrypto" v-model="adjust" size="small">
              <el-radio-button label="none">不复权</el-radio-button>
              <el-radio-button label="qfq">前复权</el-radio-button>
              <el-radio-button label="hfq">后复权</el-radio-button>
            </el-radio-group>
            <el-select v-if="!isCrypto" v-model="source" size="small" style="width: 120px">
              <el-option label="自动兜底" value="auto" />
              <el-option label="腾讯" value="tencent" />
              <el-option label="新浪" value="sina" />
              <el-option label="东方财富" value="eastmoney" />
            </el-select>
            <el-select v-else v-model="source" size="small" style="width: 120px">
              <el-option label="自动兜底" value="auto" />
              <el-option label="CoinGecko" value="coingecko" />
            </el-select>
            <el-button size="small" @click="goInspect">
              诊断数据源
            </el-button>
          </div>
        </div>
      </template>
      <div ref="chartContainer" class="chart-container"></div>
      <el-empty v-if="!loading && klines.length === 0" description="无 K 线数据" />
    </el-card>
  </div>
</template>

<style scoped>
.detail-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  background: #fff;
  padding: 12px 16px;
  border-radius: 4px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.code {
  font-weight: 600;
  font-size: 16px;
}

.name {
  color: #606266;
}

.quote-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 16px;
}

.quote-item {
  text-align: center;
}

.quote-item .label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.quote-item .value {
  font-size: 20px;
  font-weight: 600;
}

.kline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.kline-controls {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chart-container {
  width: 100%;
  height: 480px;
}

.text-up {
  color: #f56c6c;
}

.text-down {
  color: #67c23a;
}

.text-flat {
  color: #909399;
}
</style>
