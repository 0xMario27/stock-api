"""FastAPI WebSocket 端点 -- 前端实时推送。

前端连接 ws://host:8000/ws/realtime，发送订阅消息：
    {"action": "subscribe", "symbols": ["bitcoin", "ethereum"]}
    {"action": "unsubscribe", "symbols": ["bitcoin"]}

后端通过 Binance WebSocket 获取实时数据，推送给前端。
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from stock_api.realtime.binance_ws import (
    init_binance_ws,
    subscribe_ticker,
    unsubscribe_ticker,
)
from stock_api.realtime.manager import close_pool, get_pool

logger = logging.getLogger("stock_api.realtime.server")

router = APIRouter()

_initialized = False


async def ensure_init() -> None:
    global _initialized
    if not _initialized:
        await init_binance_ws()
        _initialized = True


@router.websocket("/ws/realtime")
async def realtime_endpoint(ws: WebSocket) -> None:
    """WebSocket 端点：前端连接后订阅/取消订阅实时行情。"""
    await ws.accept()
    await ensure_init()

    # 记录当前连接的所有订阅
    active_subs: dict[str, tuple[str, any]] = {}  # coin_id -> (key, callback)

    async def send_json(data: dict) -> None:
        with suppress(Exception):
            await ws.send_text(json.dumps(data, ensure_ascii=False, default=str))

    # 发送连接成功消息
    await send_json({"type": "connected", "message": "Realtime connection established"})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send_json({"type": "error", "message": "Invalid JSON"})
                continue

            action = msg.get("action")
            symbols = msg.get("symbols", [])

            if action == "subscribe":
                for coin_id in symbols:
                    if coin_id in active_subs:
                        continue  # 已订阅

                    # 创建回调：收到的 quote 推给前端
                    async def make_callback(cid: str):
                        async def callback(quote):
                            await send_json({
                                "type": "quote",
                                "code": cid,
                                "data": quote.model_dump(mode="json"),
                            })
                        return callback

                    # 同步回调包装（pool 用同步调用）
                    def make_sync_callback(cid: str):
                        def callback(quote):
                            asyncio.create_task(send_json({
                                "type": "quote",
                                "code": cid,
                                "data": quote.model_dump(mode="json"),
                            }))
                        return callback

                    cb = make_sync_callback(coin_id)
                    try:
                        key = await subscribe_ticker(coin_id, cb)
                        active_subs[coin_id] = (key, cb)
                        await send_json({"type": "subscribed", "code": coin_id})
                    except Exception as e:
                        await send_json({"type": "error", "code": coin_id, "message": str(e)})

            elif action == "unsubscribe":
                for coin_id in symbols:
                    if coin_id in active_subs:
                        key, cb = active_subs.pop(coin_id)
                        await unsubscribe_ticker(key, coin_id, cb)
                        await send_json({"type": "unsubscribed", "code": coin_id})

            elif action == "health":
                pool = get_pool()
                await send_json({"type": "health", "data": pool.get_health()})

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # 清理所有订阅
        for coin_id, (key, cb) in active_subs.items():
            with suppress(Exception):
                await unsubscribe_ticker(key, coin_id, cb)


@asynccontextmanager
@asynccontextmanager
async def realtime_lifespan():
    """FastAPI lifespan: 启动时初始化，关闭时清理。"""
    await ensure_init()
    yield
    await close_pool()
