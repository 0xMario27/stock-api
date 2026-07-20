"""腾讯股票数据源。对应原 TS 的 stocks/tencent/index.ts。"""

from __future__ import annotations

from urllib.parse import quote

from stock_api.core.base import DataProvider
from stock_api.core.models import (
    AssetClass,
    Inspection,
    Kline,
    KlineAdjust,
    KlineOptions,
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
    tencent_code_mapper,
)
from stock_api.market.kline import create_kline, normalize_kline_options
from stock_api.providers._shared import create_inspection
from stock_api.utils.http import fetch_bytes, fetch_json


def _get_quote_url(api_codes: list[str]) -> str:
    return f"https://qt.gtimg.cn/q={','.join(api_codes)}"


def _get_search_url(key: str) -> str:
    return f"https://smartbox.gtimg.cn/s3/?v=2&t=all&c=1&q={quote(key)}"


class TencentProvider(DataProvider):
    """腾讯股票数据源。支持 A 股 / 港股 / 美股 行情、K 线、搜索。"""

    name = "tencent"
    asset_class = AssetClass.STOCK
    supported_markets = [Market.CN_A, Market.HK, Market.US]

    def __init__(self) -> None:
        self._code_mapper: CodeMapper = tencent_code_mapper()

    async def get_quote(self, code: str) -> Quote:
        quotes = await self.get_quotes([code])
        return quotes[0] if quotes else default_quote(code, self.name)

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        normalized = normalize_codes(codes)
        if not normalized:
            return []

        api_codes = [self._code_mapper.transform(c) for c in normalized]
        body = await fetch_bytes(_get_quote_url(api_codes), headers={"Referer": "https://gu.qq.com/"})
        text = body.decode("gb18030", errors="replace")
        rows = [row for row in text.split(";\n") if row]

        result: list[Quote] = []
        for code, api_code in zip(normalized, api_codes, strict=False):
            row = next((r for r in rows if api_code in r), "")
            if api_code not in row:
                result.append(default_quote(code, self.name))
                continue
            params = _extract_params(row)
            result.append(_parse_tencent_quote(code, params))
        return result

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)
        api_code = self._code_mapper.transform(code)

        endpoint = "kline/kline" if opts.adjust == KlineAdjust.NONE else "fqkline/get"
        adjust_prefix = "" if opts.adjust == KlineAdjust.NONE else opts.adjust.value
        data_key = f"{adjust_prefix}{opts.period.value}"
        adjust_param = "" if opts.adjust == KlineAdjust.NONE else f",{opts.adjust.value}"

        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/{endpoint}"
            f"?param={api_code},{opts.period.value},,,{opts.count}{adjust_param}"
        )
        response = await fetch_json(url, headers={"Accept": "application/json,text/plain,*/*"})
        data = (response or {}).get("data", {})
        rows = (data.get(api_code) or {}).get(data_key) or []

        return [
            create_kline(
                date=row[0] if len(row) > 0 else "",
                open_price=row[1] if len(row) > 1 else 0,
                close=row[2] if len(row) > 2 else 0,
                high=row[3] if len(row) > 3 else 0,
                low=row[4] if len(row) > 4 else 0,
                volume=row[5] if len(row) > 5 else None,
                source=self.name,
            )
            for row in rows
        ]

    async def search_symbols(self, query: str) -> list[Symbol]:
        body = await fetch_bytes(
            _get_search_url(query),
            headers={"Referer": "https://gu.qq.com/"},
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


def _extract_params(row: str) -> list[str]:
    """提取 `var v="a~b~c";` 中等号后的分隔字段。"""
    if "=" not in row:
        return []
    value = row.split("=", 1)[1].strip()
    value = value.strip('"').strip(";")
    return value.split("~")


def _parse_tencent_quote(code: str, params: list[str]) -> Quote:
    """对应原 TS 的 parseTencentStock。"""
    now = _number_at(params, 3)
    yesterday = _number_at(params, 4)
    percent = now / yesterday - 1 if yesterday else 0.0

    return Quote(
        code=code.upper(),
        name=str(params[1]) if len(params) > 1 else "---",
        now=now,
        low=_number_at(params, 34),
        high=_number_at(params, 33),
        yesterday=yesterday,
        percent=percent,
        source="tencent",
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


def _parse_search_codes(body: str) -> list[str]:
    """对应原 TS 的 search.parseCodes。"""
    value = body.replace('v_hint="', "").replace('";', "").replace('"', "")
    rows = value.split("^")
    codes: list[str] = []
    for row in rows:
        if "~" not in row:
            continue
        type_, code = row.split("~", 1)
        if not code:
            continue
        if type_ == "sz":
            codes.append(COMMON_SZ + code)
        elif type_ == "sh":
            codes.append(COMMON_SH + code)
        elif type_ == "hk":
            codes.append(COMMON_HK + code)
        elif type_ == "us":
            upper = code.split(".")[0].upper()
            codes.append(COMMON_US + upper)
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
