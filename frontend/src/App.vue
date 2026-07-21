<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from "vue";
import { useStockStore } from "@/stores/stock";
import { Moon, Sun, Monitor, LayoutGrid, List, ChevronsUpDown } from "lucide-vue-next";

type ThemeMode = "light" | "dark" | "system";

const store = useStockStore();
const colorRule = ref(localStorage.getItem("stock-api-py:color-rule") || "asia");
const theme = ref<ThemeMode>(
  (localStorage.getItem("stock-api-py:theme") as ThemeMode) || "dark"
);

let systemMedia: MediaQueryList | null = null;

function resolveTheme(): "light" | "dark" {
  if (theme.value === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return theme.value;
}

function applyTheme() {
  const resolved = resolveTheme();
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

function applyColorRule() {
  document.documentElement.setAttribute("data-color-rule", colorRule.value);
}

function cycleTheme() {
  const cycle: ThemeMode[] = ["dark", "light", "system"];
  const idx = cycle.indexOf(theme.value);
  theme.value = cycle[(idx + 1) % cycle.length];
  localStorage.setItem("stock-api-py:theme", theme.value);
  applyTheme();
}

const themeIcon = computed(() =>
  theme.value === "dark" ? Moon : theme.value === "light" ? Sun : Monitor
);
const themeTitle = computed(() =>
  theme.value === "dark" ? "深色模式" : theme.value === "light" ? "浅色模式" : "跟随系统"
);

function toggleColorRule() {
  colorRule.value = colorRule.value === "asia" ? "intl" : "asia";
  localStorage.setItem("stock-api-py:color-rule", colorRule.value);
  applyColorRule();
}

function listenSystemTheme() {
  systemMedia = window.matchMedia("(prefers-color-scheme: dark)");
  systemMedia.addEventListener("change", () => {
    if (theme.value === "system") applyTheme();
  });
}

onMounted(() => {
  applyTheme();
  applyColorRule();
  listenSystemTheme();
  store.initRealtime();
});

onBeforeUnmount(() => {
  systemMedia?.removeEventListener("change", applyTheme);
});
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-inner">
        <div class="header-left">
          <router-link to="/" class="brand">
            <svg class="brand-icon" width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M3 18 L8 15 L13 12 L19 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.35" fill="none"/>
              <line x1="7" y1="10" x2="7" y2="19" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
              <rect x="5.5" y="12" width="3" height="5" rx="0.5" fill="currentColor" opacity="0.55"/>
              <line x1="12" y1="7" x2="12" y2="17" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
              <rect x="10.5" y="9" width="3" height="6" rx="0.5" fill="currentColor"/>
              <line x1="17" y1="4" x2="17" y2="14" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
              <rect x="15.5" y="6" width="3" height="6" rx="0.5" fill="currentColor"/>
              <path d="M15.5 7 L19 7 L19 3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
            <span class="brand-text">StockAPI</span>
            <span class="brand-badge">PY</span>
          </router-link>

          <nav class="nav-links">
            <router-link to="/" class="nav-link" active-class="nav-active">
              <LayoutGrid :size="16" />
              <span>Dashboard</span>
            </router-link>
            <router-link to="/watchlist" class="nav-link" active-class="nav-active">
              <List :size="16" />
              <span>自选</span>
            </router-link>
          </nav>
        </div>

        <div class="header-right">
          <div class="rt-indicator" :class="{ 'rt-on': store.realtimeConnected, 'rt-off': !store.realtimeConnected }">
            <span class="rt-dot"></span>
            <span class="rt-label">{{ store.realtimeConnected ? '实时' : '离线' }}</span>
          </div>
          <button class="ui-icon-btn" @click="cycleTheme" :title="themeTitle">
            <component :is="themeIcon" :size="16" />
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
  gap: var(--space-3);
}

.rt-indicator {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 10px; border-radius: var(--radius-md);
  font-size: 12px; font-weight: 600;
  border: 1px solid transparent;
}
.rt-dot {
  width: 8px; height: 8px; border-radius: 50%;
}
.rt-on {
  background: rgba(38, 166, 154, 0.12); color: var(--color-down);
  border-color: rgba(38, 166, 154, 0.25);
}
.rt-on .rt-dot { background: var(--color-down); animation: pulse 2s infinite; }
.rt-off {
  background: var(--color-muted); color: var(--color-fg-muted);
  border-color: var(--color-border-light);
}
.rt-off .rt-dot { background: var(--color-fg-muted); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
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
