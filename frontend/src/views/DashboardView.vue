<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, reactive } from "vue";
import { useRouter } from "vue-router";
import { useStockStore } from "@/stores/stock";
import * as echarts from "echarts";
import { RefreshCw, X, LayoutGrid, GripHorizontal } from "lucide-vue-next";
import MarketBadge from "@/components/MarketBadge.vue";
import type { Quote, Kline } from "@/types";

const store = useStockStore();
const router = useRouter();
const refreshTimer = ref<number | null>(null);
const chartInstances = new Map<string, echarts.ECharts>();
const lastUpdate = ref<string>("");

const CARD_MIN_W = 300;
const CARD_MAX_W = 900;
const cardWidths = reactive<Record<string, number>>({});

interface DashCard {
  key: string;
  code: string;
  assetClass: string;
  quote: Quote | null;
  sparkline: Kline[] | null;
  return30d: number | null;
}

const cards = computed<DashCard[]>(() => {
  return store.dashItems.map((item) => {
    const key = `${item.assetClass}:${item.code}`;
    const sparkline = store.dashSparklines[key] || null;
    let return30d: number | null = null;
    if (sparkline && sparkline.length > 1) {
      const first = sparkline[0].close;
      const last = sparkline[sparkline.length - 1].close;
      if (first > 0) return30d = (last - first) / first;
    }
    return { key, code: item.code, assetClass: item.assetClass, quote: store.dashQuotes[key] || null, sparkline, return30d };
  });
});

const stats = computed(() => {
  const valid = cards.value.filter((c) => c.quote && c.quote.source !== "base");
  if (valid.length === 0) return null;
  const gainers = valid.filter((c) => c.quote!.percent > 0);
  const losers = valid.filter((c) => c.quote!.percent < 0);
  const flat = valid.length - gainers.length - losers.length;
  const avgPct = valid.reduce((s, c) => s + c.quote!.percent, 0) / valid.length;
  const best = valid.reduce((b, c) => c.quote!.percent > b.quote!.percent ? c : b, valid[0]);
  const worst = valid.reduce((w, c) => c.quote!.percent < w.quote!.percent ? c : w, valid[0]);
  const totalChange = valid.reduce((s, c) => s + (c.quote!.now - c.quote!.yesterday), 0);
  const gainSum = gainers.reduce((s, c) => s + c.quote!.percent, 0);
  const lossSum = losers.reduce((s, c) => s + c.quote!.percent, 0);
  return { total: valid.length, gainers: gainers.length, losers: losers.length, flat, avgPct, best, worst, totalChange, gainSum, lossSum };
});

function formatPrice(p: number): string {
  if (p >= 1000) return p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}
function formatPercent(p: number): string { return (p > 0 ? "+" : "") + (p * 100).toFixed(2) + "%"; }
function formatAmount(a: number): string { return (a > 0 ? "+" : "") + formatPrice(Math.abs(a)); }
function formatVolume(v: number | null | undefined): string {
  if (!v || v === 0) return "-";
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(0);
}
function formatMoney(v: number | null | undefined): string {
  if (!v || v === 0) return "-";
  if (v >= 1e12) return (v / 1e12).toFixed(2) + "万亿";
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(2);
}
function priceClass(p: number): string { return p > 0 ? "text-up" : p < 0 ? "text-down" : "text-flat"; }
function viewDetail(code: string, ac: string): void { router.push(`/stock/${code}?asset_class=${ac}`); }
function removeCard(code: string, ac: string): void {
  const key = `${ac}:${code}`;
  const chart = chartInstances.get(key);
  if (chart) { chart.dispose(); chartInstances.delete(key); }
  store.removeFromDash(code, ac as any);
}

// === 卡片拖拽调整大小 ===
let resizeCard: string | null = null;
let resizeStartX = 0;
let resizeStartW = 0;

function startResize(e: MouseEvent, key: string): void {
  resizeCard = key;
  resizeStartX = e.clientX;
  resizeStartW = cardWidths[key] || 0;
  document.addEventListener("mousemove", onResizeMove);
  document.addEventListener("mouseup", onResizeEnd);
  document.body.style.cursor = "ew-resize";
  document.body.style.userSelect = "none";
}

function onResizeMove(e: MouseEvent): void {
  if (!resizeCard) return;
  const delta = e.clientX - resizeStartX;
  const newW = Math.min(CARD_MAX_W, Math.max(CARD_MIN_W, resizeStartW + delta));
  cardWidths[resizeCard] = newW;
}

function onResizeEnd(): void {
  document.removeEventListener("mousemove", onResizeMove);
  document.removeEventListener("mouseup", onResizeEnd);
  document.body.style.cursor = "";
  document.body.style.userSelect = "";
  if (resizeCard) {
    const chart = chartInstances.get(resizeCard);
    if (chart) setTimeout(() => chart.resize(), 0);
    resizeCard = null;
  }
}

function getColors() {
  const cs = getComputedStyle(document.documentElement);
  return {
    up: cs.getPropertyValue("--color-up").trim() || "#EF4444",
    down: cs.getPropertyValue("--color-down").trim() || "#26A69A",
    fgSec: cs.getPropertyValue("--color-fg-secondary").trim() || "#94A3B8",
    fgMuted: cs.getPropertyValue("--color-fg-muted").trim() || "#64748B",
    grid: cs.getPropertyValue("--chart-grid").trim() || "rgba(51,65,85,0.2)",
    border: cs.getPropertyValue("--color-border").trim() || "#334155",
  };
}

function renderSparkline(key: string, klines: Kline[]): void {
  const el = document.getElementById("spark-" + key) as HTMLDivElement | null;
  if (!el || klines.length === 0) return;
  let chart = chartInstances.get(key);
  if (!chart) { chart = echarts.init(el, undefined, { renderer: "canvas" }); chartInstances.set(key, chart); }
  const c = getColors();
  const closes = klines.map(k => k.close);
  const volumes = klines.map(k => k.volume ?? 0);
  const lastPct = closes.length > 1 ? (closes[closes.length-1] - closes[0]) / closes[0] : 0;
  const lineColor = lastPct >= 0 ? c.up : c.down;
  const maxVal = Math.max(...closes);
  const minVal = Math.min(...closes);

  chart.setOption({
    backgroundColor: "transparent", animation: false,
    grid: [
      { left: 0, right: 0, top: 4, height: "70%" },
      { left: 0, right: 0, top: "78%", height: "22%" },
    ],
    xAxis: [
      { type: "category", show: false, boundaryGap: false, gridIndex: 0, data: klines.map((_, i) => i) },
      { type: "category", show: false, gridIndex: 1, data: klines.map((_, i) => i) },
    ],
    yAxis: [
      { type: "value", show: false, scale: true, gridIndex: 0, min: minVal * 0.995, max: maxVal * 1.005 },
      { type: "value", show: false, gridIndex: 1, scale: true },
    ],
    series: [
      {
        type: "line", data: closes, smooth: true, symbol: "none",
        lineStyle: { width: 1.8, color: lineColor },
        areaStyle: { color: lineColor, opacity: 0.1 },
        xAxisIndex: 0, yAxisIndex: 0,
        markPoint: {
          symbol: "circle", symbolSize: 5,
          data: [{ coord: [closes.length - 1, closes[closes.length - 1]], itemStyle: { color: lineColor } }],
          label: { show: false },
        },
      },
      {
        type: "bar", data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: closes[i] >= (closes[i-1] ?? closes[i]) ? c.up : c.down, opacity: 0.3 },
        })),
        xAxisIndex: 1, yAxisIndex: 1,
      },
    ],
  }, true);
}

function renderAllSparklines(): void {
  for (const card of cards.value) {
    if (card.sparkline && card.sparkline.length > 0) renderSparkline(card.key, card.sparkline);
  }
  lastUpdate.value = new Date().toLocaleTimeString("zh-CN");
}

function startAutoRefresh(): void { stopAutoRefresh(); refreshTimer.value = window.setInterval(() => store.refreshDash().then(() => setTimeout(renderAllSparklines, 100)), 30000); }
function stopAutoRefresh(): void { if (refreshTimer.value !== null) { clearInterval(refreshTimer.value); refreshTimer.value = null; } }
function handleResize(): void { chartInstances.forEach((chart) => chart.resize()); }
function handleRefresh(): void { store.refreshDash().then(() => window.setTimeout(renderAllSparklines, 100)); }

onMounted(async () => {
  await store.refreshDash();
  setTimeout(renderAllSparklines, 100);
  startAutoRefresh();
  window.addEventListener("resize", handleResize);
});
onBeforeUnmount(() => {
  stopAutoRefresh();
  window.removeEventListener("resize", handleResize);
  chartInstances.forEach((chart) => chart.dispose());
  chartInstances.clear();
});
</script>

<template>
  <div class="dash-view" v-loading="store.dashLoading">
    <!-- 页面工具栏 -->
    <div class="page-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">Dashboard</span>
        <span class="toolbar-count">{{ store.dashItems.length }} 个标的</span>
        <span v-if="lastUpdate" class="toolbar-update">更新于 {{ lastUpdate }}</span>
      </div>
      <div class="toolbar-right">
        <span class="auto-refresh-hint">每 30s 自动刷新</span>
        <button class="ui-icon-btn" @click="handleRefresh" :disabled="store.dashLoading" title="刷新">
          <RefreshCw :size="14" :class="{ 'anim-spin': store.dashLoading }" />
        </button>
      </div>
    </div>

    <!-- 概览统计栏 -->
    <div v-if="stats" class="stats-bar">
      <div class="stat-block">
        <span class="stat-num">{{ stats.total }}</span>
        <span class="stat-lbl">监控</span>
      </div>
      <div class="stat-block">
        <span class="stat-num text-up">{{ stats.gainers }}</span>
        <span class="stat-lbl">上涨</span>
      </div>
      <div class="stat-block">
        <span class="stat-num text-down">{{ stats.losers }}</span>
        <span class="stat-lbl">下跌</span>
      </div>
      <div class="stat-block">
        <span class="stat-num text-flat">{{ stats.flat }}</span>
        <span class="stat-lbl">平盘</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-block">
        <span class="stat-num" :class="priceClass(stats.avgPct)">{{ formatPercent(stats.avgPct) }}</span>
        <span class="stat-lbl">平均涨跌</span>
      </div>
      <div class="stat-block">
        <span class="stat-num text-up">{{ formatPercent(stats.gainSum) }}</span>
        <span class="stat-lbl">总涨幅</span>
      </div>
      <div class="stat-block">
        <span class="stat-num text-down">{{ formatPercent(stats.lossSum) }}</span>
        <span class="stat-lbl">总跌幅</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-block highlight">
        <span class="stat-num text-up">{{ formatPercent(stats.best.quote!.percent) }}</span>
        <span class="stat-lbl">最佳 {{ stats.best.code }}</span>
      </div>
      <div class="stat-block highlight">
        <span class="stat-num text-down">{{ formatPercent(stats.worst.quote!.percent) }}</span>
        <span class="stat-lbl">最差 {{ stats.worst.code }}</span>
      </div>
    </div>

    <el-alert v-if="store.dashError" :title="store.dashError" type="error" :closable="false" show-icon class="dash-alert" />

    <!-- 卡片网格 -->
    <div v-if="cards.length > 0" class="card-grid">
      <div v-for="card in cards" :key="card.key" class="dash-card ui-card"
        :style="cardWidths[card.key] ? { width: cardWidths[card.key] + 'px', flexShrink: 0 } : {}"
        @click="viewDetail(card.code, card.assetClass)">
        <!-- 卡片头部 -->
        <div class="card-top">
          <div class="card-id">
            <span class="card-code text-mono">{{ card.code }}</span>
            <MarketBadge :market="card.quote?.market ?? null" />
          </div>
          <button class="card-remove" @click.stop="removeCard(card.code, card.assetClass)" title="移除">
            <X :size="12" />
          </button>
        </div>

        <div v-if="card.quote && card.quote.source !== 'base'" class="card-body">
          <!-- 名称 -->
          <div class="card-name">{{ card.quote.name }}</div>

          <!-- 价格 + 涨跌 -->
          <div class="card-price-row">
            <span class="card-price text-mono" :class="priceClass(card.quote.percent)">{{ formatPrice(card.quote.now) }}</span>
            <div class="card-change" :class="priceClass(card.quote.percent)">
              <span class="card-pct text-mono">{{ formatPercent(card.quote.percent) }}</span>
              <span class="card-amt text-mono">{{ formatAmount(card.quote.now - card.quote.yesterday) }}</span>
            </div>
          </div>

          <!-- 迷你走势图（含成交量） -->
          <div :id="'spark-' + card.key" class="card-spark"></div>

          <!-- 30日收益率 -->
          <div v-if="card.return30d !== null" class="card-return-row">
            <span class="return-lbl">30日收益</span>
            <span class="return-val text-mono" :class="priceClass(card.return30d)">{{ formatPercent(card.return30d) }}</span>
          </div>

          <!-- 底部指标网格 -->
          <div class="card-stats">
            <div class="mini-stat">
              <span class="mini-lbl">开盘</span>
              <span class="mini-val text-mono">{{ card.quote.open_price ? formatPrice(card.quote.open_price) : "-" }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">最高</span>
              <span class="mini-val text-mono text-up">{{ formatPrice(card.quote.high) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">最低</span>
              <span class="mini-val text-mono text-down">{{ formatPrice(card.quote.low) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">振幅</span>
              <span class="mini-val text-mono">{{ card.quote.yesterday ? ((card.quote.high - card.quote.low) / card.quote.yesterday * 100).toFixed(2) : "0.00" }}%</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">成交量</span>
              <span class="mini-val text-mono">{{ formatVolume(card.quote.volume) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">成交额</span>
              <span class="mini-val text-mono">{{ card.quote.turnover ? formatMoney(card.quote.turnover) : "-" }}</span>
            </div>
            <div v-if="card.quote.pe_ratio" class="mini-stat">
              <span class="mini-lbl">市盈率</span>
              <span class="mini-val text-mono">{{ card.quote.pe_ratio.toFixed(2) }}</span>
            </div>
            <div v-if="card.quote.pb_ratio" class="mini-stat">
              <span class="mini-lbl">市净率</span>
              <span class="mini-val text-mono">{{ card.quote.pb_ratio.toFixed(2) }}</span>
            </div>
            <div v-if="card.quote.market_cap" class="mini-stat">
              <span class="mini-lbl">总市值</span>
              <span class="mini-val text-mono">{{ formatMoney(card.quote.market_cap) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">数据源</span>
              <span class="ui-source-badge">{{ card.quote.source }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">资产</span>
              <span class="ui-source-badge">{{ card.assetClass === "crypto" ? "加密" : "股票" }}</span>
            </div>
          </div>
        </div>

        <div v-else class="card-empty">
          <span>暂无数据</span>
        </div>
        <div class="card-resize-handle" @mousedown.prevent.stop="startResize($event, card.key)" title="拖拽调整宽度">
          <GripHorizontal :size="10" />
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!store.dashLoading" class="dash-empty">
      <LayoutGrid :size="48" style="color: var(--color-fg-muted); margin-bottom: 12px; opacity: 0.4" />
      <p>Dashboard 还没有卡片</p>
      <p class="dash-empty-hint">在自选列表中点击「加入 Dashboard」按钮添加</p>
      <button class="ui-btn ui-btn-primary" style="margin-top: 12px" @click="router.push('/watchlist')">前往自选列表</button>
    </div>
  </div>
</template>

<style scoped>
.dash-view { display: flex; flex-direction: column; gap: var(--space-4); }

/* 页面工具栏 */
.page-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: var(--space-2);
}
.toolbar-left { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: var(--space-3); }
.toolbar-title { font-size: 18px; font-weight: 700; color: var(--color-fg); }
.toolbar-count { font-size: 12px; color: var(--color-fg-muted); }
.toolbar-update { font-size: 11px; color: var(--color-fg-muted); font-family: var(--font-mono); }
.auto-refresh-hint { font-size: 11px; color: var(--color-fg-muted); }

/* 概览统计栏 */
.stats-bar {
  display: flex; gap: var(--space-4); flex-wrap: wrap; align-items: center;
  padding: var(--space-4) var(--space-5);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
}
.stat-block { display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 64px; }
.stat-num { font-family: var(--font-mono); font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat-lbl { font-size: 10px; color: var(--color-fg-muted); text-transform: uppercase; letter-spacing: 0.05em; white-space: nowrap; }
.stat-divider { width: 1px; height: 32px; background: var(--color-border-light); }
.stat-block.highlight { padding: 4px 8px; background: var(--color-muted); border-radius: var(--radius-md); }

.dash-alert { border-radius: var(--radius-md); }

/* 卡片网格 */
.card-grid {
  display: flex; flex-wrap: wrap; gap: var(--space-4);
}

.dash-card {
  flex: 1 1 var(--card-min-w); min-width: 300px; max-width: 100%;
  padding: var(--space-5);
  cursor: pointer;
  position: relative;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.dash-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-elevated);
}

.card-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--space-3);
}
.card-id { display: flex; align-items: center; gap: 6px; }
.card-code { font-size: 15px; font-weight: 700; color: var(--color-fg); }

.card-remove {
  display: flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border: none; border-radius: var(--radius-sm);
  background: transparent; cursor: pointer; color: var(--color-fg-muted);
  transition: all var(--transition-fast);
}
.card-remove:hover { color: var(--color-destructive); background: var(--color-down-bg); }

.card-body { display: flex; flex-direction: column; gap: var(--space-2); }
.card-name { font-size: 13px; color: var(--color-fg-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.card-price-row { display: flex; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.card-price { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.card-change { display: flex; flex-direction: column; gap: 1px; }
.card-pct { font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; }
.card-amt { font-size: 11px; font-weight: 500; font-variant-numeric: tabular-nums; opacity: 0.8; }

.card-spark { width: 100%; height: 90px; margin: var(--space-1) 0; }

.card-return-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 8px; background: var(--color-muted); border-radius: var(--radius-sm);
}
.return-lbl { font-size: 10px; color: var(--color-fg-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.return-val { font-size: 13px; font-weight: 700; }

.card-stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(80px, 1fr)); gap: 6px 8px;
  padding-top: var(--space-3); border-top: 1px solid var(--color-border-light);
}
.mini-stat { display: flex; flex-direction: column; gap: 1px; }
.mini-lbl { font-size: 9px; color: var(--color-fg-muted); text-transform: uppercase; letter-spacing: 0.03em; }
.mini-val { font-size: 12px; font-weight: 500; color: var(--color-fg); }

.card-empty { padding: var(--space-8) 0; text-align: center; color: var(--color-fg-muted); font-size: 13px; }

.card-resize-handle {
  position: absolute; bottom: 4px; right: 4px;
  width: 20px; height: 20px; cursor: ew-resize;
  display: flex; align-items: flex-end; justify-content: flex-end;
  opacity: 0; transition: opacity var(--transition-fast);
  color: var(--color-fg-muted);
  border-radius: 0 0 var(--radius-lg) 0;
}
.dash-card:hover .card-resize-handle { opacity: 1; }
.card-resize-handle:hover { color: var(--color-primary); }

.anim-spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.dash-empty { padding: var(--space-16) var(--space-5); text-align: center; color: var(--color-fg-muted); font-size: 14px; }
.dash-empty-hint { font-size: 12px; margin-top: 4px; }

@media (max-width: 768px) {
  .stats-bar { gap: var(--space-3); }
  .stat-block { min-width: 50px; }
  .stat-num { font-size: 16px; }
  .dash-card { flex: 1 1 100%; min-width: unset; }
  .card-spark { height: 70px; }
}
@media (max-width: 480px) {
  .stats-bar { gap: var(--space-2); padding: var(--space-3); }
  .stat-block { min-width: 45px; }
  .stat-num { font-size: 14px; }
  .card-price { font-size: 24px; }
  .card-stats { grid-template-columns: 1fr 1fr; }
}
</style>
