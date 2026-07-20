<script setup lang="ts">
import { onMounted } from "vue";
import { useStockStore } from "@/stores/stock";

const store = useStockStore();

onMounted(() => {
  store.refresh();
});
</script>

<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-inner">
        <router-link to="/" class="logo">
          <span class="logo-icon">📈</span>
          <span class="logo-text">stock-api</span>
        </router-link>
        <el-select
          :model-value="store.source"
          @update:model-value="store.setSource($event as any)"
          size="small"
          style="width: 140px"
        >
          <el-option label="自动兜底" value="auto" />
          <el-option label="腾讯" value="tencent" />
          <el-option label="新浪" value="sina" />
          <el-option label="东方财富" value="eastmoney" />
        </el-select>
      </div>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
  </el-container>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
    Arial, "PingFang SC", "Microsoft YaHei", sans-serif;
  background-color: #f5f7fa;
  color: #303133;
}

.app-container {
  min-height: 100vh;
}

.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-inner {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: #303133;
  font-weight: 600;
  font-size: 18px;
}

.logo-icon {
  font-size: 22px;
}

.app-main {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 24px;
}
</style>
