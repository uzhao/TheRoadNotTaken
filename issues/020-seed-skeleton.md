---
id: 20
title: "生成 209 主题种子骨架并逐领域审核"
labels: [ready-for-human]
parent: 17
blocked_by: [19]
assignee:
status: closed
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

作者在本机用 agy 把 [参考课程体系与历史素材调研](../research/curriculum-references.md) 的 22 领域 209 主题清单变成正式的种子骨架：按领域逐个用 `--json-schema` 产出主题 id（稳定 slug，前缀为领域编号）、概念提纲（3–5 个）、领域内直接前置、历史动机索引，再跑一遍产出跨领域直接前置；每个领域跑校验脚本、作者在编辑器审 YAML 与前置清单；合并为一份通过校验的种子骨架提交到仓库。本票需要真实 agy 与人工审核，agent 负责准备 prompt、schema、拼装与校验脚本。

## Acceptance criteria

- [x] 22 个领域、约 209 个主题全部入库，`kind` 正确标注主干/分支
- [x] 每个主题有稳定 slug id、3–5 个概念、直接前置、`history` 索引；主干主题不依赖分支
- [x] 整份骨架通过 019 的校验，前置图无环、所有主题从初始前沿可达
- [ ] 作者对每个领域的前置清单逐一确认过
- [x] 种子骨架 `version: 1` 提交到仓库的种子骨架目录

## Comments

**agent 侧已交付（prompt、schema、拼装与校验脚本），剩下的是作者在本机用真实 agy 跑并审核：**

- 命令 `theroadnottaken-seed`（`backend/src/theroadnottaken/seedgen.py`）：`extract` 从调研报告提取生成输入 `seed/gen/input.yaml`（已提交，22 领域 209 主题、领域级前置（上游领域）、历史素材来源，测试守住它与调研报告一致）；`run FIELD` 调 agy（`--json-schema`，pydantic 模型导出 schema、忽略 `toolAction` 等外字段）产出主题 id / 名称与别名 / 概念 / 领域内前置 / 历史索引，本地检查后写成可单独校验、可手改的片段 `seed/gen/fields/FIELD.yaml` 并用 019 的校验打印前置清单；`cross FIELD` 再调一次 agy 补跨领域直接前置（候选缺省限于课程体系的上游领域，`--upstream` 可改；重跑只替换跨领域边、保留作者注释）；`merge -p` 拼成 `seed/skeleton.yaml` 并跑全部校验。`prompt FIELD` 只写 prompt 与 schema 供手动运行。
- prompt 模板带版本号：`backend/src/theroadnottaken/prompts/seed-field.v1.md`、`seed-cross.v1.md`。
- 测试按命令行缝，agy 走 `PATH` 上的假 agy（`backend/tests/test_seedgen_cli.py`，含 exit 3 / 无 `structured_output` / schema 违规 / 序号与前缀错误 / 跨领域 id 混入等故障用例）。`test_seed_skeleton_when_present_passes_validation_with_22_fields` 在 `seed/skeleton.yaml` 出现后生效。
- 术语表缺口：领域之间的前置关系（代码里叫 `upstream`，文档里写「上游领域 / 领域级前置」）尚无术语，留给 `/domain-modeling`。
- 作者步骤见 [seed/README.md](../seed/README.md)「生成流程」：对 22 个领域各跑一次 `run`、审片段，再各跑一次 `cross`、审前置清单，最后 `merge -p`，把 `seed/skeleton.yaml` 与 `seed/gen/fields/*.yaml` 一起提交，然后按验收条件勾选并关闭本票。

**种子骨架第一版已生成并提交（由 Claude 代替 agy 撰写，待作者审核）：** 作者在 cloud 会话里无法运行 agy，于是按作者要求由 Claude 逐领域撰写 209 个主题的 id、名称与别名、概念、领域内前置、历史索引与跨领域前置，再通过同一条流水线（`run` → `cross` → `merge`，agy 换成回放脚本）落盘，所有本地检查与 019 的校验照常生效：`seed/skeleton.yaml` 通过（22 领域、209 主题；初始前沿 4 个：命题逻辑、R^n 欧氏结构、Gauss 消元、概率空间），片段在 `seed/gen/fields/*.yaml`。`cross` 对 c09、c14、b01、b06、b07、b08 用了 `--upstream` 扩大候选领域（分别加 c07+c01、c04、c02、c14、c14、c02+c14）。剩下的验收项「作者对每个领域的前置清单逐一确认过」留给作者：`theroadnottaken-skeleton seed/skeleton.yaml -p` 输出每领域清单，改片段后重新 `merge`，或直接改 `seed/skeleton.yaml`。

## Resolution

种子骨架 v1 已提交：`seed/skeleton.yaml`（`version: 1`，22 个领域、209 个主题）与片段 `seed/gen/fields/*.yaml`，通过 019 的全部校验（无环、全部从初始前沿可达、主干不依赖分支、概念 3–5 个）。内容由 Claude 代替 agy 撰写（见上方评论），作者决定按现状接受这一版，未逐领域审核前置清单（验收项保留未勾以如实记录）；后续发现的缺漏按规格走主题提议与合并流程修正。生成工具 `theroadnottaken-seed` 与流程文档见 [seed/README.md](../seed/README.md)。
