import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { getQuote, getQuotes } from "@/api";
import type { AssetClass, Quote, SourceName } from "@/types";

const STOCK_KEY = "stock-api-py:watchlist:stock";
const CRYPTO_KEY = "stock-api-py:watchlist:crypto";
const SOURCE_STOCK_KEY = "stock-api-py:source:stock";
const SOURCE_CRYPTO_KEY = "stock-api-py:source:crypto";
const ASSET_CLASS_KEY = "stock-api-py:asset_class";

const DEFAULT_STOCK_WATCHLIST = ["SH510500", "SZ000651", "SH600519"];
const DEFAULT_CRYPTO_WATCHLIST = ["bitcoin", "ethereum", "solana"];

function loadList(key: string, fallback: string[]): string[] {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
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

  const watchlist = computed(() =>
    assetClass.value === "crypto" ? cryptoWatchlist.value : stockWatchlist.value
  );
  const source = computed<SourceName>(() =>
    assetClass.value === "crypto" ? sourceCrypto.value : sourceStock.value
  );

  function setAssetClass(next: AssetClass): void {
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
    if (watchlist.value.length === 0) {
      quotes.value = [];
      return;
    }
    loading.value = true;
    error.value = "";
    try {
      quotes.value = await getQuotes(watchlist.value, source.value, assetClass.value);
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
    } finally {
      loading.value = false;
    }
  }

  async function refreshOne(code: string): Promise<void> {
    try {
      const quote = await getQuote(code, source.value, assetClass.value);
      const index = quotes.value.findIndex((q) => q.code === code);
      if (index >= 0) {
        quotes.value[index] = quote;
      } else {
        quotes.value.push(quote);
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
    }
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
  };
});
