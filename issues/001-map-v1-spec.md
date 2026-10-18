---
id: 1
title: "地图：交互式数学学习工具 v1 规格"
labels: [wayfinder:map]
parent:
blocked_by: []
assignee:
status: open
---

## Destination

一份可交付实现的 **v1 规格书**：单用户、本地运行的网页应用，后端调用 agy print 模式；含架构、数据布局、agy 集成方式、交互流程，以及第一版知识网骨架。

## Notes

- 领域：大学数学自学工具。语言：中文。术语以 [GLOSSARY.md](../GLOSSARY.md) 为准，发现冲突即修正。
- grilling 工单调用 `grilling` + `domain-modeling` 两个 skill；prototype 工单调用 `prototype`；research 工单调用 `research`。
- Tracker 约定见 [issues/README.md](./README.md)。
- 制图时已定的前提：
  - 只给作者本人使用；网页作为交互环境；后端通过 agy print 模式（而非原生 LLM API）生成内容。
  - agy 是**能操作数据的 agent**（非纯生成器），并且要能生成插图（如讲导数时画 $x^2$ 的图像）。
  - 知识网 = 领域 → 主题 → 概念；主题是学习、验证、推荐的单位。范围：主干（数学系本科核心）+ 分支（应用方向，可选）。
  - 骨架持久存储、可手改；学习中产生的主题提议记入提议清单，下次启动前合并进骨架。
  - 学习单元 = 讲义（以历史动机开篇，含例题与插图，缓存复用、可重新生成）+ 追问（与讲义共享 agy 会话）+ 验证。
  - 已掌握的唯一入口是验证（2–3 道简答题，agy 评分，可申诉一次；失败回到学习中并记录薄弱点）。高中数学预设已掌握，大学主题默认未学。
  - 推荐由程序按前置关系确定性计算；声称掌握的前置主题先以验证作为推荐。学习者没有固定目标，学习顺序不按历史时间顺序。

## Decisions so far

<!-- 每张已关闭工单一行 -->

- [参考课程体系与历史素材调研](./004-curriculum-references.md): 归纳 MIT/剑桥 Tripos/普林斯顿/北大复旦课程为 14 个主干领域与 8 个分支领域（209 个 30–60 分钟主题）及前置 DAG；建立《古今数学思想》51 章映射并补齐概率统计、数值、优化、图论与 ML 数学的 20 世纪史料来源；明确结合 Lean Mathlib `undergrad.yaml`（Apache-2.0）与 Metacademy（CC BY-SA 3.0）结构自建骨架（见 [research/curriculum-references.md](../research/curriculum-references.md)）。
- [数学插图方案调研](./003-figure-options.md): 按「谁来渲染」把 14 个候选插图方案分为 agy 产静态文件 / 前端渲染声明式规格 / 浏览器内编译 TeX / 手写 SVG 四类，整理 17 维对比总表与 LLM 正确率一手证据（有执行反馈的 matplotlib、TikZ 远比手写 SVG 可靠，但都需重试机制）；初步建议主方案 matplotlib 静态 SVG、交互备选 JSXGraph 围栏块，不建议 Desmos/GeoGebra/Mafs/手写 SVG 作主方案（见 [research/figure-options.md](../research/figure-options.md)）。
- [agy print 模式实测](./002-agy-print-mode.md): prompt 须写成 `--print='…'`；json 顶层与 stream-json 首行 `init` 给出 `conversation_id`，`--conversation <id>` 续接稳定而 `--continue` 不可用；stream-json 的 `agent_response` 步带 `text_delta` 可流式；短 prompt 6–8 s、讲义 50–90 s、agent 画图无上界且 `--print-timeout` 不可靠；权限拒绝不挂起而是 exit 0 自动拒绝，放行靠 `permissions.allow` 或 `--dangerously-skip-permissions`；`--sandbox`/`--add-dir` 均不限制文件写入；`--json-schema` 可用但输出混入 `toolAction`/`toolSummary` 且失败时仍 `SUCCESS`；常驻 stream-json 输入格式未打通，v1 每请求一个子进程（见 [research/agy-print-mode.md](../research/agy-print-mode.md)）。
- [数据目录与状态归属](./005-data-ownership.md): agent 只写内容（讲义、插图、提议）不写状态，状态由后端经 `--json-schema` 结果落盘；每次 agent 调用以一次性生成任务目录为 cwd、校验后搬入；单一数据目录全文本文件 + 本地 git，`state.json` 单文件、主题 id 为稳定 slug、每主题一个当前会话且重生成换会话、验证独立会话；核心取舍记为 [ADR-0001](../docs/adr/0001-agent-writes-content-not-state.md)。
- [插图方案选型](./006-figure-choice.md): v1 只有静态插图——agent 在生成任务目录用 matplotlib 产出 SVG（例外 PNG），脚本并排保存，后端统一给 `matplotlibrc`（CJK 字体、mathtext）；每讲 0–4 张、≤ 500 KB、中文图注；前端 `<img>` 显示、不执行 agent 代码；失败重试时允许"修图或删引用"；不做交互插图、不做视觉自检；记为 [ADR-0002](../docs/adr/0002-static-figures-no-frontend-code-execution.md)。
- [第一版骨架](./007-first-skeleton.md): v1 全收 22 领域约 209 主题；主题 = 1–2 讲、3–5 概念；YAML 两层（`version`、`fields[id,name,kind,order]`、`topics[id,name,field,concepts,prerequisites,history,references]`），前置为主题级直接边、主干不依赖分支、初始前沿可达；高中数学不建节点；agy 按领域用 `--json-schema` 出初稿 + 校验脚本 + 逐领域人工审；种子骨架进仓库、首启复制到数据目录；实际生成留作规格的第一项实施任务。

## Not yet specified

- **prompt 与会话编排**：讲义（含历史动机）、例题、验证出题、评分、申诉的 prompt；薄弱点如何回流到后续讲解；按主题续接会话的具体方式。
- **推荐排序**：没有目标时，前沿上多个候选主题如何排序（主干优先？解锁最多？领域交替？）；暂不学的主题何时重新推荐。
- **缓存失效**：讲义缓存何时失效；骨架修改后旧缓存怎么处理。
- **故障处理**：agy 调用失败、超时、输出不合 schema 时的行为。
- **模型与配额**：默认 Gemini 4 Argon，Claude 系列有个人配额；讲义、评分各用哪个模型与 effort，撞配额时如何降级。
- **学习历史与复习**：是否对已掌握主题做间隔复验；学习记录如何回看。

## Out of scope

- 多用户、账号、部署。
- PDF 资料导入（主题上仅保留"参考资料"字段以备将来）。
- 原生 LLM API 调用。
- 按目标倒推路径、按历史顺序学习的"路线"：学习者无固定目标，历史只作为讲义中的动机出现。
- 实现本身：本地图只产出规格。
