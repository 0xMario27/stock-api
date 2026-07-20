"""CoinGecko 加密货币数据源。

使用 CoinGecko 公开 API（无需 API Key）：
- 行情：coins/markets 端点，返回 current_price / high_24h / low_24h / price_change_percentage_24h
- K 线：coins/{id}/ohlc 端点，返回 [timestamp, open, high, low, close]
- 搜索：search 端点，返回匹配的 coins

统一代码：CoinGecko coin ID（如 bitcoin / ethereum / binancecoin），与股票的 SH/SZ/HK/US 前缀格式天然区分。

二期若要接入更多 crypto 数据源（如 Binance），只需新建 providers/crypto/binance.py，
继承 DataProvider 并设置 asset_class = CRYPTO，注册到 registry 即可，auto 路由自动生效。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from stock_api.core.base import DataProvider
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


class CoinGeckoProvider(DataProvider):
    """CoinGecko 加密货币数据源。"""

    name = "coingecko"
    asset_class = AssetClass.CRYPTO
    supported_markets = [Market.CRYPTO]

    async def get_quote(self, code: str) -> Quote:
        quotes = await self.get_quotes([code])
        return quotes[0] if quotes else default_quote(code, self.name)

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        normalized = [c.strip() for c in codes if c and c.strip()]
        if not normalized:
            return []

        ids = ",".join(normalized)
        url = (
            f"{_BASE_URL}/coins/markets"
            f"?vs_currency=usd&ids={quote(ids)}"
            f"&sparkline=false&price_change_percentage=24h"
        )
        data = await fetch_json(url, headers=_DEFAULT_HEADERS)

        if not isinstance(data, list):
            return [default_quote(c, self.name) for c in normalized]

        by_id = {item["id"]: item for item in data if isinstance(item, dict) and "id" in item}
        return [self._parse_quote(code, by_id.get(code)) for code in normalized]

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)

        # CoinGecko OHLC 不支持复权概念
        if opts.adjust != KlineAdjust.NONE:
            return []

        days = self._period_to_days(opts.period, opts.count)
        url = f"{_BASE_URL}/coins/{quote(code)}/ohlc?vs_currency=usd&days={days}"
        data = await fetch_json(url, headers=_DEFAULT_HEADERS)

        if not isinstance(data, list) or not data:
            return []

        raw_rows = self._parse_ohlc(data)
        return self._aggregate(raw_rows, opts.period, opts.count)

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
        )

    def _period_to_days(self, period: KlinePeriod, count: int) -> str:
        """根据 period 和 count 估算需要请求的天数范围。

        CoinGecko OHLC 端点支持的 days 值：1, 7, 14, 30, 90, 180, 365, max
        - days=1: 30 分钟粒度
        - days=7~30: 4 小时粒度
        - days=90+: 4 小时粒度
        - days=365/max: 日粒度

        为了拿到日 K，用 365 或 max；周 K / 月 K 同样取日粒度后聚合。
        """
        if period == KlinePeriod.MONTH or count > 90:
            return "365"
        if count > 30:
            return "90"
        return "30"

    def _parse_ohlc(self, data: list) -> list[dict[str, Any]]:
        """解析 CoinGecko OHLC 原始数据 -> [{date, open, high, low, close}]"""
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
        """将日粒度 OHLC 聚合为目标周期。"""
        if not rows:
            return []

        if period == KlinePeriod.DAY:
            # CoinGecko 30 天以内是 4 小时粒度，需要聚合成日 K
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
        """将 4 小时粒度的 OHLC 聚合为日 K。"""
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
        """将日 K 聚合为周 K 或月 K。"""
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
