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
    detect_market,
    normalize_codes,
    tencent_code_mapper,
)
from stock_api.market.kline import create_kline, normalize_kline_options
from stock_api.providers._shared import create_inspection
from stock_api.utils.http import fetch_bytes, fetch_json

# 腾讯分时 period 映射
_TENCENT_PERIOD_MAP: dict[KlinePeriod, str] = {
    KlinePeriod.MINUTE_1: "1",
    KlinePeriod.MINUTE_5: "5",
    KlinePeriod.MINUTE_15: "15",
    KlinePeriod.MINUTE_30: "30",
    KlinePeriod.HOUR: "60",
}


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

        # 腾讯分时参数映射
        tv_period = _TENCENT_PERIOD_MAP.get(opts.period, opts.period.value)
        is_intraday = opts.period in _TENCENT_PERIOD_MAP

        endpoint = "kline/kline" if opts.adjust == KlineAdjust.NONE else "fqkline/get"
        adjust_prefix = "" if opts.adjust == KlineAdjust.NONE else opts.adjust.value
        data_key = f"{adjust_prefix}{tv_period}"
        adjust_param = "" if opts.adjust == KlineAdjust.NONE else f",{opts.adjust.value}"

        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/{endpoint}"
            f"?param={api_code},{tv_period},,,{opts.count}{adjust_param}"
        )
        response = await fetch_json(url, headers={"Accept": "application/json,text/plain,*/*"})
        data = (response or {}).get("data", {})
        rows = (data.get(api_code) or {}).get(data_key) or []

        result: list[Kline] = []
        for row in rows:
            date_str = row[0] if len(row) > 0 else ""
            ts = None
            if is_intraday and " " in date_str:
                from datetime import datetime
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    ts = int(dt.timestamp())
                except ValueError:
                    pass
            result.append(create_kline(
                date=date_str,
                open_price=row[1] if len(row) > 1 else 0,
                close=row[2] if len(row) > 2 else 0,
                high=row[3] if len(row) > 3 else 0,
                low=row[4] if len(row) > 4 else 0,
                volume=row[5] if len(row) > 5 else None,
                source=self.name,
                timestamp=ts,
            ))
        return result

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
            Symbol(code=q.code, name=q.name, market=detect_market(q.code), asset_class=AssetClass.STOCK)
            for q in quotes
            if q.name != "---"
        ]

    async def inspect(self, code: str) -> Inspection:
        return await create_inspection(self.name, code, self.get_quote)


def _extract_params(row: str) -> list[str]:
    """提取 `var v="a~b~c";` 或 `var v="a,b,c";` 中等号后的分隔字段。"""
    if "=" not in row:
        return []
    value = row.split("=", 1)[1].strip()
    value = value.strip('"').strip(";")
    if "~" in value:
        return value.split("~")
    return value.split(",")


# 商品名称映射（腾讯商品响应不含名称）
_COM_NAMES: dict[str, str] = {
    "XAU": "伦敦金", "XAG": "伦敦银", "GC": "纽约黄金",
    "CL": "纽约原油", "SI": "纽约白银", "NG": "天然气",
    "HG": "伦敦铜", " Palladium": "钯金",
}


def _parse_tencent_quote(code: str, params: list[str]) -> Quote:
    """对应原 TS 的 parseTencentStock，支持股票和商品格式。"""
    upper = code.upper()

    # 商品格式（hf_ 响应，逗号分隔，字段位置不同）
    if upper.startswith("COM"):
        com_code = upper[3:]
        now = _number_at(params, 0)
        yesterday = _number_at(params, 7)
        pct = _number_at(params, 1)
        return Quote(
            code=code,
            name=_COM_NAMES.get(com_code, com_code),
            now=now,
            low=_number_at(params, 5),
            high=_number_at(params, 4),
            yesterday=yesterday,
            percent=pct / 100 if pct else 0.0,
            source="tencent",
            asset_class=AssetClass.STOCK,
            market=Market.COMMODITY,
        )

    # 股票/指数/基金格式（~ 分隔）
    now = _number_at(params, 3)
    yesterday = _number_at(params, 4)
    percent = now / yesterday - 1 if yesterday else 0.0

    open_price = _number_or_none_at(params, 5)
    volume_shou = _number_or_none_at(params, 6)
    volume = volume_shou * 100 if volume_shou else None
    turnover_wan = _number_or_none_at(params, 37)
    turnover = turnover_wan * 10000 if turnover_wan else None
    pe = _number_or_none_at(params, 39)
    pb = _number_or_none_at(params, 43)

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
        market=detect_market(code),
        open_price=open_price,
        volume=volume,
        turnover=turnover,
        pe_ratio=pe,
        pb_ratio=pb,
    )


def _number_at(params: list[str], index: int) -> float:
    if index >= len(params):
        return 0.0
    try:
        return float(params[index]) if params[index] else 0.0
    except (TypeError, ValueError):
        return 0.0


def _number_or_none_at(params: list[str], index: int) -> float | None:
    if index >= len(params):
        return None
    try:
        return float(params[index]) if params[index] and params[index] != "-" else None
    except (TypeError, ValueError):
        return None


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

