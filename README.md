# stock-api-py

`stock-api` 的 Python 重构版本，采用前后端分离架构。

- 后端：Python 3.11+ / FastAPI / async httpx / uv 包管理
- 前端：Vue 3 + Vite + TypeScript + Element Plus + Pinia
- 部署：Docker + docker-compose
- 数据源：腾讯 / 新浪 / 东方财富（自动兜底），抽象层为二期加密货币接入预留

## 目录结构

```
stock-api-py/
├── backend/          # Python FastAPI 后端
│   ├── src/stock_api/
│   │   ├── core/         # 模型 / 异常 / Provider 抽象 / 注册表
│   │   ├── providers/    # 腾讯 / 新浪 / 东方财富 / Auto 兜底
│   │   ├── market/       # 代码映射 / K 线工具
│   │   ├── utils/        # 异步 HTTP / 编码
│   │   ├── api/          # FastAPI 路由
│   │   ├── cli.py        # CLI
│   │   └── mcp_server.py # MCP server (JSON-RPC over stdio)
│   └── tests/
├── frontend/         # Vue 3 前端
│   └── src/
│       ├── api/          # axios 封装
│       ├── components/   # 行情卡片 / K 线图
│       ├── stores/       # Pinia
│       ├── types/        # TypeScript 类型
│       └── views/        # 自选 / 详情 / 搜索
├── docker/           # Dockerfile / nginx 配置
└── docker-compose.yml
```

## 快速开始

### 本地开发

后端（uv）：
```shell
cd backend
uv sync
uv run stock-api serve --reload          # 启动 FastAPI
uv run stock-api get-stock SH510500      # CLI
uv run stock-api mcp                     # MCP server
```

前端（npm）：
```shell
cd frontend
npm install
npm run dev
```

### Docker 部署

```shell
docker compose up -d --build
```

- 后端 API：http://localhost:8000
- 前端面板：http://localhost:8080
- API 文档：http://localhost:8000/docs

## 支持功能

| 能力 | API | CLI | MCP |
| --- | --- | --- | --- |
| 单只行情 | `GET /api/quote/{code}` | `get-stock` | `get_stock` |
| 批量行情 | `GET /api/quotes?codes=` | `get-stocks` | `get_stocks` |
| K 线 | `GET /api/klines/{code}` | `get-klines` | `get_klines` |
| 搜索 | `GET /api/search?q=` | `search` | `search_stocks` |
| 诊断 | `GET /api/inspect/{code}` | `inspect` | `inspect_stock` |

## 数据源抽象（为二期 crypto 准备）

核心抽象在 `backend/src/stock_api/core/`：

- `AssetClass` 枚举：`STOCK` / `CRYPTO`
- `DataProvider` 抽象基类：声明 `asset_class`、`supported_markets`、统一异步接口
- `ProviderRegistry`：按 `asset_class` 分组注册，`get_auto(asset_class)` 返回跨源兜底的 `AutoProvider`

二期接入加密货币只需：
1. 新增 `providers/crypto/binance.py`，继承 `DataProvider`，`asset_class = CRYPTO`
2. 在 `providers/__init__.py` 注册
3. 前端 / API 无需改动，auto 路由自动生效

## 免责声明

同原 `stock-api`：使用第三方公开行情接口，不保证数据准确性、完整性、实时性或持续可用性。不提供投资建议。

## License

MIT
