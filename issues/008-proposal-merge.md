---
id: 8
title: "提议清单合并流程"
labels: [wayfinder:grilling]
parent: 1
blocked_by: [5]
assignee: Jianyang Zhao
status: closed
---

## Question

主题提议从产生到合并进骨架的流程是什么？需要定下：提议由谁写入（agy 在讲义/追问中自动记录，还是学习者手动添加）、提议清单的格式、启动前由 agy 自动合并还是展示修改差异由学习者确认、合并对已有掌握状态与讲义缓存的影响（如拆分/重命名主题）。

## Resolution

经一轮 grilling 定下（无需 ADR）：

1. **写入**：agy 不直接写数据目录的 `proposals.yaml`。讲义与追问的 prompt 要求它把本次提议（≤ 3 条，仅在发现具体问题时：缺前置、主题过大、需要的概念不存在）写到生成任务目录的 `proposals.yaml`，后端校验后追加进正式清单，`source: agent`；学习者通过界面表单提交，`source: learner`。正式清单只有后端一个写者。去重规则：同主题、同 `kind`、文本完全相同的 pending 条目不重复追加。
2. **合并时机**：启动门槛。存在 `pending` 提议时应用先进入"待处理提议"页面，骨架尚未用于推荐；逐条处理或点"稍后"跳过后，后端再加载骨架进入主界面。不做运行期合并。
3. **合并方式**：agy 起草、学习者确认、程序校验。点"起草"让 agy 在独立会话用 `--json-schema` 产出具体骨架改动（新主题条目 / 前置改动 / 拆分后的各条目），界面展示前后差异，学习者可编辑后"应用"或"拒绝"。应用时跑 007 的校验脚本，通过才写 `skeleton.yaml`、`version` 加一、git 提交；不通过则显示错误、提议保持 `pending`。agy 永不自行合并。
4. **各类提议的影响**：
   - `new-topic`：新主题 `unlearned`。
   - `change-prerequisite`：不改任何掌握状态，前沿重算；讲义不动（定义哈希变化的处理留给"缓存失效"雾区）。
   - `rename`：只改 `name`，id、状态、讲义不动。
   - `split`：旧 id 退役、新 id 新建；旧主题 `mastered` → 新主题全部 `claimed`，其它状态 → `unlearned`；旧讲义目录删除（git 留历史），旧薄弱点与验证记录随旧 id 归档。
   - 新增 `remove`：主题退役，状态归档，依赖它的主题改指向其前置（起草时由 agy 给出、学习者确认）。
   - `other`：仅人工处理，无起草按钮。
5. **退役**：`skeleton.yaml` 增加 `retired[]`（`id`、`retired_at`、`successors`、`proposal`），校验脚本保证新 id 不与现役及退役 id 重复；`state.json` 中退役主题的条目移入 `archived` 段。术语「退役」已入词表。
6. **被拒提议**：保留在清单中、不再显示、v1 不回灌到生成 prompt。
