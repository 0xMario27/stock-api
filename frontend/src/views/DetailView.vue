<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, computed, nextTick } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts";
import { getKlines, getQuote } from "@/api";
import type { AssetClass, Kline, KlineAdjust, KlinePeriod, Quote, SourceName } from "@/types";

const props = defineProps<{ code: string; assetClass: AssetClass }>();
const router = useRouter();

const quote = ref<Quote | null>(null);
const klines = ref<Kline[]>([]);
const loading = ref(false);
const klineLoading = ref(false);
const period = ref<KlinePeriod>("day");
const adjust = ref<KlineAdjust>("none");
const source = ref<SourceName>("auto");
const chartContainer = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let refreshTimer: number | null = null;

const isCrypto = computed(() => props.assetClass === "crypto");

function formatPrice(price: number): string {
  if (price >= 1000) return price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (price >= 1) return price.toFixed(3);
  if (price >= 0.01) return price.toFixed(5);
  return price.toFixed(8);
}

function formatPercent(percent: number): string {
  const sign = percent > 0 ? "+" : "";
  return `${sign}${(percent * 100).toFixed(2)}%`;
}

function priceClass(percent: number): string {
  if (percent > 0) return "text-up";
  if (percent < 0) return "text-down";
  return "text-flat";
}

async function loadQuote(): Promise<void> {
  try {
    quote.value = await getQuote(props.code, source.value, props.assetClass);
  } catch {
    /* keep last */
  }
}

async function loadKlines(): Promise<void> {
  klineLoading.value = true;
  try {
    klines.value = await getKlines(
      props.code,
      { period: period.value, adjust: adjust.value, count: 120, source: source.value },
      props.assetClass
    );
    await nextTick();
    renderChart();
  } finally {
    klineLoading.value = false;
  }
}

function renderChart(): void {
  if (!chartContainer.value) return;

  if (!chart) {
    chart = echarts.init(chartContainer.value, undefined, { renderer: "canvas" });
  }

  if (klines.value.length === 0) {
    chart.clear();
    return;
  }

  const data = klines.value.map((k) => [k.open, k.close, k.low, k.high]);
  const dates = klines.value.map((k) => k.date);
  const volumes = klines.value.map((k) => k.volume ?? 0);

  // 从 CSS 变量获取涨跌色
  const style = getComputedStyle(document.documentElement);
  const upColor = style.getPropertyValue("--color-up").trim() || "#EF4444";
  const downColor = style.getPropertyValue("--color-down").trim() || "#26A69A";
  const borderColor = style.getPropertyValue("--color-border").trim() || "#334155";
  const fgSecondary = style.getPropertyValue("--color-fg-secondary").trim() || "#94A3B8";

  chart.setOption({
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross", lineStyle: { color: borderColor } },
      backgroundColor: "rgba(15, 23, 42, 0.95)",
      borderColor: borderColor,
      textStyle: { color: "#F8FAFC", fontFamily: "var(--font-mono)" },
    },
    grid: [
      { left: "6%", right: "3%", top: "4%", height: "62%" },
      { left: "6%", right: "3%", top: "72%", height: "22%" },
    ],
    xAxis: [
      {
        type: "category",
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLine: { lineStyle: { color: borderColor } },
        axisLabel: { color: fgSecondary, fontSize: 10 },
        splitLine: { show: false },
      },
      {
        type: "category",
        gridIndex: 1,
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: borderColor } },
      },
    ],
    yAxis: [
      {
        scale: true,
        splitArea: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: fgSecondary, fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(51, 65, 85, 0.3)" } },
      },
      {
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: data,
        itemStyle: {
          color: upColor,
          color0: downColor,
          borderColor: upColor,
          borderColor0: downColor,
        },
      },
      {
        name: "成交量",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: data[i][1] >= data[i][0] ? upColor : downColor, opacity: 0.5 },
        })),
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 60, end: 100 },
      {
        show: true,
        type: "slider",
        xAxisIndex: [0, 1],
        top: "96%",
        start: 60,
        end: 100,
        height: 20,
        borderColor: "transparent",
        backgroundColor: "rgba(51, 65, 85, 0.2)",
        fillerColor: "rgba(245, 158, 11, 0.1)",
        handleStyle: { color: upColor },
        textStyle: { color: fgSecondary, fontSize: 10 },
      },
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

function handleResize(): void {
  chart?.resize();
}

function goInspect(): void {
  router.push(`/inspect/${props.code}?asset_class=${props.assetClass}`);
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
</script>

<template>
  <div class="detail-view">
    <!-- 返回栏 -->
    <div class="back-bar">
      <button class="ui-back" @click="router.push('/')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        <span>返回列表</span>
      </button>
    </div>

    <!-- 行情头部 -->
    <div v-if="quote" class="quote-header ui-card">
      <div class="quote-meta">
        <div class="quote-code text-mono">{{ quote.code }}</div>
        <div class="quote-name">{{ quote.name }}</div>
        <span class="ui-source-badge">{{ quote.source }}</span>
      </div>
      <div class="quote-price-section">
        <div class="price-main" :class="priceClass(quote.percent)">
          {{ formatPrice(quote.now) }}
        </div>
        <div class="price-change" :class="priceClass(quote.percent)">
          <span>{{ formatPercent(quote.percent) }}</span>
        </div>
      </div>
      <div class="quote-stats">
        <div class="stat-item">
          <div class="stat-label">最高</div>
          <div class="stat-value text-mono">{{ formatPrice(quote.high) }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">最低</div>
          <div class="stat-value text-mono">{{ formatPrice(quote.low) }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">昨收</div>
          <div class="stat-value text-mono">{{ formatPrice(quote.yesterday) }}</div>
        </div>
      </div>
    </div>

    <!-- K 线图 -->
    <div class="ui-card kline-card">
      <div class="kline-header">
        <span class="kline-title">K 线图</span>
        <div class="kline-controls">
          <div class="ui-segmented">
            <button
              v-for="p in (['day','week','month'] as KlinePeriod[])"
              :key="p"
              :class="['ui-segmented-btn', { active: period === p }]"
              @click="period = p"
            >
              {{ p === 'day' ? '日K' : p === 'week' ? '周K' : '月K' }}
            </button>
          </div>
          <div v-if="!isCrypto" class="ui-segmented">
            <button
              v-for="a in (['none','qfq','hfq'] as KlineAdjust[])"
              :key="a"
              :class="['ui-segmented-btn', { active: adjust === a }]"
              @click="adjust = a"
            >
              {{ a === 'none' ? '不复权' : a === 'qfq' ? '前复权' : '后复权' }}
            </button>
          </div>
          <select v-if="!isCrypto" v-model="source" class="ui-select">
            <option value="auto">自动兜底</option>
            <option value="tencent">腾讯</option>
            <option value="sina">新浪</option>
            <option value="eastmoney">东方财富</option>
          </select>
          <select v-else v-model="source" class="ui-select">
            <option value="auto">自动兜底</option>
            <option value="coingecko">CoinGecko</option>
          </select>
          <button class="ui-btn" @click="goInspect">
            诊断
          </button>
        </div>
      </div>
      <div v-loading="klineLoading" class="chart-area">
        <div ref="chartContainer" class="chart-container"></div>
        <div v-if="!klineLoading && klines.length === 0" class="chart-empty">
          无 K 线数据
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 返回栏（按钮用共享 .ui-back） */
.back-bar {
  display: flex;
  align-items: center;
}

/* 行情头部 */
.quote-header {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-5) var(--space-6);
  flex-wrap: wrap;
}

.quote-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 140px;
}

.quote-code {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-fg);
}

.quote-name {
  font-size: 13px;
  color: var(--color-fg-secondary);
}

/* 数据源标签用共享 .ui-source-badge，此处仅加 margin */
.quote-meta .ui-source-badge {
  width: fit-content;
  margin-top: 4px;
}

.quote-price-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.price-main {
  font-family: var(--font-mono);
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.price-change {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.quote-stats {
  display: flex;
  gap: var(--space-6);
}

.stat-item {
  text-align: center;
}

.stat-label {
  font-size: 11px;
  color: var(--color-fg-muted);
  margin-bottom: 2px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-fg);
}

/* K 线卡片 */
.kline-card {
  display: flex;
  flex-direction: column;
}

.kline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border-light);
  flex-wrap: wrap;
  gap: var(--space-3);
}

.kline-title {
  font-size: 15px;
  font-weight: 600;
}

.kline-controls {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

/* 选项卡/下拉框/按钮均用共享 .ui-segmented / .ui-select / .ui-btn */

/* 图表区 */
.chart-area {
  position: relative;
  padding: var(--space-3);
  min-height: 520px;
}

.chart-container {
  width: 100%;
  height: 500px;
}

.chart-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: var(--color-fg-muted);
  font-size: 14px;
}

/* 响应式 */
@media (max-width: 768px) {
  .quote-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-4);
  }
  .quote-stats {
    width: 100%;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .price-main {
    font-size: 28px;
  }
}

@media (max-width: 640px) {
  .kline-controls {
    width: 100%;
  }
  .ui-select {
    flex: 1;
  }
  .chart-container {
    height: 400px;
  }
  .chart-area {
    min-height: 420px;
  }
}
</style>
