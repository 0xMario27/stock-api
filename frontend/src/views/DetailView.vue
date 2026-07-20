<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, computed, nextTick } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts";
import { getKlines, getQuote } from "@/api";
import type { AssetClass, Kline, KlineAdjust, KlinePeriod, Quote, SourceName } from "@/types";
import { buildChartOption, type IndicatorState, type ChartColors } from "@/utils/chartBuilder";

const props = defineProps<{ code: string; assetClass: AssetClass }>();
const router = useRouter();

const quote = ref<Quote | null>(null);
const klines = ref<Kline[]>([]);
const klineLoading = ref(false);
const period = ref<KlinePeriod>("day");
const adjust = ref<KlineAdjust>("none");
const source = ref<SourceName>("auto");
const indicators = ref<IndicatorState>({ ma: true, boll: false, vwap: false, vol: true, macd: false, kdj: false, rsi: false });
const chartContainer = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let refreshTimer: number | null = null;
let themeObserver: MutationObserver | null = null;

const isCrypto = computed(() => props.assetClass === "crypto");
const changeAmount = computed(() => quote.value ? quote.value.now - quote.value.yesterday : 0);
const subCount = computed(() => (indicators.value.vol?1:0)+(indicators.value.macd?1:0)+(indicators.value.kdj?1:0)+(indicators.value.rsi?1:0));
const chartHeight = computed(() => 360 + subCount.value * 90);

const indicatorList = [
  { key: "ma" as const, label: "MA", group: "main" },
  { key: "boll" as const, label: "BOLL", group: "main" },
  { key: "vwap" as const, label: "VWAP", group: "main" },
  { key: "vol" as const, label: "VOL", group: "sub" },
  { key: "macd" as const, label: "MACD", group: "sub" },
  { key: "kdj" as const, label: "KDJ", group: "sub" },
  { key: "rsi" as const, label: "RSI", group: "sub" },
];

function formatPrice(p: number): string {
  if (p >= 1000) return p.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}
function formatPercent(p: number): string { return (p>0?"+":"")+(p*100).toFixed(2)+"%"; }
function formatAmount(a: number): string { return (a>0?"+":"")+formatPrice(Math.abs(a)); }
function priceClass(p: number): string { return p>0?"text-up":p<0?"text-down":"text-flat"; }

async function loadQuote() { try { quote.value = await getQuote(props.code, source.value, props.assetClass); } catch {} }
async function loadKlines() {
  klineLoading.value = true;
  try {
    klines.value = await getKlines(props.code, { period: period.value, adjust: adjust.value, count: 120, source: source.value }, props.assetClass);
    await nextTick(); renderChart();
  } finally { klineLoading.value = false; }
}

function getColors(): ChartColors {
  const cs = getComputedStyle(document.documentElement);
  return {
    up: cs.getPropertyValue("--color-up").trim()||"#EF4444",
    down: cs.getPropertyValue("--color-down").trim()||"#26A69A",
    border: cs.getPropertyValue("--color-border").trim()||"#334155",
    fg: cs.getPropertyValue("--color-fg").trim()||"#F8FAFC",
    fgSec: cs.getPropertyValue("--color-fg-secondary").trim()||"#94A3B8",
    fgMuted: cs.getPropertyValue("--color-fg-muted").trim()||"#64748B",
    grid: cs.getPropertyValue("--chart-grid").trim()||"rgba(51,65,85,0.3)",
    tooltipBg: cs.getPropertyValue("--chart-tooltip-bg").trim()||"rgba(15,23,42,0.95)",
    primary: cs.getPropertyValue("--color-primary").trim()||"#3B82F6",
    accent: cs.getPropertyValue("--color-accent").trim()||"#8B5CF6",
  };
}

function renderChart(): void {
  if (!chartContainer.value) return;
  if (!chart) chart = echarts.init(chartContainer.value, undefined, { renderer: "canvas" });
  if (klines.value.length === 0) { chart.clear(); return; }
  const option = buildChartOption(klines.value, indicators.value, getColors(), chartHeight.value);
  chart.setOption(option, true);
}

function toggleIndicator(key: keyof IndicatorState) {
  indicators.value[key] = !indicators.value[key];
  nextTick(() => { chart?.resize(); renderChart(); });
}

function startAutoRefresh() { stopAutoRefresh(); refreshTimer = window.setInterval(() => loadQuote(), 15000); }
function stopAutoRefresh() { if (refreshTimer !== null) { clearInterval(refreshTimer); refreshTimer = null; } }
function handleResize() { chart?.resize(); }
function goInspect() { router.push("/inspect/" + props.code + "?asset_class=" + props.assetClass); }

watch(() => props.code, () => { loadQuote(); loadKlines(); });
watch([period, adjust, source], () => loadKlines());

onMounted(() => {
  loadQuote(); loadKlines(); startAutoRefresh();
  window.addEventListener("resize", handleResize);
  themeObserver = new MutationObserver(() => renderChart());
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-color-rule"] });
});
onBeforeUnmount(() => {
  stopAutoRefresh(); window.removeEventListener("resize", handleResize);
  themeObserver?.disconnect(); themeObserver = null;
  chart?.dispose(); chart = null;
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
          <div class="stat-cell"><span class="stat-label">昨收</span><span class="stat-val text-mono">{{ formatPrice(quote.yesterday) }}</span></div>
          <div class="stat-cell"><span class="stat-label">最高</span><span class="stat-val text-mono text-up">{{ formatPrice(quote.high) }}</span></div>
          <div class="stat-cell"><span class="stat-label">最低</span><span class="stat-val text-mono text-down">{{ formatPrice(quote.low) }}</span></div>
        </div>
      </div>

      <!-- 工具栏 -->
      <div class="chart-toolbar">
        <div class="toolbar-left">
          <div class="ui-segmented">
            <button v-for="p in (['day','week','month'] as KlinePeriod[])" :key="p"
              :class="['ui-segmented-btn', { active: period === p }]" @click="period = p">
              {{ p === 'day' ? '日K' : p === 'week' ? '周K' : '月K' }}
            </button>
          </div>
          <div v-if="!isCrypto" class="ui-segmented">
            <button v-for="a in (['none','qfq','hfq'] as KlineAdjust[])" :key="a"
              :class="['ui-segmented-btn', { active: adjust === a }]" @click="adjust = a">
              {{ a === 'none' ? '不复权' : a === 'qfq' ? '前复权' : '后复权' }}
            </button>
          </div>
        </div>
        <div class="toolbar-right">
          <div class="indicator-toggles">
            <button v-for="ind in indicatorList" :key="ind.key"
              :class="['ind-btn', { active: indicators[ind.key] }]"
              @click="toggleIndicator(ind.key)">
              {{ ind.label }}
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
          <button class="ui-btn" @click="goInspect">诊断</button>
        </div>
      </div>

      <!-- 图表 -->
      <div v-loading="klineLoading" class="chart-area">
        <div ref="chartContainer" class="chart-container" :style="{ height: chartHeight + 'px' }"></div>
        <div v-if="!klineLoading && klines.length === 0" class="chart-empty">无 K 线数据</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail-view { display: flex; flex-direction: column; gap: var(--space-4); }
.back-bar { display: flex; align-items: center; }
.trading-panel { display: flex; flex-direction: column; overflow: hidden; }

.quote-bar {
  display: flex; align-items: center; gap: var(--space-8);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border-light); flex-wrap: wrap;
}
.quote-identity { display: flex; flex-direction: column; gap: 2px; min-width: 120px; }
.quote-code { font-size: 17px; font-weight: 700; color: var(--color-fg); }
.quote-name { font-size: 12px; color: var(--color-fg-secondary); }
.quote-identity .ui-source-badge { width: fit-content; margin-top: 3px; }

.quote-price-block { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.price-now {
  font-family: var(--font-mono); font-size: 32px; font-weight: 700;
  letter-spacing: -0.02em; line-height: 1.1; font-variant-numeric: tabular-nums;
}
.price-change {
  font-family: var(--font-mono); font-size: 14px; font-weight: 600;
  font-variant-numeric: tabular-nums; display: flex; align-items: center; gap: 6px;
}
.change-sep { color: var(--color-fg-muted); opacity: 0.5; }

.quote-stats-bar { display: flex; gap: var(--space-5); }
.stat-cell { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.stat-label { font-size: 10px; color: var(--color-fg-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.stat-val { font-size: 14px; font-weight: 500; color: var(--color-fg); }

.chart-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--color-border-light);
  flex-wrap: wrap; gap: var(--space-2); background: var(--color-muted);
}
.toolbar-left { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }

.indicator-toggles { display: flex; gap: 4px; flex-wrap: wrap; }
.ind-btn {
  padding: 4px 8px; border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); background: var(--color-bg);
  color: var(--color-fg-muted); font-size: 11px; font-weight: 600;
  cursor: pointer; transition: all var(--transition-fast); min-height: 28px;
  font-family: var(--font-sans);
}
.ind-btn:hover { border-color: var(--color-fg-muted); color: var(--color-fg); }
.ind-btn.active {
  background: var(--color-primary); border-color: var(--color-primary);
  color: #fff;
}

.chart-area { position: relative; padding: var(--space-2); min-height: 400px; }
.chart-container { width: 100%; }
.chart-empty {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  color: var(--color-fg-muted); font-size: 14px;
}

@media (max-width: 768px) {
  .quote-bar { flex-direction: column; align-items: flex-start; gap: var(--space-3); }
  .quote-stats-bar { width: 100%; justify-content: space-between; gap: var(--space-2); }
  .price-now { font-size: 26px; }
}
@media (max-width: 640px) {
  .chart-toolbar { padding: var(--space-2); }
  .toolbar-left, .toolbar-right { width: 100%; }
  .ui-select { flex: 1; }
}
</style>
