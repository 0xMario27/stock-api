"""Binance 加密货币数据源。

使用 Binance 公开市场数据 API（data-api.binance.vision，无需 API Key）：
- 行情：/api/v3/ticker/24hr，返回 lastPrice / highPrice / lowPrice / priceChangePercent
- K 线：/api/v3/klines，返回 [openTime, open, high, low, close, volume, ...]
- 搜索：静态映射表 + exchangeInfo 缓存

统一代码：CoinGecko coin ID（如 bitcoin / ethereum），与 CoinGecko provider 一致。
内部通过 _COIN_ID_MAP 将 coin ID 转为 Binance 交易对（如 BTCUSDT）。

auto 兜底顺序：CoinGecko（coin ID 原生）-> Binance（coin ID 映射为交易对）。
Binance 限流远宽于 CoinGecko（1200/min vs 5-15/min），作为可靠 fallback。
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
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
from stock_api.market.kline import create_kline, normalize_kline_options
from stock_api.providers._shared import create_inspection
from stock_api.utils.http import fetch_json

_BASE_URL = "https://data-api.binance.vision/api/v3"
_DEFAULT_HEADERS = {"Accept": "application/json"}

# coin ID -> (Binance symbol, name)
_COIN_MAP: dict[str, tuple[str, str]] = {
    "bitcoin": ("BTCUSDT", "Bitcoin"),
    "ethereum": ("ETHUSDT", "Ethereum"),
    "binancecoin": ("BNBUSDT", "BNB"),
    "solana": ("SOLUSDT", "Solana"),
    "ripple": ("XRPUSDT", "XRP"),
    "cardano": ("ADAUSDT", "Cardano"),
    "dogecoin": ("DOGEUSDT", "Dogecoin"),
    "polkadot": ("DOTUSDT", "Polkadot"),
    "chainlink": ("LINKUSDT", "Chainlink"),
    "litecoin": ("LTCUSDT", "Litecoin"),
    "tron": ("TRXUSDT", "TRON"),
    "shiba-inu": ("SHIBUSDT", "Shiba Inu"),
    "uniswap": ("UNIUSDT", "Uniswap"),
    "cosmos": ("ATOMUSDT", "Cosmos"),
    "stellar": ("XLMUSDT", "Stellar"),
    "near": ("NEARUSDT", "NEAR Protocol"),
    "aptos": ("APTUSDT", "Aptos"),
    "filecoin": ("FILUSDT", "Filecoin"),
    "avalanche-2": ("AVAXUSDT", "Avalanche"),
    "polygon": ("MATICUSDT", "Polygon"),
    "internet-computer": ("ICPUSDT", "Internet Computer"),
    "arbitrum": ("ARBUSDT", "Arbitrum"),
    "optimism": ("OPUSDT", "Optimism"),
    "injective-protocol": ("INJUSDT", "Injective"),
    "the-graph": ("GRTUSDT", "The Graph"),
    "aave": ("AAVEUSDT", "Aave"),
    "fantom": ("FTMUSDT", "Fantom"),
    "hedera-hashgraph": ("HBARUSDT", "Hedera"),
    "sui": ("SUIUSDT", "Sui"),
    "sei-network": ("SEIUSDT", "Sei"),
    "render-token": ("RNDRUSDT", "Render"),
    "the-sandbox": ("SANDUSDT", "The Sandbox"),
    "decentraland": ("MANAUSDT", "Decentraland"),
    "tezos": ("XTZUSDT", "Tezos"),
    "algorand": ("ALGOUSDT", "Algorand"),
    "vechain": ("VETUSDT", "VeChain"),
    "theta-token": ("THETAUSDT", "Theta Network"),
    "eos": ("EOSUSDT", "EOS"),
    "flow": ("FLOWUSDT", "Flow"),
    "chiliz": ("CHZUSDT", "Chiliz"),
}

# 反向映射：symbol -> (coin ID, name)
_SYMBOL_TO_COIN: dict[str, tuple[str, str]] = {
    sym: (cid, name) for cid, (sym, name) in _COIN_MAP.items()
}

_QUOTE_CACHE_TTL = 30
_QUOTE_STALE_TTL = 300
_KLINE_CACHE_TTL = 120
_KLINE_STALE_TTL = 600


class _TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get_fresh(self, key: str, ttl: float) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts < ttl:
            return data
        return None

    def get_stale(self, key: str, max_age: float) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts < max_age:
            return data
        return None

    def set(self, key: str, data: Any) -> None:
        self._store[key] = (time.monotonic(), data)


def _coin_id_to_symbol(coin_id: str) -> str | None:
    """coin ID -> Binance 交易对，映射表未命中时尝试大写+USDT。"""
    entry = _COIN_MAP.get(coin_id.lower())
    if entry:
        return entry[0]
    # 尝试直接构造：bitcoin -> BTCUSDT 不行，但 btc -> BTCUSDT 可以
    upper = coin_id.upper()
    if upper.endswith("USDT"):
        return upper
    # 短代码（3-5位字母）尝试加 USDT
    if 2 <= len(upper) <= 6 and upper.isalpha():
        return upper + "USDT"
    return None


class BinanceProvider(DataProvider):
    """Binance 加密货币数据源，内置 TTL 缓存。"""

    name = "binance"
    asset_class = AssetClass.CRYPTO
    supported_markets = [Market.CRYPTO]

    def __init__(self) -> None:
        self._cache = _TTLCache()

    async def get_quote(self, code: str) -> Quote:
        quotes = await self.get_quotes([code])
        return quotes[0] if quotes else default_quote(code, self.name)

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        normalized = [c.strip() for c in codes if c and c.strip()]
        if not normalized:
            return []

        # 映射 coin ID -> Binance symbol
        symbol_map: list[tuple[str, str | None]] = [
            (cid, _coin_id_to_symbol(cid)) for cid in normalized
        ]
        valid_symbols = [sym for _, sym in symbol_map if sym]
        if not valid_symbols:
            return [default_quote(c, self.name) for c in normalized]

        cache_key = "tickers:" + ",".join(valid_symbols)
        cached = self._cache.get_fresh(cache_key, _QUOTE_CACHE_TTL)

        if cached is None:
            try:
                if len(valid_symbols) == 1:
                    url = f"{_BASE_URL}/ticker/24hr?symbol={valid_symbols[0]}"
                else:
                    symbols_json = json.dumps(valid_symbols, separators=(",", ":"))
                    url = f"{_BASE_URL}/ticker/24hr?symbols={quote(symbols_json, safe='')}"
                data = await fetch_json(url, headers=_DEFAULT_HEADERS)
                if isinstance(data, list):
                    self._cache.set(cache_key, data)
                elif isinstance(data, dict):
                    self._cache.set(cache_key, [data])
                    data = [data]
                else:
                    data = []
            except StockRequestError:
                stale = self._cache.get_stale(cache_key, _QUOTE_STALE_TTL)
                if stale is not None:
                    data = stale
                else:
                    return [default_quote(c, self.name) for c in normalized]
        else:
            data = cached

        # 构建 symbol -> ticker 映射
        ticker_map: dict[str, dict] = {}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "symbol" in item:
                    ticker_map[item["symbol"]] = item

        result: list[Quote] = []
        for cid, sym in symbol_map:
            if sym and sym in ticker_map:
                result.append(self._parse_quote(cid, sym, ticker_map[sym]))
            else:
                result.append(default_quote(cid, self.name))
        return result

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)
        if opts.adjust != KlineAdjust.NONE:
            return []

        symbol = _coin_id_to_symbol(code)
        if not symbol:
            return []

        interval = self._period_to_interval(opts.period)
        cache_key = f"klines:{symbol}:{interval}:{opts.count}"

        cached = self._cache.get_fresh(cache_key, _KLINE_CACHE_TTL)
        if cached is not None:
            return self._build_klines(cached)

        url = f"{_BASE_URL}/klines?symbol={symbol}&interval={interval}&limit={opts.count}"
        try:
            data = await fetch_json(url, headers=_DEFAULT_HEADERS)
            if isinstance(data, list) and data:
                self._cache.set(cache_key, data)
                return self._build_klines(data)
            return []
        except StockRequestError:
            stale = self._cache.get_stale(cache_key, _KLINE_STALE_TTL)
            if stale is not None:
                return self._build_klines(stale)
            raise

    async def search_symbols(self, query: str) -> list[Symbol]:
        q = query.lower().strip()
        if not q:
            return []

        results: list[Symbol] = []
        for coin_id, (symbol, name) in _COIN_MAP.items():
            if q in coin_id or q in name.lower() or q in symbol.lower():
                results.append(
                    Symbol(
                        code=coin_id,
                        name=name,
                        market=Market.CRYPTO,
                        asset_class=AssetClass.CRYPTO,
                    )
                )
                if len(results) >= 20:
                    break
        return results

    async def inspect(self, code: str) -> Inspection:
        return await create_inspection(self.name, code, self.get_quote)

    def _parse_quote(self, coin_id: str, symbol: str, ticker: dict) -> Quote:
        now = _num(ticker.get("lastPrice"))
        high = _num(ticker.get("highPrice"))
        low = _num(ticker.get("lowPrice"))
        yesterday = _num(ticker.get("prevClosePrice"))
        pct = _num(ticker.get("priceChangePercent"))
        percent = pct / 100 if pct else 0.0

        name = _COIN_MAP.get(coin_id, (symbol, symbol))[1]

        return Quote(
            code=coin_id,
            name=name,
            now=now,
            low=low,
            high=high,
            yesterday=yesterday,
            percent=percent,
            source=self.name,
            asset_class=AssetClass.CRYPTO,
            market=Market.CRYPTO,
            open_price=_num_or_none(ticker.get("openPrice")),
            volume=_num_or_none(ticker.get("volume")),
            turnover=_num_or_none(ticker.get("quoteVolume")),
        )

    def _period_to_interval(self, period: KlinePeriod) -> str:
        m = {
            KlinePeriod.MINUTE_1: "1m",
            KlinePeriod.MINUTE_5: "5m",
            KlinePeriod.MINUTE_15: "15m",
            KlinePeriod.MINUTE_30: "30m",
            KlinePeriod.HOUR: "1h",
            KlinePeriod.DAY: "1d",
            KlinePeriod.WEEK: "1w",
            KlinePeriod.MONTH: "1M",
        }
        return m.get(period, "1d")

    def _build_klines(self, data: list) -> list[Kline]:
        klines: list[Kline] = []
        for row in data:
            if not isinstance(row, list) or len(row) < 6:
                continue
            ts = row[0]
            date = datetime.fromtimestamp(ts / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M" if ts % 86400000 != 0 else "%Y-%m-%d")
            klines.append(
                create_kline(
                    date=date,
                    open_price=row[1],
                    close=row[4],
                    high=row[2],
                    low=row[3],
                    volume=row[5],
                    source=self.name,
                    timestamp=ts // 1000,
                )
            )
        return klines


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if result == result else 0.0


def _num_or_none(value: Any) -> float | None:
    if value is None or value == "" or value == "-":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None
