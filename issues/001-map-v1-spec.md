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
  - 已掌握的唯一入口是验证（5 道单选题，agy 出题、程序判分，可申诉一次；失败回到学习中并记录薄弱点）。原定"2–3 道简答题、agy 评分"在 [主界面原型](./010-ui-prototype.md) 中改为选择题。高中数学预设已掌握，大学主题默认未学。
  - 推荐由程序按前置关系确定性计算；声称掌握的前置主题先以验证作为推荐。学习者没有固定目标，学习顺序不按历史时间顺序。

## Decisions so far

<!-- 每张已关闭工单一行 -->

- [参考课程体系与历史素材调研](./004-curriculum-references.md): 归纳 MIT/剑桥 Tripos/普林斯顿/北大复旦课程为 14 个主干领域与 8 个分支领域（209 个 30–60 分钟主题）及前置 DAG；建立《古今数学思想》51 章映射并补齐概率统计、数值、优化、图论与 ML 数学的 20 世纪史料来源；明确结合 Lean Mathlib `undergrad.yaml`（Apache-2.0）与 Metacademy（CC BY-SA 3.0）结构自建骨架（见 [research/curriculum-references.md](../research/curriculum-references.md)）。
- [数学插图方案调研](./003-figure-options.md): 按「谁来渲染」把 14 个候选插图方案分为 agy 产静态文件 / 前端渲染声明式规格 / 浏览器内编译 TeX / 手写 SVG 四类，整理 17 维对比总表与 LLM 正确率一手证据（有执行反馈的 matplotlib、TikZ 远比手写 SVG 可靠，但都需重试机制）；初步建议主方案 matplotlib 静态 SVG、交互备选 JSXGraph 围栏块，不建议 Desmos/GeoGebra/Mafs/手写 SVG 作主方案（见 [research/figure-options.md](../research/figure-options.md)）。
- [agy print 模式实测](./002-agy-print-mode.md): prompt 须写成 `--print='…'`；json 顶层与 stream-json 首行 `init` 给出 `conversation_id`，`--conversation <id>` 续接稳定而 `--continue` 不可用；stream-json 的 `agent_response` 步带 `text_delta` 可流式；短 prompt 6–8 s、讲义 50–90 s、agent 画图无上界且 `--print-timeout` 不可靠；权限拒绝不挂起而是 exit 0 自动拒绝，放行靠 `permissions.allow` 或 `--dangerously-skip-permissions`；`--sandbox`/`--add-dir` 均不限制文件写入；`--json-schema` 可用但输出混入 `toolAction`/`toolSummary` 且失败时仍 `SUCCESS`；常驻 stream-json 输入格式未打通，v1 每请求一个子进程（见 [research/agy-print-mode.md](../research/agy-print-mode.md)）。
- [数据目录与状态归属](./005-data-ownership.md): agent 只写内容（讲义、插图、提议）不写状态，状态由后端经 `--json-schema` 结果落盘；每次 agent 调用以一次性生成任务目录为 cwd、校验后搬入；单一数据目录全文本文件 + 本地 git，`state.json` 单文件、主题 id 为稳定 slug、每主题一个当前会话且重生成换会话、验证独立会话；核心取舍记为 [ADR-0001](../docs/adr/0001-agent-writes-content-not-state.md)。
- [插图方案选型](./006-figure-choice.md): v1 只有静态插图——agent 在生成任务目录用 matplotlib 产出 SVG（例外 PNG），脚本并排保存，后端统一给 `matplotlibrc`（CJK 字体、mathtext）；每讲 0–4 张、≤ 500 KB、中文图注；前端 `<img>` 显示、不执行 agent 代码；失败重试时允许"修图或删引用"；不做交互插图、不做视觉自检；记为 [ADR-0002](../docs/adr/0002-static-figures-no-frontend-code-execution.md)。
- [第一版骨架](./007-first-skeleton.md): v1 全收 22 领域约 209 主题；主题 = 1–2 讲、3–5 概念；YAML 两层（`version`、`fields[id,name,kind,order]`、`topics[id,name,field,concepts,prerequisites,history,references]`），前置为主题级直接边、主干不依赖分支、初始前沿可达；高中数学不建节点；agy 按领域用 `--json-schema` 出初稿 + 校验脚本 + 逐领域人工审；种子骨架进仓库、首启复制到数据目录；实际生成留作规格的第一项实施任务。
- [提议清单合并流程](./008-proposal-merge.md): agent 的提议经生成任务目录校验后由后端追加（≤ 3 条/次），学习者走表单；合并在启动门槛的"待处理提议"页逐条做，agy 起草改动、学习者确认、007 校验脚本把关、`version` 加一；`split` 后旧主题已掌握则新主题置 `claimed`，退役 id 记入 `retired[]` 永不复用；新增 `remove` 类型；被拒提议只存不回灌。
- [技术栈](./009-tech-stack.md): Python + FastAPI（uv、pydantic、ruamel.yaml）后端，React + TypeScript + Vite（pnpm、react-markdown + KaTeX 离线）前端；长任务经 SSE 推 `text_delta` 与工具步状态，其余 REST；每任务一个 `agy --output-format stream-json` 子进程、硬超时、并发 2、不做常驻；知识网图库候选 Cytoscape.js 待 010 验证；monorepo `backend/ frontend/ skeleton/`，一条命令运行；记为 [ADR-0003](../docs/adr/0003-tech-stack.md)。
- [主界面原型](./010-ui-prototype.md): 选定以 A 为底的合并方案——领域侧栏 + 主题卡片看板为主视图，附只读的按领域分列、自上而下分层的全图（手写 SVG，否决 Cytoscape.js）；推荐只给一张卡；讲义居中、追问固定右侧；验证改为 5 道单选题、程序判分、≥ 4 通过、可申诉一题、评分后可与 agent 讨论（原型见 [research/prototypes/010-ui-prototype.html](../research/prototypes/010-ui-prototype.html)）。
- [prompt 与会话编排](./012-prompt-orchestration.md): 讲义 = agent 最终回复的 markdown（后端落盘为 `lecture.md`，固定节序：历史动机 → 每概念一节 → 例题 → 误区 → 小结），输入由后端拼装（画像、主题定义、前置名、薄弱点、历史索引、插图与提议契约）；追问续接主题会话不重发讲义；验证出题独立会话、`--json-schema` 恰好 5 题含选项解析与绑定概念、后端打乱选项；程序判分"至多错一题"；申诉续接验证会话输出 uphold/overturn/void；验证后对话续接同会话、记入 `followups.jsonl`；薄弱点回流三处；单一默认模型、讲义与出题 high、其余 medium。
- [推荐排序](./013-recommendation-ordering.md): 候选 = 前置全掌握的未学/学习中主题 + 声称掌握主题；确定性字典序取唯一推荐：待验证 > 学习中 > 主干 > 与最近主题同领域 > 后继多 > id；分支领域按领域开关、默认不参与；暂不学的主题在候选耗尽时回归；卡片显示命中规则的一句理由。
- [讲义缓存失效](./014-cache-invalidation.md): 主题定义变化只把讲义标为「过时」并给重新生成按钮，不自动重生成；验证失败给"重读现有讲义 / 针对薄弱点重新生成"两个选择；模板与模型改版不算失效；手动重生成有页内确认、生成期间可看旧版、失败保留旧版；单张插图可在主题会话里改脚本重画而不算失效。
- [故障处理](./015-failure-handling.md): 可重试的 `AGY_ERROR` 自动重试一次、超时不重试、无 `structured_output` 同会话补一次、`denied_actions` 视为配置错误；不自动换模型但可手动一次性覆盖；失败不写任何状态且申诉不消耗次数；超时保留部分正文不缓存；agy 不可用时全局横幅、缓存可读、生成类操作置灰；失败任务目录保留 7 天/20 个；任务可排队与取消。
- [学习历史与复习](./016-learning-history-review.md): 回看放在学习页右侧"历史"页签（验证记录、追问记录、重生成次数）；不做自动间隔复验，保留手动"再验一次"且未通过退回学习中、不级联；统计只保留现有计数；不做事件日志，靠数据目录 git 历史。
- [agy 权限规则配置实测](./011-agy-permission-rules.md): 唯一生效的规则文件是 `~/.gemini/antigravity-cli/settings.json`（无项目级配置）；最小 allow 集 `command(python3)`、`command(python3 *)`、`command(mkdir)`、`write_file(*)` 可跑通整条画图链路，规则外的网络工具在 headless 下自动拒绝；deny 优先于 `--dangerously-skip-permissions`；v1 后端不用 skip 参数、启动时校验并可一键写入规则、不写 deny（见 [research/agy-print-mode.md 第九节](../research/agy-print-mode.md)）。

## Not yet specified

<!-- 雾区已全部升格为工单（012–016）；新的雾随工单解决再补 -->

## Out of scope

- 间隔重复算法与复习排程、学习时长与打卡统计、笔记与导出、全局时间线/事件日志界面（[学习历史与复习](./016-learning-history-review.md) 划出）。
- 多用户、账号、部署。
- PDF 资料导入（主题上仅保留"参考资料"字段以备将来）。
- 原生 LLM API 调用。
- 按目标倒推路径、按历史顺序学习的"路线"：学习者无固定目标，历史只作为讲义中的动机出现。
- 实现本身：本地图只产出规格。
