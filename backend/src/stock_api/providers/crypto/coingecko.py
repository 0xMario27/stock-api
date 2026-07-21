"""CoinGecko 加密货币数据源。

使用 CoinGecko 公开 API（无需 API Key）：
- 行情：coins/markets 端点，返回 current_price / high_24h / low_24h / price_change_percentage_24h
- K 线：coins/{id}/ohlc 端点，返回 [timestamp, open, high, low, close]
- 搜索：search 端点，返回匹配的 coins

统一代码：CoinGecko coin ID（如 bitcoin / ethereum / binancecoin），与股票的 SH/SZ/HK/US 前缀格式天然区分。

限流策略：
- CoinGecko 免费 API 限制约 5-15 次/分钟
- 内置 TTL 缓存：行情 60s / K 线 300s，减少 API 调用
- 429 限流时返回过期缓存（最多 10 分钟），而非全零默认值
- 二期若要接入更多 crypto 数据源（如 Binance），只需新建 providers/crypto/binance.py，
  继承 DataProvider 并设置 asset_class = CRYPTO，注册到 registry 即可，auto 路由自动生效。
"""

from __future__ import annotations

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

_BASE_URL = "https://api.coingecko.com/api/v3"
_DEFAULT_HEADERS = {"Accept": "application/json"}

# 缓存 TTL（秒）
_QUOTE_FRESH_TTL = 60      # 新鲜缓存：60s 内直接用，不发请求
_QUOTE_STALE_TTL = 600     # 过期缓存：429 时最多用 10 分钟前的
_KLINE_FRESH_TTL = 300     # K 线新鲜缓存 5 分钟
_KLINE_STALE_TTL = 1800    # K 线过期缓存 30 分钟


class _TTLCache:
    """简单的 TTL 缓存，区分 fresh 和 stale 两个阈值。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}

    def get_fresh(self, key: str, ttl: float) -> Any | None:
        """返回新鲜缓存（age < ttl），否则 None。"""
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts < ttl:
            return data
        return None

    def get_stale(self, key: str, max_age: float) -> Any | None:
        """返回过期但仍在 max_age 内的缓存，用于 429 fallback。"""
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, data = entry
        age = time.monotonic() - ts
        if age < max_age:
            return data
        return None

    def set(self, key: str, data: Any) -> None:
        self._store[key] = (time.monotonic(), data)


class CoinGeckoProvider(DataProvider):
    """CoinGecko 加密货币数据源，内置 TTL 缓存应对限流。"""

    name = "coingecko"
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

        ids = ",".join(normalized)
        cache_key = f"markets:{ids}"

        # 1. 先查新鲜缓存，命中则直接返回
        cached_fresh = self._cache.get_fresh(cache_key, _QUOTE_FRESH_TTL)
        if cached_fresh is not None:
            return self._build_quotes(normalized, cached_fresh)

        # 2. 请求 API
        url = (
            f"{_BASE_URL}/coins/markets"
            f"?vs_currency=usd&ids={quote(ids)}"
            f"&sparkline=false&price_change_percentage=24h"
        )
        try:
            data = await fetch_json(url, headers=_DEFAULT_HEADERS)
            if isinstance(data, list):
                self._cache.set(cache_key, data)
                return self._build_quotes(normalized, data)
            return [default_quote(c, self.name) for c in normalized]
        except StockRequestError:
            # 3. 429 限流：返回过期缓存（如果有）
            stale = self._cache.get_stale(cache_key, _QUOTE_STALE_TTL)
            if stale is not None:
                return self._build_quotes(normalized, stale)
            raise

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)

        if opts.adjust != KlineAdjust.NONE:
            return []

        # CoinGecko 不支持分时，返回空（Binance 会兜底）
        if opts.period in (KlinePeriod.MINUTE_1, KlinePeriod.MINUTE_5, KlinePeriod.MINUTE_15, KlinePeriod.MINUTE_30, KlinePeriod.HOUR):
            return []

        days = self._period_to_days(opts.period, opts.count)
        cache_key = f"ohlc:{code}:{days}"

        # 1. 新鲜缓存
        cached_fresh = self._cache.get_fresh(cache_key, _KLINE_FRESH_TTL)
        if cached_fresh is not None:
            return self._build_klines(cached_fresh, opts.period, opts.count)

        url = f"{_BASE_URL}/coins/{quote(code)}/ohlc?vs_currency=usd&days={days}"
        try:
            data = await fetch_json(url, headers=_DEFAULT_HEADERS)
            if isinstance(data, list) and data:
                self._cache.set(cache_key, data)
                return self._build_klines(data, opts.period, opts.count)
            return []
        except StockRequestError:
            # 2. 429 限流：返回过期缓存
            stale = self._cache.get_stale(cache_key, _KLINE_STALE_TTL)
            if stale is not None:
                return self._build_klines(stale, opts.period, opts.count)
            raise

    async def search_symbols(self, query: str) -> list[Symbol]:
        url = f"{_BASE_URL}/search?query={quote(query)}"
        data = await fetch_json(url, headers=_DEFAULT_HEADERS)

        if not isinstance(data, dict):
            return []

        coins = data.get("coins") or []
        results: list[Symbol] = []
        for coin in coins[:20]:
            if not isinstance(coin, dict):
                continue
            coin_id = coin.get("id")
            if not coin_id:
                continue
            results.append(
                Symbol(
                    code=coin_id,
                    name=coin.get("name", coin_id),
                    market=Market.CRYPTO,
                    asset_class=AssetClass.CRYPTO,
                )
            )
        return results

    async def inspect(self, code: str) -> Inspection:
        return await create_inspection(self.name, code, self.get_quote)

    def _build_quotes(self, codes: list[str], data: list[Any]) -> list[Quote]:
        by_id = {
            item["id"]: item
            for item in data
            if isinstance(item, dict) and "id" in item
        }
        return [self._parse_quote(code, by_id.get(code)) for code in codes]

    def _build_klines(
        self, data: list, period: KlinePeriod, count: int
    ) -> list[Kline]:
        raw_rows = self._parse_ohlc(data)
        return self._aggregate(raw_rows, period, count)

    def _parse_quote(self, code: str, item: dict[str, Any] | None) -> Quote:
        if not item:
            return default_quote(code, self.name)

        now = _number(item.get("current_price"))
        high = _number(item.get("high_24h"))
        low = _number(item.get("low_24h"))
        percent_value = _number(item.get("price_change_percentage_24h"))
        percent = percent_value / 100 if percent_value else 0.0
        yesterday = now / (1 + percent) if (now and percent) else now

        return Quote(
            code=code,
            name=item.get("name", code),
            now=now,
            low=low,
            high=high,
            yesterday=yesterday,
            percent=percent,
            source=self.name,
            asset_class=AssetClass.CRYPTO,
            market=Market.CRYPTO,
            market_cap=_num_or_none(item.get("market_cap")),
            volume=_num_or_none(item.get("total_volume")),
            turnover=_num_or_none(item.get("total_volume")),
        )

    def _period_to_days(self, period: KlinePeriod, count: int) -> str:
        if period == KlinePeriod.MONTH or count > 90:
            return "365"
        if count > 30:
            return "90"
        return "30"

    def _parse_ohlc(self, data: list) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, list) or len(item) < 5:
                continue
            timestamp = item[0]
            date = datetime.fromtimestamp(timestamp / 1000, tz=UTC).strftime("%Y-%m-%d")
            rows.append(
                {
                    "date": date,
                    "open": _number(item[1]),
                    "high": _number(item[2]),
                    "low": _number(item[3]),
                    "close": _number(item[4]),
                }
            )
        return rows

    def _aggregate(
        self,
        rows: list[dict[str, Any]],
        period: KlinePeriod,
        count: int,
    ) -> list[Kline]:
        if not rows:
            return []

        if period == KlinePeriod.DAY:
            daily = self._aggregate_to_daily(rows) if len(rows) > count * 4 else rows
            return [
                create_kline(
                    date=r["date"],
                    open_price=r["open"],
                    close=r["close"],
                    high=r["high"],
                    low=r["low"],
                    source=self.name,
                )
                for r in daily[-count:]
            ]

        if period == KlinePeriod.WEEK:
            daily = self._aggregate_to_daily(rows)
            weekly = self._aggregate_by_period(daily, "week")
            return [
                create_kline(
                    date=r["date"],
                    open_price=r["open"],
                    close=r["close"],
                    high=r["high"],
                    low=r["low"],
                    source=self.name,
                )
                for r in weekly[-count:]
            ]

        if period == KlinePeriod.MONTH:
            daily = self._aggregate_to_daily(rows)
            monthly = self._aggregate_by_period(daily, "month")
            return [
                create_kline(
                    date=r["date"],
                    open_price=r["open"],
                    close=r["close"],
                    high=r["high"],
                    low=r["low"],
                    source=self.name,
                )
                for r in monthly[-count:]
            ]

        return []

    def _aggregate_to_daily(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_date: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            by_date.setdefault(r["date"], []).append(r)

        daily: list[dict[str, Any]] = []
        for date, group in by_date.items():
            daily.append(
                {
                    "date": date,
                    "open": group[0]["open"],
                    "close": group[-1]["close"],
                    "high": max(g["high"] for g in group),
                    "low": min(g["low"] for g in group),
                }
            )
        daily.sort(key=lambda r: r["date"])
        return daily

    def _aggregate_by_period(
        self, daily: list[dict[str, Any]], period: str
    ) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in daily:
            dt = datetime.strptime(r["date"], "%Y-%m-%d")
            if period == "week":
                iso_year, iso_week, _ = dt.isocalendar()
                key = f"{iso_year}-W{iso_week:02d}"
            else:
                key = f"{dt.year}-{dt.month:02d}"
            groups.setdefault(key, []).append(r)

        result: list[dict[str, Any]] = []
        for key in sorted(groups.keys()):
            group = groups[key]
            result.append(
                {
                    "date": group[0]["date"],
                    "open": group[0]["open"],
                    "close": group[-1]["close"],
                    "high": max(g["high"] for g in group),
                    "low": min(g["low"] for g in group),
                }
            )
        return result


def _number(value: Any) -> float:
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
