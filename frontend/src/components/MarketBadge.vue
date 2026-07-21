<script setup lang="ts">
import type { Market } from "@/types";

defineProps<{ market: Market | null }>();

const labels: Record<string, string> = {
  cn_a: "A股", hk: "港股", us: "美股", index: "指数", fund: "基金",
  future: "期指", option: "期权", commodity: "商品", crypto: "加密",
};
</script>

<template>
  <span v-if="market" :class="['market-badge', `market-${market}`]">
    {{ labels[market] || "?" }}
  </span>
</template>

<style scoped>
.market-badge {
  display: inline-flex; align-items: center;
  font-size: 10px; font-weight: 700; letter-spacing: 0.03em;
  padding: 2px 8px; border-radius: 999px;
  border: 0.5px solid transparent;
  line-height: 1.4; white-space: nowrap;
}

.market-cn_a   { background: rgba(239,68,68,0.18);  color: var(--color-up);        border-color: rgba(239,68,68,0.30);  }
.market-hk     { background: rgba(245,158,11,0.18); color: #F59E0B;                 border-color: rgba(245,158,11,0.30); }
.market-us     { background: rgba(59,130,246,0.18); color: var(--color-primary);    border-color: rgba(59,130,246,0.30); }
.market-index  { background: rgba(139,92,246,0.18); color: var(--color-accent);     border-color: rgba(139,92,246,0.30); }
.market-fund   { background: rgba(34,197,94,0.18);  color: #22C55E;                 border-color: rgba(34,197,94,0.30);  }
.market-future { background: rgba(236,72,153,0.18); color: #EC4899;                 border-color: rgba(236,72,153,0.30); }
.market-option { background: rgba(14,165,233,0.18); color: #0EA5E9;                 border-color: rgba(14,165,233,0.30); }
.market-commodity { background: rgba(217,119,6,0.18); color: #D97706;               border-color: rgba(217,119,6,0.30); }
.market-crypto { background: rgba(139,92,246,0.18); color: var(--color-accent);     border-color: rgba(139,92,246,0.30); }
</style>
