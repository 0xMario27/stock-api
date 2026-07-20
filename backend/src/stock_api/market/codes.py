"""统一代码与数据源代码的映射。

对应原 TS 的 shared/code-mapper.ts + base/utils/constant.ts + 各源 utils/constant.ts。

统一代码格式：
    SH510500  SZ000651  HK02020  USDJI

各数据源代码格式：
    腾讯: sh510500  sz000651  hk02020  usDJI
    新浪: sh510500  sz000651  hk02020  gb_dji
    东方财富: 1.510500  0.000651  (仅支持 A 股)

二期 crypto 接入时，crypto provider 自行实现 code 转换（如 BTCUSDT 直传）。
"""

from __future__ import annotations

from collections.abc import Callable

from stock_api.core.exceptions import StockCodeError
from stock_api.core.models import Market

# 统一代码前缀
COMMON_SH = "SH"
COMMON_SZ = "SZ"
COMMON_HK = "HK"
COMMON_US = "US"

# SH / SZ 都是 A 股
A_SHARE_PREFIXES = (COMMON_SH, COMMON_SZ)


# 数据源前缀映射键（SH/SZ/HK/US 四类，各自独立配置）
MarketPrefix = str  # "SH" | "SZ" | "HK" | "US"


def detect_market(code: str) -> Market | None:
    """根据统一代码前缀判断市场。"""
    upper = code.upper()
    if upper.startswith(COMMON_SH) or upper.startswith(COMMON_SZ):
        return Market.CN_A
    if upper.startswith(COMMON_HK):
        return Market.HK
    if upper.startswith(COMMON_US):
        return Market.US
    return None


def is_a_share(code: str) -> bool:
    return code.upper().startswith(COMMON_SH) or code.upper().startswith(COMMON_SZ)


def is_hk_stock(code: str) -> bool:
    return code.upper().startswith(COMMON_HK)


def is_us_stock(code: str) -> bool:
    return code.upper().startswith(COMMON_US)


class CodeMapper:
    """通用代码映射器。对应原 TS 的 createCodeMapper。

    按 SH/SZ/HK/US 四个前缀独立配置输出前缀，
    将统一代码（SH510500）转成数据源代码（如 sh510500 / gb_dji）。
    """

    def __init__(
        self,
        output_prefixes: dict[str, str],
        *,
        unknown_error: str = "请检查统一代码是否正确",
        format_output: Callable[[str, str], str] | None = None,
    ) -> None:
        """output_prefixes: {"SH": "sh", "SZ": "sz", "HK": "hk", "US": "us"}"""
        self._output_prefixes = output_prefixes
        self._unknown_error = unknown_error
        self._format_output = format_output

    def transform(self, code: str) -> str:
        upper = code.upper()
        market_prefix = _get_common_prefix(upper)
        if market_prefix is None or market_prefix not in self._output_prefixes:
            raise StockCodeError(self._unknown_error)

        value = upper[len(market_prefix):]
        if self._format_output is not None:
            value = self._format_output(market_prefix, value)
        return self._output_prefixes[market_prefix] + value

    def transforms(self, codes: list[str]) -> list[str]:
        return [self.transform(code) for code in codes]


def _get_common_prefix(upper_code: str) -> str | None:
    for prefix in (COMMON_SH, COMMON_SZ, COMMON_HK, COMMON_US):
        if upper_code.startswith(prefix):
            return prefix
    return None


# ---- 各数据源代码映射配置 ----

def tencent_code_mapper() -> CodeMapper:
    """腾讯: SH->sh SZ->sz HK->hk US->us (HK/US 大写)"""
    return CodeMapper(
        output_prefixes={
            COMMON_SH: "sh",
            COMMON_SZ: "sz",
            COMMON_HK: "hk",
            COMMON_US: "us",
        },
        format_output=_tencent_format,
    )


def _tencent_format(market_prefix: str, value: str) -> str:
    if market_prefix in (COMMON_HK, COMMON_US):
        return value.upper()
    return value


def sina_code_mapper() -> CodeMapper:
    """新浪: SH->sh SZ->sz HK->hk US->gb_ (US 小写)"""
    return CodeMapper(
        output_prefixes={
            COMMON_SH: "sh",
            COMMON_SZ: "sz",
            COMMON_HK: "hk",
            COMMON_US: "gb_",
        },
        format_output=_sina_format,
    )


def _sina_format(market_prefix: str, value: str) -> str:
    if market_prefix == COMMON_US:
        return value.lower()
    return value


class EastmoneyCodeMapper:
    """东方财富: SH->1. SZ->0. (仅 A 股)"""

    def __init__(self) -> None:
        self._unknown_error = "东方财富仅支持 A 股代码（SH/SZ 前缀）"

    def transform(self, code: str) -> str:
        upper = code.upper()
        if upper.startswith(COMMON_SH):
            return f"1.{upper[len(COMMON_SH):]}"
        if upper.startswith(COMMON_SZ):
            return f"0.{upper[len(COMMON_SZ):]}"
        raise StockCodeError(self._unknown_error)

    def transforms(self, codes: list[str]) -> list[str]:
        return [self.transform(code) for code in codes]


def eastmoney_code_mapper() -> EastmoneyCodeMapper:
    return EastmoneyCodeMapper()


def normalize_codes(codes: list[str]) -> list[str]:
    """去重并过滤空字符串。对应原 TS 的 normalizeCodes。"""
    seen: set[str] = set()
    result: list[str] = []
    for code in codes:
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result
