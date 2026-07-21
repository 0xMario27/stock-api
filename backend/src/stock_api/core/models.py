"""统一数据模型 (pydantic v2)。

对齐原 TS 版的 Stock / Kline / Inspection，并扩展 AssetClass / Market 字段
为二期加密货币接入预留。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssetClass(StrEnum):
    """资产类别。二期接入加密货币时新增 CRYPTO 即可。"""

    STOCK = "stock"
    CRYPTO = "crypto"


class Market(StrEnum):
    """市场标识。"""

    CN_A = "cn_a"
    HK = "hk"
    US = "us"
    INDEX = "index"
    FUND = "fund"
    FUTURE = "future"
    OPTION = "option"
    COMMODITY = "commodity"
    CRYPTO = "crypto"


class KlinePeriod(StrEnum):
    MINUTE_1 = "minute1"
    MINUTE_5 = "minute5"
    MINUTE_15 = "minute15"
    MINUTE_30 = "minute30"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class KlineAdjust(StrEnum):
    NONE = "none"
    QFQ = "qfq"
    HFQ = "hfq"


class KlineOptions(BaseModel):
    """K 线查询参数。"""

    model_config = ConfigDict(extra="forbid")

    period: KlinePeriod = KlinePeriod.DAY
    count: int = Field(default=120, ge=1, le=1000)
    adjust: KlineAdjust = KlineAdjust.NONE


class Quote(BaseModel):
    """标准化行情报价。对应原 TS 的 Stock。

    所有数据源的行情返回都归一化为此结构。provider-specific 原始字段不暴露。
    扩展字段为 Optional，数据源有则填充，无则为 null。
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="统一代码，如 SH510500 / SZ000651 / HK02020 / USDJI")
    name: str = Field(default="---", description="证券名称")
    now: float = Field(default=0.0, description="最新价")
    low: float = Field(default=0.0, description="最低价")
    high: float = Field(default=0.0, description="最高价")
    yesterday: float = Field(default=0.0, description="昨收价")
    percent: float = Field(default=0.0, description="涨跌幅，0.01 表示 1%")
    source: str = Field(default="base", description="实际返回数据的数据源")
    asset_class: AssetClass = Field(default=AssetClass.STOCK, description="资产类别")
    market: Market | None = Field(default=None, description="市场")
    # 行情扩展字段（Optional = 数据源提供时填充）
    open_price: float | None = Field(default=None, description="今日开盘价")
    volume: float | None = Field(default=None, description="成交量（标准化单位：股票=股，加密=币）")
    turnover: float | None = Field(default=None, description="成交额（标准化单位：股票=元，加密=USDT）")
    pe_ratio: float | None = Field(default=None, description="市盈率（TTM）")
    pb_ratio: float | None = Field(default=None, description="市净率")
    market_cap: float | None = Field(default=None, description="总市值（元/USDT）")
    circulating_cap: float | None = Field(default=None, description="流通市值（元/USDT）")
    high_52w: float | None = Field(default=None, description="52周最高价")
    low_52w: float | None = Field(default=None, description="52周最低价")


class Kline(BaseModel):
    """标准化 K 线行。对应原 TS 的 Kline。"""

    model_config = ConfigDict(extra="forbid")

    date: str = Field(description="日期 YYYY-MM-DD 或 YYYY-MM-DD HH:MM")
    open: float = 0.0
    close: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float | None = Field(default=None, description="成交量，数据源提供时返回")
    source: str = Field(default="base")
    timestamp: int | None = Field(default=None, description="UNIX 时间戳（秒），分时数据用")


class Symbol(BaseModel):
    """搜索结果中的代码项。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    name: str = "---"
    market: Market | None = None
    asset_class: AssetClass = AssetClass.STOCK


InspectionStatus = Literal["success", "empty", "error"]


class Inspection(BaseModel):
    """单个数据源的诊断结果。对应原 TS 的 StockProviderInspection。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    source: str
    status: InspectionStatus
    quote: Quote | None = None
    error: str | None = None


class AutoInspection(BaseModel):
    """auto 模式跨源诊断结果。对应原 TS 的 AutoStockInspection。"""

    model_config = ConfigDict(extra="forbid")

    code: str
    source: str = "base"
    quote: Quote
    sources: list[Inspection] = Field(default_factory=list)


def default_quote(code: str, source: str = "base") -> Quote:
    """构造缺失股票的默认报价。对应原 TS 的 DEFAULT_STOCK。"""

    return Quote(code=code, name="---", source=source)
