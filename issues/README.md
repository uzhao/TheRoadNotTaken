# issues/ — 本地 markdown issue tracker

本仓库不使用远程 issue tracker，所有 issue 以 markdown 文件存放于此目录。

## 文件约定

- 一个 issue 一个文件：`NNN-<slug>.md`，`NNN` 为三位数字 id，即 issue 的身份。
- 文件以 YAML frontmatter 开头：

```yaml
---
id: 5
title: 数据目录与状态归属
labels: [wayfinder:grilling]
parent: 1          # 父 issue id（地图的子工单指向地图）
blocked_by: [2]    # 阻塞本 issue 的 issue id 列表
assignee:          # 认领人；为空表示未认领
status: open       # open | closed
---
```

- 正文之后，解决时追加 `## Resolution` 段作为"解决评论"，并把 `status` 改为 `closed`。
- 解决过程中产生的资产（调研笔记、原型）放在仓库别处，从 issue 中链接，不贴进正文。

## Wayfinding operations

- **地图**：带 `wayfinder:map` 标签的 issue。
- **子工单**：`parent` 指向地图 id 的 issue。
- **阻塞**：`blocked_by` 字段（本 tracker 无原生阻塞关系，故用此约定）。
- **认领**：开工前先把 `assignee` 填为驾驶地图的开发者。
- **前沿（frontier）**：`status: open`、`assignee` 为空、且 `blocked_by` 中所有 issue 均已 `closed` 的子工单，按 id 升序。
- **调研产出**：写入 `research/<name>.md`，从工单中链接。
