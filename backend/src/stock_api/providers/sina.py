"""新浪股票数据源。对应原 TS 的 stocks/sina/index.ts。"""

from __future__ import annotations

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
from stock_api.market.codes import (
    COMMON_HK,
    COMMON_SH,
    COMMON_SZ,
    COMMON_US,
    CodeMapper,
    normalize_codes,
    sina_code_mapper,
)
from stock_api.market.kline import create_kline, normalize_kline_options
from stock_api.providers._shared import create_inspection
from stock_api.utils.http import fetch_bytes, fetch_json

_REFER_HEADER = {"Referer": "https://finance.sina.com.cn/"}


def _get_quote_url(api_codes: list[str]) -> str:
    return f"https://hq.sinajs.cn/list={','.join(api_codes)}"


def _get_search_url(key: str) -> str:
    return f"https://suggest3.sinajs.cn/suggest/type=2&key={quote(key)}"


def _get_kline_url(api_code: str, period: str, count: int) -> str:
    scale = _get_scale(period)
    return (
        f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData"
        f"?symbol={api_code}&scale={scale}&ma=no&datalen={count}"
    )


def _get_scale(period: KlinePeriod) -> str:
    scales = {
        KlinePeriod.MINUTE_5: "5",
        KlinePeriod.MINUTE_15: "15",
        KlinePeriod.MINUTE_30: "30",
        KlinePeriod.HOUR: "60",
        KlinePeriod.DAY: "240",
        KlinePeriod.WEEK: "1200",
        KlinePeriod.MONTH: "7200",
    }
    return scales.get(period, "240")


def _is_intraday(period: KlinePeriod) -> bool:
    return period in (KlinePeriod.MINUTE_5, KlinePeriod.MINUTE_15, KlinePeriod.MINUTE_30, KlinePeriod.HOUR)


# 新浪不同市场的字段位置。对应原 TS 的 fieldMap。
_FIELD_MAP: dict[str, dict[str, int]] = {
    COMMON_SH: {"name": 0, "now": 3, "low": 5, "high": 4, "yesterday": 2},
    COMMON_SZ: {"name": 0, "now": 3, "low": 5, "high": 4, "yesterday": 2},
    COMMON_HK: {"name": 1, "now": 6, "low": 5, "high": 4, "yesterday": 3},
    COMMON_US: {"name": 0, "now": 1, "low": 7, "high": 6, "yesterday": 26},
}


class SinaProvider(DataProvider):
    """新浪股票数据源。支持 A 股 / 港股 / 美股 行情、K 线（仅日/周/月未复权）、搜索。"""

    name = "sina"
    asset_class = AssetClass.STOCK
    supported_markets = [Market.CN_A, Market.HK, Market.US]

    def __init__(self) -> None:
        self._code_mapper: CodeMapper = sina_code_mapper()

    async def get_quote(self, code: str) -> Quote:
        quotes = await self.get_quotes([code])
        return quotes[0] if quotes else default_quote(code, self.name)

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        normalized = normalize_codes(codes)
        if not normalized:
            return []

        api_codes = [self._code_mapper.transform(c) for c in normalized]
        body = await fetch_bytes(
            _get_quote_url(api_codes),
            headers=_REFER_HEADER,
        )
        text = body.decode("gb18030", errors="replace")
        rows = [row for row in text.split("\n") if row.strip()]

        result: list[Quote] = []
        for code, api_code in zip(normalized, api_codes, strict=False):
            row = next((r for r in rows if api_code in r), "")
            value = _extract_assigned_value(row)
            if value == '""' or not value:
                result.append(default_quote(code, self.name))
                continue
            params = value.strip('"').split(",")
            result.append(_parse_sina_quote(code, params))
        return result

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)

        # 新浪仅支持未复权
        if opts.adjust != KlineAdjust.NONE:
            return []

        # 新浪不支持 1 分钟数据
        if opts.period == KlinePeriod.MINUTE_1:
            return []

        api_code = self._code_mapper.transform(code)
        url = _get_kline_url(api_code, _get_scale(opts.period), opts.count)
        rows = await fetch_json(url, headers={**_REFER_HEADER, "Accept": "application/json,text/plain,*/*"})

        if not isinstance(rows, list):
            return []

        intraday = _is_intraday(opts.period)
        result: list[Kline] = []
        for row in rows:
            date_str = row.get("day", "")
            ts = None
            if intraday and " " in date_str:
                from datetime import datetime
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    ts = int(dt.timestamp())
                except ValueError:
                    pass
            result.append(create_kline(
                date=date_str,
                open_price=row.get("open"),
                close=row.get("close"),
                high=row.get("high"),
                low=row.get("low"),
                volume=row.get("volume"),
                source=self.name,
                timestamp=ts,
            ))
        return result

    async def search_symbols(self, query: str) -> list[Symbol]:
        body = await fetch_bytes(
            _get_search_url(query),
            headers=_REFER_HEADER,
        )
        text = body.decode("gb18030", errors="replace")
        codes = _parse_search_codes(text)
        if not codes:
            return []

        quotes = await self.get_quotes(codes)
        return [
            Symbol(code=q.code, name=q.name, market=_detect_market(q.code), asset_class=AssetClass.STOCK)
            for q in quotes
            if q.name != "---"
        ]

    async def inspect(self, code: str) -> Inspection:
        return await create_inspection(self.name, code, self.get_quote)


def _extract_assigned_value(row: str) -> str:
    """提取 `var hq_str="...";` 等号后的值。对应原 TS 的 getAssignedValue。"""
    if "=" not in row:
        return ""
    return row.split("=", 1)[1].rstrip(";\n").strip()


def _parse_sina_quote(code: str, params: list[str]) -> Quote:
    """对应原 TS 的 parseSinaStock。"""
    market_prefix = code[:2].upper()
    fields = _FIELD_MAP.get(market_prefix)

    if fields is None:
        return default_quote(code, "sina")

    now = _number_at(params, fields["now"])
    yesterday = _number_at(params, fields["yesterday"])
    percent = now / yesterday - 1 if yesterday else 0.0

    return Quote(
        code=code.upper(),
        name=_string_at(params, fields["name"]),
        now=now,
        low=_number_at(params, fields["low"]),
        high=_number_at(params, fields["high"]),
        yesterday=yesterday,
        percent=percent,
        source="sina",
        asset_class=AssetClass.STOCK,
        market=_detect_market(code),
    )


def _number_at(params: list[str], index: int) -> float:
    if index >= len(params):
        return 0.0
    try:
        return float(params[index]) if params[index] else 0.0
    except (TypeError, ValueError):
        return 0.0


def _string_at(params: list[str], index: int) -> str:
    if index >= len(params):
        return "---"
    return str(params[index]) if params[index] else "---"


def _parse_search_codes(body: str) -> list[str]:
    """对应原 TS 的 search.parseCodes。"""
    value = body.replace('var suggestvalue="', "").replace('";', "")
    rows = value.split(";")
    codes: list[str] = []
    for row in rows:
        if not row:
            continue
        code = row.split(",")[0]
        if code.startswith("us"):
            codes.append(COMMON_US + code[2:])
        elif code.startswith("sz"):
            codes.append(COMMON_SZ + code[2:])
        elif code.startswith("sh"):
            codes.append(COMMON_SH + code[2:])
        elif code.startswith("hk"):
            codes.append(COMMON_HK + code[2:])
        elif code.startswith("of"):
            fund_code = code[2:]
            codes.append(COMMON_SZ + fund_code)
            codes.append(COMMON_SH + fund_code)
    return normalize_codes(codes)


def _detect_market(code: str) -> Market | None:
    upper = code.upper()
    if upper.startswith(COMMON_SH) or upper.startswith(COMMON_SZ):
        return Market.CN_A
    if upper.startswith(COMMON_HK):
        return Market.HK
    if upper.startswith(COMMON_US):
        return Market.US
    return None
