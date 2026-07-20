<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useStockStore } from "@/stores/stock";

const store = useStockStore();
const colorRule = ref(localStorage.getItem("stock-api-py:color-rule") || "asia");

function applyColorRule() {
  document.documentElement.setAttribute("data-color-rule", colorRule.value);
}

function toggleColorRule() {
  colorRule.value = colorRule.value === "asia" ? "intl" : "asia";
  localStorage.setItem("stock-api-py:color-rule", colorRule.value);
  applyColorRule();
}

onMounted(() => {
  document.documentElement.classList.add("dark");
  applyColorRule();
  store.refresh();
});
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <router-link to="/" class="brand">
          <svg class="brand-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
            <polyline points="16 7 22 7 22 13" />
          </svg>
          <span class="brand-text">StockAPI</span>
          <span class="brand-badge">PY</span>
        </router-link>

        <div class="header-controls">
          <el-radio-group
            :model-value="store.assetClass"
            @update:model-value="store.setAssetClass($event as any)"
            size="small"
          >
            <el-radio-button label="stock">股票</el-radio-button>
            <el-radio-button label="crypto">加密货币</el-radio-button>
          </el-radio-group>

          <el-select
            v-if="store.assetClass === 'stock'"
            :model-value="store.source"
            @update:model-value="store.setSource($event as any)"
            size="small"
            class="source-select"
          >
            <el-option label="自动兜底" value="auto" />
            <el-option label="腾讯" value="tencent" />
            <el-option label="新浪" value="sina" />
            <el-option label="东方财富" value="eastmoney" />
          </el-select>
          <el-select
            v-else
            :model-value="store.source"
            @update:model-value="store.setSource($event as any)"
            size="small"
            class="source-select"
          >
            <el-option label="自动兜底" value="auto" />
            <el-option label="CoinGecko" value="coingecko" />
          </el-select>

          <button class="color-toggle" @click="toggleColorRule" title="切换涨跌颜色">
            <span class="color-dot color-up-dot"></span>
            <span class="color-dot color-down-dot"></span>
          </button>
        </div>
      </div>
    </header>

    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  height: var(--header-height);
  background: var(--color-bg-elevated);
  border-bottom: 1px solid var(--color-border-light);
  position: sticky;
  top: 0;
  z-index: 100;
  backdrop-filter: blur(12px);
}

.header-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  height: 100%;
  padding: 0 var(--space-6);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-fg);
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.02em;
}

.brand-icon {
  color: var(--color-primary);
  filter: drop-shadow(0 0 8px rgba(245, 158, 11, 0.3));
}

.brand-text {
  font-size: 16px;
}

.brand-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: var(--color-bg);
  letter-spacing: 0.05em;
  line-height: 1.4;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.source-select {
  width: 130px;
}

.color-toggle {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  cursor: pointer;
  transition: border-color var(--transition-fast);
  min-width: 44px;
  min-height: 44px;
  justify-content: center;
  align-items: center;
}

.color-toggle:hover {
  border-color: var(--color-fg-muted);
}

.color-dot {
  width: 14px;
  height: 4px;
  border-radius: 2px;
}

.color-up-dot {
  background: var(--color-up);
}

.color-down-dot {
  background: var(--color-down);
}

.app-main {
  flex: 1;
  max-width: var(--max-width);
  width: 100%;
  margin: 0 auto;
  padding: var(--space-6);
}

@media (max-width: 640px) {
  .header-inner {
    padding: 0 var(--space-4);
  }
  .brand-text {
    display: none;
  }
  .source-select {
    width: 100px;
  }
}
</style>
