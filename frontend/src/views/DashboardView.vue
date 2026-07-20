<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useStockStore } from "@/stores/stock";
import * as echarts from "echarts";
import type { Quote, Kline } from "@/types";

const store = useStockStore();
const router = useRouter();
const refreshTimer = ref<number | null>(null);
const chartInstances = new Map<string, echarts.ECharts>();

const marketLabel: Record<string, string> = {
  cn_a: "A股", hk: "港股", us: "美股", crypto: "加密",
};

const marketBadgeClass: Record<string, string> = {
  cn_a: "market-a", hk: "market-hk", us: "market-us", crypto: "market-crypto",
};

interface DashCard {
  key: string;
  code: string;
  assetClass: string;
  quote: Quote | null;
  sparkline: Kline[] | null;
}

const cards = computed<DashCard[]>(() => {
  return store.dashItems.map((item) => {
    const key = `${item.assetClass}:${item.code}`;
    return {
      key,
      code: item.code,
      assetClass: item.assetClass,
      quote: store.dashQuotes[key] || null,
      sparkline: store.dashSparklines[key] || null,
    };
  });
});

// 统计指标
const stats = computed(() => {
  const valid = cards.value.filter((c) => c.quote && c.quote.source !== "base");
  if (valid.length === 0) return null;

  const gainers = valid.filter((c) => c.quote!.percent > 0);
  const losers = valid.filter((c) => c.quote!.percent < 0);
  const avgPct = valid.reduce((sum, c) => sum + c.quote!.percent, 0) / valid.length;
  const best = valid.reduce((best, c) => c.quote!.percent > best.quote!.percent ? c : best, valid[0]);
  const worst = valid.reduce((worst, c) => c.quote!.percent < worst.quote!.percent ? c : worst, valid[0]);

  return {
    total: valid.length,
    gainers: gainers.length,
    losers: losers.length,
    avgPct,
    best,
    worst,
  };
});

function formatPrice(p: number): string {
  if (p >= 1000) return p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}

function formatPercent(p: number): string {
  return (p > 0 ? "+" : "") + (p * 100).toFixed(2) + "%";
}

function priceClass(p: number): string {
  return p > 0 ? "text-up" : p < 0 ? "text-down" : "text-flat";
}

function viewDetail(code: string, ac: string): void {
  router.push(`/stock/${code}?asset_class=${ac}`);
}

function removeCard(code: string, ac: string): void {
  const key = `${ac}:${code}`;
  const chart = chartInstances.get(key);
  if (chart) { chart.dispose(); chartInstances.delete(key); }
  store.removeFromDash(code, ac as any);
}

function getColors() {
  const cs = getComputedStyle(document.documentElement);
  return {
    up: cs.getPropertyValue("--color-up").trim() || "#EF4444",
    down: cs.getPropertyValue("--color-down").trim() || "#26A69A",
    fgSec: cs.getPropertyValue("--color-fg-secondary").trim() || "#94A3B8",
    grid: cs.getPropertyValue("--chart-grid").trim() || "rgba(51,65,85,0.2)",
  };
}

function renderSparkline(key: string, klines: Kline[]): void {
  const el = document.getElementById("spark-" + key) as HTMLDivElement | null;
  if (!el || klines.length === 0) return;

  let chart = chartInstances.get(key);
  if (!chart) {
    chart = echarts.init(el, undefined, { renderer: "canvas" });
    chartInstances.set(key, chart);
  }

  const c = getColors();
  const closes = klines.map(k => k.close);
  const lastPct = closes.length > 1 ? (closes[closes.length-1] - closes[0]) / closes[0] : 0;
  const lineColor = lastPct >= 0 ? c.up : c.down;

  chart.setOption({
    backgroundColor: "transparent",
    animation: false,
    grid: { left: 0, right: 0, top: 2, bottom: 0 },
    xAxis: { type: "category", show: false, boundaryGap: false, data: klines.map((_, i) => i) },
    yAxis: { type: "value", show: false, scale: true },
    series: [{
      type: "line",
      data: closes,
      smooth: true,
      symbol: "none",
      lineStyle: { width: 1.5, color: lineColor },
      areaStyle: { color: lineColor, opacity: 0.08 },
    }],
  }, true);
}

function renderAllSparklines(): void {
  for (const card of cards.value) {
    if (card.sparkline && card.sparkline.length > 0) {
      renderSparkline(card.key, card.sparkline);
    }
  }
}

function startAutoRefresh(): void {
  stopAutoRefresh();
  refreshTimer.value = window.setInterval(() => store.refreshDash(), 30000);
}

function stopAutoRefresh(): void {
  if (refreshTimer.value !== null) { clearInterval(refreshTimer.value); refreshTimer.value = null; }
}

function handleResize(): void {
  chartInstances.forEach((chart) => chart.resize());
}

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
        <span class="stat-num" :class="priceClass(stats.avgPct)">{{ formatPercent(stats.avgPct) }}</span>
        <span class="stat-lbl">平均涨跌</span>
      </div>
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
      <div v-for="card in cards" :key="card.key" class="dash-card ui-card" @click="viewDetail(card.code, card.assetClass)">
        <!-- 卡片头部 -->
        <div class="card-top">
          <div class="card-id">
            <span class="card-code text-mono">{{ card.code }}</span>
            <span v-if="card.quote?.market" :class="['market-badge', marketBadgeClass[card.quote.market] || '']">
              {{ marketLabel[card.quote.market] || "?" }}
            </span>
          </div>
          <button class="card-remove" @click.stop="removeCard(card.code, card.assetClass)" title="移除">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div v-if="card.quote && card.quote.source !== 'base'" class="card-body">
          <!-- 名称 -->
          <div class="card-name">{{ card.quote.name }}</div>

          <!-- 价格 + 涨跌 -->
          <div class="card-price-row">
            <span class="card-price text-mono" :class="priceClass(card.quote.percent)">{{ formatPrice(card.quote.now) }}</span>
            <span class="card-pct text-mono" :class="priceClass(card.quote.percent)">{{ formatPercent(card.quote.percent) }}</span>
          </div>

          <!-- 迷你走势图 -->
          <div :id="'spark-' + card.key" class="card-spark"></div>

          <!-- 底部指标 -->
          <div class="card-stats">
            <div class="mini-stat">
              <span class="mini-lbl">高</span>
              <span class="mini-val text-mono text-up">{{ formatPrice(card.quote.high) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">低</span>
              <span class="mini-val text-mono text-down">{{ formatPrice(card.quote.low) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">昨收</span>
              <span class="mini-val text-mono">{{ formatPrice(card.quote.yesterday) }}</span>
            </div>
            <div class="mini-stat">
              <span class="mini-lbl">源</span>
              <span class="ui-source-badge">{{ card.quote.source }}</span>
            </div>
          </div>
        </div>

        <div v-else class="card-empty">
          <span>暂无数据</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!store.dashLoading" class="dash-empty">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--color-fg-muted); margin-bottom: 12px">
        <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
      </svg>
      <p>Dashboard 还没有卡片</p>
      <p class="dash-empty-hint">在自选列表中点击「加入 Dashboard」按钮添加</p>
      <button class="ui-btn ui-btn-primary" style="margin-top: 12px" @click="router.push('/')">前往自选列表</button>
    </div>
  </div>
</template>

<style scoped>
.dash-view { display: flex; flex-direction: column; gap: var(--space-4); }

/* 概览统计栏 */
.stats-bar {
  display: flex; gap: var(--space-3); flex-wrap: wrap;
  padding: var(--space-4) var(--space-5);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
}
.stat-block { display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 70px; }
.stat-num { font-family: var(--font-mono); font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
.stat-lbl { font-size: 10px; color: var(--color-fg-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.stat-block.highlight { padding: 4px 12px; border-left: 1px solid var(--color-border-light); }

.dash-alert { border-radius: var(--radius-md); }

/* 卡片网格 */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-4);
}

.dash-card {
  padding: var(--space-4);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.dash-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-elevated);
}

.card-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--space-2);
}
.card-id { display: flex; align-items: center; gap: 6px; }
.card-code { font-size: 14px; font-weight: 700; color: var(--color-fg); }

.market-badge {
  font-size: 9px; font-weight: 700; padding: 1px 5px;
  border-radius: var(--radius-sm); letter-spacing: 0.02em;
  white-space: nowrap; line-height: 1.5;
}
.market-a { background: rgba(239,68,68,0.15); color: var(--color-up); }
.market-hk { background: rgba(245,158,11,0.15); color: #F59E0B; }
.market-us { background: rgba(59,130,246,0.15); color: var(--color-primary); }
.market-crypto { background: rgba(139,92,246,0.15); color: var(--color-accent); }

.card-remove {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border: none; border-radius: var(--radius-sm);
  background: transparent; cursor: pointer; color: var(--color-fg-muted);
  transition: all var(--transition-fast);
}
.card-remove:hover { color: var(--color-destructive); background: var(--color-down-bg); }

.card-body { display: flex; flex-direction: column; gap: var(--space-2); }
.card-name { font-size: 12px; color: var(--color-fg-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.card-price-row { display: flex; align-items: baseline; gap: var(--space-2); }
.card-price { font-size: 24px; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.card-pct { font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }

.card-spark { width: 100%; height: 50px; margin: 2px 0; }

.card-stats {
  display: grid; grid-template-columns: 1fr 1fr; gap: 4px 8px;
  padding-top: var(--space-2); border-top: 1px solid var(--color-border-light);
}
.mini-stat { display: flex; align-items: center; gap: 4px; }
.mini-lbl { font-size: 10px; color: var(--color-fg-muted); }
.mini-val { font-size: 11px; font-weight: 500; color: var(--color-fg); }

.card-empty { padding: var(--space-8) 0; text-align: center; color: var(--color-fg-muted); font-size: 13px; }

/* 空状态 */
.dash-empty { padding: var(--space-16) var(--space-5); text-align: center; color: var(--color-fg-muted); font-size: 14px; }
.dash-empty-hint { font-size: 12px; margin-top: 4px; }

@media (max-width: 640px) {
  .stats-bar { gap: var(--space-2); padding: var(--space-3); }
  .stat-block { min-width: 55px; }
  .stat-num { font-size: 16px; }
  .card-grid { grid-template-columns: 1fr; }
}
</style>
