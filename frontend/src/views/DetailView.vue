<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch, computed } from "vue";
import { useRouter } from "vue-router";
import { getQuote } from "@/api";
import type { AssetClass, KlinePeriod, Quote, SourceName } from "@/types";
import TradingViewChart from "@/components/TradingViewChart.vue";

const props = defineProps<{ code: string; assetClass: AssetClass }>();
const router = useRouter();

const quote = ref<Quote | null>(null);
const period = ref<KlinePeriod>("day");
const source = ref<SourceName>("auto");
let refreshTimer: number | null = null;

const isCrypto = computed(() => props.assetClass === "crypto");
const changeAmount = computed(() => quote.value ? quote.value.now - quote.value.yesterday : 0);

// TradingView interval 映射
const tvInterval = computed(() => {
  if (period.value === "week") return "W";
  if (period.value === "month") return "M";
  return "D";
});

// 读取当前主题
const theme = ref<"light" | "dark">(
  (localStorage.getItem("stock-api-py:theme") as "light" | "dark") || "dark"
);
let themeObserver: MutationObserver | null = null;

function formatPrice(p: number): string {
  if (p >= 1000) return p.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}
function formatPercent(p: number): string { return (p>0?"+":"")+(p*100).toFixed(2)+"%"; }
function formatAmount(a: number): string { return (a>0?"+":"")+formatPrice(Math.abs(a)); }
function priceClass(p: number): string { return p>0?"text-up":p<0?"text-down":"text-flat"; }

async function loadQuote() {
  try { quote.value = await getQuote(props.code, source.value, props.assetClass); } catch {}
}

function startAutoRefresh() { stopAutoRefresh(); refreshTimer = window.setInterval(() => loadQuote(), 15000); }
function stopAutoRefresh() { if (refreshTimer !== null) { clearInterval(refreshTimer); refreshTimer = null; } }
function goInspect() { router.push("/inspect/" + props.code + "?asset_class=" + props.assetClass); }

watch(() => props.code, () => { loadQuote(); });
watch(source, () => loadQuote());

onMounted(() => {
  loadQuote(); startAutoRefresh();
  themeObserver = new MutationObserver(() => {
    theme.value = document.documentElement.getAttribute("data-theme") as "light" | "dark" || "dark";
  });
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
});

onBeforeUnmount(() => {
  stopAutoRefresh();
  themeObserver?.disconnect(); themeObserver = null;
});
</script>

<template>
  <div class="detail-view">
    <div class="back-bar">
      <button class="ui-back" @click="router.push('/watchlist')">
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
            <option value="binance">Binance</option>
          </select>
          <button class="ui-btn" @click="goInspect">诊断</button>
        </div>
      </div>

      <!-- TradingView 图表 -->
      <div class="chart-area">
        <TradingViewChart
          :code="props.code"
          :asset-class="props.assetClass"
          :interval="tvInterval"
          :theme="theme"
        />
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

.chart-area {
  position: relative;
  height: 600px;
  padding: var(--space-2);
}

@media (max-width: 768px) {
  .quote-bar { flex-direction: column; align-items: flex-start; gap: var(--space-3); }
  .quote-stats-bar { width: 100%; justify-content: space-between; gap: var(--space-2); }
  .price-now { font-size: 26px; }
  .chart-area { height: 500px; }
}
@media (max-width: 640px) {
  .chart-toolbar { padding: var(--space-2); }
  .toolbar-left, .toolbar-right { width: 100%; }
  .ui-select { flex: 1; }
  .chart-area { height: 450px; }
}
</style>
