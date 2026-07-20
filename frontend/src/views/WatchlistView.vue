<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useStockStore } from "@/stores/stock";
import { searchSymbols } from "@/api";
import type { Symbol as StockSymbol, Quote } from "@/types";

const store = useStockStore();
const router = useRouter();
const searchQuery = ref("");
const searchResults = ref<StockSymbol[]>([]);
const searching = ref(false);
const refreshTimer = ref<number | null>(null);
const prevPrices = ref<Record<string, number>>({});

const marketLabel: Record<string, string> = {
  cn_a: "A",
  hk: "HK",
  us: "US",
  crypto: "COIN",
};

function formatPrice(price: number): string {
  if (price >= 1000) return price.toFixed(2);
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

function flashClass(quote: Quote): string {
  const prev = prevPrices.value[quote.code];
  if (prev === undefined || prev === quote.now) return "";
  return prev < quote.now ? "flash-up" : "flash-down";
}

function updatePrevPrices() {
  prevPrices.value = Object.fromEntries(store.quotes.map((q) => [q.code, q.now]));
}

function viewDetail(code: string): void {
  router.push(`/stock/${code}?asset_class=${store.assetClass}`);
}

async function doSearch(): Promise<void> {
  const query = searchQuery.value.trim();
  if (!query) {
    searchResults.value = [];
    return;
  }
  searching.value = true;
  try {
    searchResults.value = await searchSymbols(query, store.source, store.assetClass);
  } catch (e) {
    ElMessage.error("搜索失败：" + (e instanceof Error ? e.message : String(e)));
    searchResults.value = [];
  } finally {
    searching.value = false;
  }
}

function addFromSearch(code: string): void {
  store.addCode(code);
  store.refreshOne(code);
  ElMessage.success(`已添加 ${code}`);
}

function startAutoRefresh(): void {
  stopAutoRefresh();
  refreshTimer.value = window.setInterval(async () => {
    await store.refresh();
    updatePrevPrices();
  }, 30000);
}

function stopAutoRefresh(): void {
  if (refreshTimer.value !== null) {
    clearInterval(refreshTimer.value);
    refreshTimer.value = null;
  }
}

const isLoading = computed(() => store.loading && store.quotes.length === 0);

onMounted(() => {
  store.refresh().then(updatePrevPrices);
  startAutoRefresh();
});

onBeforeUnmount(() => {
  stopAutoRefresh();
});
</script>

<template>
  <div class="watchlist-view">
    <!-- 搜索栏 -->
    <div class="search-section">
      <div class="search-row">
        <el-input
          v-model="searchQuery"
          :placeholder="store.assetClass === 'crypto'
            ? '搜索加密货币名称或 ID，如 bitcoin / ethereum'
            : '搜索股票代码或名称，如 格力电器 / SH510500'"
          clearable
          size="large"
          @keyup.enter="doSearch"
        >
          <template #prefix>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: var(--color-fg-muted)">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </template>
        </el-input>
        <el-button type="primary" size="large" :loading="searching" @click="doSearch">
          搜索
        </el-button>
      </div>

      <div v-if="searchResults.length > 0" class="search-results">
        <span class="search-hint">搜索结果（点击添加到自选）</span>
        <div class="search-tags">
          <button
            v-for="item in searchResults"
            :key="item.code"
            class="search-tag"
            @click="addFromSearch(item.code)"
          >
            <span class="search-tag-code">{{ item.code }}</span>
            <span class="search-tag-name">{{ item.name }}</span>
            <span class="search-tag-market">{{ marketLabel[item.market || ""] || "?" }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 自选列表 -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <span>自选列表</span>
          <span class="card-count">{{ store.watchlist.length }}</span>
        </div>
        <div class="card-actions">
          <span class="auto-refresh-hint">每 30s 自动刷新</span>
          <button class="btn-refresh" @click="store.refresh().then(updatePrevPrices)" :disabled="store.loading">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
          </button>
        </div>
      </div>

      <el-alert
        v-if="store.error"
        :title="store.error"
        type="error"
        :closable="false"
        show-icon
        class="error-alert"
      />

      <!-- 骨架屏 -->
      <div v-if="isLoading" class="skeleton-list">
        <div v-for="i in 4" :key="i" class="skeleton-row">
          <div class="skeleton-line" style="width: 80px"></div>
          <div class="skeleton-line" style="width: 120px; flex: 1"></div>
          <div class="skeleton-line" style="width: 70px"></div>
          <div class="skeleton-line" style="width: 60px"></div>
        </div>
      </div>

      <!-- 数据表 -->
      <div v-else-if="store.quotes.length > 0" class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th class="col-code">代码</th>
              <th class="col-name">名称</th>
              <th class="col-price ta-right">最新价</th>
              <th class="col-pct ta-right">涨跌幅</th>
              <th class="col-high ta-right">最高</th>
              <th class="col-low ta-right">最低</th>
              <th class="col-src ta-center">来源</th>
              <th class="col-action ta-center">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="quote in store.quotes"
              :key="quote.code"
              :class="flashClass(quote)"
              class="data-row"
              @click="viewDetail(quote.code)"
            >
              <td class="col-code text-mono">{{ quote.code }}</td>
              <td class="col-name">{{ quote.name }}</td>
              <td class="col-price ta-right text-mono">{{ formatPrice(quote.now) }}</td>
              <td class="col-pct ta-right text-mono">
                <span :class="priceClass(quote.percent)">{{ formatPercent(quote.percent) }}</span>
              </td>
              <td class="col-high ta-right text-mono text-secondary">{{ formatPrice(quote.high) }}</td>
              <td class="col-low ta-right text-mono text-secondary">{{ formatPrice(quote.low) }}</td>
              <td class="col-src ta-center">
                <span class="source-badge">{{ quote.source }}</span>
              </td>
              <td class="col-action ta-center">
                <button class="btn-remove" @click.stop="store.removeCode(quote.code)" title="删除">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--color-fg-muted); margin-bottom: 12px">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <p>还没有自选，搜索并添加{{ store.assetClass === "crypto" ? "加密货币" : "股票" }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.watchlist-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 搜索区 */
.search-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.search-row {
  display: flex;
  gap: var(--space-3);
}

.search-results {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.search-hint {
  font-size: 12px;
  color: var(--color-fg-muted);
}

.search-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.search-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-elevated);
  cursor: pointer;
  transition: all var(--transition-fast);
  min-height: 32px;
}

.search-tag:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-hover);
}

.search-tag-code {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-fg);
}

.search-tag-name {
  font-size: 12px;
  color: var(--color-fg-secondary);
}

.search-tag-market {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  background: var(--color-muted);
  color: var(--color-fg-muted);
  letter-spacing: 0.05em;
}

/* 卡片 */
.card {
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border-light);
}

.card-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 15px;
  font-weight: 600;
}

.card-count {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: var(--radius-sm);
  background: var(--color-muted);
  color: var(--color-fg-secondary);
}

.card-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.auto-refresh-hint {
  font-size: 11px;
  color: var(--color-fg-muted);
}

.btn-refresh {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  cursor: pointer;
  color: var(--color-fg-secondary);
  transition: all var(--transition-fast);
}

.btn-refresh:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-alert {
  margin: var(--space-4) var(--space-5) 0;
}

/* 骨架屏 */
.skeleton-list {
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.skeleton-row {
  display: flex;
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-2) 0;
}

/* 数据表 */
.table-wrapper {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table thead th {
  padding: 10px var(--space-5);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-fg-secondary);
  background: var(--color-muted);
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

.data-table tbody td {
  padding: 12px var(--space-5);
  border-bottom: 1px solid var(--color-border-light);
  white-space: nowrap;
}

.data-row {
  cursor: pointer;
  transition: background var(--transition-fast);
}

.data-row:hover {
  background: var(--color-bg-hover);
}

.ta-right { text-align: right; }
.ta-center { text-align: center; }

.col-code { font-weight: 600; }
.col-pct { font-weight: 600; }

.source-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  background: var(--color-muted);
  color: var(--color-fg-secondary);
}

.btn-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  color: var(--color-fg-muted);
  transition: all var(--transition-fast);
}

.btn-remove:hover {
  color: var(--color-destructive);
  background: var(--color-down-bg);
}

/* 空状态 */
.empty-state {
  padding: var(--space-12) var(--space-5);
  text-align: center;
  color: var(--color-fg-muted);
  font-size: 14px;
}

/* 响应式 */
@media (max-width: 768px) {
  .col-high, .col-low {
    display: none;
  }
}

@media (max-width: 640px) {
  .col-src {
    display: none;
  }
  .auto-refresh-hint {
    display: none;
  }
  .data-table thead th,
  .data-table tbody td {
    padding-left: var(--space-3);
    padding-right: var(--space-3);
  }
}
</style>
