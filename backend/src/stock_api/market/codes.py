"""统一代码与数据源代码的映射。

统一代码格式：
    股票:  SH510500  SZ000651  HK02020  USAAPL
    指数:  SH000001  SZ399001  HKHSI  USDJI
    基金:  SH510500  SZ161725
    期指:  FUTIF0107
    期权:  OPT10000001
    商品:  COMXAU  COMGC

各数据源代码格式：
    腾讯: sh510500  sz000651  hk02020  usDJI  nf_IF0107  hf_XAU
    新浪: sh510500  sz000651  hk02020  gb_dji  nf_IF0107  hf_XAU  op_10000001
    东方财富: 1.510500  0.000651  (仅支持 A 股/指数/基金)
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
COMMON_FUT = "FUT"
COMMON_OPT = "OPT"
COMMON_COM = "COM"

# SH / SZ 都是 A 股
A_SHARE_PREFIXES = (COMMON_SH, COMMON_SZ)

# 数据源前缀映射键（SH/SZ/HK/US 四类，各自独立配置）
MarketPrefix = str  # "SH" | "SZ" | "HK" | "US"


def detect_market(code: str) -> Market | None:
    """根据统一代码前缀和代码模式判断市场类型。

    A 股代码细分：
      SH000xxx / SZ399xxx -> INDEX（指数）
      SH5xxxxx / SZ15xxxx / SZ16xxxx / SZ18xxxx -> FUND（基金/ETF）
      其他 SH/SZ -> CN_A（A股）
    美股代码细分：
      USDJI / USIXIC / USINX / USSPX -> INDEX（指数）
      USXAU / USXAG / USGC / US_SI -> COMMODITY（商品/黄金）
      其他 US -> US（美股）
    港股代码细分：
      HKHSI / HKHSTECH -> INDEX（指数）
      其他 HK -> HK（港股）
    新前缀：
      FUT -> FUTURE（期指/期货）
      OPT -> OPTION（期权）
      COM -> COMMODITY（商品）
    """
    upper = code.upper()

    # 新前缀直接映射
    if upper.startswith(COMMON_FUT):
        return Market.FUTURE
    if upper.startswith(COMMON_OPT):
        return Market.OPTION
    if upper.startswith(COMMON_COM):
        return Market.COMMODITY

    # SH/SZ 按代码模式细分
    if upper.startswith(COMMON_SH):
        num = upper[2:]
        if num.startswith("000"):
            return Market.INDEX
        if num.startswith("5"):
            return Market.FUND
        return Market.CN_A
    if upper.startswith(COMMON_SZ):
        num = upper[2:]
        if num.startswith("399"):
            return Market.INDEX
        if num.startswith(("15", "16", "18")):
            return Market.FUND
        return Market.CN_A

    # HK 按代码细分
    if upper.startswith(COMMON_HK):
        rest = upper[2:]
        if rest in ("HSI", "HSTECH", "HSCEI", "HSTECH"):
            return Market.INDEX
        return Market.HK

    # US 按代码细分
    if upper.startswith(COMMON_US):
        rest = upper[2:]
        if rest in ("DJI", "IXIC", "INX", "SPX"):
            return Market.INDEX
        if rest in ("XAU", "XAG", "GC", "SI", "CL", "NG"):
            return Market.COMMODITY
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
    for prefix in (COMMON_SH, COMMON_SZ, COMMON_HK, COMMON_US, COMMON_FUT, COMMON_OPT, COMMON_COM):
        if upper_code.startswith(prefix):
            return prefix
    return None


# ---- 各数据源代码映射配置 ----

def tencent_code_mapper() -> CodeMapper:
    """腾讯: SH->sh SZ->sz HK->hk US->us FUT->nf_ COM->hf_ (HK/US 大写)"""
    return CodeMapper(
        output_prefixes={
            COMMON_SH: "sh",
            COMMON_SZ: "sz",
            COMMON_HK: "hk",
            COMMON_US: "us",
            COMMON_FUT: "nf_",
            COMMON_COM: "hf_",
        },
        format_output=_tencent_format,
    )


def _tencent_format(market_prefix: str, value: str) -> str:
    if market_prefix in (COMMON_HK, COMMON_US, COMMON_FUT, COMMON_COM):
        return value.upper()
    return value


def sina_code_mapper() -> CodeMapper:
    """新浪: SH->sh SZ->sz HK->hk US->gb_ FUT->nf_ COM->hf_ OPT->op_ (US 小写)"""
    return CodeMapper(
        output_prefixes={
            COMMON_SH: "sh",
            COMMON_SZ: "sz",
            COMMON_HK: "hk",
            COMMON_US: "gb_",
            COMMON_FUT: "nf_",
            COMMON_COM: "hf_",
            COMMON_OPT: "op_",
        },
        format_output=_sina_format,
    )


def _sina_format(market_prefix: str, value: str) -> str:
    if market_prefix == COMMON_US:
        return value.lower()
    if market_prefix in (COMMON_COM, COMMON_FUT):
        return value.upper()
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
