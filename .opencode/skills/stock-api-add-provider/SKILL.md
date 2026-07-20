---
name: stock-api-add-provider
description: Add a new market data source (provider) to the stock-api-py project. Use when the user wants to integrate a new stock exchange, crypto exchange, or any financial data API. Covers DataProvider ABC implementation, ProviderRegistry registration, code mapping, testing, and end-to-end verification. Triggers: "add provider", "add data source", "integrate binance/okx/coinbase", "new exchange", "接入新数据源", "新增行情源".
---

# stock-api-add-provider

Add a new market data source to the stock-api-py project by implementing the
`DataProvider` abstract base class and registering it in the `ProviderRegistry`.

## When to use

- User wants to add a new stock/crypto/financial data source
- User mentions a specific exchange or API (Binance, OKX, Coinbase, etc.)
- User says "add provider" / "add data source" / "接入新数据源" / "新增行情源"

## Architecture overview

```
backend/src/stock_api/
├── core/
│   ├── base.py          # DataProvider ABC (must implement)
│   ├── models.py        # Quote / Kline / Symbol / Inspection models
│   ├── registry.py      # ProviderRegistry + AutoProvider + create_default_registry()
│   └── exceptions.py    # StockApiError / StockCodeError / StockRequestError
├── providers/
│   ├── _shared.py       # create_inspection() helper
│   ├── tencent.py       # Stock provider example
│   ├── sina.py          # Stock provider example
│   ├── eastmoney.py     # Stock provider example (non-factory style)
│   └── crypto/
│       └── coingecko.py # Crypto provider example
├── market/
│   ├── codes.py         # CodeMapper for unified code -> API code conversion
│   └── kline.py         # create_kline() / normalize_kline_options()
└── utils/
    └── http.py          # async fetch_bytes / fetch_text / fetch_json (httpx)
```

Key design:
- `DataProvider` is the ABC all providers implement (5 async methods)
- `ProviderRegistry` groups providers by `AssetClass` (STOCK / CRYPTO)
- `AutoProvider` does cross-source fallback within the same asset class
- `asset_class` routes in API/CLI/MCP automatically — no routing code to change

## Steps to add a new provider

### Step 1: Determine asset class and market

```python
from stock_api.core.models import AssetClass, Market

# Stock providers:
asset_class = AssetClass.STOCK
supported_markets = [Market.CN_A, Market.HK, Market.US]

# Crypto providers:
asset_class = AssetClass.CRYPTO
supported_markets = [Market.CRYPTO]
```

### Step 2: Create the provider file

**Stock provider** -> `backend/src/stock_api/providers/{name}.py`
**Crypto provider** -> `backend/src/stock_api/providers/crypto/{name}.py`

### Step 3: Implement DataProvider

```python
from __future__ import annotations
from stock_api.core.base import DataProvider
from stock_api.core.models import AssetClass, Inspection, Kline, KlineOptions, Market, Quote, Symbol, default_quote
from stock_api.market.kline import create_kline, normalize_kline_options
from stock_api.providers._shared import create_inspection
from stock_api.utils.http import fetch_json, fetch_bytes, fetch_text


class YourProvider(DataProvider):
    name = "your_provider"           # unique identifier
    asset_class = AssetClass.STOCK   # or AssetClass.CRYPTO
    supported_markets = [Market.CN_A]

    async def get_quote(self, code: str) -> Quote:
        quotes = await self.get_quotes([code])
        return quotes[0] if quotes else default_quote(code, self.name)

    async def get_quotes(self, codes: list[str]) -> list[Quote]:
        # 1. Convert unified codes to API codes (if needed)
        # 2. Call the data source API
        # 3. Parse response into Quote models
        # 4. Return list[Quote] aligned with input codes order
        ...

    async def get_klines(self, code: str, options: KlineOptions | None = None) -> list[Kline]:
        opts = normalize_kline_options(options)
        # Fetch K-line data and return list[Kline]
        # Use create_kline(date=..., open_price=..., close=..., high=..., low=..., volume=..., source=self.name)
        ...

    async def search_symbols(self, query: str) -> list[Symbol]:
        # Search by keyword, return list[Symbol]
        ...

    async def inspect(self, code: str) -> Inspection:
        return await create_inspection(self.name, code, self.get_quote)
```

### Step 4: Handle code mapping (if needed)

If the data source uses different code formats, create a code mapper in
`backend/src/stock_api/market/codes.py` or inline in the provider.

Unified codes: `SH510500` / `SZ000651` / `HK02020` / `USDJI` (stock) or
coin IDs like `bitcoin` (crypto).

```python
from stock_api.market.codes import CodeMapper, COMMON_SH, COMMON_SZ

mapper = CodeMapper(
    output_prefixes={COMMON_SH: "sh", COMMON_SZ: "sz"},
    format_output=lambda market, value: value.lower(),
)
api_code = mapper.transform("SH510500")  # -> "sh510500"
```

### Step 5: Register in the registry

Edit `backend/src/stock_api/core/registry.py`, in `create_default_registry()`:

```python
def create_default_registry() -> ProviderRegistry:
    from stock_api.providers.your_provider import YourProvider
    ...
    registry = ProviderRegistry()
    registry.register(TencentProvider())
    registry.register(SinaProvider())
    registry.register(EastmoneyProvider())
    registry.register(CoinGeckoProvider())
    registry.register(YourProvider())  # <-- add here
    return registry
```

Also update `backend/src/stock_api/providers/__init__.py` to export it.

### Step 6: Update source lists (3 places)

1. **CLI** `backend/src/stock_api/cli.py` — update `--source` help text
2. **MCP** `backend/src/stock_api/mcp_server.py` — add name to `_SOURCE_NAMES`
3. **Frontend** `frontend/src/types/index.ts` — add to `SourceName` type,
   and add `<el-option>` in `App.vue` / `DetailView.vue` source dropdowns

### Step 7: Add tests

Create `backend/tests/unit/providers/your_provider_test.py`:

```python
import pytest
from stock_api.providers.your_provider import YourProvider

@pytest.mark.asyncio
async def test_get_quote_returns_normalized():
    provider = YourProvider()
    quote = await provider.get_quote("SH510500")
    assert quote.code == "SH510500"
    assert quote.source == "your_provider"
```

### Step 8: Verify end-to-end

```bash
# Lint
cd backend && uv run ruff check src/

# CLI test
uv run stock-api get-stock SH510500 --source your_provider
uv run stock-api inspect SH510500   # should show your_provider in sources

# API test
uv run stock-api serve &
curl "http://localhost:8000/api/quote/SH510500?source=your_provider"
curl "http://localhost:8000/api/sources"  # should list your_provider
kill %1
```

## Reference: DataProvider interface

| Method | Signature | Returns |
|--------|-----------|---------|
| `get_quote` | `(code: str)` | `Quote` |
| `get_quotes` | `(codes: list[str])` | `list[Quote]` |
| `get_klines` | `(code: str, options: KlineOptions \| None)` | `list[Kline]` |
| `search_symbols` | `(query: str)` | `list[Symbol]` |
| `inspect` | `(code: str)` | `Inspection` |

## Reference: Quote model fields

```python
class Quote(BaseModel):
    code: str           # unified code (SH510500 / bitcoin)
    name: str           # security name
    now: float          # current price
    low: float          # day low
    high: float         # day high
    yesterday: float    # previous close
    percent: float      # change pct, 0.01 = 1%
    source: str         # provider name
    asset_class: AssetClass
    market: Market | None
```

## Reference: Kline model fields

```python
class Kline(BaseModel):
    date: str           # "2026-05-22"
    open: float
    close: float
    high: float
    low: float
    volume: float | None
    source: str
```

## Common patterns

### HTTP requests (async httpx)

```python
from stock_api.utils.http import fetch_json, fetch_bytes, fetch_text

# JSON API
data = await fetch_json(url, headers={"Referer": "..."})

# Raw bytes (for GBK/GB2312 encoded responses)
body = await fetch_bytes(url)
text = body.decode("gb18030", errors="replace")
```

### Rate limit handling

The `fetch_bytes` function already handles 429 with exponential backoff
(0.5s, 1s, 2s). No extra code needed unless the API requires special handling.

### Missing/empty data

Return `default_quote(code, self.name)` for missing stocks — do NOT raise.
This matches the original TS behavior and lets `AutoProvider` fall back.

### K-line period mapping

```python
from stock_api.core.models import KlinePeriod

# Map KlinePeriod to your API's period parameter:
period_map = {
    KlinePeriod.DAY: "1d",
    KlinePeriod.WEEK: "1w",
    KlinePeriod.MONTH: "1M",
}
```

### Auto-fallback order

Providers registered first in `create_default_registry()` are tried first
by `AutoProvider`. Place more reliable sources earlier in the list.

## Checklist

- [ ] Provider file created with `DataProvider` implementation
- [ ] All 5 async methods implemented
- [ ] `name`, `asset_class`, `supported_markets` set
- [ ] Registered in `create_default_registry()`
- [ ] Exported from `providers/__init__.py`
- [ ] `_SOURCE_NAMES` updated in `mcp_server.py`
- [ ] `SourceName` type updated in `frontend/src/types/index.ts`
- [ ] Frontend source dropdowns updated (App.vue, DetailView.vue)
- [ ] Unit test added
- [ ] `uv run ruff check src/` passes
- [ ] CLI test: `uv run stock-api get-stock <code> --source <name>`
- [ ] Inspect test: `uv run stock-api inspect <code>` shows new source
