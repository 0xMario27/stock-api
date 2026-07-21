"""FastAPI 应用工厂。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_api.api.routes import router
from stock_api.core.registry import create_default_registry
from stock_api.realtime.manager import close_pool
from stock_api.realtime.server import ensure_init
from stock_api.realtime.server import router as ws_router
from stock_api.utils.http import close_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_init()
    yield
    await close_pool()
    await close_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title="stock-api",
        description="A股 / 港股 / 美股 / 加密货币行情查询 API + WebSocket 实时推送",
        version="2.7.3",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.registry = create_default_registry()
    app.include_router(router, prefix="/api", tags=["stock"])
    app.include_router(ws_router, tags=["realtime"])
    return app


# 模块级实例，供 gunicorn 直接引用
app = create_app()
