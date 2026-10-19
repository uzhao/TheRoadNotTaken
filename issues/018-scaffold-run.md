---
id: 18
title: "仓库脚手架与一条命令运行"
labels: [ready-for-agent]
parent: 17
blocked_by: []
assignee:
status: closed
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

作者克隆仓库后，用一条命令启动应用，浏览器里能看到带顶栏（品牌、知识网 / 学习 / 验证导航占位）的空壳页面；开发时前端热更新并代理到后端。仓库成为 monorepo：后端（Python + FastAPI + uvicorn，uv 管理）、前端（React + TypeScript + Vite，pnpm）、种子骨架目录。测试基础设施就位：pytest + ruff、vitest + eslint，以及主缝的测试夹具——临时数据目录 + 应用工厂，后续每张票的测试都从它开始（见规格 Testing Decisions）。

## Acceptance criteria

- [x] 一条命令（指定数据目录参数或环境变量）启动后端并托管前端构建产物，`/api/health` 返回版本信息
- [x] 开发模式下 Vite dev server 代理 `/api` 到后端
- [x] pytest 能用临时数据目录启动应用实例并请求 `/api/health`
- [x] ruff、eslint、vitest、pytest 在空项目上全部通过
- [x] README 写明启动、开发、测试三条命令

## Resolution

仓库成为 monorepo：`backend/`（uv 管理的 `theroadnottaken` 包，FastAPI + uvicorn）、`frontend/`（pnpm 管理的 React + TypeScript + Vite）、`seed/`（种子骨架目录占位，内容由 019/020 交付）。根目录 `Makefile` 提供三条命令（`make run` / `make dev` / `make test`），README 写明用法与不用 make 的等价命令。

- **一条命令启动**：`make run DATA_DIR=…` 构建前端后运行 `theroadnottaken --data-dir …`，后端托管 `frontend/dist` 并把非 `/api` 的未知路径回退到 `index.html`；`GET /api/health` 返回 `{"name","version","data_dir"}`。数据目录取 `--data-dir` → 环境变量 `ROAD_DATA_DIR` → 缺省 `~/.theroadnottaken`。
- **开发模式**：`make dev` 起后端并运行 Vite dev server，`/api` 代理到后端（`BACKEND_URL` 可改）。
- **测试基础设施**：`backend/tests/conftest.py` 提供主缝夹具 `data_dir`、`client`、`static_client`（真实应用 + 临时数据目录，经 HTTP 断言）；前端按规格不做组件级单元测试，vitest 配置 `passWithNoTests`，端到端留给 032。
- 空壳页面顶栏含品牌与「知识网 / 学习 / 验证」占位，并显示 `/api/health` 的版本号以便目测代理是否生效（已掌握计数由 021 接上）。

未做、留给后续工单：数据目录的创建与初始化（021）；后端热重载（开发时只要求前端热更新）。
