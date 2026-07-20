<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useStockStore } from "@/stores/stock";
import { searchSymbols } from "@/api";
import type { Symbol as StockSymbol } from "@/types";

const store = useStockStore();
const router = useRouter();
const searchQuery = ref("");
const searchResults = ref<StockSymbol[]>([]);
const searching = ref(false);
const refreshTimer = ref<number | null>(null);

const marketLabel: Record<string, string> = {
  cn_a: "A股",
  hk: "港股",
  us: "美股",
  crypto: "加密",
};

function percentClass(percent: number): string {
  if (percent > 0) return "text-up";
  if (percent < 0) return "text-down";
  return "text-flat";
}

function formatPercent(percent: number): string {
  return `${(percent * 100).toFixed(2)}%`;
}

function viewDetail(code: string): void {
  router.push(`/stock/${code}`);
}

async function doSearch(): Promise<void> {
  const query = searchQuery.value.trim();
  if (!query) {
    searchResults.value = [];
    return;
  }
  searching.value = true;
  try {
    searchResults.value = await searchSymbols(query, store.source);
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
  refreshTimer.value = window.setInterval(() => store.refresh(), 30000);
}

function stopAutoRefresh(): void {
  if (refreshTimer.value !== null) {
    clearInterval(refreshTimer.value);
    refreshTimer.value = null;
  }
}

onMounted(() => {
  startAutoRefresh();
});
</script>

<template>
  <div class="watchlist-view">
    <!-- 搜索区 -->
    <el-card class="search-card" shadow="never">
      <div class="search-row">
        <el-input
          v-model="searchQuery"
          placeholder="输入股票代码或名称搜索，如 格力电器 / SH510500"
          clearable
          @keyup.enter="doSearch"
        />
        <el-button type="primary" :loading="searching" @click="doSearch">搜索</el-button>
        <el-button @click="store.refresh()" :loading="store.loading">刷新行情</el-button>
      </div>
      <div v-if="searchResults.length > 0" class="search-results">
        <el-text type="info" size="small">搜索结果（点击添加到自选）：</el-text>
        <div class="search-list">
          <el-tag
            v-for="item in searchResults"
            :key="item.code"
            class="search-tag"
            @click="addFromSearch(item.code)"
          >
            {{ item.code }} · {{ item.name }}
            <span class="market-badge">{{ marketLabel[item.market || ""] || "其他" }}</span>
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 自选列表 -->
    <el-card shadow="never" class="watchlist-card">
      <template #header>
        <div class="card-header">
          <span>自选列表（{{ store.watchlist.length }}）</span>
          <el-text type="info" size="small">每 30 秒自动刷新</el-text>
        </div>
      </template>

      <el-alert
        v-if="store.error"
        :title="store.error"
        type="error"
        :closable="false"
        show-icon
        class="error-alert"
      />

      <el-table
        :data="store.quotes"
        v-loading="store.loading"
        style="width: 100%"
        @row-click="(row: any) => viewDetail(row.code)"
        row-key="code"
      >
        <el-table-column prop="code" label="代码" width="120" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="now" label="最新价" width="100" align="right">
          <template #default="{ row }">
            {{ row.now.toFixed(3) }}
          </template>
        </el-table-column>
        <el-table-column prop="percent" label="涨跌幅" width="110" align="right">
          <template #default="{ row }">
            <span :class="percentClass(row.percent)">{{ formatPercent(row.percent) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="high" label="最高" width="90" align="right">
          <template #default="{ row }">{{ row.high.toFixed(3) }}</template>
        </el-table-column>
        <el-table-column prop="low" label="最低" width="90" align="right">
          <template #default="{ row }">{{ row.low.toFixed(3) }}</template>
        </el-table-column>
        <el-table-column prop="yesterday" label="昨收" width="90" align="right">
          <template #default="{ row }">{{ row.yesterday.toFixed(3) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="数据源" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.source }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button
              size="small"
              type="danger"
              link
              @click.stop="store.removeCode(row.code)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!store.loading && store.quotes.length === 0"
        description="还没有自选，搜索并添加股票"
      />
    </el-card>
  </div>
</template>

<style scoped>
.watchlist-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.search-row {
  display: flex;
  gap: 12px;
}

.search-results {
  margin-top: 12px;
}

.search-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.search-tag {
  cursor: pointer;
}

.market-badge {
  margin-left: 6px;
  opacity: 0.6;
  font-size: 11px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.error-alert {
  margin-bottom: 12px;
}

.text-up {
  color: #f56c6c;
  font-weight: 600;
}

.text-down {
  color: #67c23a;
  font-weight: 600;
}

.text-flat {
  color: #909399;
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
