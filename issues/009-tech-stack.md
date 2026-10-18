---
id: 9
title: "技术栈"
labels: [wayfinder:grilling]
parent: 1
blocked_by: [2, 5]
assignee: Jianyang Zhao
status: closed
---

## Question

v1 用什么技术栈？需要定下：前端框架（或原生）、数学公式渲染（KaTeX / MathJax）、markdown 渲染、后端语言与框架、后端如何管理 agy 进程（每次请求起一个 `agy -p`，还是常驻 stream-json 进程）、流式内容如何推给浏览器（SSE / WebSocket）、知识网可视化库。

## Resolution

经两轮 grilling 定下（记为 [ADR-0003](../docs/adr/0003-tech-stack.md)）：

1. **后端**：Python + FastAPI + uvicorn；依赖管理 uv；pydantic 校验状态与 agy 结构化输出，ruamel.yaml 读写骨架（保留注释与顺序）；数据目录 git 操作直接调 `git` 命令行；测试 pytest，lint ruff。
2. **前端**：React + TypeScript + Vite 单页应用，pnpm；`react-markdown` + `remark-math` + `rehype-katex`，不启用 `rehype-raw`（原始 HTML 当文本）；KaTeX 及字体随前端打包、离线，`throwOnError: false`；流式时对累计文本每约 100 ms 节流重渲染；测试 vitest，lint eslint。
3. **流式**：长任务（讲义、追问、验证评分）由后端建任务返回 id，前端 `EventSource` 订阅 `/jobs/<id>/events`，后端把 agy 的 `text_delta` 与工具步状态（"正在画图"）转为 SSE 事件；其余为 JSON REST。不用 WebSocket。
4. **agy 子进程**：每任务 `asyncio.create_subprocess_exec` 启 `agy --output-format stream-json --disable-slash-commands [--conversation <id>] --print=…`，cwd 为生成任务目录；逐行解析 stdout，非 JSON 行记日志；`init` 事件到达即持久化会话 id；硬超时讲义 10 分钟、追问 5 分钟、验证评分 3 分钟，到期杀进程组；并发上限 2、其余排队；任务状态在内存，重启后未完成任务视为失败并清理目录；每任务的原始 NDJSON 落 `agy.ndjson`，成功时随目录删除、失败时保留。不做常驻进程。
5. **知识网可视化**：候选 Cytoscape.js + dagre/elk 布局；是否采用以及是否画图由 [主界面原型](./010-ui-prototype.md) 验证后定。
6. **仓库与运行**：本仓库为 monorepo：`backend/`、`frontend/`、`skeleton/`（种子骨架）。生产形态 `python -m theroadnottaken --data-dir <路径>`，FastAPI 同时托管前端构建产物与 API；开发时 Vite dev server 代理后端。数据目录来自 `--data-dir` 或 `TRNT_DATA_DIR`，缺省 `~/.local/share/theroadnottaken`。
7. **插图静态路由**：`/data/lectures/<主题id>/figures/<文件>`，后端做路径包含检查。

假设：作者机器已有 node、pnpm、uv、git，实施第一步核对版本。
