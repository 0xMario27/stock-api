.PHONY: help install install-dev dev dev-backend dev-frontend build lint lint-fix typecheck check test test-unit docker-build docker-up docker-down docker-logs clean cli mcp

# 默认目标
.DEFAULT_GOAL := help

# 颜色
CYAN  := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

help: ## 显示所有可用命令
	@printf "$(CYAN)stock-api-py Makefile$(RESET)\n"
	@printf "用法: make <target>\n\n"
	@printf "$(GREEN)开发$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / { printf "  $(YELLOW)%-18s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST) | sort

# ============================================================
# 依赖安装
# ============================================================

install: ## 安装后端 + 前端依赖
	cd backend && uv sync
	cd frontend && npm install

install-dev: ## 安装后端开发依赖（含 ruff/pytest/mypy）
	cd backend && uv sync --extra dev
	cd frontend && npm install

# ============================================================
# 开发服务器
# ============================================================

dev-backend: ## 启动后端 FastAPI 开发服务器（热重载）
	cd backend && uv run stock-api serve --reload

dev-frontend: ## 启动前端 Vite 开发服务器
	cd frontend && npm run dev

dev: ## 同时启动前后端开发服务器（后台）
	@printf "$(GREEN)启动后端（端口 8000）...$(RESET)\n"
	@cd backend && uv run stock-api serve --reload &
	@printf "$(GREEN)启动前端（端口 5173）...$(RESET)\n"
	@cd frontend && npm run dev

# ============================================================
# 构建与检查
# ============================================================

build: ## 构建前端生产包
	cd frontend && npm run build

lint: ## 运行代码检查（ruff + vue-tsc）
	cd backend && uv run ruff check src/
	cd frontend && npm run type-check

lint-fix: ## 自动修复 ruff 可修复的问题
	cd backend && uv run ruff check src/ --fix

typecheck: ## TypeScript 类型检查
	cd frontend && npm run type-check

check: ## 完整检查（lint + build）
	cd backend && uv run ruff check src/
	cd frontend && npm run type-check
	cd frontend && npm run build
	@printf "$(GREEN)✓ All checks passed$(RESET)\n"

# ============================================================
# 测试
# ============================================================

test: ## 运行后端单元测试
	cd backend && uv run pytest tests/ -v

test-unit: ## 运行后端单元测试（带覆盖率）
	cd backend && uv run pytest tests/unit/ -v --cov=stock_api

# ============================================================
# Docker
# ============================================================

docker-build: ## 构建 Docker 镜像
	docker compose build

docker-up: ## 启动 Docker 容器（后台）
	docker compose up -d --build
	@printf "$(GREEN)✓ 容器已启动$(RESET)\n"
	@printf "  前端面板: http://localhost:8080\n"
	@printf "  API 文档: http://localhost:8000/docs\n"

docker-down: ## 停止并移除 Docker 容器
	docker compose down

docker-logs: ## 查看容器日志（实时）
	docker compose logs -f

docker-restart: ## 重启 Docker 容器
	docker compose restart

# ============================================================
# CLI 便捷入口
# ============================================================

cli: ## 执行 CLI 命令: make cli CMD="get-stock SH510500"
	cd backend && uv run stock-api $(CMD)

mcp: ## 启动 MCP server（JSON-RPC over stdio）
	cd backend && uv run stock-api mcp

# ============================================================
# 清理
# ============================================================

clean: ## 清理构建产物和缓存
	rm -rf frontend/dist
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)✓ Cleaned$(RESET)\n"
