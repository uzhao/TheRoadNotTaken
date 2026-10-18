---
id: 2
title: "agy print 模式实测"
labels: [wayfinder:research]
parent: 1
blocked_by: []
assignee: Jianyang Zhao
status: open
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
