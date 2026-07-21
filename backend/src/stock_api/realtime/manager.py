"""WebSocket 连接池管理器。

管理到各数据源的 WebSocket 连接，提供：
- 连接池：按 provider 维护连接，多 symbol 复用
- 保活：定时发送 ping/heartbeat
- 健康检查：监控连接状态，自动标记不健康
- 自动重连：断线后指数退避重连
- 订阅管理：多 subscriber 复用同一连接
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import websockets

logger = logging.getLogger("stock_api.realtime")

# 心跳间隔（秒）
HEARTBEAT_INTERVAL = 30
# 重连初始延迟
RECONNECT_INITIAL_DELAY = 1.0
# 重连最大延迟
RECONNECT_MAX_DELAY = 60.0
# 重连最大次数（0 = 无限）
RECONNECT_MAX_ATTEMPTS = 0
# 健康检查超时
HEALTH_CHECK_TIMEOUT = 10


class ConnectionStatus(StrEnum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class ConnectionHealth:
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_ping: float = 0
    last_pong: float = 0
    last_message: float = 0
    reconnect_attempts: int = 0
    total_messages: int = 0
    total_errors: int = 0
    connected_at: float = 0


@dataclass
class Subscription:
    """一个订阅：symbol -> callback。"""
    key: str  # 唯一标识，如 "binance:btcusdt:ticker"
    callback: Callable[[dict[str, Any]], None]
    provider: str
    stream: str  # provider 特定的 stream 名称


class WSConnection:
    """单个 WebSocket 连接，支持多 stream 复用。"""

    def __init__(
        self,
        name: str,
        url_builder: Callable[[list[str]], str],
        on_message: Callable[[dict[str, Any]], None],
        ping_payload: str | None = None,
        ping_interval: float = HEARTBEAT_INTERVAL,
    ) -> None:
        self.name = name
        self._url_builder = url_builder
        self._on_message = on_message
        self._ping_payload = ping_payload
        self._ping_interval = ping_interval
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._streams: set[str] = set()
        self._health = ConnectionHealth()
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._lock = asyncio.Lock()

    @property
    def health(self) -> ConnectionHealth:
        return self._health

    @property
    def is_healthy(self) -> bool:
        if self._health.status != ConnectionStatus.CONNECTED:
            return False
        return not (self._health.last_pong > 0 and time.monotonic() - self._health.last_pong > self._ping_interval * 3)

    async def start(self, streams: list[str]) -> None:
        """启动连接并订阅指定 streams。"""
        async with self._lock:
            self._streams.update(streams)
            if not self._running:
                self._running = True
                task = asyncio.create_task(self._run())
                self._tasks.append(task)

    async def stop(self) -> None:
        """停止连接。"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        if self._ws:
            await self._ws.close()
        self._health.status = ConnectionStatus.DISCONNECTED

    async def add_streams(self, streams: list[str]) -> None:
        """动态添加订阅（需要重连以更新 URL）。"""
        new_streams = [s for s in streams if s not in self._streams]
        if not new_streams:
            return
        self._streams.update(new_streams)
        # 重连以订阅新的 streams
        await self._reconnect()

    async def _run(self) -> None:
        """主循环：连接 -> 收消息 -> 断线重连。"""
        while self._running:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.warning(f"[{self.name}] connection error: {e}")
                self._health.total_errors += 1
                self._health.status = ConnectionStatus.RECONNECTING

            if not self._running:
                break

            # 指数退避重连
            self._health.reconnect_attempts += 1
            delay = min(
                RECONNECT_INITIAL_DELAY * (2 ** min(self._health.reconnect_attempts - 1, 6)),
                RECONNECT_MAX_DELAY,
            )
            logger.info(f"[{self.name}] reconnecting in {delay:.1f}s (attempt {self._health.reconnect_attempts})")
            await asyncio.sleep(delay)

    async def _connect_and_listen(self) -> None:
        """连接并监听消息。"""
        streams = list(self._streams)
        if not streams:
            return

        url = self._url_builder(streams)
        self._health.status = ConnectionStatus.CONNECTING
        logger.info(f"[{self.name}] connecting to {url[:80]}...")

        async with websockets.connect(
            url,
            ping_interval=self._ping_interval,
            ping_timeout=HEALTH_CHECK_TIMEOUT,
            close_timeout=5,
            max_queue=256,
        ) as ws:
            self._ws = ws
            self._health.status = ConnectionStatus.CONNECTED
            self._health.connected_at = time.monotonic()
            self._health.reconnect_attempts = 0
            logger.info(f"[{self.name}] connected, streams: {len(streams)}")

            # 启动心跳任务
            if self._ping_payload:
                heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                self._tasks.append(heartbeat_task)

            # 接收消息循环
            async for raw in ws:
                if not self._running:
                    break
                self._health.last_message = time.monotonic()
                self._health.total_messages += 1
                try:
                    msg = json.loads(raw)
                    self._on_message(msg)
                except json.JSONDecodeError:
                    logger.debug(f"[{self.name}] non-JSON message: {raw[:100]}")
                except Exception as e:
                    logger.error(f"[{self.name}] message handler error: {e}")

    async def _heartbeat_loop(self) -> None:
        """发送自定义心跳（某些 provider 需要文本 ping 而非 WS 协议 ping）。"""
        while self._running and self._ws:
            try:
                await asyncio.sleep(self._ping_interval)
                if self._ws and self._ws.open:
                    self._health.last_ping = time.monotonic()
                    await self._ws.send(self._ping_payload)
                    logger.debug(f"[{self.name}] heartbeat sent")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[{self.name}] heartbeat error: {e}")
                break

    async def _reconnect(self) -> None:
        """强制重连（用于动态添加 stream）。"""
        if self._ws:
            await self._ws.close()
        # _run 循环会自动重连


class ConnectionPool:
    """WebSocket 连接池，按 provider 维护连接。"""

    def __init__(self) -> None:
        self._connections: dict[str, WSConnection] = {}
        self._subscribers: dict[str, list[Subscription]] = {}  # stream -> subscriptions
        self._provider_builders: dict[str, Callable] = {}

    def register_provider(
        self,
        provider: str,
        url_builder: Callable[[list[str]], str],
        message_router: Callable[[dict[str, Any]], None],
        ping_payload: str | None = None,
    ) -> None:
        """注册一个 WebSocket provider 的连接配置。"""
        self._provider_builders[provider] = {
            "url_builder": url_builder,
            "message_router": message_router,
            "ping_payload": ping_payload,
        }

    async def subscribe(
        self,
        key: str,
        provider: str,
        stream: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """订阅一个 stream。"""
        sub = Subscription(key=key, callback=callback, provider=provider, stream=stream)

        # 记录订阅
        if stream not in self._subscribers:
            self._subscribers[stream] = []
        self._subscribers[stream].append(sub)

        # 获取或创建连接
        if provider not in self._connections:
            config = self._provider_builders.get(provider)
            if not config:
                raise ValueError(f"Provider {provider} not registered")

            conn = WSConnection(
                name=f"{provider}-ws",
                url_builder=config["url_builder"],
                on_message=self._route_message,
                ping_payload=config["ping_payload"],
            )
            self._connections[provider] = conn

        conn = self._connections[provider]
        if conn.health.status == ConnectionStatus.DISCONNECTED:
            await conn.start([stream])
        else:
            await conn.add_streams([stream])

    async def unsubscribe(self, key: str) -> None:
        """取消订阅。"""
        for stream, subs in list(self._subscribers.items()):
            self._subscribers[stream] = [s for s in subs if s.key != key]
            if not self._subscribers[stream]:
                del self._subscribers[stream]
                # 从连接中移除 stream（需要重连）
                # 简化处理：不动态移除，连接保持

    def _route_message(self, msg: dict[str, Any]) -> None:
        """将收到的消息路由到对应的订阅者。"""
        stream = msg.get("stream") or ""
        data = msg.get("data") or msg

        # 尝试匹配订阅者
        subs = self._subscribers.get(stream, [])
        for sub in subs:
            try:
                sub.callback(data)
            except Exception as e:
                logger.error(f"subscriber {sub.key} callback error: {e}")

        # 如果没有精确匹配，尝试所有订阅者（broadcast）
        if not subs:
            for _stream_key, subs_list in self._subscribers.items():
                for sub in subs_list:
                    with suppress(Exception):
                        sub.callback(data)

    def get_health(self) -> dict[str, dict]:
        """获取所有连接的健康状态。"""
        result = {}
        for name, conn in self._connections.items():
            h = conn.health
            result[name] = {
                "status": h.status.value,
                "is_healthy": conn.is_healthy,
                "streams": len(conn._streams),
                "messages": h.total_messages,
                "errors": h.total_errors,
                "reconnects": h.reconnect_attempts,
                "uptime": time.monotonic() - h.connected_at if h.connected_at else 0,
            }
        return result

    async def close_all(self) -> None:
        """关闭所有连接。"""
        for conn in self._connections.values():
            await conn.stop()
        self._connections.clear()
        self._subscribers.clear()


# 全局连接池单例
_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close_all()
        _pool = None
