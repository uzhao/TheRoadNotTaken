---
id: 18
title: "仓库脚手架与一条命令运行"
labels: [ready-for-agent]
parent: 17
blocked_by: []
assignee:
status: open
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

作者克隆仓库后，用一条命令启动应用，浏览器里能看到带顶栏（品牌、知识网 / 学习 / 验证导航占位）的空壳页面；开发时前端热更新并代理到后端。仓库成为 monorepo：后端（Python + FastAPI + uvicorn，uv 管理）、前端（React + TypeScript + Vite，pnpm）、种子骨架目录。测试基础设施就位：pytest + ruff、vitest + eslint，以及主缝的测试夹具——临时数据目录 + 应用工厂，后续每张票的测试都从它开始（见规格 Testing Decisions）。

## Acceptance criteria

- [ ] 一条命令（指定数据目录参数或环境变量）启动后端并托管前端构建产物，`/api/health` 返回版本信息
- [ ] 开发模式下 Vite dev server 代理 `/api` 到后端
- [ ] pytest 能用临时数据目录启动应用实例并请求 `/api/health`
- [ ] ruff、eslint、vitest、pytest 在空项目上全部通过
- [ ] README 写明启动、开发、测试三条命令
