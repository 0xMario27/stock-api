"""REST API 路由。

对应原 TS 的 CLI / MCP 暴露的能力，统一以 RESTful 风格对外：
    GET /api/quote/{code}
    GET /api/quotes?codes=SH510500&codes=SZ000651
    GET /api/klines/{code}?period=day&count=120&adjust=none
    GET /api/search?q=格力电器
    GET /api/inspect/{code}
    GET /api/sources
    GET /api/capabilities
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from stock_api.core.exceptions import (
    ProviderNotFoundError,
    StockApiError,
    StockCodeError,
)
from stock_api.core.models import (
    AssetClass,
    AutoInspection,
    Kline,
    KlineAdjust,
    KlineOptions,
    KlinePeriod,
    Quote,
    Symbol,
)

router = APIRouter()


def _resolve_source(request: Request, source: str):
    """从 app.state.registry 解析 source（auto 或具体数据源）。"""
    registry = request.app.state.registry
    try:
        if source == "auto":
            return registry.get_auto(AssetClass.STOCK)
        return registry.get(source)
    except ProviderNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/quote/{code}", response_model=Quote)
async def get_quote(
    code: str,
    request: Request,
    source: Annotated[str, Query(description="auto / tencent / sina / eastmoney")] = "auto",
) -> Quote:
    try:
        provider = _resolve_source(request, source)
        return await provider.get_quote(code)
    except StockCodeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except StockApiError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/quotes", response_model=list[Quote])
async def get_quotes(
    request: Request,
    codes: Annotated[list[str], Query(description="股票代码列表")],
    source: str = "auto",
) -> list[Quote]:
    if not codes:
        raise HTTPException(status_code=400, detail="codes is required")
    try:
        provider = _resolve_source(request, source)
        return await provider.get_quotes(codes)
    except StockCodeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except StockApiError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/klines/{code}", response_model=list[Kline])
async def get_klines(
    code: str,
    request: Request,
    period: KlinePeriod = KlinePeriod.DAY,
    count: Annotated[int, Query(ge=1, le=500)] = 120,
    adjust: KlineAdjust = KlineAdjust.NONE,
    source: str = "auto",
) -> list[Kline]:
    options = KlineOptions(period=period, count=count, adjust=adjust)
    try:
        provider = _resolve_source(request, source)
        return await provider.get_klines(code, options)
    except StockCodeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except StockApiError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/search", response_model=list[Symbol])
async def search_symbols(
    request: Request,
    q: Annotated[str, Query(description="搜索关键词", min_length=1)],
    source: str = "auto",
) -> list[Symbol]:
    try:
        provider = _resolve_source(request, source)
        return await provider.search_symbols(q)
    except StockApiError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/inspect/{code}", response_model=AutoInspection)
async def inspect_stock(
    code: str,
    request: Request,
    source: str = "auto",
) -> AutoInspection:
    try:
        provider = _resolve_source(request, source)
        return await provider.inspect(code)
    except StockApiError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get("/sources", response_model=list[str])
async def list_sources(request: Request) -> list[str]:
    registry = request.app.state.registry
    return registry.list_names(AssetClass.STOCK)


@router.get("/capabilities")
async def get_capabilities(request: Request) -> list[dict]:
    registry = request.app.state.registry
    providers = registry.list_providers(AssetClass.STOCK)
    return [
        {
            "name": p.name,
            "asset_class": p.asset_class.value,
            "supported_markets": [m.value for m in p.supported_markets],
        }
        for p in providers
    ]


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
