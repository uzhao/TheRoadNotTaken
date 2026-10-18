---
id: 5
title: "数据目录与状态归属"
labels: [wayfinder:grilling]
parent: 1
blocked_by: [2]
assignee: Jianyang Zhao
status: closed
---

## Question

agy 作为能操作数据的 agent，与网页后端共享哪些数据、如何划分读写权？需要定下：

- 数据目录布局与格式：骨架、掌握状态与薄弱点、讲义缓存（含插图资产）、追问会话记录、提议清单。
- 哪些由后端独占写、哪些允许 agy 写；推荐计算读的是哪份状态。
- 如何防止 agy 写坏状态（schema 校验、写前备份、git 管理数据目录等）。
- agy 会话 id 与主题的对应关系存在哪里。

## Resolution

经三轮 grilling 定下（核心取舍记为 [ADR-0001](../docs/adr/0001-agent-writes-content-not-state.md)）：

1. **隔离手段**：agy 与后端同一 Unix 用户运行，不做 OS 级隔离（002 已证明 `--sandbox`/`--add-dir` 关不住 agy）；靠写权分界 + 校验 + git 兜底。单独用户 / bubblewrap 记为将来可选。
2. **写权分界**：**状态**（掌握状态、薄弱点、暂不学、声称掌握、验证记录、主题会话映射）只有后端写，agy 的评分结果经 `--json-schema` 结构化输出交给后端；**内容**（讲义、插图、主题提议）允许 agy 写。推荐计算只读后端写的状态。
3. **生成任务目录**：每次 agy 调用（讲义、追问、含插图）都以 `jobs/<任务id>/` 为 cwd；结束后后端校验（`lecture.md` 非空；所有 `![]()` 指向任务目录内 `figures/` 的 svg/png，无绝对路径与 `..`；多余文件丢弃）再搬入正式位置；校验失败在同一主题会话自动重试一次并告知错误，再失败保留任务目录、标记失败、界面可手动重试。
4. **数据目录**：单一可配置根目录，全部为人可读改的文本文件，不用数据库；初始化为本地 git 仓库，后端每次写状态或搬入产出后自动提交，`jobs/` 忽略；状态写入用临时文件 + 原子改名，写前 schema 校验。布局：
   ```
   skeleton.yaml  state.json  conversations.json  proposals.yaml
   lectures/<主题id>/{lecture.md, figures/, meta.json, followups.jsonl}
   jobs/<任务id>/  .git/
   ```
5. **主题 id**：稳定短 slug（如 `c02-derivative-definition`，前缀沿用领域编号），显示名在骨架中可改，id 有了状态或讲义后永不改；拆分即旧 id 退役、新 id 新建。
6. **状态文件**：`state.json` 单文件，键为主题 id，每项含 `status`（词表五态 `unlearned | learning | deferred | claimed | mastered`）、`weak_points[]`（自由文本，由评分输出产生，验证通过后清空）、`verifications[]`（内嵌每次验证：时间、会话 id、是否通过、是否申诉、逐题问答与评分）、`updated_at`。高中数学不入此文件。
7. **主题会话**：`conversations.json` 每主题一个当前会话 id，在 stream-json 首行 `init` 到达时写入；讲义重新生成即开新会话覆盖旧 id；追问始终续接当前会话。**验证每次新开独立会话**、只喂主题定义与薄弱点，其 id 记在验证记录里。
8. **agy 读什么**：后端把主题定义、概念提纲、前置、薄弱点拼进 prompt；agy 可读骨架，不读状态文件。
9. **骨架加载**：只在启动时读入，启动校验 id 唯一、前置存在、无环、领域已定义，失败拒绝启动；手改骨架 = 改文件后重启。
10. **`meta.json`**：生成时间、模型与 effort、主题定义哈希（名称 + 概念提纲 + 前置）、薄弱点快照、重生成次数、生成任务 id；失效策略留在雾区。
11. **追问记录**：后端把每轮问答追加到 `followups.jsonl`（时间、问、答、任务 id）；追问产生的插图经生成任务目录校验后搬入同一 `figures/`，文件名加任务 id 前缀；重生成讲义时保留。
12. **提议清单格式**：`proposals.yaml` 追加式条目：`id`、`created_at`、`source`（`agent | learner`）、`topic`（可空）、`kind`（`new-topic | change-prerequisite | rename | split | other`）、`text`、`status`（`pending | merged | rejected`）。谁写、怎么合并留给 [提议清单合并流程](./008-proposal-merge.md)。

术语新增：数据目录、主题会话、生成任务（见 [GLOSSARY.md](../GLOSSARY.md)）。

## Comments

- [插图方案选型](./006-figure-choice.md) 对第 3 条搬运校验的补充：`figures/` 内除 svg/png 外放行同名 `.py` 生成脚本；SVG 需可被 XML 解析且根元素为 `<svg>`，PNG 需文件头正确；每份讲义插图 0–4 张、追问单次 ≤ 2 张、每张 ≤ 500 KB，超限视为校验失败。
- [提议清单合并流程](./008-proposal-merge.md) 对第 2、12 条的补充：agent 的提议经生成任务目录校验后由后端追加，`proposals.yaml` 实际只有后端写；`kind` 增加 `remove`；`skeleton.yaml` 增加 `retired[]`，`state.json` 增加 `archived` 段。
