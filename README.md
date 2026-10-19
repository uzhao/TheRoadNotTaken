# TheRoadNotTaken

一个由 agent 驱动的交互式数学学习工具：维护一张覆盖大学数学的知识网，追踪掌握状态，推荐下一步学什么。术语以 [GLOSSARY.md](./GLOSSARY.md) 为准，规格见 [issues/017](./issues/017-spec-v1.md)。

## 仓库布局

| 目录 | 内容 |
| --- | --- |
| `backend/` | Python + FastAPI + uvicorn 后端，[uv](https://docs.astral.sh/uv/) 管理；包名 `theroadnottaken` |
| `frontend/` | React + TypeScript + Vite 单页应用，[pnpm](https://pnpm.io/) 管理 |
| `seed/` | 随仓库分发的种子骨架 |
| `issues/`、`docs/`、`research/` | 本地 issue tracker、ADR 与 agent 文档、调研笔记 |

前置：Python ≥ 3.12 与 uv、Node ≥ 22 与 pnpm、GNU make。

## 三条命令

```sh
make run DATA_DIR=~/math-data   # 启动：构建前端，后端在 http://127.0.0.1:8000 托管页面与 API
make dev                        # 开发：后端 :8000 + Vite dev server :5173（热更新，/api 代理到后端）
make test                       # 测试：ruff、pytest、eslint、vitest
```

数据目录按以下顺序决定：`--data-dir` / `DATA_DIR` 参数 → 环境变量 `ROAD_DATA_DIR` → 缺省 `~/.theroadnottaken`。

不用 make 时的等价命令：

```sh
pnpm --dir frontend install && pnpm --dir frontend build
uv run --project backend theroadnottaken --data-dir ~/math-data     # 启动
uv run --project backend theroadnottaken & pnpm --dir frontend dev  # 开发
uv run --project backend pytest backend && pnpm --dir frontend test # 测试
```

`GET /api/health` 返回 `{"name", "version", "data_dir"}`，可用来确认后端在跑、代理是否生效。

## 骨架校验脚本

生成与审核骨架时，对一份骨架 YAML（完整骨架或单个领域的片段）独立运行校验：

```sh
uv run --project backend theroadnottaken-skeleton seed/skeleton.yaml      # 通过，或带行号与 id 的错误列表
uv run --project backend theroadnottaken-skeleton seed/skeleton.yaml -p   # 另输出每领域的 markdown 前置清单
```

退出码 0 通过、1 校验失败、2 文件无法读取或解析。校验规则与骨架结构见规格「骨架」一节；`-p` 在校验失败时也输出清单，缺失的前置会标出，方便逐领域审核片段。样例骨架在 `backend/tests/fixtures/sample-skeleton.yaml`。

## 测试约定

后端测试只走一条主缝：真实 FastAPI 应用 + 临时数据目录（夹具在 `backend/tests/conftest.py`：`data_dir`、`client`、`static_client`）。后续工单的测试都从这两个夹具开始，不新增缝；详见规格的 Testing Decisions。
