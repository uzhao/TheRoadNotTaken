# 三条命令：make run（启动）、make dev（开发）、make test（测试）。详见 README.md。

DATA_DIR ?= $(or $(ROAD_DATA_DIR),$(HOME)/.theroadnottaken)
HOST ?= 127.0.0.1
PORT ?= 8000
BACKEND = uv run --project backend theroadnottaken --data-dir "$(DATA_DIR)" --host $(HOST) --port $(PORT)

.PHONY: install run dev test lint build

install:
	uv sync --project backend
	pnpm --dir frontend install

build: install
	pnpm --dir frontend build

## 一条命令启动：构建前端，后端托管构建产物与 API。
run: build
	$(BACKEND)

## 开发：后端在 $(PORT)，Vite dev server 热更新并把 /api 代理到后端。
dev: install
	@trap 'kill 0' EXIT INT TERM; \
	$(BACKEND) & \
	BACKEND_URL=http://$(HOST):$(PORT) pnpm --dir frontend dev

lint: install
	uv run --project backend ruff check backend
	uv run --project backend ruff format --check backend
	pnpm --dir frontend lint

## 测试：ruff + pytest、eslint + vitest。
test: lint
	uv run --project backend pytest backend
	pnpm --dir frontend test
