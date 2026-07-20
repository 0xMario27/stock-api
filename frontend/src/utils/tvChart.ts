import {
  createChart, CandlestickSeries, LineSeries, HistogramSeries,
  CrosshairMode, LineStyle, ColorType,
  type IChartApi, type ISeriesApi, type Time,
} from "lightweight-charts";
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

function fp(p: number): string {
  if (p >= 1000) return p.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
  if (p >= 1) return p.toFixed(3);
  if (p >= 0.01) return p.toFixed(5);
  return p.toFixed(8);
}
function fv(v: number): string {
  if (!v||v===0) return "-";
  if (v>=1e8) return (v/1e8).toFixed(2)+"亿";
  if (v>=1e4) return (v/1e4).toFixed(2)+"万";
  return v.toFixed(0);
}
function tt(d: string): Time { return d as Time; }
function lineData(times: Time[], vals: (number|null)[]): any[] {
  return times.map((t,j)=>({time:t,value:vals[j]})).filter(d=>d.value!==null);
}

export class TVChartManager {
  private chart: IChartApi | null = null;
  private seriesList: ISeriesApi<any>[] = [];
  private legendEl: HTMLElement | null = null;
  private klines: Kline[] = [];
  private indicators: IndicatorState;
  private colors: ChartColors;
  private container: HTMLElement | null = null;
  private ro: ResizeObserver | null = null;

  constructor(ind: IndicatorState, colors: ChartColors) {
    this.indicators = ind;
    this.colors = colors;
  }

  mount(container: HTMLElement): void {
    this.container = container;
    container.style.position = "relative";
    const c = this.colors;
    this.chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: c.fgSec, fontSize: 11,
        fontFamily: "JetBrains Mono, monospace",
        panes: { separatorColor: c.border, separatorHoverColor: c.fgMuted },
      },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: c.fgMuted, width: 1, style: LineStyle.Dashed, labelBackgroundColor: c.primary },
        horzLine: { color: c.fgMuted, width: 1, style: LineStyle.Dashed, labelBackgroundColor: c.primary },
      },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, rightOffset: 4 },
    });
    this.legendEl = document.createElement("div");
    this.legendEl.style.cssText = "position:absolute;top:4px;left:8px;z-index:10;pointer-events:none;font-family:JetBrains Mono,monospace;font-size:11px;line-height:1.6";
    container.appendChild(this.legendEl);
    this.chart.subscribeCrosshairMove((param:any) => this.onCrosshair(param));
    this.ro = new ResizeObserver(() => {
      if (!this.chart || !this.container) return;
      this.chart.applyOptions({ width: this.container.clientWidth, height: this.container.clientHeight });
    });
    this.ro.observe(container);
  }

  setData(kl: Kline[]): void {
    this.klines = kl;
    this.rebuild();
    this.updateLegend(-1);
  }

  updateIndicators(ind: IndicatorState): void {
    this.indicators = ind;
    this.rebuild();
    this.updateLegend(-1);
  }

  updateColors(colors: ChartColors): void {
    this.colors = colors;
    if (!this.chart) return;
    const c = colors;
    this.chart.applyOptions({
      layout: { textColor: c.fgSec, panes: { separatorColor: c.border, separatorHoverColor: c.fgMuted } },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      crosshair: {
        vertLine: { color: c.fgMuted, labelBackgroundColor: c.primary },
        horzLine: { color: c.fgMuted, labelBackgroundColor: c.primary },
      },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border },
    });
    this.rebuild();
  }

  private rebuild(): void {
    if (!this.chart || this.klines.length === 0) return;
    for (const s of this.seriesList) this.chart.removeSeries(s);
    this.seriesList = [];
    const panes = this.chart.panes();
    for (let i = panes.length - 1; i >= 1; i--) this.chart.removePane(i);

    const kl = this.klines;
    const c = this.colors;
    const ind = this.indicators;
    const times = kl.map(k => tt(k.date));

    // 蜡烛图
    const candle = this.chart.addSeries(CandlestickSeries, {
      upColor: c.up, downColor: c.down, borderUpColor: c.up, borderDownColor: c.down,
      wickUpColor: c.up, wickDownColor: c.down,
    }, 0);
    candle.setData(kl.map(k => ({ time: tt(k.date), open: k.open, high: k.high, low: k.low, close: k.close })));
    this.seriesList.push(candle);

    // MA
    if (ind.ma) {
      const mc = ["#FBBF24", c.primary, c.accent];
      [5,10,20].forEach((p,i) => {
        const s = this.chart!.addSeries(LineSeries, { color: mc[i], lineWidth: 1, priceLineVisible: false, lastValueVisible: false }, 0);
        s.setData(lineData(times, calcMA(kl.map(k=>k.close), p)));
        this.seriesList.push(s);
      });
    }

    // BOLL
    if (ind.boll) {
      const b = calcBOLL(kl.map(k=>k.close));
      const cfgs = [{d:b.upper,c:c.accent,s:LineStyle.Solid},{d:b.middle,c:c.fgMuted,s:LineStyle.Dashed},{d:b.lower,c:c.accent,s:LineStyle.Solid}];
      for (const cfg of cfgs) {
        const s = this.chart!.addSeries(LineSeries, { color: cfg.c, lineWidth: 1, lineStyle: cfg.s, priceLineVisible: false, lastValueVisible: false }, 0);
        s.setData(lineData(times, cfg.d));
        this.seriesList.push(s);
      }
    }

    // VWAP
    if (ind.vwap) {
      const v = calcVWAP(kl.map(k=>k.high), kl.map(k=>k.low), kl.map(k=>k.close), kl.map(k=>k.volume??0));
      const s = this.chart.addSeries(LineSeries, { color: "#F59E0B", lineWidth: 2, priceLineVisible: false, lastValueVisible: false }, 0);
      s.setData(lineData(times, v.values));
      this.seriesList.push(s);
    }

    // 主 pane 高度
    const subN = (ind.vol?1:0)+(ind.macd?1:0)+(ind.kdj?1:0)+(ind.rsi?1:0);
    this.chart.panes()[0].setStretchFactor(subN > 0 ? 3 : 1);

    let pi = 1;

    // Volume
    if (ind.vol) {
      this.chart.addPane().setStretchFactor(1);
      const vs = this.chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol" }, pi);
      vs.setData(kl.map(k => ({ time: tt(k.date), value: k.volume??0, color: k.close>=k.open ? c.up+"50" : c.down+"50" })));
      this.seriesList.push(vs);
      pi++;
    }

    // MACD
    if (ind.macd) {
      const m = calcMACD(kl.map(k=>k.close));
      this.chart.addPane().setStretchFactor(1);
      const hs = this.chart.addSeries(HistogramSeries, {}, pi);
      hs.setData(times.map((t,j)=>({time:t,value:m.histogram[j]??0,color:(m.histogram[j]??0)>=0?c.up+"60":c.down+"60"})));
      this.seriesList.push(hs);
      const ds = this.chart.addSeries(LineSeries,{color:c.fg,lineWidth:1,priceLineVisible:false,lastValueVisible:false},pi);
      ds.setData(lineData(times, m.dif));
      this.seriesList.push(ds);
      const es = this.chart.addSeries(LineSeries,{color:"#F59E0B",lineWidth:1,priceLineVisible:false,lastValueVisible:false},pi);
      es.setData(lineData(times, m.dea));
      this.seriesList.push(es);
      pi++;
    }

    // KDJ
    if (ind.kdj) {
      const k = calcKDJ(kl.map(x=>x.high), kl.map(x=>x.low), kl.map(x=>x.close));
      this.chart.addPane().setStretchFactor(1);
      const ks = this.chart.addSeries(LineSeries,{color:c.fg,lineWidth:1,priceLineVisible:false,lastValueVisible:false},pi);
      ks.setData(lineData(times, k.k)); this.seriesList.push(ks);
      const ds = this.chart.addSeries(LineSeries,{color:"#F59E0B",lineWidth:1,priceLineVisible:false,lastValueVisible:false},pi);
      ds.setData(lineData(times, k.d)); this.seriesList.push(ds);
      const js = this.chart.addSeries(LineSeries,{color:c.accent,lineWidth:1,priceLineVisible:false,lastValueVisible:false},pi);
      js.setData(lineData(times, k.j)); this.seriesList.push(js);
      pi++;
    }

    // RSI
    if (ind.rsi) {
      const r = calcRSI(kl.map(k=>k.close));
      this.chart.addPane().setStretchFactor(1);
      const rs = this.chart.addSeries(LineSeries,{color:c.primary,lineWidth:2,priceLineVisible:false,lastValueVisible:false},pi);
      rs.setData(lineData(times, r.values));
      this.seriesList.push(rs);
      pi++;
    }

    this.chart.timeScale().fitContent();
  }

  private onCrosshair(param: any): void {
    if (!param || !param.time) { this.updateLegend(-1); return; }
    const idx = this.klines.findIndex(k => k.date === param.time);
    if (idx >= 0) this.updateLegend(idx);
  }

  private updateLegend(idx: number): void {
    if (!this.legendEl) return;
    const kl = this.klines;
    if (kl.length === 0) { this.legendEl.innerHTML = ""; return; }
    const i = idx >= 0 ? idx : kl.length - 1;
    const k = kl[i];
    const c = this.colors;
    const chg = k.close - k.open;
    const chgPct = k.open ? (chg / k.open * 100).toFixed(2) : "0.00";
    const cc = chg >= 0 ? c.up : c.down;
    const ind = this.indicators;

    let html = '<div style="margin-bottom:2px">';
    html += '<span style="color:'+c.fg+';font-weight:600">O</span> <span style="color:'+c.fgSec+'">'+fp(k.open)+'</span>';
    html += ' <span style="color:'+c.fg+';font-weight:600">H</span> <span style="color:'+c.up+'">'+fp(k.high)+'</span>';
    html += ' <span style="color:'+c.fg+';font-weight:600">L</span> <span style="color:'+c.down+'">'+fp(k.low)+'</span>';
    html += ' <span style="color:'+c.fg+';font-weight:600">C</span> <span style="color:'+cc+'">'+fp(k.close)+'</span>';
    html += ' <span style="color:'+cc+'">'+(chg>=0?"+":"")+chg.toFixed(2)+' ('+chgPct+'%)</span>';
    html += '</div>';

    const closes = kl.map(x => x.close);
    const secondRow: string[] = [];
    if (ind.ma) {
      [5,10,20].forEach((p) => {
        const data = calcMA(closes, p);
        const v = data[i];
        if (v != null) secondRow.push('<span style="color:#FBBF24">MA'+p+'</span> <span style="color:'+c.fgSec+'">'+fp(v)+'</span>');
      });
    }
    if (ind.boll) {
      const b = calcBOLL(closes);
      if (b.upper[i] != null) {
        secondRow.push('<span style="color:'+c.accent+'">BOLL</span> <span style="color:'+c.fgSec+'">'+fp(b.upper[i]!)+'/'+fp(b.middle[i]!)+'/'+fp(b.lower[i]!)+'</span>');
      }
    }
    if (ind.vwap) {
      const v = calcVWAP(kl.map(x=>x.high),kl.map(x=>x.low),closes,kl.map(x=>x.volume??0));
      if (v.values[i] != null) secondRow.push('<span style="color:#F59E0B">VWAP</span> <span style="color:'+c.fgSec+'">'+fp(v.values[i]!)+'</span>');
    }
    if (ind.vol) secondRow.push('<span style="color:'+c.fgMuted+'">VOL</span> <span style="color:'+c.fgSec+'">'+fv(k.volume??0)+'</span>');
    if (ind.macd) {
      const m = calcMACD(closes);
      if (m.dif[i] != null) secondRow.push('<span style="color:'+c.fg+'">MACD</span> <span style="color:'+c.fgSec+'">'+(m.dif[i]??0).toFixed(2)+'/'+(m.dea[i]??0).toFixed(2)+'/'+(m.histogram[i]??0).toFixed(2)+'</span>');
    }
    if (ind.kdj) {
      const kd = calcKDJ(kl.map(x=>x.high),kl.map(x=>x.low),closes);
      if (kd.k[i] != null) secondRow.push('<span style="color:'+c.accent+'">KDJ</span> <span style="color:'+c.fgSec+'">'+(kd.k[i]??0).toFixed(1)+'/'+(kd.d[i]??0).toFixed(1)+'/'+(kd.j[i]??0).toFixed(1)+'</span>');
    }
    if (ind.rsi) {
      const r = calcRSI(closes);
      if (r.values[i] != null) secondRow.push('<span style="color:'+c.primary+'">RSI</span> <span style="color:'+c.fgSec+'">'+(r.values[i]??0).toFixed(1)+'</span>');
    }
    if (secondRow.length > 0) html += '<div style="margin-bottom:2px">'+secondRow.join("  ")+'</div>';

    html += '<div style="color:'+c.fgMuted+';font-size:10px">'+k.date+'</div>';
    this.legendEl.innerHTML = html;
  }

  resize(): void {
    if (this.chart && this.container) {
      this.chart.applyOptions({ width: this.container.clientWidth, height: this.container.clientHeight });
    }
  }

  destroy(): void {
    this.ro?.disconnect();
    this.ro = null;
    this.chart?.remove();
    this.chart = null;
    this.seriesList = [];
    if (this.legendEl) { this.legendEl.remove(); this.legendEl = null; }
    this.container = null;
  }
}
