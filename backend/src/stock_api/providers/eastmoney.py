"""东方财富股票数据源。对应原 TS 的 stocks/eastmoney/index.ts。

仅支持 A 股。行情 / K 线 / 搜索均独立接口，非 provider 工厂模式。
"""

from __future__ import annotations

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
from stock_api.market.codes import EastmoneyCodeMapper, detect_market, normalize_codes
from stock_api.market.kline import create_kline, normalize_kline_options
from stock_api.providers._shared import create_inspection
from stock_api.utils.http import fetch_json

_QUOTE_FIELDS = "f2,f3,f14,f15,f16,f18,f43,f44,f45,f46,f47,f48,f51,f52,f57,f58,f60,f116,f117,f162,f167,f170"
_KLINE_FIELDS = "f51,f52,f53,f54,f55,f56"
_SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
_REQUEST_TIMEOUT = 4.0
_DEFAULT_PUSH2_HOST = "push2delay.eastmoney.com"
_DEFAULT_PUSH2_HIS_HOST = "push2his.eastmoney.com"
_PUSH2_HIS_HOSTS = [
    _DEFAULT_PUSH2_HIS_HOST,
    "7.push2his.eastmoney.com",
    "33.push2his.eastmoney.com",
    "63.push2his.eastmoney.com",
    "91.push2his.eastmoney.com",
]

_EASTMONEY_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://quote.eastmoney.com/",
}


def _get_suggest_url(key: str) -> str:
    return (
        f"https://searchapi.eastmoney.com/api/suggest/get"
        f"?input={quote(key)}&type=14&token={_SUGGEST_TOKEN}"
    )


def _get_kline_period_code(period: KlinePeriod) -> str:
    codes = {
        KlinePeriod.MINUTE_1: "1",
        KlinePeriod.MINUTE_5: "5",
        KlinePeriod.MINUTE_15: "15",
        KlinePeriod.MINUTE_30: "30",
        KlinePeriod.HOUR: "60",
        KlinePeriod.DAY: "101",
        KlinePeriod.WEEK: "102",
        KlinePeriod.MONTH: "103",
    }
    return codes.get(period, "101")


def _is_intraday(period: KlinePeriod) -> bool:
    return period in (KlinePeriod.MINUTE_1, KlinePeriod.MINUTE_5, KlinePeriod.MINUTE_15, KlinePeriod.MINUTE_30, KlinePeriod.HOUR)


def _get_adjust_code(adjust: KlineAdjust) -> str:
    if adjust == KlineAdjust.QFQ:
        return "1"
    if adjust == KlineAdjust.HFQ:
        return "2"
    return "0"


class EastmoneyProvider(DataProvider):
    """东方财富股票数据源。仅支持 A 股。"""

    name = "eastmoney"
    asset_class = AssetClass.STOCK
    supported_markets = [Market.CN_A, Market.INDEX, Market.FUND, Market.FUTURE, Market.COMMODITY]

    def __init__(self) -> None:
        self._code_mapper = EastmoneyCodeMapper()

    async def get_quote(self, code: str) -> Quote:
        quotes = await self.get_quotes([code])
        return quotes[0] if quotes else default_quote(code, self.name)

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        normalized = normalize_codes(codes)
        if not normalized:
            return []

        import asyncio

        return await asyncio.gather(*[self._fetch_one(code) for code in normalized])

    async def _fetch_one(self, code: str) -> Quote:
        api_code = self._code_mapper.transform(code)
        url = (
            f"https://{_DEFAULT_PUSH2_HOST}/api/qt/stock/get"
            f"?fltt=2&invt=2&secid={quote(api_code)}&fields={_QUOTE_FIELDS}"
        )
        quote_data = await self._request_quote(url)
        if not quote_data or (not quote_data.get("f57") and not quote_data.get("f58")):
            return default_quote(code, self.name)
        return _parse_eastmoney_quote(code, quote_data)

    async def _request_quote(self, url: str) -> dict[str, Any] | None:
        response = await self._request_json(url, retries=1)
        quote_data = (response or {}).get("data")
        if quote_data and (quote_data.get("f57") or quote_data.get("f58")):
            return quote_data
        return None

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)
        api_code = self._code_mapper.transform(code)
        intraday = _is_intraday(opts.period)
        url = (
            f"https://{_DEFAULT_PUSH2_HIS_HOST}/api/qt/stock/kline/get"
            f"?fields1=f1,f2,f3,f4,f5,f6&fields2={_KLINE_FIELDS}"
            f"&ut=7eea3edcaed734bea9cbfc24409ed989"
            f"&klt={_get_kline_period_code(opts.period)}"
            f"&fqt={_get_adjust_code(opts.adjust)}"
            f"&secid={quote(api_code)}&beg=19700101&end=20500101&lmt={opts.count}"
        )
        response = await self._request_json_from_hosts(url, _PUSH2_HIS_HOSTS)
        rows = (response or {}).get("data", {}).get("klines") or []

        klines: list[Kline] = []
        for line in rows:
            parts = line.split(",")
            if len(parts) < 6:
                continue
            date_str = parts[0]
            ts = None
            if intraday and " " in date_str:
                from datetime import datetime
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                    ts = int(dt.timestamp())
                except ValueError:
                    pass
            klines.append(
                create_kline(
                    date=date_str,
                    open_price=parts[1],
                    close=parts[2],
                    high=parts[3],
                    low=parts[4],
                    volume=parts[5],
                    source=self.name,
                    timestamp=ts,
                )
            )
        return klines

    async def search_symbols(self, query: str) -> list[Symbol]:
        url = _get_suggest_url(query)
        response = await self._request_json(url, retries=1)
        items = (response or {}).get("QuotationCodeTable", {}).get("Data") or []
        codes: list[str] = []
        for item in items:
            code = _parse_suggest_code(item)
            if code:
                codes.append(code)
        if not codes:
            return []

        quotes = await self.get_quotes(codes)
        return [
            Symbol(code=q.code, name=q.name, market=Market.CN_A, asset_class=AssetClass.STOCK)
            for q in quotes
            if q.name != "---"
        ]

    async def inspect(self, code: str) -> Inspection:
        return await create_inspection(self.name, code, self.get_quote)

    async def _request_json(self, url: str, retries: int = 0) -> dict[str, Any]:
        last_error: Exception | None = None
        for _ in range(retries + 1):
            try:
                return await fetch_json(url, headers=_EASTMONEY_HEADERS, timeout=_REQUEST_TIMEOUT)
            except Exception as error:  # noqa: BLE001
                last_error = error
        if last_error:
            raise last_error
        return {}

    async def _request_json_from_hosts(
        self, url: str, hosts: list[str]
    ) -> dict[str, Any]:
        from urllib.parse import urlsplit, urlunsplit

        last_error: Exception | None = None
        for host in hosts:
            try:
                parts = urlsplit(url)
                replaced = urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
                return await fetch_json(replaced, headers=_EASTMONEY_HEADERS, timeout=_REQUEST_TIMEOUT)
            except Exception as error:  # noqa: BLE001
                last_error = error
        if last_error:
            raise last_error
        return {}


def _parse_eastmoney_quote(code: str, quote_data: dict[str, Any]) -> Quote:
    """对应原 TS 的 parseEastmoneyStock。"""
    now = _number_value(quote_data.get("f43") or quote_data.get("f2"))
    yesterday = _number_value(quote_data.get("f60") or quote_data.get("f18"))
    percent_value = _number_value(quote_data.get("f170") or quote_data.get("f3"))

    if percent_value:
        percent = percent_value / 100
    elif now and yesterday:
        percent = now / yesterday - 1
    else:
        percent = 0.0

    open_price = _number_value_or_none(quote_data.get("f46"))
    volume_shou = _number_value_or_none(quote_data.get("f47"))
    volume = volume_shou * 100 if volume_shou else None
    turnover = _number_value_or_none(quote_data.get("f48"))
    pe = _number_value_or_none(quote_data.get("f162"))
    pb = _number_value_or_none(quote_data.get("f167"))
    mcap = _number_value_or_none(quote_data.get("f116"))
    cmcap = _number_value_or_none(quote_data.get("f117"))
    h52 = _number_value_or_none(quote_data.get("f51"))
    l52 = _number_value_or_none(quote_data.get("f52"))

    return Quote(
        code=code.upper(),
        name=str(quote_data.get("f58") or quote_data.get("f14") or "---"),
        now=now,
        low=_number_value(quote_data.get("f45") or quote_data.get("f16")),
        high=_number_value(quote_data.get("f44") or quote_data.get("f15")),
        yesterday=yesterday,
        percent=percent,
        source="eastmoney",
        asset_class=AssetClass.STOCK,
        market=detect_market(code),
        open_price=open_price,
        volume=volume,
        turnover=turnover,
        pe_ratio=pe,
        pb_ratio=pb,
        market_cap=mcap,
        circulating_cap=cmcap,
        high_52w=h52,
        low_52w=l52,
    )


def _number_value_or_none(value: Any) -> float | None:
    """类似 _number_value 但保留 None（用于可选字段）。"""
    if value is None or value == "-" or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _number_value(value: Any) -> float:
    if value is None or value == "-" or value == "":
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if result == result else 0.0


def _parse_suggest_code(item: dict[str, Any]) -> str:
    quote_id = item.get("QuoteID") or ""
    code = item.get("Code") or (quote_id.split(".")[1] if "." in quote_id else "")
    market = item.get("MktNum") or (quote_id.split(".")[0] if "." in quote_id else "")
    if not code:
        return ""
    if market == "1":
        return f"SH{code}"
    if market == "0":
        return f"SZ{code}"
    # 期货市场: 220(CFFEX), 115(SHFE), 113(DCE), 114(CZCE), 116(GFEX), 118(INE)
    if market in ("220", "115", "113", "114", "116", "118", "8"):
        return f"FUT{code}"
    # 外盘商品: 122(international)
    if market == "122":
        return f"COM{code}"
    return ""
