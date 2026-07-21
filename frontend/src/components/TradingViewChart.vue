<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from "vue";

const props = defineProps<{
  code: string;
  assetClass: string;
  interval: string;
  theme: "light" | "dark";
}>();

const container = ref<HTMLDivElement | null>(null);
let widget: any = null;

const cryptoMap: Record<string, string> = {
  bitcoin: "BINANCE:BTCUSDT", ethereum: "BINANCE:ETHUSDT",
  binancecoin: "BINANCE:BNBUSDT", solana: "BINANCE:SOLUSDT",
  ripple: "BINANCE:XRPUSDT", cardano: "BINANCE:ADAUSDT",
  dogecoin: "BINANCE:DOGEUSDT", polkadot: "BINANCE:DOTUSDT",
  chainlink: "BINANCE:LINKUSDT", litecoin: "BINANCE:LTCUSDT",
  tron: "BINANCE:TRXUSDT", "shiba-inu": "BINANCE:SHIBUSDT",
  uniswap: "BINANCE:UNIUSDT", cosmos: "BINANCE:ATOMUSDT",
  stellar: "BINANCE:XLMUSDT", near: "BINANCE:NEARUSDT",
  aptos: "BINANCE:APTUSDT", filecoin: "BINANCE:FILUSDT",
  "avalanche-2": "BINANCE:AVAXUSDT", polygon: "BINANCE:MATICUSDT",
};

function toTVSymbol(): string {
  const code = props.code;
  if (props.assetClass === "crypto") {
    if (cryptoMap[code]) return cryptoMap[code];
    const u = code.toUpperCase();
    return u.endsWith("USDT") ? "BINANCE:" + u : "BINANCE:" + u + "USDT";
  }
  const u = code.toUpperCase();
  if (u.startsWith("SH")) return "SSE:" + u.slice(2);
  if (u.startsWith("SZ")) return "SZSE:" + u.slice(2);
  if (u.startsWith("HK")) return "HKEX:" + u.slice(2);
  if (u.startsWith("US")) {
    const s = u.slice(2);
    if (s === "DJI") return "INDEX:DJI";
    if (s === "IXIC") return "INDEX:IXIC";
    if (s === "INX") return "INDEX:SPX";
    return "NASDAQ:" + s;
  }
  return code;
}

function loadScript(): Promise<void> {
  if ((window as any).TradingView) return Promise.resolve();
  return new Promise((resolve) => {
    const s = document.createElement("script");
    s.src = "https://s3.tradingview.com/tv.js";
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => resolve();
    document.head.appendChild(s);
  });
}

async function createWidget() {
  if (!container.value) return;
  await loadScript();
  const TV = (window as any).TradingView;
  if (!TV) return;
  container.value.innerHTML = "";
  widget = new TV.widget({
    container_id: container.value.id,
    symbol: toTVSymbol(),
    interval: props.interval,
    theme: props.theme,
    locale: "zh",
    autosize: true,
    toolbar_bg: props.theme === "dark" ? "#1A2332" : "#F8FAFC",
    enable_publishing: false,
    allow_symbol_change: false,
    hide_side_toolbar: false,
    withdateranges: true,
    details: false,
    hotlist: false,
    calendar: false,
    studies: ["MASimple@tv-basicstudies", "MAExp@tv-basicstudies"],
    supported_resolutions: ["D", "W", "M"],
  });
}

function removeWidget() {
  if (widget && widget.remove) { widget.remove(); widget = null; }
  if (container.value) container.value.innerHTML = "";
}

onMounted(() => { createWidget(); });
onBeforeUnmount(() => { removeWidget(); });

watch(() => [props.code, props.assetClass, props.interval, props.theme], () => {
  removeWidget();
  createWidget();
});
</script>

<template>
  <div ref="container" id="tv_chart_container" class="tv-chart-container"></div>
</template>

<style scoped>
.tv-chart-container {
  width: 100%;
  height: 100%;
  min-height: 500px;
}
.tv-chart-container iframe {
  border: none;
  border-radius: var(--radius-md);
}
</style>
