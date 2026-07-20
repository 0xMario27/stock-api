import axios from "axios";
import type {
  AutoInspection,
  Kline,
  KlineQuery,
  Quote,
  SourceName,
  Symbol,
} from "@/types";

const http = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

export async function getQuote(code: string, source: SourceName = "auto"): Promise<Quote> {
  const { data } = await http.get<Quote>(`/quote/${code}`, { params: { source } });
  return data;
}

export async function getQuotes(codes: string[], source: SourceName = "auto"): Promise<Quote[]> {
  const { data } = await http.get<Quote[]>("/quotes", {
    params: { codes, source },
  });
  return data;
}

export async function getKlines(code: string, query: KlineQuery = {}): Promise<Kline[]> {
  const { data } = await http.get<Kline[]>(`/klines/${code}`, {
    params: {
      period: query.period ?? "day",
      count: query.count ?? 120,
      adjust: query.adjust ?? "none",
      source: query.source ?? "auto",
    },
  });
  return data;
}

export async function searchSymbols(q: string, source: SourceName = "auto"): Promise<Symbol[]> {
  const { data } = await http.get<Symbol[]>("/search", { params: { q, source } });
  return data;
}

export async function inspectStock(code: string, source: SourceName = "auto"): Promise<AutoInspection> {
  const { data } = await http.get<AutoInspection>(`/inspect/${code}`, { params: { source } });
  return data;
}

export async function listSources(): Promise<string[]> {
  const { data } = await http.get<string[]>("/sources");
  return data;
}

export async function getCapabilities(): Promise<
  Array<{ name: string; asset_class: string; supported_markets: string[] }>
> {
  const { data } = await http.get("/capabilities");
  return data;
}

export async function healthCheck(): Promise<boolean> {
  try {
    const { status } = await http.get("/health");
    return status === 200;
  } catch {
    return false;
  }
}
