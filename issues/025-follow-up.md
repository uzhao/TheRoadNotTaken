---
id: 25
title: "追问"
labels: [ready-for-agent]
parent: 17
blocked_by: [24]
assignee:
status: open
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

学习者在学习页右侧面板追问，agent 续接该主题的会话（不重发讲义），回答流式出现；消息由后端包装当前所在节标题、变化了的薄弱点与约束（默认约 300 字、插图最多两张、可写提议）；每轮问答追加到追问记录，追问里的插图加任务 id 前缀搬入同一插图目录。

## Acceptance criteria

- [ ] 追问任务带 `--conversation <当前会话 id>`，prompt 包含前端上报的节标题
- [ ] 回答结束后 `followups.jsonl` 多一条 `kind: lecture` 记录并 git 提交
- [ ] 追问产生的插图通过校验后出现在该主题 `figures/`，文件名带任务 id 前缀，讲义不变
- [ ] 超过两张插图的追问被校验拒绝并走一次重试
- [ ] 面板显示历史问答，刷新页面后仍在
