"""异步 HTTP 客户端，基于 httpx。

对应原 TS 的 utils/fetch.ts：
- 默认 User-Agent / Accept
- 超时控制
- 重试
- 二进制 body 返回（交由 encoding 模块解码）

使用共享 AsyncClient 以复用连接池；进程退出时通过 close() 关闭。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from stock_api.core.exceptions import StockRequestError

DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 2
DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (compatible; stock-api-py/2.7)",
}

_global_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _global_client
    if _global_client is None or _global_client.is_closed:
        _global_client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
            follow_redirects=True,
        )
    return _global_client


async def close_client() -> None:
    """进程退出时调用，关闭共享连接池。"""
    global _global_client
    if _global_client is not None and not _global_client.is_closed:
        await _global_client.aclose()
        _global_client = None


async def fetch_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    retries: int = DEFAULT_RETRIES,
) -> bytes:
    """GET 请求，返回原始 bytes（不解码，交给 encoding 模块）。

    对 429 限流做指数退避重试。
    """
    client = _get_client()
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response = await client.get(
                url,
                headers=headers,
                timeout=timeout if timeout is not None else DEFAULT_TIMEOUT,
            )
            if response.status_code == 429:
                # 限流：指数退避（2s, 5s, 10s...），给按分钟限流的 API 足够恢复时间
                wait = 2.0 * (2.5 ** attempt)
                await asyncio.sleep(wait)
                last_error = StockRequestError(f"Rate limited (429), retrying after {wait:.1f}s")
                continue
            if response.status_code >= 400:
                raise StockRequestError(f"Request failed with status {response.status_code}")
            return response.content
        except httpx.TimeoutException:
            last_error = StockRequestError(
                f"Request timed out after {timeout or DEFAULT_TIMEOUT}s"
            )
        except httpx.HTTPError as error:
            last_error = StockRequestError(str(error))

    raise last_error or StockRequestError("Request failed")


async def fetch_text(
    url: str,
    *,
    encoding: str = "utf-8",
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    retries: int = DEFAULT_RETRIES,
) -> str:
    """GET 请求，按指定编码解码为字符串。"""
    body = await fetch_bytes(url, headers=headers, timeout=timeout, retries=retries)
    return decode_bytes(body, encoding)


async def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
    retries: int = DEFAULT_RETRIES,
) -> Any:
    """GET 请求，解析 JSON。"""
    import json

    text = await fetch_text(url, encoding="utf-8", headers=headers, timeout=timeout, retries=retries)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise StockRequestError(f"Failed to parse JSON: {error}") from error


def decode_bytes(body: bytes, encoding: str) -> str:
    """按编码解码 bytes。gbk 归一为 gb18030（对齐原 TS iconv.ts）。"""
    normalized = "gb18030" if encoding.lower() in ("gbk", "gb2312") else encoding
    try:
        return body.decode(normalized, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
