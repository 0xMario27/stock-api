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
const klineLoading = ref(false);
const period = ref<KlinePeriod>("day");
const adjust = ref<KlineAdjust>("none");
const source = ref<SourceName>("auto");
const showMA = ref(true);
const chartContainer = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let refreshTimer: number | null = null;
let themeObserver: MutationObserver | null = null;

const isCrypto = computed(() => props.assetClass === "crypto");

const changeAmount = computed(() => {
  if (!quote.value) return 0;
  return quote.value.now - quote.value.yesterday;
});

function formatPrice(price: number): string {
  if (price >= 1000) return price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (price >= 1) return price.toFixed(3);
  if (price >= 0.01) return price.toFixed(5);
  return price.toFixed(8);
}

function formatPercent(percent: number): string {
  const sign = percent > 0 ? "+" : "";
  return sign + (percent * 100).toFixed(2) + "%";
}

function formatAmount(amount: number): string {
  const sign = amount > 0 ? "+" : "";
  return sign + formatPrice(Math.abs(amount));
}

function formatVolume(vol: number | null | undefined): string {
  if (!vol || vol === 0) return "-";
  if (vol >= 1e8) return (vol / 1e8).toFixed(2) + "亿";
  if (vol >= 1e4) return (vol / 1e4).toFixed(2) + "万";
  return vol.toFixed(0);
}

function priceClass(percent: number): string {
  if (percent > 0) return "text-up";
  if (percent < 0) return "text-down";
  return "text-flat";
}

async function loadQuote(): Promise<void> {
  try {
    quote.value = await getQuote(props.code, source.value, props.assetClass);
  } catch { /* keep last */ }
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

function calcMA(data: number[], maPeriod: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < maPeriod - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = 0; j < maPeriod; j++) sum += data[i - j];
      result.push(sum / maPeriod);
    }
  }
  return result;
}

function buildTooltipHTML(params: any[], colors: Record<string, string>): string {
  if (!params || params.length === 0) return "";
  const date = params[0]?.axisValue || "";
  let html = '<div style="margin-bottom:4px;color:' + colors.fgSec + ';font-size:11px">' + date + "</div>";

  for (const p of params) {
    const name = p.seriesName;
    const val = p.value;

    if (name === "K线" && Array.isArray(val)) {
      const open = val[0], close = val[1], high = val[2], low = val[3];
      const chg = close - open;
      const chgPct = open ? (chg / open * 100).toFixed(2) : "0.00";
      const chgColor = chg >= 0 ? colors.up : colors.down;
      html += '<div style="display:grid;grid-template-columns:auto auto;gap:2px 12px;font-size:11px">';
      html += '<span style="color:' + colors.fgSec + '">开</span><span style="color:' + colors.fg + '">' + formatPrice(open) + "</span>";
      html += '<span style="color:' + colors.fgSec + '">收</span><span style="color:' + chgColor + '">' + formatPrice(close) + "</span>";
      html += '<span style="color:' + colors.fgSec + '">高</span><span style="color:' + colors.fg + '">' + formatPrice(high) + "</span>";
      html += '<span style="color:' + colors.fgSec + '">低</span><span style="color:' + colors.fg + '">' + formatPrice(low) + "</span>";
      html += '<span style="color:' + colors.fgSec + '">涨跌</span><span style="color:' + chgColor + '">' + (chg >= 0 ? "+" : "") + chg.toFixed(2) + " (" + chgPct + "%)</span>";
      html += "</div>";
    } else if (name === "成交量") {
      html += '<div style="font-size:11px;margin-top:2px"><span style="color:' + colors.fgSec + '">量</span><span style="color:' + colors.fg + ';margin-left:8px">' + formatVolume(val) + "</span></div>";
    } else if (name && name.startsWith("MA") && val != null) {
      html += '<div style="font-size:11px;margin-top:2px"><span style="color:' + colors.fgSec + '">' + name + '</span><span style="color:' + p.color + ';margin-left:8px">' + formatPrice(val) + "</span></div>";
    }
  }
  return html;
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

  const closes = klines.value.map((k) => k.close);
  const candleData = klines.value.map((k) => [k.open, k.close, k.low, k.high]);
  const dates = klines.value.map((k) => k.date);
  const volumes = klines.value.map((k) => k.volume ?? 0);

  const ma5 = calcMA(closes, 5);
  const ma10 = calcMA(closes, 10);
  const ma20 = calcMA(closes, 20);

  const cs = getComputedStyle(document.documentElement);
  const colors = {
    up: cs.getPropertyValue("--color-up").trim() || "#EF4444",
    down: cs.getPropertyValue("--color-down").trim() || "#26A69A",
    border: cs.getPropertyValue("--color-border").trim() || "#334155",
    fg: cs.getPropertyValue("--color-fg").trim() || "#F8FAFC",
    fgSec: cs.getPropertyValue("--color-fg-secondary").trim() || "#94A3B8",
    fgMuted: cs.getPropertyValue("--color-fg-muted").trim() || "#64748B",
    grid: cs.getPropertyValue("--chart-grid").trim() || "rgba(51,65,85,0.3)",
    tooltipBg: cs.getPropertyValue("--chart-tooltip-bg").trim() || "rgba(15,23,42,0.95)",
    primary: cs.getPropertyValue("--color-primary").trim() || "#3B82F6",
    accent: cs.getPropertyValue("--color-accent").trim() || "#8B5CF6",
  };
  const maColors = ["#FBBF24", colors.primary, colors.accent];

  chart.setOption({
    backgroundColor: "transparent",
    animation: false,
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "cross",
        lineStyle: { color: colors.fgMuted, width: 1, type: "dashed" },
        label: { backgroundColor: colors.primary },
      },
      backgroundColor: colors.tooltipBg,
      borderColor: colors.border,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: colors.fg, fontSize: 12, fontFamily: "JetBrains Mono, monospace" },
      formatter: (params: any[]) => buildTooltipHTML(params, colors),
    },
    legend: {
      show: showMA.value,
      top: 4,
      right: 8,
      data: ["MA5", "MA10", "MA20"],
      textStyle: { color: colors.fgSec, fontSize: 10 },
      itemWidth: 14,
      itemHeight: 2,
      inactiveColor: colors.fgMuted,
    },
    grid: [
      { left: 64, right: 16, top: showMA.value ? 32 : 8, height: "58%" },
      { left: 64, right: 16, top: "74%", height: "18%" },
    ],
    xAxis: [
      {
        type: "category", data: dates, scale: true, boundaryGap: true,
        axisLine: { lineStyle: { color: colors.border } },
        axisTick: { show: false },
        axisLabel: { color: colors.fgSec, fontSize: 10 },
        splitLine: { show: false },
        min: "dataMin", max: "dataMax",
      },
      {
        type: "category", gridIndex: 1, data: dates, scale: true, boundaryGap: true,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: colors.border } },
        axisTick: { show: false },
      },
    ],
    yAxis: [
      {
        scale: true, splitArea: { show: false },
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: colors.fgSec, fontSize: 10, formatter: (val: number) => formatPrice(val) },
        splitLine: { lineStyle: { color: colors.grid } },
      },
      {
        gridIndex: 1, splitNumber: 2,
        axisLabel: { show: true, color: colors.fgSec, fontSize: 9, formatter: (val: number) => formatVolume(val) },
        axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false },
      },
    ],
    series: [
      {
        name: "K线", type: "candlestick", data: candleData,
        itemStyle: { color: colors.up, color0: colors.down, borderColor: colors.up, borderColor0: colors.down },
        barWidth: "60%",
      },
      { name: "MA5", type: "line", data: ma5, smooth: false, symbol: "none", lineStyle: { width: 1, color: maColors[0] }, z: 2 },
      { name: "MA10", type: "line", data: ma10, smooth: false, symbol: "none", lineStyle: { width: 1, color: maColors[1] }, z: 2 },
      { name: "MA20", type: "line", data: ma20, smooth: false, symbol: "none", lineStyle: { width: 1, color: maColors[2] }, z: 2 },
      {
        name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: candleData[i][1] >= candleData[i][0] ? colors.up : colors.down, opacity: 0.4 },
        })),
        barWidth: "60%",
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 50, end: 100 },
      {
        show: true, type: "slider", xAxisIndex: [0, 1], bottom: 4, height: 18,
        start: 50, end: 100, borderColor: "transparent",
        backgroundColor: colors.grid,
        fillerColor: "rgba(59, 130, 246, 0.08)",
        handleStyle: { color: colors.primary, borderColor: colors.primary },
        moveHandleStyle: { color: colors.fgMuted },
        textStyle: { color: colors.fgSec, fontSize: 10 },
        dataBackground: { lineStyle: { color: colors.fgMuted }, areaStyle: { color: colors.grid } },
        selectedDataBackground: { lineStyle: { color: colors.primary }, areaStyle: { color: "rgba(59, 130, 246, 0.15)" } },
      },
    ],
  }, true);
}

function startAutoRefresh(): void {
  stopAutoRefresh();
  refreshTimer = window.setInterval(() => loadQuote(), 15000);
}

function stopAutoRefresh(): void {
  if (refreshTimer !== null) { clearInterval(refreshTimer); refreshTimer = null; }
}

function handleResize(): void { chart?.resize(); }

function goInspect(): void {
  router.push("/inspect/" + props.code + "?asset_class=" + props.assetClass);
}

watch(() => props.code, () => { loadQuote(); loadKlines(); });
watch([period, adjust, source], () => loadKlines());
watch(showMA, () => renderChart());

onMounted(() => {
  loadQuote();
  loadKlines();
  startAutoRefresh();
  window.addEventListener("resize", handleResize);
  themeObserver = new MutationObserver(() => renderChart());
  themeObserver.observe(document.documentElement, {
    attributes: true, attributeFilter: ["data-theme", "data-color-rule"],
  });
});

onBeforeUnmount(() => {
  stopAutoRefresh();
  window.removeEventListener("resize", handleResize);
  themeObserver?.disconnect();
  themeObserver = null;
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div class="detail-view">
    <div class="back-bar">
      <button class="ui-back" @click="router.push('/')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        <span>返回列表</span>
      </button>
    </div>

    <div class="ui-card trading-panel">
      <!-- 行情头部 -->
      <div v-if="quote" class="quote-bar">
        <div class="quote-identity">
          <div class="quote-code text-mono">{{ quote.code }}</div>
          <div class="quote-name">{{ quote.name }}</div>
          <span class="ui-source-badge">{{ quote.source }}</span>
        </div>

        <div class="quote-price-block">
          <div class="price-now" :class="priceClass(quote.percent)">{{ formatPrice(quote.now) }}</div>
          <div class="price-change" :class="priceClass(quote.percent)">
            <span>{{ formatAmount(changeAmount) }}</span>
            <span class="change-sep">|</span>
            <span>{{ formatPercent(quote.percent) }}</span>
          </div>
        </div>

        <div class="quote-stats-bar">
          <div class="stat-cell">
            <span class="stat-label">昨收</span>
            <span class="stat-val text-mono">{{ formatPrice(quote.yesterday) }}</span>
          </div>
          <div class="stat-cell">
            <span class="stat-label">最高</span>
            <span class="stat-val text-mono text-up">{{ formatPrice(quote.high) }}</span>
          </div>
          <div class="stat-cell">
            <span class="stat-label">最低</span>
            <span class="stat-val text-mono text-down">{{ formatPrice(quote.low) }}</span>
          </div>
        </div>
      </div>

      <!-- 工具栏 -->
      <div class="chart-toolbar">
        <div class="toolbar-left">
          <div class="ui-segmented">
            <button
              v-for="p in (['day','week','month'] as KlinePeriod[])"
              :key="p"
              :class="['ui-segmented-btn', { active: period === p }]"
              @click="period = p"
            >{{ p === 'day' ? '日K' : p === 'week' ? '周K' : '月K' }}</button>
          </div>
          <div v-if="!isCrypto" class="ui-segmented">
            <button
              v-for="a in (['none','qfq','hfq'] as KlineAdjust[])"
              :key="a"
              :class="['ui-segmented-btn', { active: adjust === a }]"
              @click="adjust = a"
            >{{ a === 'none' ? '不复权' : a === 'qfq' ? '前复权' : '后复权' }}</button>
          </div>
          <button
            :class="['ui-segmented-btn', 'ma-toggle', { active: showMA }]"
            @click="showMA = !showMA"
          >MA</button>
        </div>
        <div class="toolbar-right">
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
          <button class="ui-btn" @click="goInspect">诊断</button>
        </div>
      </div>

      <!-- 图表 -->
      <div v-loading="klineLoading" class="chart-area">
        <div ref="chartContainer" class="chart-container"></div>
        <div v-if="!klineLoading && klines.length === 0" class="chart-empty">无 K 线数据</div>
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

.back-bar {
  display: flex;
  align-items: center;
}

/* 交易面板（合并行情+图表） */
.trading-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* === 行情头部 === */
.quote-bar {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border-light);
  flex-wrap: wrap;
}

.quote-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 120px;
}

.quote-code {
  font-size: 17px;
  font-weight: 700;
  color: var(--color-fg);
}

.quote-name {
  font-size: 12px;
  color: var(--color-fg-secondary);
}

.quote-identity .ui-source-badge {
  width: fit-content;
  margin-top: 3px;
}

.quote-price-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.price-now {
  font-family: var(--font-mono);
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.price-change {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  gap: 6px;
}

.change-sep {
  color: var(--color-fg-muted);
  opacity: 0.5;
}

.quote-stats-bar {
  display: flex;
  gap: var(--space-5);
}

.stat-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-label {
  font-size: 10px;
  color: var(--color-fg-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-val {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-fg);
}

/* === 工具栏 === */
.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--color-border-light);
  flex-wrap: wrap;
  gap: var(--space-2);
  background: var(--color-muted);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.ma-toggle {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  min-height: 32px;
  padding: 6px 10px;
  font-weight: 600;
}

.ma-toggle.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

/* === 图表区 === */
.chart-area {
  position: relative;
  padding: var(--space-2);
  min-height: 560px;
}

.chart-container {
  width: 100%;
  height: 540px;
}

.chart-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: var(--color-fg-muted);
  font-size: 14px;
}

/* === 响应式 === */
@media (max-width: 768px) {
  .quote-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-3);
  }
  .quote-stats-bar {
    width: 100%;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .price-now {
    font-size: 26px;
  }
  .chart-container {
    height: 440px;
  }
  .chart-area {
    min-height: 460px;
  }
}

@media (max-width: 640px) {
  .chart-toolbar {
    padding: var(--space-2);
  }
  .toolbar-left, .toolbar-right {
    width: 100%;
  }
  .ui-select {
    flex: 1;
  }
  .chart-container {
    height: 380px;
  }
  .chart-area {
    min-height: 400px;
  }
}
</style>
