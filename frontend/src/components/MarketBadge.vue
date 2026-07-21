<script setup lang="ts">
import type { Market } from "@/types";

defineProps<{ market: Market | null }>();

const labels: Record<string, string> = {
  cn_a: "A股", hk: "港股", us: "美股", index: "指数", fund: "基金",
  future: "期指", option: "期权", commodity: "商品", crypto: "加密",
};

const dotColors: Record<string, string> = {
  cn_a: "#EF4444",
  hk: "#F59E0B",
  us: "#3B82F6",
  index: "#8B5CF6",
  fund: "#22C55E",
  future: "#EC4899",
  option: "#0EA5E9",
  commodity: "#D97706",
  crypto: "#8B5CF6",
};
</script>

<template>
  <span v-if="market" class="market-badge">
    <span class="market-dot" :style="{ background: dotColors[market] }" />
    {{ labels[market] || "?" }}
  </span>
</template>

<style scoped>
.market-badge {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 10px; font-weight: 600; letter-spacing: 0.02em;
  padding: 1px 8px; border-radius: 999px;
  background: var(--color-muted);
  color: var(--color-fg-muted);
  border: 1px solid var(--color-border);
  line-height: 1.6; white-space: nowrap;
}
.market-dot {
  width: 6px; height: 6px; border-radius: 50%;
  flex-shrink: 0;
}
</style>
