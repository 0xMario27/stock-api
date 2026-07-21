# stock-api-py

`stock-api` 的 Python 重构版本，采用前后端分离架构。

- 后端：Python 3.11+ / FastAPI / async httpx / uv 包管理
- 前端：Vue 3 + Vite + TypeScript + Element Plus + Pinia + ECharts + Lightweight Charts
- 部署：Docker + docker-compose（开发环境 uvicorn / 生产环境 gunicorn 多 worker）
- 股票数据源：腾讯 / 新浪 / 东方财富 / Yahoo Finance（自动兜底）
- 加密货币数据源：CoinGecko / Binance（自动兜底）
- 实时推送：Binance WebSocket（加密货币实时行情，前端自动订阅）
- 统一抽象层：DataProvider + ProviderRegistry，按 AssetClass 分组路由

## 目录结构

```
stock-api-py/
├── backend/              # Python FastAPI 后端
│   ├── src/stock_api/
│   │   ├── core/             # 模型 / 异常 / Provider 抽象 / 注册表
│   │   ├── providers/        # 腾讯 / 新浪 / 东方财富 / Yahoo / CoinGecko / Binance
│   │   ├── realtime/         # WebSocket 连接池 / Binance WS / 实时推送端点
│   │   ├── market/           # 代码映射 / K 线工具
│   │   ├── utils/            # 异步 HTTP / 编码
│   │   ├── api/              # FastAPI 路由
│   │   ├── cli.py            # CLI
│   │   └── mcp_server.py     # MCP server (JSON-RPC over stdio)
│   ├── tests/
│   ├── Dockerfile
│   └── gunicorn_conf.py      # 生产环境 gunicorn 配置
├── frontend/             # Vue 3 前端
│   ├── src/
│   │   ├── api/              # axios 封装
│   │   ├── components/       # MarketBadge 共享组件
│   │   ├── stores/           # Pinia（自选 / Dashboard / 实时推送状态）
│   │   ├── types/            # TypeScript 类型
│   │   ├── utils/            # realtime.ts / tvChart.ts / indicators.ts
│   │   └── views/            # Dashboard / 自选 / 详情 / 诊断
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml        # 开发环境
├── docker-compose.prod.yml   # 生产环境（端口 8002，gunicorn）
└── .env.example              # 生产环境配置模板
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

开发环境（端口 8080）：
```shell
docker compose up -d --build
```

生产环境（端口 8002，gunicorn 多 worker）：
```shell
# 可选：创建 .env 调整配置
cp .env.example .env

# 构建并启动
make docker-prod
# 或手动：
docker compose -f docker-compose.prod.yml up -d --build
```

- 前端面板：http://localhost:8002
- API 文档：http://localhost:8002/api/docs

#### 生产环境配置说明

通过 `.env` 文件或环境变量调整：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `GUNICORN_WORKERS` | 3 | gunicorn worker 进程数，建议 `CPU核心数 * 2 + 1` |
| `LOG_LEVEL` | info | 日志级别：debug / info / warning / error |
| `PROD_PORT` | 8002 | 对外暴露的端口 |

获取服务器 CPU 核心数：

```shell
nproc          # Linux
sysctl -n hw.ncpu   # macOS
```

根据 CPU 核心数设置 worker：

| CPU 核心数 | 建议 GUNICORN_WORKERS |
| --- | --- |
| 1 | 2 |
| 2 | 3 |
| 4 | 5 |
| 8 | 9 |

示例 `.env` 文件：
```shell
# 2 核服务器
GUNICORN_WORKERS=3
LOG_LEVEL=info
PROD_PORT=8002
```

## 支持功能

所有接口均支持 `asset_class=stock|crypto` 参数切换资产类别。

| 能力 | API | CLI | MCP |
| --- | --- | --- | --- |
| 单只行情 | `GET /api/quote/{code}` | `get-stock` | `get_stock` |
| 批量行情 | `GET /api/quotes?codes=` | `get-stocks` | `get_stocks` |
| K 线 | `GET /api/klines/{code}` | `get-klines` | `get_klines` |
| 搜索 | `GET /api/search?q=` | `search` | `search_stocks` |
| 诊断 | `GET /api/inspect/{code}` | `inspect` | `inspect_stock` |
| 实时推送 | `WS /ws/realtime` | - | - |

### 市场类型

| 代码前缀 | 市场 | 示例 |
| --- | --- | --- |
| `SH` / `SZ` | A 股 | SH510500, SZ000651 |
| `HK` | 港股 | HK02020 |
| `US` | 美股 | USAAPL |
| `FUT` | 期指 | FUTIF2406 |
| `COM` | 商品 | COMXAU |
| `OPT` | 期权 | OPT10000125 |
| coin ID | 加密货币 | bitcoin, ethereum |

加密货币使用 CoinGecko coin ID，可通过搜索接口查询。

### 前端页面

| 页面 | 功能 |
| --- | --- |
| Dashboard | 可调整大小的卡片网格，含走势图 / 涨跌统计 / 成交量 / 市值 / PE/PB |
| 自选列表 | 股票 / 加密货币切换，搜索添加，30s 自动刷新，实时推送 |
| 详情页 | K 线图（TradingView Lightweight Charts），8 种技术指标，分时 / 日 / 周 / 月 K |
| 诊断 | 跨数据源对比，自动兜底链可视化 |

支持深色 / 浅色 / 跟随系统主题切换，A 股涨跌色 / 国际涨跌色切换。

## 数据源抽象

核心抽象在 `backend/src/stock_api/core/`：

- `AssetClass` 枚举：`STOCK` / `CRYPTO`
- `DataProvider` 抽象基类：声明 `asset_class`、`supported_markets`、统一异步接口
- `ProviderRegistry`：按 `asset_class` 分组注册，`get_auto(asset_class)` 返回跨源兜底的 `AutoProvider`

### 已支持数据源

| 资产类别 | 数据源 | auto 兜底顺序 | 支持市场 |
| --- | --- | --- | --- |
| 股票 (stock) | 腾讯 / 新浪 / 东方财富 / Yahoo Finance | tencent -> sina -> eastmoney -> yahoo | A股 / 港股 / 美股 / 指数 / 基金 / 期指 / 期权 / 商品 |
| 加密货币 (crypto) | CoinGecko / Binance | coingecko -> binance | 加密货币 |

行情字段包括：现价 / 开盘 / 最高 / 最低 / 昨收 / 涨跌幅 / 成交量 / 成交额 / 市盈率 / 市净率 / 总市值 / 流通市值 / 52周高低（各数据源按可用性填充）。

### 扩展新数据源

1. 新增 `providers/xxx.py`，继承 `DataProvider`，设置 `asset_class` 和 `supported_markets`
2. 在 `core/registry.py` 的 `create_default_registry()` 注册
3. 前端 / API / MCP 无需改动，auto 路由自动生效

### 实时推送

- 后端：`realtime/manager.py`（连接池 / 自动重连）+ `realtime/binance_ws.py`（Binance WS 订阅）+ `realtime/server.py`（FastAPI WS 端点）
- 前端：`utils/realtime.ts`（RealtimeClient，自动重连 + 心跳），加密货币自选列表和详情页自动订阅
- 动态订阅：使用 Binance SUBSCRIBE 方法添加新币种，无需重连

## 免责声明

使用第三方公开行情接口，不保证数据准确性、完整性、实时性或持续可用性。不提供投资建议。

## License

MIT
