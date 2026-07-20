"""stock-api Python backend.

提供 A 股 / 港股 / 美股行情查询，支持 FastAPI / CLI / MCP 三种接入方式。
核心数据源抽象为 DataProvider，按 AssetClass 分组注册，便于二期接入加密货币。
"""

from stock_api.core.base import DataProvider
from stock_api.core.exceptions import (
    ProviderError,
    ProviderNotFoundError,
    StockApiError,
    StockCodeError,
    StockParseError,
    StockRequestError,
)
from stock_api.core.models import (
    AssetClass,
    Inspection,
    InspectionStatus,
    Kline,
    KlineAdjust,
    KlineOptions,
    KlinePeriod,
    Market,
    Quote,
    Symbol,
)
from stock_api.core.registry import ProviderRegistry, create_default_registry

__all__ = [
    "AssetClass",
    "DataProvider",
    "Inspection",
    "InspectionStatus",
    "Kline",
    "KlineAdjust",
    "KlineOptions",
    "KlinePeriod",
    "Market",
    "ProviderError",
    "ProviderNotFoundError",
    "ProviderRegistry",
    "Quote",
    "StockApiError",
    "StockCodeError",
    "StockParseError",
    "StockRequestError",
    "Symbol",
    "create_default_registry",
]
