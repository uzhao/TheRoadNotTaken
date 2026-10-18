---
id: 19
title: "骨架校验脚本与样例骨架"
labels: [ready-for-agent]
parent: 17
blocked_by: [18]
assignee:
status: open
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

作者能对一份骨架 YAML 运行独立的校验命令，得到通过或带定位的错误列表，以及每个领域的 markdown 前置清单，供逐领域审核使用。骨架的数据结构按规格定义（`version`、`fields`、`topics`、`retired`；主题字段 id/name/field/concepts/prerequisites/history/references/aliases）。随票交付一份 6 个主题左右、含主干与分支、含跨领域前置的样例骨架，后续票的测试都用它。

## Acceptance criteria

- [ ] 校验规则全部实现：id 唯一且与退役 id 不重复、前置存在、无环、每主题属于已定义领域、主干主题的前置只能是主干、除初始前沿外每主题至少一条入边、所有主题从初始前沿可达、概念 3–5 个、`version` 为正整数
- [ ] 每条规则各有一个最小违规用例，断言错误信息包含主题或领域 id
- [ ] 命令行输出每领域的 markdown 前置清单（主题名 → 直接前置名）
- [ ] 样例骨架通过校验并提交到仓库
