/* 技术指标计算工具库 */

export interface BOLLResult {
  upper: (number | null)[];
  middle: (number | null)[];
  lower: (number | null)[];
}

export interface MACDResult {
  dif: (number | null)[];
  dea: (number | null)[];
  histogram: (number | null)[];
}

export interface KDJResult {
  k: (number | null)[];
  d: (number | null)[];
  j: (number | null)[];
}

export interface RSIResult {
  values: (number | null)[];
}

export interface VWAPResult {
  values: (number | null)[];
}

/* 简单移动平均 */
export function calcMA(closes: number[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { result.push(null); continue; }
    let sum = 0;
    for (let j = 0; j < period; j++) sum += closes[i - j];
    result.push(sum / period);
  }
  return result;
}

/* 指数移动平均 */
export function calcEMA(values: number[], period: number): number[] {
  const result: number[] = [];
  const k = 2 / (period + 1);
  for (let i = 0; i < values.length; i++) {
    if (i === 0) { result.push(values[0]); }
    else { result.push(values[i] * k + result[i - 1] * (1 - k)); }
  }
  return result;
}

/* 布林带 BOLL(20, 2) */
export function calcBOLL(closes: number[], period: number = 20, mult: number = 2): BOLLResult {
  const upper: (number | null)[] = [];
  const middle: (number | null)[] = [];
  const lower: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { upper.push(null); middle.push(null); lower.push(null); continue; }
    let sum = 0;
    for (let j = 0; j < period; j++) sum += closes[i - j];
    const ma = sum / period;
    let variance = 0;
    for (let j = 0; j < period; j++) variance += (closes[i - j] - ma) ** 2;
    const std = Math.sqrt(variance / period);
    upper.push(ma + mult * std);
    middle.push(ma);
    lower.push(ma - mult * std);
  }
  return { upper, middle, lower };
}

/* MACD(12, 26, 9) */
export function calcMACD(closes: number[], fast: number = 12, slow: number = 26, signal: number = 9): MACDResult {
  const emaFast = calcEMA(closes, fast);
  const emaSlow = calcEMA(closes, slow);
  const dif: number[] = [];
  for (let i = 0; i < closes.length; i++) dif.push(emaFast[i] - emaSlow[i]);
  const deaRaw = calcEMA(dif, signal);
  const difResult: (number | null)[] = [];
  const dea: (number | null)[] = [];
  const histogram: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < slow - 1) { difResult.push(null); dea.push(null); histogram.push(null); }
    else { difResult.push(dif[i]); dea.push(deaRaw[i]); histogram.push((dif[i] - deaRaw[i]) * 2); }
  }
  return { dif: difResult, dea, histogram };
}

/* KDJ(9, 3, 3) */
export function calcKDJ(highs: number[], lows: number[], closes: number[], n: number = 9, m1: number = 3, m2: number = 3): KDJResult {
  const k: (number | null)[] = [];
  const d: (number | null)[] = [];
  const j: (number | null)[] = [];
  let prevK = 50;
  let prevD = 50;
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) { k.push(null); d.push(null); j.push(null); continue; }
    let hh = highs[i];
    let ll = lows[i];
    for (let p = 1; p < n; p++) {
      if (highs[i - p] > hh) hh = highs[i - p];
      if (lows[i - p] < ll) ll = lows[i - p];
    }
    const rsv = hh === ll ? 0 : ((closes[i] - ll) / (hh - ll)) * 100;
    const curK = (prevK * (m1 - 1) + rsv) / m1;
    const curD = (prevD * (m2 - 1) + curK) / m2;
    const curJ = 3 * curK - 2 * curD;
    k.push(curK);
    d.push(curD);
    j.push(curJ);
    prevK = curK;
    prevD = curD;
  }
  return { k, d, j };
}

/* RSI(14) */
export function calcRSI(closes: number[], period: number = 14): RSIResult {
  const values: (number | null)[] = [];
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 0; i < closes.length; i++) {
    if (i === 0) { values.push(null); continue; }
    const change = closes[i] - closes[i - 1];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? -change : 0;
    if (i <= period) {
      avgGain += gain;
      avgLoss += loss;
      if (i === period) {
        avgGain /= period;
        avgLoss /= period;
        values.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
      } else { values.push(null); }
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
      values.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
    }
  }
  return { values };
}

/* VWAP 成交量加权平均价 */
export function calcVWAP(highs: number[], lows: number[], closes: number[], volumes: number[]): VWAPResult {
  const values: (number | null)[] = [];
  let cumPV = 0;
  let cumVol = 0;
  for (let i = 0; i < closes.length; i++) {
    if (!volumes[i] || volumes[i] === 0) { values.push(null); continue; }
    const tp = (highs[i] + lows[i] + closes[i]) / 3;
    cumPV += tp * volumes[i];
    cumVol += volumes[i];
    values.push(cumVol === 0 ? null : cumPV / cumVol);
  }
  return { values };
}
