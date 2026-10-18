---
id: 23
title: "假 agy 夹具与生成任务运行器"
labels: [ready-for-agent]
parent: 17
blocked_by: [21]
assignee:
status: open
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

后端能在一次性的生成任务目录里启动 agy 子进程、逐行解析 stream-json、把正文增量与工具步状态经 SSE 推给前端，并在 `init` 事件到达时持久化会话 id；硬超时杀进程组、并发上限 2 与排队、取消、原始事件落 `agy.ndjson`。启动时校验 agy 全局 settings 的四条 allow 规则，缺失则顶栏横幅给出 JSON 片段并提供页内确认的「写入规则」。测试侧交付可脚本化的假 agy 可执行文件：按场景文件回放事件、在 cwd 写文件、模拟全部故障形态、记录收到的命令行与 prompt。演示：顶栏「重试连接」触发一个最小任务并在页面看到事件流。

## Acceptance criteria

- [ ] 假 agy 能模拟：正常流式、工具步、`init`/`result`、exit 3 + `AGY_ERROR`（可重试与不可重试）、长时间不退出、`SUCCESS` 但无 `structured_output`、`denied_actions`、非 JSON 行、写越界路径或超大文件
- [ ] 任务 API：创建任务返回 id，`EventSource` 订阅到按顺序的事件，`init` 到达后会话映射文件已更新
- [ ] 命令行约定被断言：`--output-format stream-json`、`--disable-slash-commands`、`--print=` 形式、续接时的 `--conversation`、effort 参数、cwd 为任务目录
- [ ] 超时任务的进程组被杀且任务标记失败；第三个任务排队并上报位次；取消删除任务目录且不改状态
- [ ] 权限规则缺失时横幅出现，确认后规则被追加到全局 settings 且不覆盖其它键
