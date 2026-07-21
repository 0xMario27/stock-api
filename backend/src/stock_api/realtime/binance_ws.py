"""Binance WebSocket 实时数据提供者。

使用 Binance 公共 WebSocket Stream API（无需 API Key）：
- Ticker: wss://stream.binance.com:9443/ws/{symbol}@ticker
- K线: wss://stream.binance.com:9443/ws/{symbol}@kline_{interval}
- 组合流: wss://stream.binance.com:9443/stream?streams=a/b/c

消息格式（ticker）:
{
  "e": "24hrTicker", "s": "BTCUSDT",
  "c": "64000.00",  // 最新价
  "h": "65000.00",  // 24h 最高
  "l": "63000.00",  // 24h 最低
  "p": "1.50",      // 24h 涨跌额
  "P": "2.50",      // 24h 涨跌幅 %
  "o": "62500.00",  // 24h 开盘
  "v": "1000.5",    // 24h 成交量
  "q": "64000000"   // 24h 成交额
}
"""

from __future__ import annotations

import logging
from typing import Any

from stock_api.core.models import AssetClass, Market, Quote
from stock_api.realtime.manager import get_pool

logger = logging.getLogger("stock_api.realtime.binance")

_BASE_WS = "wss://stream.binance.com:9443"

# coin ID -> Binance 交易对
_CRYPTO_MAP: dict[str, str] = {
    "bitcoin": "btcusdt", "ethereum": "ethusdt", "binancecoin": "bnbusdt",
    "solana": "solusdt", "ripple": "xrpusdt", "cardano": "adausdt",
    "dogecoin": "dogeusdt", "polkadot": "dotusdt", "chainlink": "linkusdt",
    "litecoin": "ltcusdt", "tron": "trxusdt",
}


def _coin_to_stream(coin_id: str) -> str | None:
    """coin ID -> Binance stream symbol。"""
    stream = _CRYPTO_MAP.get(coin_id.lower())
    if stream:
        return stream
    # 尝试直接构造
    upper = coin_id.upper()
    if upper.endswith("USDT"):
        return upper.lower()
    if 2 <= len(upper) <= 6 and upper.isalpha():
        return upper.lower() + "usdt"
    return None


def _build_url(streams: list[str]) -> str:
    """构建 Binance combined stream URL。"""
    if len(streams) == 1:
        return f"{_BASE_WS}/ws/{streams[0]}"
    return f"{_BASE_WS}/stream?streams={'/'.join(streams)}"


def _parse_ticker(msg: dict[str, Any]) -> Quote | None:
    """解析 Binance ticker 消息为 Quote。"""
    # 组合流消息格式: {"stream": "btcusdt@ticker", "data": {...}}
    data = msg.get("data", msg)
    symbol = data.get("s") or ""
    if not symbol:
        return None

    now = _f(data.get("c"))
    high = _f(data.get("h"))
    low = _f(data.get("l"))
    open_price = _f(data.get("o"))
    pct = _f(data.get("P"))

    # Binance symbol -> coin ID（反向映射）
    rev_map = {v: k for k, v in _CRYPTO_MAP.items()}
    coin_id = rev_map.get(symbol.lower(), symbol.lower())

    return Quote(
        code=coin_id,
        name=coin_id,
        now=now,
        low=low,
        high=high,
        yesterday=open_price,
        percent=pct / 100 if pct else 0.0,
        source="binance_ws",
        asset_class=AssetClass.CRYPTO,
        market=Market.CRYPTO,
    )


def _f(v: Any) -> float:
    try:
        return float(v) if v else 0.0
    except (TypeError, ValueError):
        return 0.0


# 存储活跃订阅的回调
_subscribers: dict[str, list[Any]] = {}  # coin_id -> [callbacks]


async def init_binance_ws() -> None:
    """初始化 Binance WebSocket provider，注册到连接池。"""
    pool = get_pool()
    pool.register_provider(
        provider="binance",
        url_builder=_build_url,
        message_router=_on_binance_message,
    )
    logger.info("Binance WS provider registered")


def _on_binance_message(msg: dict[str, Any]) -> None:
    """处理 Binance WebSocket 消息。"""
    quote = _parse_ticker(msg)
    if not quote:
        return
    # 通知所有该 coin 的订阅者
    callbacks = _subscribers.get(quote.code, [])
    for cb in callbacks:
        try:
            cb(quote)
        except Exception as e:
            logger.error(f"subscriber callback error: {e}")


async def subscribe_ticker(
    coin_id: str,
    callback: Any,
) -> str:
    """订阅某个加密货币的实时行情。

    Args:
        coin_id: 统一代码（如 bitcoin）
        callback: 收到行情时的回调函数

    Returns:
        订阅 key（用于取消订阅）
    """
    stream_sym = _coin_to_stream(coin_id)
    if not stream_sym:
        raise ValueError(f"Cannot map {coin_id} to Binance symbol")

    stream = f"{stream_sym}@ticker"
    key = f"binance:{coin_id}:ticker"

    # 记录回调
    if coin_id not in _subscribers:
        _subscribers[coin_id] = []
    _subscribers[coin_id].append(callback)

    # 订阅
    pool = get_pool()
    await pool.subscribe(key, "binance", stream, lambda _: None)
    logger.info(f"Subscribed to {coin_id} ({stream})")
    return key


async def unsubscribe_ticker(key: str, coin_id: str, callback: Any) -> None:
    """取消订阅。"""
    if coin_id in _subscribers:
        _subscribers[coin_id] = [cb for cb in _subscribers[coin_id] if cb is not callback]
        if not _subscribers[coin_id]:
            del _subscribers[coin_id]

    pool = get_pool()
    await pool.unsubscribe(key)
    logger.info(f"Unsubscribed from {coin_id}")
