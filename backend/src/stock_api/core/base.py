"""DataProvider 抽象基类。

所有数据源（腾讯 / 新浪 / 东方财富 / 二期 crypto）都实现此接口。
对齐原 TS 的 StockApi + StockProviderApi，统一为异步方法。

二期接入加密货币：新建 providers/crypto/binance.py，继承 DataProvider，
设置 asset_class = CRYPTO，实现以下方法，注册到 registry 即可。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from stock_api.core.models import (
    AssetClass,
    Inspection,
    Kline,
    KlineOptions,
    Market,
    Quote,
    Symbol,
)


class DataProvider(ABC):
    """数据源抽象基类。

    子类必须声明:
        name: 数据源唯一标识，如 "tencent" / "sina" / "eastmoney" / "binance"
        asset_class: 资产类别，STOCK 或 CRYPTO
        supported_markets: 支持的市场列表

    并实现以下异步方法:
        get_quote / get_quotes / get_klines / search_symbols / inspect
    """

    name: str = "base"
    asset_class: AssetClass = AssetClass.STOCK
    supported_markets: list[Market] = []

    @abstractmethod
    async def get_quote(self, code: str) -> Quote:
        """获取单只行情。"""

    @abstractmethod
    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        """批量获取行情。"""

    @abstractmethod
    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        """获取 K 线。"""

    @abstractmethod
    async def search_symbols(self, query: str) -> list[Symbol]:
        """搜索代码。"""

    @abstractmethod
    async def inspect(self, code: str) -> Inspection:
        """诊断单数据源可用性。"""

    def supports(self, market: Market) -> bool:
        """是否支持指定市场。"""
        return market in self.supported_markets
