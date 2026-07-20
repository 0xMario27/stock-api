/* ECharts K线图配置构建器 - 动态指标 + 子图布局 */
import type { Kline } from "@/types";
import { calcMA, calcBOLL, calcMACD, calcKDJ, calcRSI, calcVWAP } from "./indicators";

export interface IndicatorState {
  ma: boolean; boll: boolean; vwap: boolean;
  vol: boolean; macd: boolean; kdj: boolean; rsi: boolean;
}

export interface ChartColors {
  up: string; down: string; border: string; fg: string;
  fgSec: string; fgMuted: string; grid: string; tooltipBg: string;
  primary: string; accent: string;
}

function formatPrice(p: number): string {
  if (p >= 1000) return p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}

function formatVolume(v: number): string {
  if (!v || v === 0) return "-";
  if (v >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (v >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(0);
}

export function buildTooltip(params: any[], c: ChartColors): string {
  if (!params || params.length === 0) return "";
  const date = params[0]?.axisValue || "";
  let html = '<div style="margin-bottom:4px;color:' + c.fgSec + ';font-size:11px">' + date + "</div>";
  for (const p of params) {
    const name = p.seriesName;
    const val = p.value;
    if (name === "K线" && Array.isArray(val)) {
      const [open, close, high, low] = val;
      const chg = close - open;
      const chgPct = open ? (chg / open * 100).toFixed(2) : "0.00";
      const cc = chg >= 0 ? c.up : c.down;
      html += '<div style="display:grid;grid-template-columns:auto auto;gap:2px 12px;font-size:11px">';
      html += '<span style="color:' + c.fgSec + '">开</span><span style="color:' + c.fg + '">' + formatPrice(open) + "</span>";
      html += '<span style="color:' + c.fgSec + '">收</span><span style="color:' + cc + '">' + formatPrice(close) + "</span>";
      html += '<span style="color:' + c.fgSec + '">高</span><span style="color:' + c.fg + '">' + formatPrice(high) + "</span>";
      html += '<span style="color:' + c.fgSec + '">低</span><span style="color:' + c.fg + '">' + formatPrice(low) + "</span>";
      html += '<span style="color:' + c.fgSec + '">涨跌</span><span style="color:' + cc + '">' + (chg >= 0 ? "+" : "") + chg.toFixed(2) + " (" + chgPct + "%)</span>";
      html += "</div>";
    } else if (name === "成交量" && typeof val === "number") {
      html += '<div style="font-size:11px;margin-top:2px"><span style="color:' + c.fgSec + '">量</span><span style="color:' + c.fg + ';margin-left:8px">' + formatVolume(val) + "</span></div>";
    } else if (val != null && typeof val === "number") {
      const isOsc = name.startsWith("RSI") || name.startsWith("K") || name.startsWith("D") || name.startsWith("J") || name === "DIF" || name === "DEA";
      const valStr = isOsc ? val.toFixed(2) : formatPrice(val);
      html += '<div style="font-size:11px;margin-top:1px"><span style="color:' + c.fgSec + '">' + name + '</span><span style="color:' + p.color + ';margin-left:8px">' + valStr + "</span></div>";
    }
  }
  return html;
}

export function buildChartOption(klines: Kline[], ind: IndicatorState, c: ChartColors, totalHeight: number) {
  const closes = klines.map(k => k.close);
  const highs = klines.map(k => k.high);
  const lows = klines.map(k => k.low);
  const candleData = klines.map(k => [k.open, k.close, k.low, k.high]);
  const dates = klines.map(k => k.date);
  const volumes = klines.map(k => k.volume ?? 0);

  const legendH = (ind.ma || ind.boll || ind.vwap) ? 28 : 8;
  const mainTop = 8 + legendH;
  const subH = 80;
  const gap = 8;
  const dataZoomH = 24;

  const subNames: string[] = [];
  if (ind.vol) subNames.push("VOL");
  if (ind.macd) subNames.push("MACD");
  if (ind.kdj) subNames.push("KDJ");
  if (ind.rsi) subNames.push("RSI");
  const totalSubH = subNames.length * (subH + gap);
  const mainH = totalHeight - mainTop - totalSubH - dataZoomH - 8;

  const grids: any[] = [];
  const xAxes: any[] = [];
  const yAxes: any[] = [];
  const series: any[] = [];
  const legendData: string[] = [];

  // 主图
  grids.push({ left: 64, right: 16, top: mainTop, height: mainH });
  xAxes.push({ type: "category", data: dates, scale: true, boundaryGap: true, gridIndex: 0, axisLine: { lineStyle: { color: c.border } }, axisTick: { show: false }, axisLabel: { show: false }, splitLine: { show: false } });
  yAxes.push({ scale: true, gridIndex: 0, splitArea: { show: false }, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: c.fgSec, fontSize: 10, formatter: (v: number) => formatPrice(v) }, splitLine: { lineStyle: { color: c.grid } } });

  series.push({ name: "K线", type: "candlestick", data: candleData, xAxisIndex: 0, yAxisIndex: 0, itemStyle: { color: c.up, color0: c.down, borderColor: c.up, borderColor0: c.down }, barWidth: "60%" });

  if (ind.ma) {
    const maColors = ["#FBBF24", c.primary, c.accent];
    [5, 10, 20].forEach((p, i) => {
      legendData.push("MA" + p);
      series.push({ name: "MA" + p, type: "line", data: calcMA(closes, p), xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { width: 1, color: maColors[i] }, z: 2 });
    });
  }

  if (ind.boll) {
    const boll = calcBOLL(closes);
    legendData.push("BOLL-UP", "BOLL-MID", "BOLL-LOW");
    series.push({ name: "BOLL-UP", type: "line", data: boll.upper, xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { width: 1, color: c.accent, opacity: 0.6 }, z: 1 });
    series.push({ name: "BOLL-MID", type: "line", data: boll.middle, xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { width: 1, color: c.fgMuted, type: "dashed" }, z: 1 });
    series.push({ name: "BOLL-LOW", type: "line", data: boll.lower, xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { width: 1, color: c.accent, opacity: 0.6 }, z: 1 });
  }

  if (ind.vwap) {
    const vwap = calcVWAP(highs, lows, closes, volumes);
    legendData.push("VWAP");
    series.push({ name: "VWAP", type: "line", data: vwap.values, xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { width: 1.5, color: "#F59E0B" }, z: 2 });
  }

  // 子图
  let subIdx = 1;
  let subTop = mainTop + mainH + gap;

  function addSubGrid(name: string) {
    grids.push({ left: 64, right: 16, top: subTop, height: subH });
    xAxes.push({ type: "category", gridIndex: subIdx, data: dates, scale: true, boundaryGap: true, axisLabel: { show: false }, axisLine: { lineStyle: { color: c.border } }, axisTick: { show: false } });
    yAxes.push({ gridIndex: subIdx, splitNumber: 2, axisLabel: { color: c.fgSec, fontSize: 9 }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } });
  }

  if (ind.vol) {
    addSubGrid("VOL");
    yAxes[subIdx].axisLabel.formatter = (v: number) => formatVolume(v);
    series.push({ name: "成交量", type: "bar", xAxisIndex: subIdx, yAxisIndex: subIdx, data: volumes.map((v, i) => ({ value: v, itemStyle: { color: candleData[i][1] >= candleData[i][0] ? c.up : c.down, opacity: 0.4 } })), barWidth: "60%" });
    subIdx++; subTop += subH + gap;
  }

  if (ind.macd) {
    const macd = calcMACD(closes);
    addSubGrid("MACD");
    yAxes[subIdx].axisLabel.formatter = (v: number) => v.toFixed(2);
    series.push({ name: "MACD", type: "bar", xAxisIndex: subIdx, yAxisIndex: subIdx, data: macd.histogram.map(v => v == null ? null : ({ value: v, itemStyle: { color: v >= 0 ? c.up : c.down, opacity: 0.5 } })), barWidth: "60%" });
    series.push({ name: "DIF", type: "line", data: macd.dif, xAxisIndex: subIdx, yAxisIndex: subIdx, symbol: "none", lineStyle: { width: 1, color: c.fg } });
    series.push({ name: "DEA", type: "line", data: macd.dea, xAxisIndex: subIdx, yAxisIndex: subIdx, symbol: "none", lineStyle: { width: 1, color: "#F59E0B" } });
    subIdx++; subTop += subH + gap;
  }

  if (ind.kdj) {
    const kdj = calcKDJ(highs, lows, closes);
    addSubGrid("KDJ");
    yAxes[subIdx].axisLabel.formatter = (v: number) => v.toFixed(0);
    series.push({ name: "K", type: "line", data: kdj.k, xAxisIndex: subIdx, yAxisIndex: subIdx, symbol: "none", lineStyle: { width: 1, color: c.fg } });
    series.push({ name: "D", type: "line", data: kdj.d, xAxisIndex: subIdx, yAxisIndex: subIdx, symbol: "none", lineStyle: { width: 1, color: "#F59E0B" } });
    series.push({ name: "J", type: "line", data: kdj.j, xAxisIndex: subIdx, yAxisIndex: subIdx, symbol: "none", lineStyle: { width: 1, color: c.accent } });
    subIdx++; subTop += subH + gap;
  }

  if (ind.rsi) {
    const rsi = calcRSI(closes);
    addSubGrid("RSI");
    yAxes[subIdx].axisLabel.formatter = (v: number) => v.toFixed(0);
    yAxes[subIdx].min = 0;
    yAxes[subIdx].max = 100;
    series.push({ name: "RSI", type: "line", data: rsi.values, xAxisIndex: subIdx, yAxisIndex: subIdx, symbol: "none", lineStyle: { width: 1.5, color: c.primary } });
    subIdx++; subTop += subH + gap;
  }

  const allXAxisIndices: number[] = [];
  for (let i = 0; i < subIdx; i++) allXAxisIndices.push(i);

  return {
    backgroundColor: "transparent",
    animation: false,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross", lineStyle: { color: c.fgMuted, width: 1, type: "dashed" }, label: { backgroundColor: c.primary } },
      backgroundColor: c.tooltipBg, borderColor: c.border, borderWidth: 1, padding: [8, 12],
      textStyle: { color: c.fg, fontSize: 12, fontFamily: "JetBrains Mono, monospace" },
      formatter: (params: any[]) => buildTooltip(params, c),
    },
    legend: {
      show: legendData.length > 0,
      top: 4, right: 8,
      data: legendData,
      textStyle: { color: c.fgSec, fontSize: 10 },
      itemWidth: 14, itemHeight: 2, inactiveColor: c.fgMuted,
    },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    series: series,
    dataZoom: [
      { type: "inside", xAxisIndex: allXAxisIndices, start: 50, end: 100 },
      {
        show: true, type: "slider", xAxisIndex: allXAxisIndices, bottom: 4, height: 18,
        start: 50, end: 100, borderColor: "transparent", backgroundColor: c.grid,
        fillerColor: "rgba(59, 130, 246, 0.08)",
        handleStyle: { color: c.primary, borderColor: c.primary },
        moveHandleStyle: { color: c.fgMuted },
        textStyle: { color: c.fgSec, fontSize: 10 },
        dataBackground: { lineStyle: { color: c.fgMuted }, areaStyle: { color: c.grid } },
        selectedDataBackground: { lineStyle: { color: c.primary }, areaStyle: { color: "rgba(59, 130, 246, 0.15)" } },
      },
    ],
  };
}
