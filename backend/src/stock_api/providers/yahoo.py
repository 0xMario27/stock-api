"""雅虎财经数据源。

使用 Yahoo Finance 公开 API（无需 API Key）：
- 行情 + K 线：/v8/finance/chart/{symbol} 一个端点同时返回行情和 OHLC
- 支持：美股 / 港股 / A 股 / 指数 / 外汇 / 商品 / 加密货币

统一代码 -> Yahoo 符号映射：
    SH600519 -> 600519.SS (上交所)
    SZ000651 -> 000651.SZ (深交所)
    HK02020  -> 02020.HK (港交所)
    USAAPL   -> AAPL (美股)
    USDJI    -> ^DJI (道琼斯指数)
    COMXAU   -> GC=F (COMEX 黄金期货)
    bitcoin  -> BTC-USD (加密货币)
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from stock_api.core.base import DataProvider
from stock_api.core.exceptions import StockRequestError
from stock_api.core.models import (
    AssetClass,
    Inspection,
    Kline,
    KlineAdjust,
    KlineOptions,
    KlinePeriod,
    Market,
    Quote,
    Symbol,
    default_quote,
)
from stock_api.market.codes import detect_market
from stock_api.market.kline import create_kline, normalize_kline_options
from stock_api.providers._shared import create_inspection
from stock_api.utils.http import fetch_json

_BASE_URL = "https://query1.finance.yahoo.com"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; stock-api-py/2.7)"}

# 统一代码 -> Yahoo 符号
def _to_yahoo_symbol(code: str) -> str:
    u = code.upper()
    if u.startswith("SH"):
        return u[2:] + ".SS"
    if u.startswith("SZ"):
        return u[2:] + ".SZ"
    if u.startswith("HK"):
        return u[2:] + ".HK"
    if u.startswith("US"):
        rest = u[2:]
        if rest == "DJI":
            return "^DJI"
        if rest == "IXIC":
            return "^IXIC"
        if rest == "INX" or rest == "SPX":
            return "^GSPC"
        if rest == "XAU":
            return "GC=F"
        if rest == "XAG":
            return "SI=F"
        if rest == "CL":
            return "CL=F"
        return rest
    if u.startswith("FUT"):
        inner = u[3:]
        if inner.startswith("IF"):
            return inner + ".CFX"
        return inner + ".CFX"
    if u.startswith("COM"):
        inner = u[3:]
        commodity_map = {"XAU": "GC=F", "XAG": "SI=F", "CL": "CL=F", "NG": "NG=F", "HG": "HG=F"}
        return commodity_map.get(inner, inner + "=F")
    # crypto: bitcoin -> BTC-USD
    lower = code.lower()
    crypto_map = {
        "bitcoin": "BTC-USD", "ethereum": "ETH-USD", "binancecoin": "BNB-USD",
        "solana": "SOL-USD", "ripple": "XRP-USD", "cardano": "ADA-USD",
        "dogecoin": "DOGE-USD", "polkadot": "DOT-USD", "chainlink": "LINK-USD",
        "litecoin": "LTC-USD", "tron": "TRX-USD",
    }
    return crypto_map.get(lower, code.upper() + "-USD")


def _period_to_range(period: KlinePeriod) -> str:
    """Yahoo range 参数。"""
    mapping = {
        KlinePeriod.MINUTE_1: "1d",
        KlinePeriod.MINUTE_5: "5d",
        KlinePeriod.MINUTE_15: "1mo",
        KlinePeriod.MINUTE_30: "1mo",
        KlinePeriod.HOUR: "3mo",
        KlinePeriod.DAY: "6mo",
        KlinePeriod.WEEK: "2y",
        KlinePeriod.MONTH: "10y",
    }
    return mapping.get(period, "6mo")


def _period_to_interval(period: KlinePeriod) -> str:
    """Yahoo interval 参数。"""
    mapping = {
        KlinePeriod.MINUTE_1: "1m",
        KlinePeriod.MINUTE_5: "5m",
        KlinePeriod.MINUTE_15: "15m",
        KlinePeriod.MINUTE_30: "30m",
        KlinePeriod.HOUR: "60m",
        KlinePeriod.DAY: "1d",
        KlinePeriod.WEEK: "1wk",
        KlinePeriod.MONTH: "1mo",
    }
    return mapping.get(period, "1d")


class YahooProvider(DataProvider):
    """雅虎财经数据源。支持全市场类型。"""

    name = "yahoo"
    asset_class = AssetClass.STOCK
    supported_markets = [
        Market.CN_A, Market.HK, Market.US, Market.INDEX, Market.FUND,
        Market.FUTURE, Market.COMMODITY, Market.CRYPTO,
    ]

    async def get_quote(self, code: str) -> Quote:
        quotes = await self.get_quotes([code])
        return quotes[0] if quotes else default_quote(code, self.name)

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        import asyncio

        normalized = [c.strip() for c in codes if c and c.strip()]
        if not normalized:
            return []
        return await asyncio.gather(*[self._fetch_one(c) for c in normalized])

    async def _fetch_one(self, code: str) -> Quote:
        symbol = _to_yahoo_symbol(code)
        url = f"{_BASE_URL}/v8/finance/chart/{quote(symbol)}?interval=1d&range=5d"
        try:
            data = await fetch_json(url, headers=_HEADERS, timeout=8.0)
        except StockRequestError:
            return default_quote(code, self.name)

        result = (data or {}).get("chart", {}).get("result")
        if not result or not isinstance(result, list):
            return default_quote(code, self.name)

        meta = result[0].get("meta", {})
        now = _num(meta.get("regularMarketPrice"))
        if not now:
            return default_quote(code, self.name)

        prev = _num(meta.get("chartPreviousClose") or meta.get("previousClose"))
        high = _num(meta.get("regularMarketDayHigh"))
        low = _num(meta.get("regularMarketDayLow"))
        percent = (now - prev) / prev if prev else 0.0
        name = meta.get("longName") or meta.get("shortName") or code

        # 推断 asset_class 和 market
        ac = AssetClass.CRYPTO if "-USD" in symbol or "-EUR" in symbol else AssetClass.STOCK
        market = detect_market(code)

        return Quote(
            code=code,
            name=name,
            now=now,
            low=low,
            high=high,
            yesterday=prev,
            percent=percent,
            source=self.name,
            asset_class=ac,
            market=market,
        )

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)
        if opts.adjust != KlineAdjust.NONE:
            return []

        symbol = _to_yahoo_symbol(code)
        interval = _period_to_interval(opts.period)
        range_ = _period_to_range(opts.period)
        url = f"{_BASE_URL}/v8/finance/chart/{quote(symbol)}?interval={interval}&range={range_}"

        try:
            data = await fetch_json(url, headers=_HEADERS, timeout=10.0)
        except StockRequestError:
            return []

        result = (data or {}).get("chart", {}).get("result")
        if not result or not isinstance(result, list):
            return []

        r = result[0]
        timestamps = r.get("timestamp") or []
        quotes_data = r.get("indicators", {}).get("quote", [{}])
        if not quotes_data:
            return []
        q = quotes_data[0]

        opens = q.get("open") or []
        closes = q.get("close") or []
        highs = q.get("high") or []
        lows = q.get("low") or []
        volumes = q.get("volume") or []

        is_intraday = opts.period in (
            KlinePeriod.MINUTE_1, KlinePeriod.MINUTE_5, KlinePeriod.MINUTE_15,
            KlinePeriod.MINUTE_30, KlinePeriod.HOUR,
        )

        klines: list[Kline] = []
        for i, ts in enumerate(timestamps):
            if i >= len(closes) or closes[i] is None:
                continue
            from datetime import UTC, datetime
            dt = datetime.fromtimestamp(ts, tz=UTC)
            date_str = dt.strftime("%Y-%m-%d %H:%M") if is_intraday else dt.strftime("%Y-%m-%d")

            klines.append(create_kline(
                date=date_str,
                open_price=opens[i] if i < len(opens) else 0,
                close=closes[i],
                high=highs[i] if i < len(highs) else 0,
                low=lows[i] if i < len(lows) else 0,
                volume=volumes[i] if i < len(volumes) else None,
                source=self.name,
                timestamp=ts,
            ))

        return klines[-opts.count:] if len(klines) > opts.count else klines

    async def search_symbols(self, query: str) -> list[Symbol]:
        url = f"{_BASE_URL}/v1/finance/search?q={quote(query)}&quotesCount=15&newsCount=0"
        try:
            data = await fetch_json(url, headers=_HEADERS, timeout=8.0)
        except StockRequestError:
            return []

        results = []
        for item in (data or {}).get("quotes", []):
            symbol = item.get("symbol", "")
            if not symbol:
                continue
            # 映射 Yahoo 符号回统一代码
            unified = _from_yahoo_symbol(symbol)
            if not unified:
                continue
            results.append(Symbol(
                code=unified,
                name=item.get("longname") or item.get("shortname") or unified,
                market=detect_market(unified),
                asset_class=AssetClass.CRYPTO if item.get("quoteType") == "CRYPTOCURRENCY" else AssetClass.STOCK,
            ))
        return results

    async def inspect(self, code: str) -> Inspection:
        return await create_inspection(self.name, code, self.get_quote)


def _from_yahoo_symbol(symbol: str) -> str | None:
    """Yahoo 符号 -> 统一代码。"""
    s = symbol.upper()
    # A 股
    if s.endswith(".SS"):
        return "SH" + s[:-3]
    if s.endswith(".SZ"):
        return "SZ" + s[:-3]
    # 港股
    if s.endswith(".HK"):
        return "HK" + s[:-3].zfill(5)
    # 指数
    if s == "^DJI":
        return "USDJI"
    if s == "^IXIC":
        return "USIXIC"
    if s in ("^GSPC", "^SPX"):
        return "USINX"
    # 商品期货
    commodity_rev = {"GC=F": "COMXAU", "SI=F": "COMXAG", "CL=F": "COMCL", "NG=F": "COMNG", "HG=F": "COMHG"}
    if s in commodity_rev:
        return commodity_rev[s]
    # 加密货币
    if "-USD" in s:
        crypto_rev = {
            "BTC-USD": "bitcoin", "ETH-USD": "ethereum", "BNB-USD": "binancecoin",
            "SOL-USD": "solana", "XRP-USD": "ripple", "ADA-USD": "cardano",
            "DOGE-USD": "dogecoin", "DOT-USD": "polkadot", "LINK-USD": "chainlink",
            "LTC-USD": "litecoin", "TRX-USD": "tron",
        }
        if s in crypto_rev:
            return crypto_rev[s]
        return s.replace("-USD", "").lower()
    # 美股
    if s and not s.startswith("^") and "=" not in s:
        return "US" + s
    return None


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if result == result else 0.0
