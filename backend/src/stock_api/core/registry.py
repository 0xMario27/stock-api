"""Provider 注册表与 Auto 兜底路由。

核心设计（为二期 crypto 准备）：
- ProviderRegistry 按 asset_class 分组管理 providers
- get_auto(asset_class) 返回跨源兜底的 AutoProvider
- 新增 crypto 只需 register(crypto_provider)，前端/API 无需改动

对应原 TS 的 createAutoStockApi + providers 数组。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from stock_api.core.base import DataProvider
from stock_api.core.exceptions import ProviderNotFoundError
from stock_api.core.models import (
    AssetClass,
    AutoInspection,
    Inspection,
    Kline,
    KlineOptions,
    Quote,
    Symbol,
    default_quote,
)


class ProviderRegistry:
    """数据源注册表，按 asset_class 分组。"""

    def __init__(self) -> None:
        self._providers: dict[str, DataProvider] = {}
        self._by_asset_class: dict[AssetClass, list[str]] = defaultdict(list)

    def register(self, provider: DataProvider) -> None:
        """注册一个数据源。同名 provider 会覆盖。"""
        name = provider.name
        self._providers[name] = provider
        order = self._by_asset_class[provider.asset_class]
        if name not in order:
            order.append(name)

    def get(self, name: str) -> DataProvider:
        """按名称获取数据源。"""
        if name not in self._providers:
            raise ProviderNotFoundError(f"Provider not found: {name}")
        return self._providers[name]

    def list_names(self, asset_class: AssetClass | None = None) -> list[str]:
        """列出数据源名称。asset_class 为 None 时列出全部。"""
        if asset_class is None:
            return list(self._providers.keys())
        return list(self._by_asset_class.get(asset_class, []))

    def list_providers(self, asset_class: AssetClass | None = None) -> list[DataProvider]:
        """列出数据源实例。"""
        return [self.get(name) for name in self.list_names(asset_class)]

    def get_auto(self, asset_class: AssetClass) -> AutoProvider:
        """获取指定资产类别的自动兜底 provider。"""
        providers = self.list_providers(asset_class)
        return AutoProvider(asset_class=asset_class, providers=providers)


class AutoProvider(DataProvider):
    """自动兜底 provider：按顺序尝试多个数据源。

    对应原 TS 的 createAutoStockApi，行为：
    - get_quote / get_quotes: 逐源尝试，取第一个成功且非默认值的结果
    - get_klines: 按固定顺序尝试，取第一个非空结果
    - search_symbols: 逐源尝试，取第一个非空结果
    - inspect: 跑全部数据源，汇总各源状态，选第一个成功的作为最终结果
    """

    def __init__(
        self,
        asset_class: AssetClass,
        providers: list[DataProvider],
    ) -> None:
        self.asset_class = asset_class
        self.providers = list(providers)
        self.name = "auto"

    async def get_quote(self, code: str) -> Quote:
        inspection = await self.inspect(code)
        return inspection.quote

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        normalized = _normalize_codes(codes)
        return await asyncio.gather(*[self.get_quote(code) for code in normalized])

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        for provider in self.providers:
            try:
                klines = await provider.get_klines(code, options)
            except Exception:
                continue
            if klines:
                return klines
        return []

    async def search_symbols(self, query: str) -> list[Symbol]:
        for provider in self.providers:
            try:
                symbols = await provider.search_symbols(query)
            except Exception:
                continue
            if symbols:
                return symbols
        return []

    async def inspect(self, code: str) -> AutoInspection:
        """跨源诊断：跑全部数据源，选第一个成功的作为最终 quote。"""
        sources: list[Inspection] = []
        selected_quote: Quote | None = None
        selected_source = "base"

        for provider in self.providers:
            inspection = await provider.inspect(code)
            sources.append(inspection)
            if (
                selected_quote is None
                and inspection.status == "success"
                and inspection.quote is not None
            ):
                selected_quote = inspection.quote
                selected_source = inspection.source

        quote = selected_quote or default_quote(code, "base")
        return AutoInspection(
            code=code,
            source=selected_source,
            quote=quote,
            sources=sources,
        )


def _normalize_codes(codes: list[str]) -> list[str]:
    """去重并过滤空字符串。对应原 TS 的 normalizeCodes。"""
    seen: set[str] = set()
    result: list[str] = []
    for code in codes:
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result


def create_default_registry() -> ProviderRegistry:
    """创建默认注册表，注册股票三大数据源 + 加密货币数据源。

    二期接入更多 crypto 数据源时（如 Binance），在此处追加注册即可，
    或单独提供 register_crypto_providers(registry) 函数。
    """
    from stock_api.providers.crypto import CoinGeckoProvider
    from stock_api.providers.eastmoney import EastmoneyProvider
    from stock_api.providers.sina import SinaProvider
    from stock_api.providers.tencent import TencentProvider

    registry = ProviderRegistry()
    # 股票数据源：auto 兜底顺序 tencent -> sina -> eastmoney
    registry.register(TencentProvider())
    registry.register(SinaProvider())
    registry.register(EastmoneyProvider())
    # 加密货币数据源：auto 兜底顺序 coingecko（后续可追加 Binance 等）
    registry.register(CoinGeckoProvider())
    return registry
