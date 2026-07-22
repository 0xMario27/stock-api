import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { getQuote, getQuotes, getKlines } from "@/api";
import { getRealtimeClient, type RealtimeClient } from "@/utils/realtime";
import type { AssetClass, Kline, Quote, SourceName } from "@/types";

const STOCK_KEY = "stock-api-py:watchlist:stock";
const CRYPTO_KEY = "stock-api-py:watchlist:crypto";
const SOURCE_STOCK_KEY = "stock-api-py:source:stock";
const SOURCE_CRYPTO_KEY = "stock-api-py:source:crypto";
const ASSET_CLASS_KEY = "stock-api-py:asset_class";
const DASH_KEY = "stock-api-py:dashitems";

const DEFAULT_STOCK_WATCHLIST = ["SH510500", "SZ000651", "SH600519", "USIXIC", "COMNQ"];
const DEFAULT_CRYPTO_WATCHLIST = ["bitcoin", "ethereum", "solana"];
const DEFAULT_DASH: DashItem[] = [
  { code: "SH510500", assetClass: "stock" },
  { code: "SZ000651", assetClass: "stock" },
  { code: "SH600519", assetClass: "stock" },
  { code: "USIXIC", assetClass: "stock" },
  { code: "COMNQ", assetClass: "stock" },
  { code: "bitcoin", assetClass: "crypto" },
];

export interface DashItem {
  code: string;
  assetClass: AssetClass;
}

function loadList(key: string, fallback: string[]): string[] {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function loadDash(): DashItem[] {
  try {
    const raw = localStorage.getItem(DASH_KEY);
    return raw ? JSON.parse(raw) : DEFAULT_DASH;
  } catch {
    return DEFAULT_DASH;
  }
}

export const useStockStore = defineStore("stock", () => {
  const assetClass = ref<AssetClass>(
    (localStorage.getItem(ASSET_CLASS_KEY) as AssetClass) || "stock"
  );
  const stockWatchlist = ref<string[]>(loadList(STOCK_KEY, DEFAULT_STOCK_WATCHLIST));
  const cryptoWatchlist = ref<string[]>(loadList(CRYPTO_KEY, DEFAULT_CRYPTO_WATCHLIST));
  const sourceStock = ref<SourceName>(
    (localStorage.getItem(SOURCE_STOCK_KEY) as SourceName) || "auto"
  );
  const sourceCrypto = ref<SourceName>(
    (localStorage.getItem(SOURCE_CRYPTO_KEY) as SourceName) || "auto"
  );

  const quotes = ref<Quote[]>([]);
  const loading = ref(false);
  const error = ref("");

  // Dashboard 状态
  const dashItems = ref<DashItem[]>(loadDash());
  const dashQuotes = ref<Record<string, Quote>>({});
  const dashSparklines = ref<Record<string, Kline[]>>({});
  const dashLoading = ref(false);
  const dashError = ref("");
  const dashSparklineFetched = ref<Record<string, number>>({});

  let refreshGeneration = 0;
  let dashGeneration = 0;

  const watchlist = computed(() =>
    assetClass.value === "crypto" ? cryptoWatchlist.value : stockWatchlist.value
  );
  const source = computed<SourceName>(() =>
    assetClass.value === "crypto" ? sourceCrypto.value : sourceStock.value
  );

  function setAssetClass(next: AssetClass): void {
    if (assetClass.value === next) return;
    assetClass.value = next;
    localStorage.setItem(ASSET_CLASS_KEY, next);
    quotes.value = [];
    refresh();
  }

  function setSource(next: SourceName): void {
    if (assetClass.value === "crypto") {
      sourceCrypto.value = next;
      localStorage.setItem(SOURCE_CRYPTO_KEY, next);
    } else {
      sourceStock.value = next;
      localStorage.setItem(SOURCE_STOCK_KEY, next);
    }
  }

  function persistWatchlist(): void {
    const key = assetClass.value === "crypto" ? CRYPTO_KEY : STOCK_KEY;
    localStorage.setItem(key, JSON.stringify(watchlist.value));
  }

  function addCode(code: string): void {
    const normalized =
      assetClass.value === "crypto" ? code.trim().toLowerCase() : code.trim().toUpperCase();
    if (normalized && !watchlist.value.includes(normalized)) {
      watchlist.value.push(normalized);
      persistWatchlist();
    }
  }

  function removeCode(code: string): void {
    const list = assetClass.value === "crypto" ? cryptoWatchlist : stockWatchlist;
    list.value = list.value.filter((c) => c !== code);
    quotes.value = quotes.value.filter((q) => q.code !== code);
    persistWatchlist();
  }

  async function refresh(): Promise<void> {
    const generation = ++refreshGeneration;
    const currentClass = assetClass.value;
    if (watchlist.value.length === 0) {
      if (generation === refreshGeneration) quotes.value = [];
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      const result = await getQuotes(watchlist.value, source.value, currentClass);
      if (generation !== refreshGeneration) return;
      // 合并：不覆盖 WS 实时数据（source === "binance_ws" 的 quote 保留）
      const wsQuotes = new Map<string, Quote>();
      for (const q of quotes.value) {
        if (q.source === "binance_ws") wsQuotes.set(q.code, q);
      }
      quotes.value = result.map((q) => wsQuotes.get(q.code) ?? q);
      const allFailed = result.length > 0 && result.every((q) => q.source === "base");
      if (allFailed) {
        const label = currentClass === "crypto" ? "加密货币" : "股票";
        error.value = `${label}数据源暂时不可用（可能被限流），稍后会自动重试`;
      }
      // 实时推送：crypto 自动订阅 Binance WS
      if (currentClass === "crypto") {
        for (const q of result) {
          if (q.source !== "base") subscribeRealtime(q.code);
        }
      }
    } catch (e) {
      if (generation !== refreshGeneration) return;
      error.value = e instanceof Error ? e.message : String(e);
    } finally {
      if (generation === refreshGeneration) loading.value = false;
    }
  }

  async function refreshOne(code: string): Promise<void> {
    const generation = refreshGeneration;
    const currentClass = assetClass.value;
    try {
      const quote = await getQuote(code, source.value, currentClass);
      if (generation !== refreshGeneration) return;
      const index = quotes.value.findIndex((q) => q.code === code);
      if (index >= 0) quotes.value[index] = quote;
      else quotes.value.push(quote);
    } catch (e) {
      if (generation !== refreshGeneration) return;
      error.value = e instanceof Error ? e.message : String(e);
    }
  }

  // === Dashboard 操作 ===
  function persistDash(): void {
    localStorage.setItem(DASH_KEY, JSON.stringify(dashItems.value));
  }

  function addToDash(code: string, ac: AssetClass): void {
    const normalized = ac === "crypto" ? code.trim().toLowerCase() : code.trim().toUpperCase();
    const exists = dashItems.value.some(
      (d) => d.code === normalized && d.assetClass === ac
    );
    if (!exists) {
      dashItems.value.push({ code: normalized, assetClass: ac });
      persistDash();
    }
  }

  function removeFromDash(code: string, ac: AssetClass): void {
    dashItems.value = dashItems.value.filter(
      (d) => !(d.code === code && d.assetClass === ac)
    );
    const key = `${ac}:${code}`;
    delete dashQuotes.value[key];
    delete dashSparklines.value[key];
    persistDash();
  }

  function isInDash(code: string, ac: AssetClass): boolean {
    return dashItems.value.some((d) => d.code === code && d.assetClass === ac);
  }

  async function refreshDash(): Promise<void> {
    const generation = ++dashGeneration;
    if (dashItems.value.length === 0) {
      dashQuotes.value = {};
      dashSparklines.value = {};
      return;
    }
    dashLoading.value = true;
    dashError.value = "";

    // 按资产类别分组
    const stockCodes = dashItems.value.filter((d) => d.assetClass === "stock").map((d) => d.code);
    const cryptoCodes = dashItems.value.filter((d) => d.assetClass === "crypto").map((d) => d.code);

    // 1. 优先加载行情（批量 API，快）
    const quoteTasks: Promise<void>[] = [];
    if (stockCodes.length > 0) {
      quoteTasks.push(fetchDashGroup(stockCodes, "stock", generation));
    }
    if (cryptoCodes.length > 0) {
      quoteTasks.push(fetchDashGroup(cryptoCodes, "crypto", generation));
    }
    await Promise.allSettled(quoteTasks);

    // 行情加载完成即可交互
    if (generation === dashGeneration) {
      dashLoading.value = false;
    }

    // 2. 后台加载迷你 K 线（5 分钟内不重复请求）
    const now = Date.now();
    const SPARKLINE_TTL = 5 * 60 * 1000;
    const sparklineTasks: Promise<void>[] = [];
    for (const item of dashItems.value) {
      const key = `${item.assetClass}:${item.code}`;
      const last = dashSparklineFetched.value[key] || 0;
      if (now - last > SPARKLINE_TTL) {
        sparklineTasks.push(fetchDashSparkline(item.code, item.assetClass, generation));
      }
    }
    if (sparklineTasks.length > 0) {
      await Promise.allSettled(sparklineTasks);
    }
  }

  async function fetchDashGroup(codes: string[], ac: AssetClass, generation: number): Promise<void> {
    try {
      const result = await getQuotes(codes, "auto", ac);
      if (generation !== dashGeneration) return;
      for (const q of result) {
        const key = `${ac}:${q.code}`;
        // 保留 WS 实时数据（不覆盖 source=binance_ws 的更新）
        const existing = dashQuotes.value[key];
        if (existing && existing.source === "binance_ws") continue;
        dashQuotes.value[key] = q;
      }
    } catch (e) {
      if (generation === dashGeneration) {
        dashError.value = e instanceof Error ? e.message : String(e);
      }
    }
  }

  async function fetchDashSparkline(code: string, ac: AssetClass, generation: number): Promise<void> {
    try {
      const result = await getKlines(code, { period: "day", count: 20, source: "auto" }, ac);
      if (generation !== dashGeneration) return;
      const key = `${ac}:${code}`;
      dashSparklines.value[key] = result;
      dashSparklineFetched.value[key] = Date.now();
    } catch {
      // 迷你图失败不影响主数据
    }
  }

  // === 实时推送 ===
  const realtime = ref<RealtimeClient | null>(null);
  const realtimeConnected = ref(false);
  const realtimeCodes = ref<Set<string>>(new Set());

  function initRealtime(): void {
    if (realtime.value) return;
    const client = getRealtimeClient();
    client.connect();

    // 每 2 秒检查连接状态
    setInterval(() => {
      realtimeConnected.value = client.connected;
    }, 2000);

    realtime.value = client;
  }

  function subscribeRealtime(code: string): void {
    // 延迟初始化：子组件 onMounted 早于父组件，realtime 可能还没初始化
    if (!realtime.value) {
      initRealtime();
    }
    if (!realtime.value) return;
    if (!realtimeCodes.value.has(code)) {
      realtimeCodes.value.add(code);
      realtime.value.subscribe(code, (_code, data) => {
        // 更新 watchlist quotes
        const idx = quotes.value.findIndex((q) => q.code === code);
        if (idx >= 0) {
          quotes.value[idx] = { ...quotes.value[idx], ...data, source: "binance_ws" };
        }
        // 更新 dashboard quotes
        const dashKey = `crypto:${code}`;
        if (dashKey in dashQuotes.value) {
          dashQuotes.value[dashKey] = { ...dashQuotes.value[dashKey]!, ...data, source: "binance_ws" };
        }
        // 更新 detail page 的实时回调
        const cbs = realtimeDetailCallbacks.get(code);
        if (cbs) cbs.forEach((cb) => cb(data));
      });
    }
  }

  // Detail page 等外部组件注册的实时回调
  const realtimeDetailCallbacks = new Map<string, Set<(data: any) => void>>();

  function subscribeRealtimeCallback(code: string, cb: (data: any) => void): void {
    if (!realtimeDetailCallbacks.has(code)) {
      realtimeDetailCallbacks.set(code, new Set());
    }
    realtimeDetailCallbacks.get(code)!.add(cb);
  }

  function unsubscribeRealtimeCallback(code: string, cb: (data: any) => void): void {
    realtimeDetailCallbacks.get(code)?.delete(cb);
  }

  function unsubscribeRealtime(code: string): void {
    if (!realtime.value) return;
    realtimeCodes.value.delete(code);
    realtime.value.unsubscribe(code);
  }

  function disconnectRealtime(): void {
    if (realtime.value) {
      realtime.value.disconnect();
      realtime.value = null;
    }
    realtimeCodes.value.clear();
    realtimeConnected.value = false;
  }

  return {
    assetClass,
    quotes,
    loading,
    error,
    source,
    watchlist,
    addCode,
    removeCode,
    refresh,
    refreshOne,
    setAssetClass,
    setSource,
    // Dashboard
    dashItems,
    dashQuotes,
    dashSparklines,
    dashLoading,
    dashError,
    addToDash,
    removeFromDash,
    isInDash,
    refreshDash,
    persistDash,
    // Realtime
    realtimeConnected,
    initRealtime,
    subscribeRealtime,
    subscribeRealtimeCallback,
    unsubscribeRealtime,
    unsubscribeRealtimeCallback,
    disconnectRealtime,
  };
});
