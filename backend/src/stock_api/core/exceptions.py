"""自定义异常类型。

对齐原 TS 版 errors.ts：StockApiError 为基类，下设 Code / Request / Parse 三类。
额外新增 ProviderError / ProviderNotFoundError 用于注册表与 auto 路由。
"""

from __future__ import annotations


class StockApiError(Exception):
    """所有 stock-api 异常的基类。"""


class StockCodeError(StockApiError):
    """统一代码格式错误。"""


class StockRequestError(StockApiError):
    """请求失败或超时。"""


class StockParseError(StockApiError):
    """解析数据源返回失败。"""


class ProviderError(StockApiError):
    """Provider 内部错误。"""


class ProviderNotFoundError(StockApiError):
    """请求的数据源未注册。"""
