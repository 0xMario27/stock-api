"""CLI 入口，基于 typer。

对应原 TS 的 cli.ts：
    stock-api get-stock SH510500
    stock-api get-stocks SH510500 SZ000651
    stock-api get-klines SH600519 --period week --count 20 --adjust qfq
    stock-api search 格力电器
    stock-api inspect SH510500
    stock-api mcp
    stock-api serve
"""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console

from stock_api.core.models import AssetClass, KlineAdjust, KlineOptions, KlinePeriod
from stock_api.core.registry import create_default_registry

app = typer.Typer(
    name="stock-api",
    help="A 股 / 港股 / 美股 / 加密货币行情查询 CLI",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _get_provider(registry, source: str, asset_class: AssetClass = AssetClass.STOCK):
    if source == "auto":
        return registry.get_auto(asset_class)
    return registry.get(source)


def _print_json(value) -> None:
    console.print_json(json.dumps(value, ensure_ascii=False, default=_json_default))


def _json_default(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@app.command()
def get_stock(
    code: str = typer.Argument(..., help="代码，如 SH510500 或 bitcoin"),
    source: str = typer.Option("auto", "--source", "-s", help="auto / tencent / sina / eastmoney / coingecko"),
    asset_class: AssetClass = typer.Option(AssetClass.STOCK, "--asset-class", "-a", help="stock / crypto"),
) -> None:
    """获取单只行情。"""
    registry = create_default_registry()
    provider = _get_provider(registry, source, asset_class)
    quote = asyncio.run(provider.get_quote(code))
    _print_json(quote)


@app.command()
def get_stocks(
    codes: list[str] = typer.Argument(..., help="代码列表"),
    source: str = typer.Option("auto", "--source", "-s"),
    asset_class: AssetClass = typer.Option(AssetClass.STOCK, "--asset-class", "-a"),
) -> None:
    """批量获取行情。"""
    registry = create_default_registry()
    provider = _get_provider(registry, source, asset_class)
    quotes = asyncio.run(provider.get_quotes(codes))
    _print_json(quotes)


@app.command()
def get_klines(
    code: str = typer.Argument(..., help="代码"),
    period: KlinePeriod = typer.Option(KlinePeriod.DAY, "--period", "-p", help="day / week / month"),
    count: int = typer.Option(120, "--count", "-c", help="返回条数"),
    adjust: KlineAdjust = typer.Option(KlineAdjust.NONE, "--adjust", help="none / qfq / hfq"),
    source: str = typer.Option("auto", "--source", "-s"),
    asset_class: AssetClass = typer.Option(AssetClass.STOCK, "--asset-class", "-a"),
) -> None:
    """获取 K 线数据。"""
    registry = create_default_registry()
    provider = _get_provider(registry, source, asset_class)
    options = KlineOptions(period=period, count=count, adjust=adjust)
    klines = asyncio.run(provider.get_klines(code, options))
    _print_json(klines)


@app.command()
def search(
    query: str = typer.Argument(..., help="搜索关键词"),
    source: str = typer.Option("auto", "--source", "-s"),
    asset_class: AssetClass = typer.Option(AssetClass.STOCK, "--asset-class", "-a"),
) -> None:
    """搜索代码。"""
    registry = create_default_registry()
    provider = _get_provider(registry, source, asset_class)
    symbols = asyncio.run(provider.search_symbols(query))
    _print_json(symbols)


@app.command()
def inspect(
    code: str = typer.Argument(..., help="代码"),
    source: str = typer.Option("auto", "--source", "-s"),
    asset_class: AssetClass = typer.Option(AssetClass.STOCK, "--asset-class", "-a"),
) -> None:
    """诊断数据源可用性。"""
    registry = create_default_registry()
    provider = _get_provider(registry, source, asset_class)
    inspection = asyncio.run(provider.inspect(code))
    _print_json(inspection)


@app.command()
def sources(
    asset_class: AssetClass | None = typer.Option(None, "--asset-class", "-a", help="stock / crypto"),
) -> None:
    """列出可用数据源。"""
    registry = create_default_registry()
    _print_json(registry.list_names(asset_class))


@app.command()
def mcp() -> None:
    """启动 MCP server (JSON-RPC over stdio)。"""
    from stock_api.mcp_server import run_mcp_server

    asyncio.run(run_mcp_server())


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="监听地址"),
    port: int = typer.Option(8000, "--port", help="监听端口"),
    reload: bool = typer.Option(False, "--reload", help="开发热重载"),
) -> None:
    """启动 FastAPI 服务。"""
    import uvicorn

    uvicorn.run(
        "stock_api.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
