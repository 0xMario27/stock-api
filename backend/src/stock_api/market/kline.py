"""K 线工具。对应原 TS 的 shared/kline.ts。"""

from __future__ import annotations

from typing import Any

from stock_api.core.models import Kline, KlineAdjust, KlineOptions, KlinePeriod

_DEFAULT_PERIOD = KlinePeriod.DAY
_DEFAULT_COUNT = 120
_DEFAULT_ADJUST = KlineAdjust.NONE


def normalize_kline_options(options: KlineOptions | None) -> KlineOptions:
    """归一化 K 线选项，补默认值。"""
    if options is None:
        return KlineOptions()
    return KlineOptions(
        period=options.period or _DEFAULT_PERIOD,
        count=max(1, options.count) if options.count else _DEFAULT_COUNT,
        adjust=options.adjust or _DEFAULT_ADJUST,
    )


def parse_kline_number(value: Any) -> float:
    """把任意值安全转成 float，失败返回 0.0。对应原 TS 的 parseKlineNumber。"""
    if value is None or value == "-" or value == "":
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if result == result else 0.0  # NaN check


def create_kline(
    *,
    date: str,
    open_price: Any,
    close: Any,
    high: Any,
    low: Any,
    volume: Any = None,
    source: str,
) -> Kline:
    """构造 Kline。对应原 TS 的 createKline。"""
    kline = Kline(
        date=date,
        open=parse_kline_number(open_price),
        close=parse_kline_number(close),
        high=parse_kline_number(high),
        low=parse_kline_number(low),
        source=source,
    )
    if volume is not None:
        kline.volume = parse_kline_number(volume)
    return kline
