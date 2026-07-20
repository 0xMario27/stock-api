<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { inspectStock } from "@/api";
import type { AutoInspection, SourceName } from "@/types";

const props = defineProps<{ code: string }>();
const router = useRouter();

const inspection = ref<AutoInspection | null>(null);
const loading = ref(false);
const source = ref<SourceName>("auto");

async function loadInspection(): Promise<void> {
  loading.value = true;
  try {
    inspection.value = await inspectStock(props.code, source.value);
  } finally {
    loading.value = false;
  }
}

function statusType(status: string): "success" | "warning" | "danger" | "info" {
  if (status === "success") return "success";
  if (status === "empty") return "warning";
  if (status === "error") return "danger";
  return "info";
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { success: "成功", empty: "空数据", error: "错误" };
  return map[status] || status;
}

onMounted(() => loadInspection());
</script>

<template>
  <div class="inspect-view" v-loading="loading">
    <el-page-header @back="router.push(`/stock/${code}`)" class="page-header">
      <template #content>
        <span>{{ code }} 数据源诊断</span>
      </template>
    </el-page-header>

    <el-card v-if="inspection" shadow="never">
      <template #header>
        <div class="card-header">
          <span>最终结果：来自 {{ inspection.source }}</span>
          <el-button size="small" @click="loadInspection">重新诊断</el-button>
        </div>
      </template>

      <el-descriptions v-if="inspection.quote" :column="3" border>
        <el-descriptions-item label="代码">{{ inspection.quote.code }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ inspection.quote.name }}</el-descriptions-item>
        <el-descriptions-item label="最新价">{{ inspection.quote.now.toFixed(3) }}</el-descriptions-item>
        <el-descriptions-item label="涨跌幅">
          {{ (inspection.quote.percent * 100).toFixed(2) }}%
        </el-descriptions-item>
        <el-descriptions-item label="最高">{{ inspection.quote.high.toFixed(3) }}</el-descriptions-item>
        <el-descriptions-item label="最低">{{ inspection.quote.low.toFixed(3) }}</el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h4>各数据源状态</h4>
      <el-table :data="inspection.sources" style="width: 100%" row-key="source">
        <el-table-column prop="source" label="数据源" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quote.name" label="名称" width="180">
          <template #default="{ row }">
            {{ row.quote?.name || "-" }}
          </template>
        </el-table-column>
        <el-table-column prop="quote.now" label="最新价" width="100" align="right">
          <template #default="{ row }">
            {{ row.quote?.now?.toFixed(3) || "-" }}
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误信息">
          <template #default="{ row }">
            <span v-if="row.error" class="error-text">{{ row.error }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.inspect-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  background: #fff;
  padding: 12px 16px;
  border-radius: 4px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

h4 {
  margin: 16px 0 8px;
  color: #303133;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}
</style>
