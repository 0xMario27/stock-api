"""Gunicorn 生产环境配置。

用法: gunicorn -c gunicorn_conf.py stock_api.api.app:create_app --factory
"""

import multiprocessing
import os

# 绑定地址
bind = "0.0.0.0:8000"

# Worker 类型：uvicorn worker 支持 ASGI + WebSocket
worker_class = "uvicorn.workers.UvicornWorker"

# Worker 数量：CPU 核心数 * 2 + 1（gunicorn 推荐公式）
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# 每个 worker 的并发协程数（uvicorn worker 专属）
worker_connections = 1000

# 超时（秒）：行情数据源响应较慢时需要更长超时
timeout = 60

# 优雅关闭超时
graceful_timeout = 30

# Keep-alive 超时（秒）
keepalive = 5

# 预加载应用（节省内存，加快启动）
preload_app = True

# 最大请求数（0 = 不限，生产可设为 10000 防止内存泄漏）
max_requests = 10000
max_requests_jitter = 500

# 日志
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# 进程名
proc_name = "stock-api"

# 允许热重启
daemon = False
