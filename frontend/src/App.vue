<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useStockStore } from "@/stores/stock";

const store = useStockStore();
const colorRule = ref(localStorage.getItem("stock-api-py:color-rule") || "asia");
const theme = ref<"light" | "dark">(
  (localStorage.getItem("stock-api-py:theme") as "light" | "dark") || "dark"
);

function applyTheme() {
  document.documentElement.setAttribute("data-theme", theme.value);
  document.documentElement.classList.toggle("dark", theme.value === "dark");
}

function applyColorRule() {
  document.documentElement.setAttribute("data-color-rule", colorRule.value);
}

function toggleTheme() {
  theme.value = theme.value === "dark" ? "light" : "dark";
  localStorage.setItem("stock-api-py:theme", theme.value);
  applyTheme();
}

function toggleColorRule() {
  colorRule.value = colorRule.value === "asia" ? "intl" : "asia";
  localStorage.setItem("stock-api-py:color-rule", colorRule.value);
  applyColorRule();
}

onMounted(() => {
  applyTheme();
  applyColorRule();
});
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <div class="header-left">
          <router-link to="/" class="brand">
            <svg class="brand-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
              <polyline points="16 7 22 7 22 13" />
            </svg>
            <span class="brand-text">StockAPI</span>
            <span class="brand-badge">PY</span>
          </router-link>

          <nav class="nav-links">
            <router-link to="/" class="nav-link" active-class="nav-active">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
              </svg>
              <span>Dashboard</span>
            </router-link>
            <router-link to="/watchlist" class="nav-link" active-class="nav-active">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" />
                <line x1="8" y1="18" x2="21" y2="18" /><line x1="3" y1="6" x2="3.01" y2="6" />
                <line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
              </svg>
              <span>自选</span>
            </router-link>
          </nav>
        </div>

        <div class="header-right">
          <button class="ui-icon-btn" @click="toggleTheme" :title="theme === 'dark' ? '切换到浅色' : '切换到深色'">
            <svg v-if="theme === 'light'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
            </svg>
            <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
            </svg>
          </button>

          <button class="ui-icon-btn" @click="toggleColorRule" title="切换涨跌颜色">
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
  transition: background var(--transition-normal), border-color var(--transition-normal);
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

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-fg);
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.02em;
  transition: color var(--transition-normal);
}

.brand-icon {
  color: var(--color-primary);
  filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.3));
  transition: color var(--transition-normal);
}

.brand-text { font-size: 16px; }

.brand-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  background: var(--color-primary);
  color: #FFFFFF;
  letter-spacing: 0.05em;
  line-height: 1.4;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 2px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: var(--radius-md);
  color: var(--color-fg-secondary);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition-fast);
  min-height: 32px;
}
.nav-link:hover {
  background: var(--color-bg-hover);
  color: var(--color-fg);
}
.nav-active {
  color: var(--color-primary);
  background: rgba(59, 130, 246, 0.1);
}

.color-dot {
  display: block;
  width: 14px;
  height: 4px;
  border-radius: 2px;
}
.color-up-dot { background: var(--color-up); }
.color-down-dot { background: var(--color-down); margin-top: 3px; }

.app-main {
  flex: 1;
  max-width: var(--max-width);
  width: 100%;
  margin: 0 auto;
  padding: var(--space-6);
  transition: background var(--transition-normal);
}

@media (max-width: 640px) {
  .header-inner { padding: 0 var(--space-4); }
  .brand-text { display: none; }
}
</style>
