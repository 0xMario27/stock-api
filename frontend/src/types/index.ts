// 后端返回的数据模型，与 backend/src/stock_api/core/models.py 对齐

export type AssetClass = "stock" | "crypto";
export type Market = "cn_a" | "hk" | "us" | "crypto" | "index" | "fund" | "future" | "option" | "commodity";
export type KlinePeriod = "minute1" | "minute5" | "minute15" | "minute30" | "hour" | "day" | "week" | "month";
export type KlineAdjust = "none" | "qfq" | "hfq";
export type InspectionStatus = "success" | "empty" | "error";
export type SourceName = "auto" | "tencent" | "sina" | "eastmoney" | "yahoo" | "coingecko" | "binance";

export interface Quote {
  code: string;
  name: string;
  now: number;
  low: number;
  high: number;
  yesterday: number;
  percent: number;
  source: string;
  asset_class: AssetClass;
  market: Market | null;
  open_price?: number | null;
  volume?: number | null;
  turnover?: number | null;
  pe_ratio?: number | null;
  pb_ratio?: number | null;
  market_cap?: number | null;
  circulating_cap?: number | null;
  high_52w?: number | null;
  low_52w?: number | null;
}

export interface Kline {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number | null;
  source: string;
  timestamp?: number | null;
}

export interface Symbol {
  code: string;
  name: string;
  market: Market | null;
  asset_class: AssetClass;
}

export interface Inspection {
  code: string;
  source: string;
  status: InspectionStatus;
  quote: Quote | null;
  error: string | null;
}

export interface AutoInspection {
  code: string;
  source: string;
  quote: Quote;
  sources: Inspection[];
}

export interface KlineQuery {
  period?: KlinePeriod;
  count?: number;
  adjust?: KlineAdjust;
  source?: SourceName;
}
