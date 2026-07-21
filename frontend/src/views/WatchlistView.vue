<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useStockStore } from "@/stores/stock";
import { searchSymbols } from "@/api";
import type { Symbol as StockSymbol, Quote, Market } from "@/types";

const store = useStockStore();
const router = useRouter();
const searchQuery = ref("");
const searchResults = ref<StockSymbol[]>([]);
const searching = ref(false);
const refreshTimer = ref<number | null>(null);
const prevPrices = ref<Record<string, number>>({});

const marketLabel: Record<string, string> = {
  cn_a: "A股",
  hk: "港股",
  us: "美股",
  index: "指数",
  fund: "基金",
  future: "期指",
  option: "期权",
  commodity: "商品",
  crypto: "加密",
};

const marketShort: Record<string, string> = {
  cn_a: "A",
  hk: "HK",
  us: "US",
  index: "IDX",
  fund: "FND",
  future: "FUT",
  option: "OPT",
  commodity: "COM",
  crypto: "COIN",
};

const marketBadgeClass: Record<string, string> = {
  cn_a: "market-a",
  hk: "market-hk",
  us: "market-us",
  index: "market-index",
  fund: "market-fund",
  future: "market-future",
  option: "market-option",
  commodity: "market-commodity",
  crypto: "market-crypto",
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

function isValidCode(query: string): boolean {
  const u = query.trim().toUpperCase();
  if (u.length < 4) return false;
  if (/^SH\d{4,6}$/.test(u) || /^SZ\d{4,6}$/.test(u)) return true;
  for (const p of ["HK", "US", "FUT", "COM", "OPT"]) {
    if (u.startsWith(p) && u.length > p.length + 1) return true;
  }
  return false;
}

/* 前端推断市场类型，与后端 detect_market() 对齐 */
function detectMarket(code: string): Market | null {
  const u = code.toUpperCase();
  if (u.startsWith("FUT")) return "future";
  if (u.startsWith("COM")) return "commodity";
  if (u.startsWith("OPT")) return "option";
  if (u.startsWith("SH")) {
    const num = u.slice(2);
    if (/^000/.test(num)) return "index";
    if (/^5/.test(num)) return "fund";
    return "cn_a";
  }
  if (u.startsWith("SZ")) {
    const num = u.slice(2);
    if (/^399/.test(num)) return "index";
    if (/^1[568]/.test(num)) return "fund";
    return "cn_a";
  }
  if (u.startsWith("HK")) {
    const rest = u.slice(2);
    if (/^(HSI|HSTECH|HSCEI)$/.test(rest)) return "index";
    return "hk";
  }
  if (u.startsWith("US")) {
    const rest = u.slice(2);
    if (/^(DJI|IXIC|INX|SPX)$/.test(rest)) return "index";
    if (/^(XAU|XAG|GC|CL|SI|NG)$/.test(rest)) return "commodity";
    return "us";
  }
  return null;
}

/* 为搜索 API 覆盖不到的市场类型构造候选代码 */
function constructCandidates(query: string): StockSymbol[] {
  const u = query.trim().toUpperCase();
  const codes: string[] = [];
  const now = new Date();
  const currentMonth = now.getMonth() + 1; // 1-12

  // 纯数字: 期货模糊匹配 + A股/美股猜测
  if (/^\d{2,4}$/.test(u)) {
    if (u.length === 2) {
      // 年份 -> 仅当前月及以后(减少无效候选)
      for (let m = currentMonth; m <= 12; m++) {
        const mm = String(m).padStart(2, "0");
        for (const p of ["IF","IC","IH","IM"]) codes.push("FUT" + p + u + mm);
      }
    } else if (u.length === 3) {
      // 年份+月份首数字 -> 补全月份个位 0-9
      for (let d = 0; d <= 9; d++) {
        for (const p of ["IF","IC","IH","IM"]) codes.push("FUT" + p + u + d);
      }
    } else {
      // 4位 = YYMM 精确匹配
      for (const p of ["IF","IC","IH","IM"]) codes.push("FUT" + p + u);
    }
    codes.push("SH" + u);
    codes.push("SZ" + u);
    codes.push("US" + u);
  }
  // 字母: 尝试商品/期权
  if (/^[A-Z]{3,5}$/.test(u)) {
    codes.push("COM" + u);
    codes.push("OPT" + u);
  }
  // 字母+数字: 期货/商品/期权
  if (/^[A-Z]{2,4}\d{2,4}$/.test(u) && u.length >= 4) {
    codes.push("FUT" + u);
    codes.push("COM" + u);
    codes.push("OPT" + u);
  }

  return codes.map((code) => ({
    code,
    name: code,
    market: detectMarket(code),
    asset_class: store.assetClass,
  }));
}

async function doSearch(): Promise<void> {
  const query = searchQuery.value.trim();
  if (!query) {
    searchResults.value = [];
    return;
  }

  // 精确代码: 直接添加
  if (isValidCode(query)) {
    store.addCode(query);
    store.refreshOne(query);
    searchQuery.value = "";
    searchResults.value = [];
    return;
  }

  searching.value = true;
  const apiResults: StockSymbol[] = [];
  try {
    // 1. 搜索 API（覆盖股票/指数/基金/加密）
    apiResults.push(...(await searchSymbols(query, store.source, store.assetClass)));
  } catch (e) {
    ElMessage.error("搜索失败：" + (e instanceof Error ? e.message : String(e)));
  }

  // 2. 构造候选代码（覆盖期货/商品/期权/其他）
  const apiCodes = new Set(apiResults.map((r) => r.code));
  const constructed = constructCandidates(query)
    .filter((c) => !apiCodes.has(c.code))
    .slice(0, 10);

  // 3. 合并结果
  searchResults.value = [...apiResults, ...constructed];
  searching.value = false;
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
    <!-- 页面工具栏 -->
    <div class="page-toolbar">
      <div class="ui-segmented">
        <button
          :class="['ui-segmented-btn', { active: store.assetClass === 'stock' }]"
          @click="store.setAssetClass('stock')"
        >股票</button>
        <button
          :class="['ui-segmented-btn', { active: store.assetClass === 'crypto' }]"
          @click="store.setAssetClass('crypto')"
        >加密货币</button>
      </div>
      <select
        v-if="store.assetClass === 'stock'"
        :value="store.source"
        @change="store.setSource(($event.target as HTMLSelectElement).value as any)"
        class="ui-select"
      >
        <option value="auto">自动兜底</option>
        <option value="tencent">腾讯</option>
        <option value="sina">新浪</option>
        <option value="eastmoney">东方财富</option>
      </select>
      <select
        v-else
        :value="store.source"
        @change="store.setSource(($event.target as HTMLSelectElement).value as any)"
        class="ui-select"
      >
        <option value="auto">自动兜底</option>
        <option value="coingecko">CoinGecko</option>
        <option value="binance">Binance</option>
      </select>
    </div>

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
        <button class="ui-btn ui-btn-primary ui-btn-lg" :disabled="searching" @click="doSearch">
          <svg v-if="searching" class="spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
          {{ searching ? "搜索中" : "搜索" }}
        </button>
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
            <span
              v-if="item.market"
              :class="['market-badge', marketBadgeClass[item.market] || '']"
            >{{ marketLabel[item.market] || "?" }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 自选列表 -->
    <div class="ui-card">
      <div class="ui-card-header">
        <div class="card-title">
          <span>自选列表</span>
          <span class="card-count">{{ store.watchlist.length }}</span>
        </div>
        <div class="card-actions">
          <span class="auto-refresh-hint">每 30s 自动刷新</span>
          <button class="ui-icon-btn" @click="store.refresh().then(updatePrevPrices)" :disabled="store.loading">
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
              <td class="col-code">
                <div class="code-cell">
                  <span class="text-mono">{{ quote.code }}</span>
                  <span
                    v-if="quote.market"
                    :class="['market-badge', marketBadgeClass[quote.market] || '']"
                  >{{ marketLabel[quote.market] || "?" }}</span>
                </div>
              </td>
              <td class="col-name">{{ quote.name }}</td>
              <td class="col-price ta-right text-mono">{{ formatPrice(quote.now) }}</td>
              <td class="col-pct ta-right text-mono">
                <span :class="priceClass(quote.percent)">{{ formatPercent(quote.percent) }}</span>
              </td>
              <td class="col-high ta-right text-mono text-secondary">{{ formatPrice(quote.high) }}</td>
              <td class="col-low ta-right text-mono text-secondary">{{ formatPrice(quote.low) }}</td>
              <td class="col-src ta-center">
                <span class="ui-source-badge">{{ quote.source }}</span>
              </td>
              <td class="col-action ta-center">
                <div class="action-group">
                  <button
                    class="btn-dash"
                    :class="{ 'btn-dash-active': store.isInDash(quote.code, store.assetClass) }"
                    @click.stop="store.isInDash(quote.code, store.assetClass)
                      ? store.removeFromDash(quote.code, store.assetClass)
                      : store.addToDash(quote.code, store.assetClass)"
                    :title="store.isInDash(quote.code, store.assetClass) ? '从 Dashboard 移除' : '加入 Dashboard'"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                      <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
                    </svg>
                  </button>
                  <button class="btn-remove" @click.stop="store.removeCode(quote.code)" title="删除">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>
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

/* 页面工具栏 */
.page-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
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

/* 卡片标题（卡片本身用 .ui-card 共享类） */
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

.col-code {
  font-weight: 600;
}

.code-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.market-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.02em;
  white-space: nowrap;
  line-height: 1.5;
  flex-shrink: 0;
}

.market-a {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-up);
}

.market-hk {
  background: rgba(245, 158, 11, 0.15);
  color: #F59E0B;
}

.market-us {
  background: rgba(59, 130, 246, 0.15);
  color: var(--color-primary);
}

.market-index {
  background: rgba(139, 92, 246, 0.15);
  color: var(--color-accent);
}

.market-fund {
  background: rgba(34, 197, 94, 0.15);
  color: #22C55E;
}

.market-future {
  background: rgba(236, 72, 153, 0.15);
  color: #EC4899;
}

.market-option {
  background: rgba(14, 165, 233, 0.15);
  color: #0EA5E9;
}

.market-commodity {
  background: rgba(217, 119, 6, 0.15);
  color: #D97706;
}

.market-crypto {
  background: rgba(139, 92, 246, 0.15);
  color: var(--color-accent);
}
.col-pct { font-weight: 600; }

/* 数据源标签用共享 .ui-source-badge */

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

.action-group {
  display: inline-flex;
  gap: 4px;
}

.btn-dash {
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

.btn-dash:hover {
  color: var(--color-primary);
  background: rgba(59, 130, 246, 0.1);
}

.btn-dash-active {
  color: var(--color-primary);
  background: rgba(59, 130, 246, 0.15);
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
