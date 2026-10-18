---
status: accepted
---

# 技术栈：Python + FastAPI 后端、React + TypeScript 前端、每请求一个 agy 子进程、SSE 推流

v1 是单用户本地网页应用，生成引擎是 `agy -p`。后端用 Python + FastAPI + uvicorn：整条链上唯一必须有 Python 的环节是 agent 画 matplotlib 插图，后端同语言可以直接检查绘图环境、生成 `matplotlibrc`，并用 pydantic 校验骨架与状态；前端是独立的 React + TypeScript + Vite 单页应用，用 `react-markdown` + `remark-math` + `rehype-katex` 在客户端渲染讲义，KaTeX 随前端打包离线使用。每个生成任务启一个 `agy --output-format stream-json` 子进程（cwd 为生成任务目录），后端逐行解析 NDJSON、把 `text_delta` 与工具步状态经 SSE 推给浏览器，其余操作走 JSON REST；不做常驻 agy 进程，不用 WebSocket。数据层没有数据库，只有 [ADR-0001](./0001-agent-writes-content-not-state.md) 定义的纯文本数据目录加本地 git。

## Considered Options

- 常驻 `--input-format stream-json` 进程：实测（[agy print 模式实测](../../research/agy-print-mode.md)）未找到输入事件格式；每请求起进程的固定开销约 3 秒，相对 1–6 分钟的生成任务可忽略。
- WebSocket：数据流单向，SSE 更简单且自带重连。
- 服务端模板 + htmx：知识网图与流式 markdown 仍需客户端 JS，两套范式并存不值得。
- MathJax：覆盖更广但更重更慢；讲义公式是教材级，KaTeX 足够。
- Go / Node 后端：可行，但要为绘图环境检查与 YAML/JSON 校验另起一套工具链。

## Consequences

- 后端必须自备硬超时与进程组清理，因为 agy 的 `--print-timeout` 与退出码都不可靠。
- 换前端框架或后端语言的代价以季度计；知识网可视化库（候选 Cytoscape.js）由主界面原型验证后再定，不在本 ADR 内。
