# 新增数据源指南

本文件说明如何为 stock-api-py 接入新的行情数据源。详细 AI skill 见 `~/.config/opencode/skills/stock-api-add-provider/SKILL.md`。

## 架构概览

```
backend/src/stock_api/
├── core/
│   ├── base.py          # DataProvider 抽象基类（必须实现）
│   ├── models.py        # Quote / Kline / Symbol / Inspection 模型
│   ├── registry.py      # ProviderRegistry + AutoProvider
│   └── exceptions.py    # 异常类型
├── providers/
│   ├── _shared.py       # create_inspection() 辅助函数
│   ├── tencent.py       # 股票数据源示例
│   ├── sina.py
│   ├── eastmoney.py
│   └── crypto/
│       └── coingecko.py # 加密货币数据源示例
├── market/
│   ├── codes.py         # CodeMapper 代码映射
│   └── kline.py         # create_kline() / normalize_kline_options()
└── utils/
    └── http.py          # 异步 HTTP 客户端（httpx）
```

核心设计：
- `DataProvider` 是所有数据源实现的抽象基类（5 个异步方法）
- `ProviderRegistry` 按 `AssetClass`（STOCK / CRYPTO）分组管理
- `AutoProvider` 在同一 asset_class 内做跨源兜底
- API / CLI / MCP 通过 `asset_class` 参数自动路由，无需改路由代码

## 接入步骤

### 1. 确定 asset_class 和 market

```python
from stock_api.core.models import AssetClass, Market

# 股票:
asset_class = AssetClass.STOCK
supported_markets = [Market.CN_A, Market.HK, Market.US]

# 加密货币:
asset_class = AssetClass.CRYPTO
supported_markets = [Market.CRYPTO]
```

### 2. 创建 provider 文件

- 股票：`backend/src/stock_api/providers/{name}.py`
- 加密货币：`backend/src/stock_api/providers/crypto/{name}.py`

### 3. 实现 DataProvider

```python
from stock_api.core.base import DataProvider
from stock_api.core.models import AssetClass, Inspection, Kline, KlineOptions, Market, Quote, Symbol, default_quote
from stock_api.market.kline import create_kline, normalize_kline_options
from stock_api.providers._shared import create_inspection
from stock_api.utils.http import fetch_json


class YourProvider(DataProvider):
    name = "your_provider"
    asset_class = AssetClass.STOCK
    supported_markets = [Market.CN_A]

    async def get_quote(self, code: str) -> Quote:
        quotes = await self.get_quotes([code])
        return quotes[0] if quotes else default_quote(code, self.name)

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        ...

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)
        ...

    async def search_symbols(self, query: str) -> list[Symbol]:
        ...

    async def inspect(self, code: str) -> Inspection:
        return await create_inspection(self.name, code, self.get_quote)
```

### 4. 注册到 registry

编辑 `backend/src/stock_api/core/registry.py` 的 `create_default_registry()`：

```python
registry.register(YourProvider())  # 加入注册表
```

同时更新 `backend/src/stock_api/providers/__init__.py` 导出。

### 5. 更新 source 列表（3 处）

| 位置 | 文件 | 改动 |
|------|------|------|
| MCP | `backend/src/stock_api/mcp_server.py` | `_SOURCE_NAMES` 列表加入 name |
| 前端类型 | `frontend/src/types/index.ts` | `SourceName` 联合类型加入 name |
| 前端下拉框 | `frontend/src/App.vue` + `DetailView.vue` | 加 `<el-option>` |

### 6. 加测试

`backend/tests/unit/providers/your_provider_test.py`

### 7. 验证

```bash
make lint                                    # 代码检查
make cli CMD="get-stock SH510500 --source your_provider"
make cli CMD="inspect SH510500"              # 应显示新数据源
```

## Checklist

- [ ] provider 文件实现 DataProvider（5 个异步方法）
- [ ] `name` / `asset_class` / `supported_markets` 设置
- [ ] `create_default_registry()` 注册
- [ ] `providers/__init__.py` 导出
- [ ] `mcp_server.py` 的 `_SOURCE_NAMES` 更新
- [ ] 前端 `SourceName` 类型和下拉框更新
- [ ] 单元测试
- [ ] `make lint` 通过
- [ ] CLI 实测通过
