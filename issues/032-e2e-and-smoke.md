---
id: 32
title: "端到端用例与真实 agy 冒烟脚本"
labels: [ready-for-agent]
parent: 17
blocked_by: [29, 30]
assignee:
status: open
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

Playwright 在真实后端 + 假 agy 上跑两条主路径：推荐 → 开始学习 → 流式讲义出现 → 去验证 → 通过 → 推荐变化；验证未通过 → 两个按钮 → 重读讲义。把 002 与 011 的手动实测整理成可重复运行的冒烟脚本与说明，供在作者机器上对真实 agy 做发布前检查。

## Acceptance criteria

- [ ] 两条端到端用例在 CI 环境可重复通过
- [ ] 冒烟脚本覆盖：短 prompt、json 与 stream-json、`--conversation` 续接、`--json-schema`、最小 allow 规则下的画图、权限拒绝
- [ ] README 的测试章节说明如何运行端到端与冒烟
