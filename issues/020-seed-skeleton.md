---
id: 20
title: "生成 209 主题种子骨架并逐领域审核"
labels: [ready-for-human]
parent: 17
blocked_by: [19]
assignee:
status: open
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

作者在本机用 agy 把 [参考课程体系与历史素材调研](../research/curriculum-references.md) 的 22 领域 209 主题清单变成正式的种子骨架：按领域逐个用 `--json-schema` 产出主题 id（稳定 slug，前缀为领域编号）、概念提纲（3–5 个）、领域内直接前置、历史动机索引，再跑一遍产出跨领域直接前置；每个领域跑校验脚本、作者在编辑器审 YAML 与前置清单；合并为一份通过校验的种子骨架提交到仓库。本票需要真实 agy 与人工审核，agent 负责准备 prompt、schema、拼装与校验脚本。

## Acceptance criteria

- [ ] 22 个领域、约 209 个主题全部入库，`kind` 正确标注主干/分支
- [ ] 每个主题有稳定 slug id、3–5 个概念、直接前置、`history` 索引；主干主题不依赖分支
- [ ] 整份骨架通过 019 的校验，前置图无环、所有主题从初始前沿可达
- [ ] 作者对每个领域的前置清单逐一确认过
- [ ] 种子骨架 `version: 1` 提交到仓库的种子骨架目录
