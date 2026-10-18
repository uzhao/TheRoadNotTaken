---
id: 2
title: "agy print 模式实测"
labels: [wayfinder:research]
parent: 1
blocked_by: []
assignee: Jianyang Zhao
status: closed
---

## Question

作为网页后端的生成引擎，agy print 模式（`agy -p`）的实际能力与限制是什么？需要实测并记录：

- **延迟**：短 prompt / 生成一份长讲义的首 token 时间与总耗时；`--effort`、`--model` 的影响。
- **会话续接**：`--conversation <id>` / `--continue` 在 print 模式下能否稳定续接；会话 id 从哪里拿到（`--output-format json` 的输出里？）。
- **流式**：`--output-format stream-json` 的事件格式（文本增量、工具调用、最终结果各长什么样）。
- **常驻进程**：`--input-format stream-json` 能否让一个进程连续处理多轮，减少启动开销。
- **结构化输出**：`--json-schema` 的可靠性（嵌套 schema、失败时的行为）。
- **并发**：同时跑多个 `agy -p` 进程是否可行。
- **权限与沙箱**：`--sandbox`、`--mode`、`--dangerously-skip-permissions`、`--add-dir` 组合下，agy 能否在指定目录读写文件、执行代码（例如运行 Python 画图）；如何限制它只碰数据目录。
- **非交互约束**：`--disable-slash-commands`、`--print-timeout` 的作用；遇到需要权限确认时 print 模式会怎样。

注意：沙箱终端的 PATH 里找不到 `agy`，实测可能需要在用户 shell 中运行或绕过沙箱。

## Resolution

三轮实测（agy 1.4.2，Ubuntu，命令由 agent 设计、作者本机执行）已整理至 [research/agy-print-mode.md](../research/agy-print-mode.md)，核心结论：

1. **命令行与输出**：Go 风格 flag，prompt 必须写成 `--print='…'`。`--output-format json` 返回单个对象，顶层 `conversation_id`、`status`、`response`、`usage`，带 schema 时多 `structured_output`，有拒绝时多 `denied_actions`。`stream-json` 为 NDJSON，三种事件 `init` / `step_update` / `result`；`agent_response` 步的 ACTIVE 事件带 `text_delta`，可做讲义流式；工具步只有 ACTIVE/DONE，不带输出；非 JSON 提示行会混入，需逐行容错。
2. **延迟**：短 prompt 6–8 s（启动开销约 3 s）；1500 字讲义 51–71 s；800 字 + 一张 matplotlib 插图 88 s，首个正文 delta 出现在 72 s；续接会话重画一张图 379 s。agent 式画图时间无上界，后端需自备硬超时；`--print-timeout` 到期仍 `SUCCESS` + 空 response，不可依赖。
3. **会话**：id 从 json 顶层或 stream-json 首行 `init` 获得；`--conversation <id>` 跨进程续接稳定（6 s）；`--continue` 只接最近一条，并发下接错，不用。会话状态不在本机，推测在服务端。
4. **常驻进程**：`--input-format stream-json` 存在但输入事件名未找到（`user_input` / `message` / `prompt` 均不支持），未打通；v1 用每请求一个子进程即可。
5. **结构化输出**：`--json-schema` 可用，但 `structured_output` 混入 `toolAction` / `toolSummary`；schema 不可满足时 `status` 仍 `SUCCESS`、无 `structured_output`、模型循环尝试 87 s。后端以"`structured_output` 存在且本地校验通过"为准。
6. **并发**：3 进程并行各 6 s，无互相拖慢。
7. **权限与沙箱**：print 模式遇需确认的工具自动拒绝、exit 0、stderr 一行提示；`--mode accept-edits` 不放行命令，`--mode auto` 本账号不可用；放行靠 settings 的 `permissions.allow`（`command(<target>)` 格式）或 `--dangerously-skip-permissions`。**`--sandbox` 与 `--add-dir` 都不限制文件写入**（主目录、`/tmp`、工作区外均可写），`--sandbox` 只挡了 Python DNS；"只碰数据目录"必须靠 OS 用户 / 容器或 git 备份兜底。
8. **退出码**：成功、拒绝、超时均为 0；模型/配额错误为 3，stderr 带 `AGY_ERROR: {…, "retryable": true}`。默认模型 Gemini 4 Argon (High)，Claude Sonnet 5.5 本次撞个人配额。
9. **非交互**：不加 `--disable-slash-commands` 时 `/help` 会被展开，学习者输入应加此参数。
