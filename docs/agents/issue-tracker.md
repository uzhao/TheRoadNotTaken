# Issue tracker: 本地 Markdown（`issues/`）

本仓库的 issue、规格（spec）与 wayfinder 地图都以 markdown 文件存放在仓库根目录的 `issues/`。文件格式的权威说明是 [`issues/README.md`](../../issues/README.md)；本文件说明各 skill 的操作如何映射到这套约定。

## 文件约定（摘要）

- 一个 issue 一个文件：`issues/NNN-<slug>.md`，`NNN` 为三位数字 id，从已有最大 id 顺延。
- 文件以 YAML frontmatter 开头：`id`、`title`、`labels`、`parent`、`blocked_by`、`assignee`、`status`（`open` | `closed`）。
- triage 状态写在 `labels` 列表里（标签字符串见 `triage-labels.md`）。
- 解决时在正文末尾追加 `## Resolution` 段，并把 `status` 改为 `closed`。评论与讨论追加在文件末尾的 `## Comments` 段。
- 过程中产生的资产（调研笔记、原型）放在仓库别处并从 issue 链接：调研写入 `research/<name>.md`，不要贴进 issue 正文。

## 当 skill 说"发布到 issue tracker"（publish）

新建一个 `issues/NNN-<slug>.md`，填好 frontmatter。

- **规格**（`/to-spec`）：一份规格一个 issue，正文即规格全文，`labels: [ready-for-agent]`。
- **工单**（`/to-tickets`）：一张工单一个文件，按依赖顺序（阻塞者在前）依次编号；`parent` 指向来源规格的 id（若有），`blocked_by` 列出阻塞它的工单 id；默认 `labels: [ready-for-agent]`。不要把多张工单合并成一个文件。

## 当 skill 说"获取相关工单"（fetch）

按 id 或路径读取对应文件。用户通常直接给出 id（如 `004`）或文件路径。

## 当 skill 说"按 tracker 的方式关闭工单"（resolve / close）

追加 `## Resolution` 段，`status` 改为 `closed`。本 tracker 不通过 PR 关闭工作。

## Wayfinding operations

供 `/wayfinder` 使用。

- **地图（Map）**：带 `wayfinder:map` 标签的 issue，正文含 Destination / Notes / Decisions so far / Not yet specified / Out of scope。
- **子工单（Child ticket）**：`parent` 指向地图 id 的 issue，带 `wayfinder:<type>` 标签（`research` / `prototype` / `grilling` / `task`）。地图与子工单只带 `wayfinder:*` 标签，不带 triage 标签。
- **阻塞（Blocking）**：`blocked_by` 字段；当其中所有 id 均为 `closed` 时解除阻塞。
- **前沿（Frontier）**：`status: open`、`assignee` 为空、且已解除阻塞的子工单，按 id 升序，取第一个。
- **认领（Claim）**：开工前把 `assignee` 填上并保存。
- **解决（Resolve）**：在工单末尾追加 `## Resolution`（即答案），`status` 改为 `closed`，然后在地图的 **Decisions so far** 追加一行（要点 + 指向该工单的链接）。
- **调研产出**：写入 `research/<name>.md`，从工单的 Resolution 中链接。
