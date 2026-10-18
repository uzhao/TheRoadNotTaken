---
id: 15
title: "故障处理"
labels: [wayfinder:grilling]
parent: 1
blocked_by: [12]
assignee: Jianyang Zhao
status: open
---

## Question

[agy print 模式实测](./002-agy-print-mode.md) 给出了失败形态：exit 3 加 `AGY_ERROR`（含 `retryable`，如 429 配额）、硬超时、`SUCCESS` 但无 `structured_output`、权限被拒的 `denied_actions`、搬运校验失败。针对讲义生成、追问、验证出题、评分、申诉、提议起草各流程，需要定下：

- 哪些失败自动重试、重试几次、是否换模型（如 Claude 配额耗尽时退到 Gemini）；哪些直接报错。
- 失败时界面显示什么、学习者能做什么（重试、换模型、放弃）；状态是否回滚（如评分失败时验证记录如何写）。
- 超时后已流出的部分讲义正文是否保留给学习者看。
- agy 不可用（未登录、网络断）时应用的启动行为与降级：缓存讲义可读、验证不可做。
- 任务目录与 `agy.ndjson` 的保留期限与清理。
