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

`GET /api/health` 返回 `{"name", "version", "data_dir"}`，可用来确认后端在跑、代理是否生效。知识网的只读视图：`GET /api/fields`（领域、进度计数与已掌握总数）、`GET /api/topics?field=<领域id>`（主题、状态、不可学与缺失前置；不带 `field` 返回全部）。学习页：`POST /api/lectures/<主题id>`（开始学习：未学 / 暂不学 → 学习中；有缓存直接返回讲义，否则返回讲义任务，经 `GET /api/jobs/<任务id>/events` 看流式生成）、`GET /api/lectures/<主题id>`（只读）、`GET /api/lectures/<主题id>/figures/<文件名>`（插图）。

## 数据目录

首次启动时，后端在数据目录里复制种子骨架 `seed/skeleton.yaml`、建立空的 `state.json`、`conversations.json`、`proposals.yaml`，写入忽略 `jobs/` 的 `.gitignore`，`git init` 并提交首个 commit。此后每次启动只补齐缺失的文件，不覆盖已有内容，也不把学习者未提交的手改顺手提交；数据目录里的骨架副本是权威，手改骨架 = 改文件后重启。

每次启动都校验骨架与状态文件：不合法则进程以非零退出并在 stderr 打印定位（骨架如 `第 23 行 主题 c02-derivative-definition：前置 c02-nope 不存在`，状态文件如 `state.json: c02-derivative-definition.status: …`）。

## 骨架校验脚本

生成与审核骨架时，对一份骨架 YAML（完整骨架或单个领域的片段）独立运行校验：

```sh
uv run --project backend theroadnottaken-skeleton seed/skeleton.yaml      # 通过，或带行号与 id 的错误列表
uv run --project backend theroadnottaken-skeleton seed/skeleton.yaml -p   # 另输出每领域的 markdown 前置清单
```

退出码 0 通过、1 校验失败、2 文件无法读取或解析。校验规则与骨架结构见规格「骨架」一节；`-p` 在校验失败时也输出清单，缺失的前置会标出，方便逐领域审核片段。样例骨架在 `backend/tests/fixtures/sample-skeleton.yaml`。

种子骨架的生成工具 `theroadnottaken-seed`（`extract` / `prompt` / `run` / `cross` / `merge`）配合作者本机的真实 agy 逐领域生成并审核 209 个主题，流程见 [seed/README.md](./seed/README.md)：

```sh
uv run --project backend theroadnottaken-seed run c01        # 调 agy 生成一个领域的片段并校验
uv run --project backend theroadnottaken-seed cross c02      # 为一个领域补跨领域前置
uv run --project backend theroadnottaken-seed merge -p       # 拼成 seed/skeleton.yaml 并校验
```

## 测试约定

后端测试只走一条主缝：真实 FastAPI 应用 + 假 agy + 临时数据目录（夹具在 `backend/tests/conftest.py`：`data_dir`、`client`、`static_client`，都以 `sample_skeleton` 给出的样例骨架为种子，并接好 `fake_agy` 与 `agy_settings`）。后续工单的测试都从这些夹具开始，不新增缝；唯一的例外是骨架阶段独立运行的两个命令——骨架校验脚本与种子骨架生成工具——按命令行方式测试（argv 进、stdout / 退出码 / 文件出），后者的 agent 调用走 `PATH` 上的假 `agy`（夹具在 `backend/tests/test_seedgen_cli.py`）。详见规格的 Testing Decisions。

- `fake_agy`：`PATH` 前置的假 `agy`（`backend/tests/fake_agy.py`），按场景回放 stream-json 事件、在 cwd 写文件、模拟各种故障，并记录收到的命令行与 prompt。场景用 `backend/tests/agy_steps.py` 的步骤函数拼：`fake_agy.script(s.run(s.init("conv-1"), s.text("…"), s.result()))`，读回调用用 `fake_agy.calls()`。
- `agy_settings`：代替 `~/.gemini/antigravity-cli/settings.json` 的临时路径，缺省不存在。
- 讲义任务走 `POST /api/lectures/<主题id>`（见 `backend/tests/test_lecture.py`）；尚无 HTTP 入口的任务类型（追问等）暂经 `client.portal.call(client.app.state.jobs.submit, spec)` 提交，事件仍经 SSE 观察；对应路由上线后改走路由。
