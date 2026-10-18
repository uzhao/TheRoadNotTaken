---
id: 5
title: "数据目录与状态归属"
labels: [wayfinder:grilling]
parent: 1
blocked_by: [2]
assignee:
status: open
---

## Question

agy 作为能操作数据的 agent，与网页后端共享哪些数据、如何划分读写权？需要定下：

- 数据目录布局与格式：骨架、掌握状态与薄弱点、讲义缓存（含插图资产）、追问会话记录、提议清单。
- 哪些由后端独占写、哪些允许 agy 写；推荐计算读的是哪份状态。
- 如何防止 agy 写坏状态（schema 校验、写前备份、git 管理数据目录等）。
- agy 会话 id 与主题的对应关系存在哪里。
