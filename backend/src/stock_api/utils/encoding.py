"""编码工具。对应原 TS 的 utils/iconv.ts。

Python 原生支持 gb18030，无需额外依赖。
"""

from __future__ import annotations


def normalize_encoding(encoding: str) -> str:
    """gbk / gb2312 归一为 gb18030（兼容更广）。"""
    lower = encoding.lower()
    if lower in ("gbk", "gb2312"):
        return "gb18030"
    return encoding


def decode_bytes(body: bytes, encoding: str) -> str:
    """按编码解码 bytes，失败时回退 utf-8。"""
    normalized = normalize_encoding(encoding)
    try:
        return body.decode(normalized, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
