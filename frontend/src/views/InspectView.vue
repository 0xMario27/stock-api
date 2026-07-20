<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { inspectStock } from "@/api";
import type { AssetClass, AutoInspection, SourceName } from "@/types";

const props = defineProps<{ code: string; assetClass: AssetClass }>();
const router = useRouter();

const inspection = ref<AutoInspection | null>(null);
const loading = ref(false);
const source = ref<SourceName>("auto");

async function loadInspection(): Promise<void> {
  loading.value = true;
  try {
    inspection.value = await inspectStock(props.code, source.value, props.assetClass);
  } finally {
    loading.value = false;
  }
}

function statusIcon(status: string): string {
  if (status === "success") return "M20 6L9 17l-5-5";
  if (status === "empty") return "M12 8v4M12 16h.01";
  return "M18 6L6 18M6 6l12 12";
}

function statusColor(status: string): string {
  if (status === "success") return "status-success";
  if (status === "empty") return "status-empty";
  return "status-error";
}

function formatPrice(price: number | undefined): string {
  if (price === undefined || price === 0) return "-";
  if (price >= 1000) return price.toFixed(2);
  if (price >= 1) return price.toFixed(3);
  return price.toFixed(8);
}

onMounted(() => loadInspection());
</script>

<template>
  <div class="inspect-view" v-loading="loading">
    <div class="back-bar">
      <button class="ui-back" @click="router.push(`/stock/${props.code}?asset_class=${props.assetClass}`)">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        <span>返回详情</span>
      </button>
    </div>

    <div v-if="inspection" class="ui-card">
      <div class="ui-card-header">
        <div class="header-title">
          <span class="code text-mono">{{ inspection.code }}</span>
          <span class="header-separator">·</span>
          <span>数据源诊断</span>
        </div>
        <button class="ui-btn" @click="loadInspection" :disabled="loading">
          重新诊断
        </button>
      </div>

      <!-- 最终结果 -->
      <div class="result-section">
        <div class="result-label">最终结果来源</div>
        <div class="result-value">
          <span class="ui-badge" :class="{ 'ui-badge-active': inspection.source !== 'base' }">
            {{ inspection.source }}
          </span>
        </div>
      </div>

      <div v-if="inspection.quote" class="result-quote">
        <div class="quote-item">
          <span class="quote-label">名称</span>
          <span class="quote-val">{{ inspection.quote.name }}</span>
        </div>
        <div class="quote-item">
          <span class="quote-label">最新价</span>
          <span class="quote-val text-mono">{{ formatPrice(inspection.quote.now) }}</span>
        </div>
        <div class="quote-item">
          <span class="quote-label">涨跌幅</span>
          <span class="quote-val text-mono" :class="inspection.quote.percent > 0 ? 'text-up' : inspection.quote.percent < 0 ? 'text-down' : 'text-flat'">
            {{ (inspection.quote.percent * 100).toFixed(2) }}%
          </span>
        </div>
      </div>

      <!-- 分隔线 -->
      <div class="divider"></div>

      <!-- 各源状态 -->
      <div class="sources-title">各数据源状态</div>
      <div class="sources-list">
        <div
          v-for="src in inspection.sources"
          :key="src.source"
          class="source-row"
        >
          <div class="source-info">
            <div :class="['status-icon', statusColor(src.status)]">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <path :d="statusIcon(src.status)" />
              </svg>
            </div>
            <span class="source-name">{{ src.source }}</span>
            <span class="source-status-text" :class="statusColor(src.status)">{{ src.status }}</span>
          </div>
          <div class="source-detail">
            <span v-if="src.quote && src.quote.name !== '---'" class="source-quote-name">{{ src.quote.name }}</span>
            <span v-if="src.quote && src.quote.now" class="source-quote-price text-mono">{{ formatPrice(src.quote.now) }}</span>
            <span v-if="src.error" class="source-error">{{ src.error }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.inspect-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.back-bar {
  display: flex;
  align-items: center;
}

/* 卡片/按钮/返回均用共享 .ui-card / .ui-btn / .ui-back */

.header-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 15px;
  font-weight: 600;
}

.code {
  font-size: 16px;
}

.header-separator {
  color: var(--color-fg-muted);
}

/* 最终结果 */
.result-section {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
}

.result-label {
  font-size: 12px;
  color: var(--color-fg-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* 结果徽章用共享 .ui-badge / .ui-badge-active */
.result-value .ui-badge {
  font-size: 13px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: var(--radius-md);
}

.result-quote {
  display: flex;
  gap: var(--space-8);
  padding: 0 var(--space-5) var(--space-4);
  flex-wrap: wrap;
}

.quote-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quote-label {
  font-size: 11px;
  color: var(--color-fg-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.quote-val {
  font-size: 14px;
  font-weight: 500;
}

.divider {
  height: 1px;
  background: var(--color-border-light);
  margin: 0 var(--space-5);
}

/* 各源状态 */
.sources-title {
  padding: var(--space-4) var(--space-5) var(--space-2);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-fg-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.sources-list {
  padding: 0 var(--space-5) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.source-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--color-bg);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  gap: var(--space-4);
}

.source-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 160px;
}

.status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-success {
  background: rgba(38, 166, 154, 0.15);
  color: #26A69A;
}

.status-empty {
  background: rgba(245, 158, 11, 0.15);
  color: var(--color-primary);
}

.status-error {
  background: rgba(239, 68, 68, 0.15);
  color: var(--color-destructive);
}

.source-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-fg);
}

.source-status-text {
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.source-detail {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex: 1;
  justify-content: flex-end;
}

.source-quote-name {
  font-size: 12px;
  color: var(--color-fg-secondary);
}

.source-quote-price {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-fg);
}

.source-error {
  font-size: 11px;
  color: var(--color-destructive);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .source-row {
    flex-direction: column;
    align-items: flex-start;
  }
  .source-detail {
    justify-content: flex-start;
    width: 100%;
  }
  .result-quote {
    gap: var(--space-4);
  }
}
</style>
