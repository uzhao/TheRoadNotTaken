---
id: 23
title: "假 agy 夹具与生成任务运行器"
labels: [ready-for-agent]
parent: 17
blocked_by: [21]
assignee:
status: closed
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

后端能在一次性的生成任务目录里启动 agy 子进程、逐行解析 stream-json、把正文增量与工具步状态经 SSE 推给前端，并在 `init` 事件到达时持久化会话 id；硬超时杀进程组、并发上限 2 与排队、取消、原始事件落 `agy.ndjson`。启动时校验 agy 全局 settings 的四条 allow 规则，缺失则顶栏横幅给出 JSON 片段并提供页内确认的「写入规则」。测试侧交付可脚本化的假 agy 可执行文件：按场景文件回放事件、在 cwd 写文件、模拟全部故障形态、记录收到的命令行与 prompt。演示：顶栏「重试连接」触发一个最小任务并在页面看到事件流。

## Acceptance criteria

- [x] 假 agy 能模拟：正常流式、工具步、`init`/`result`、exit 3 + `AGY_ERROR`（可重试与不可重试）、长时间不退出、`SUCCESS` 但无 `structured_output`、`denied_actions`、非 JSON 行、写越界路径或超大文件
- [x] 任务 API：创建任务返回 id，`EventSource` 订阅到按顺序的事件，`init` 到达后会话映射文件已更新
- [x] 命令行约定被断言：`--output-format stream-json`、`--disable-slash-commands`、`--print=` 形式、续接时的 `--conversation`、effort 参数、cwd 为任务目录
- [x] 超时任务的进程组被杀且任务标记失败；第三个任务排队并上报位次；取消删除任务目录且不改状态
- [x] 权限规则缺失时横幅出现，确认后规则被追加到全局 settings 且不覆盖其它键

## Resolution

按 TDD 在主缝（真实 FastAPI 应用 + 假 agy + 临时数据目录）上实现。会话映射沿用 021 的数据目录：`DataDir.set_conversation` 在写锁内原子写 `conversations.json` 并提交 git，`read_conversations` 校验形状（主题 id → 会话 id），启动时与状态文件一起校验；任务目录在 021 已忽略的 `jobs/` 下。

- **agy 调用约定**（`backend/src/theroadnottaken/agy.py`）：`agy --output-format stream-json --disable-slash-commands --effort=<high|medium> [--conversation <id>] --print=<prompt>`，prompt 放最后；逐行解析 `init` / `step_update`（正文增量与工具步）/ `result`，非 JSON 行记日志后忽略；从 stderr 取最后一行 `AGY_ERROR:` JSON。
- **任务运行器**（`jobs.py`）：每任务一个 `jobs/<任务id>/` 作 cwd，原始 stdout 落 `agy.ndjson`、stderr 落 `agy.stderr`；`start_new_session` 起进程，硬超时与取消都 `killpg` 整个进程组；并发上限 2，其余排队并在位次变化时发 `queued{position}`；`init` 到达时若任务绑定主题（`conversation_topic`）立即写会话映射。结果分类：退出码非 0 → `agy_error`（带 `retryable`/`short_error`/`error_id`）或 `exit`；无 `result` → `no_result`；`result.status` 非 `SUCCESS` → `result`；起进程失败 → `spawn`；超时 → `timeout`。`denied_actions` 与 `structured_output` 原样透传到 `done`，按故障矩阵判定留给 030。失败的目录保留；成功的目录默认保留给调用方搬运（024），无产出的任务用 `delete_dir_on_success` 让运行器直接删；取消删目录、不碰状态。任务状态只在内存，应用关闭时取消全部任务。
- **HTTP API**：`POST /api/jobs {"kind":"ping"}`（「重试连接」的最小调用，超时 60 s）、`GET /api/jobs/{id}`、`GET /api/jobs/{id}/events`（SSE，事件 `queued`/`started`/`conversation`/`delta`/`tool`/`done`，带递增 `id`，支持 `Last-Event-ID` 续读，`done` 后流结束）、`DELETE /api/jobs/{id}`（取消；已结束 409）。讲义等任务类型暂无路由，测试经 portal 调 `app.state.jobs.submit`，由后续工单接上路由。
- **权限规则**（`agy_permissions.py`）：启动时读取 `~/.gemini/antigravity-cli/settings.json`，缺规则记警告日志；`GET /api/agy/permissions` 返回缺失规则与 JSON 片段，`POST` 只把缺失项追加到 `permissions.allow` 末尾（文件不存在则新建），其它键不动；文件无法解析时只报告、拒绝写入（409）。`create_app(agy_settings=…)` 可改路径供测试。
- **假 agy**（`backend/tests/fake_agy.py` + `agy_steps.py`，夹具 `fake_agy`）：按场景回放事件，第 n 次调用用第 n 个 run（加锁计数，并发安全）；步骤支持 init、正文、工具步、result 覆盖、非 JSON 行、stderr、`AGY_ERROR`、在 cwd 写文件（不查越界、可指定大小）、sleep、永不退出（可起子进程并记 pid）；按 Go 风格解析 flag（`-p` 吞下一个 flag 时像真 agy 一样报错），记录 argv、cwd、prompt、会话 id、effort。README 测试约定已更新。
- **前端**：顶栏「重试连接」起 ping 任务并经 `EventSource` 在主区逐条列出事件（`done` 后关闭连接，可取消）；权限缺失横幅显示 settings 路径与 JSON 片段，「写入规则」经页内确认后调用写入接口。

留给后续：搬运校验与成功目录删除（024）；重试矩阵、`denied_actions`/缺 `structured_output` 判失败、agent 不可用横幅、失败目录 7 天 / 20 个清理与重启清理（030）。

