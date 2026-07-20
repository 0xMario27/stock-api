import { defineStore } from "pinia";
import { ref } from "vue";
import { getQuote, getQuotes } from "@/api";
import type { Quote, SourceName } from "@/types";

const WATCHLIST_KEY = "stock-api-py:watchlist";
const SOURCE_KEY = "stock-api-py:source";

export const useStockStore = defineStore("stock", () => {
  const quotes = ref<Quote[]>([]);
  const loading = ref(false);
  const error = ref("");
  const source = ref<SourceName>(
    (localStorage.getItem(SOURCE_KEY) as SourceName) || "auto"
  );
  const watchlist = ref<string[]>(loadWatchlist());

  function loadWatchlist(): string[] {
    try {
      const raw = localStorage.getItem(WATCHLIST_KEY);
      return raw ? JSON.parse(raw) : ["SH510500", "SZ000651", "SH600519"];
    } catch {
      return ["SH510500", "SZ000651", "SH600519"];
    }
  }

  function persistWatchlist(): void {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist.value));
  }

  function setSource(next: SourceName): void {
    source.value = next;
    localStorage.setItem(SOURCE_KEY, next);
  }

  function addCode(code: string): void {
    const normalized = code.trim().toUpperCase();
    if (normalized && !watchlist.value.includes(normalized)) {
      watchlist.value.push(normalized);
      persistWatchlist();
    }
  }

  function removeCode(code: string): void {
    watchlist.value = watchlist.value.filter((c) => c !== code);
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
      quotes.value = await getQuotes(watchlist.value, source.value);
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e);
    } finally {
      loading.value = false;
    }
  }

  async function refreshOne(code: string): Promise<void> {
    try {
      const quote = await getQuote(code, source.value);
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
    quotes,
    loading,
    error,
    source,
    watchlist,
    addCode,
    removeCode,
    refresh,
    refreshOne,
    setSource,
  };
});
