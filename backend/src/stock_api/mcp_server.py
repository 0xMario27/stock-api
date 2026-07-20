"""MCP server：JSON-RPC 2.0 over stdio。

对应原 TS 的 mcp/server.ts，手写实现，无外部 MCP SDK 依赖。
5 个工具：get_stock / get_stocks / get_klines / search_stocks / inspect_stock。
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from stock_api.core.models import AssetClass, KlineAdjust, KlineOptions, KlinePeriod
from stock_api.core.registry import create_default_registry

_PROTOCOL_VERSION = "2025-06-18"

_SOURCE_NAMES = ["auto", "tencent", "sina", "eastmoney", "coingecko", "binance"]
_ASSET_CLASSES = ["stock", "crypto"]

def _source_schema() -> dict[str, Any]:
    return {
        "type": "string",
        "enum": _SOURCE_NAMES,
        "description": "Data source. Defaults to auto.",
    }


def _asset_class_schema() -> dict[str, Any]:
    return {
        "type": "string",
        "enum": _ASSET_CLASSES,
        "description": "Asset class: stock or crypto. Defaults to stock.",
    }


_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_stock",
        "description": "Get one normalized stock or crypto quote by code.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["code"],
            "properties": {
                "code": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Stock code (SH510500) or crypto coin id (bitcoin).",
                },
                "source": _source_schema(),
                "asset_class": _asset_class_schema(),
            },
        },
    },
    {
        "name": "get_stocks",
        "description": "Get normalized quotes for multiple codes.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["codes"],
            "properties": {
                "codes": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "description": "Stock codes or crypto coin ids.",
                },
                "source": _source_schema(),
                "asset_class": _asset_class_schema(),
            },
        },
    },
    {
        "name": "get_klines",
        "description": "Get normalized K-line rows for charting.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["code"],
            "properties": {
                "code": {"type": "string", "minLength": 1},
                "period": {
                    "type": "string",
                    "enum": ["day", "week", "month"],
                    "description": "K-line period. Defaults to day.",
                },
                "count": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 500,
                    "description": "Number of rows to return.",
                },
                "adjust": {
                    "type": "string",
                    "enum": ["none", "qfq", "hfq"],
                    "description": "Price adjustment mode. Defaults to none.",
                },
                "source": _source_schema(),
                "asset_class": _asset_class_schema(),
            },
        },
    },
    {
        "name": "search_stocks",
        "description": "Search stock or crypto symbols by keyword.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Search keyword, such as 格力电器 or bitcoin.",
                },
                "source": _source_schema(),
                "asset_class": _asset_class_schema(),
            },
        },
    },
    {
        "name": "inspect_stock",
        "description": "Inspect quote availability and provider fallback details.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["code"],
            "properties": {
                "code": {"type": "string", "minLength": 1},
                "source": _source_schema(),
                "asset_class": _asset_class_schema(),
            },
        },
    },
]


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False, default=_json_default) + "\n")
    sys.stdout.flush()


def _error_response(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _result_response(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _is_request(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("jsonrpc") == "2.0"
        and isinstance(value.get("method"), str)
    )


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid {name}")
    return value.strip()


def _require_string_array(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Missing or invalid {name}")
    return [_require_string(item, name) for item in value]


def _optional_source(value: Any) -> str:
    if value is None:
        return "auto"
    source = _require_string(value, "source")
    if source not in _SOURCE_NAMES:
        raise ValueError(f"Invalid source: {source}")
    return source


def _optional_asset_class(value: Any) -> AssetClass:
    if value is None:
        return AssetClass.STOCK
    ac = _require_string(value, "asset_class")
    if ac == "crypto":
        return AssetClass.CRYPTO
    if ac == "stock":
        return AssetClass.STOCK
    raise ValueError(f"Invalid asset_class: {ac}")


def _optional_period(value: Any) -> KlinePeriod | None:
    if value is None:
        return None
    period = _require_string(value, "period")
    if period not in ("day", "week", "month"):
        raise ValueError(f"Invalid period: {period}")
    return KlinePeriod(period)


def _optional_adjust(value: Any) -> KlineAdjust | None:
    if value is None:
        return None
    adjust = _require_string(value, "adjust")
    if adjust not in ("none", "qfq", "hfq"):
        raise ValueError(f"Invalid adjust: {adjust}")
    return KlineAdjust(adjust)


def _optional_count(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"Invalid count: {value}")
    return int(value)


def _tool_result(data: dict[str, Any]) -> dict[str, Any]:
    structured = json.loads(json.dumps(data, ensure_ascii=False, default=_json_default))
    return {
        "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False, indent=2)}],
        "structuredContent": structured,
    }


async def _execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    registry = create_default_registry()

    def _get_provider(source: str, asset_class: AssetClass):
        if source == "auto":
            return registry.get_auto(asset_class)
        return registry.get(source)

    if name == "get_stock":
        source = _optional_source(args.get("source"))
        asset_class = _optional_asset_class(args.get("asset_class"))
        code = _require_string(args.get("code"), "code")
        provider = _get_provider(source, asset_class)
        quote = await provider.get_quote(code)
        return {"input": {"code": code, "source": source, "asset_class": asset_class.value}, "response": {"stock": quote}}

    if name == "get_stocks":
        source = _optional_source(args.get("source"))
        asset_class = _optional_asset_class(args.get("asset_class"))
        codes = _require_string_array(args.get("codes"), "codes")
        provider = _get_provider(source, asset_class)
        quotes = await provider.get_quotes(codes)
        return {
            "input": {"codes": codes, "source": source, "asset_class": asset_class.value},
            "response": {"count": len(quotes), "stocks": quotes},
        }

    if name == "get_klines":
        source = _optional_source(args.get("source"))
        asset_class = _optional_asset_class(args.get("asset_class"))
        code = _require_string(args.get("code"), "code")
        period = _optional_period(args.get("period"))
        adjust = _optional_adjust(args.get("adjust"))
        count = _optional_count(args.get("count"))
        provider = _get_provider(source, asset_class)
        options = KlineOptions(period=period, adjust=adjust, count=count)
        klines = await provider.get_klines(code, options)
        return {
            "input": {
                "code": code,
                "period": options.period.value,
                "count": options.count,
                "adjust": options.adjust.value,
                "source": source,
                "asset_class": asset_class.value,
            },
            "response": {"count": len(klines), "klines": klines},
        }

    if name == "search_stocks":
        source = _optional_source(args.get("source"))
        asset_class = _optional_asset_class(args.get("asset_class"))
        query = _require_string(args.get("query"), "query")
        provider = _get_provider(source, asset_class)
        symbols = await provider.search_symbols(query)
        return {
            "input": {"query": query, "source": source, "asset_class": asset_class.value},
            "response": {"count": len(symbols), "stocks": symbols},
        }

    if name == "inspect_stock":
        source = _optional_source(args.get("source"))
        asset_class = _optional_asset_class(args.get("asset_class"))
        code = _require_string(args.get("code"), "code")
        provider = _get_provider(source, asset_class)
        inspection = await provider.inspect(code)
        return {"input": {"code": code, "source": source, "asset_class": asset_class.value}, "response": {"inspection": inspection}}

    raise ValueError(f"Unknown tool: {name}")


async def _handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    if not _is_request(request):
        return _error_response(None, -32600, "Invalid Request")

    req_id = request.get("id")

    if req_id is None:
        # notification，无需响应
        return None

    method = request["method"]
    try:
        result = await _route(method, request.get("params"))
        return _result_response(req_id, result)
    except Exception as error:  # noqa: BLE001
        return _error_response(req_id, -32603, str(error))


async def _route(method: str, params: Any) -> Any:
    if method == "initialize":
        return {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "stock-api", "version": "2.7.3"},
        }
    if method == "tools/list":
        return {"tools": _TOOLS}
    if method == "tools/call":
        if not isinstance(params, dict):
            return _tool_result({"error": "invalid params"})
        name = params.get("name")
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        try:
            data = await _execute_tool(str(name), args)
            return _tool_result(data)
        except Exception as error:  # noqa: BLE001
            data = {
                "input": {"arguments": args, "tool": name},
                "response": {"code": "STOCK_API_TOOL_ERROR", "message": str(error)},
            }
            return {**_tool_result(data), "isError": True}
    raise ValueError(f"Unknown method: {method}")


async def run_mcp_server() -> None:
    """从 stdin 读取 JSON-RPC，处理后写到 stdout。"""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    buffer = ""
    while True:
        chunk = await reader.read(4096)
        if not chunk:
            break
        buffer += chunk.decode("utf-8", errors="replace")

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                _write(_error_response(None, -32700, str(error)))
                continue

            messages = payload if isinstance(payload, list) else [payload]
            for message in messages:
                response = await _handle_request(message)
                if response is not None:
                    _write(response)
