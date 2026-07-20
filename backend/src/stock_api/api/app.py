"""FastAPI 应用工厂。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stock_api.api.routes import router
from stock_api.core.registry import create_default_registry
from stock_api.utils.http import close_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title="stock-api",
        description="A 股 / 港股 / 美股行情查询 API，支持腾讯 / 新浪 / 东方财富自动兜底",
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
    return app
