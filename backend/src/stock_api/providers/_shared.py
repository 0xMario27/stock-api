"""共享的 provider 基类工具。

对应原 TS 的 shared/provider.ts 中跨源复用的逻辑：
- create_stock_inspection: 单源诊断
- is_available_quote: 判断 quote 是否有效（非默认值）
"""

from __future__ import annotations

from stock_api.core.models import Inspection, Quote


def is_available_quote(quote: Quote | None) -> bool:
    """quote 非空且 name 不是默认值。对应原 TS 的 isAvailableStock。"""
    return bool(quote and quote.name != "---")


async def create_inspection(
    source: str,
    code: str,
    get_quote_fn,
) -> Inspection:
    """单数据源诊断。对应原 TS 的 createStockInspection。"""
    try:
        quote = await get_quote_fn(code)
        status: str = "success" if is_available_quote(quote) else "empty"
        return Inspection(code=code, source=source, status=status, quote=quote)
    except Exception as error:  # noqa: BLE001
        return Inspection(
            code=code,
            source=source,
            status="error",
            error=str(error),
        )
