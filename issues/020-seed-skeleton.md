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

## Comments

**agent 侧已交付（prompt、schema、拼装与校验脚本），剩下的是作者在本机用真实 agy 跑并审核：**

- 命令 `theroadnottaken-seed`（`backend/src/theroadnottaken/seedgen.py`）：`extract` 从调研报告提取生成输入 `seed/gen/input.yaml`（已提交，22 领域 209 主题、领域间直接先修关系、历史素材来源，测试守住它与调研报告一致）；`run FIELD` 调 agy（`--json-schema`，pydantic 模型导出 schema、忽略 `toolAction` 等外字段）产出主题 id / 名称与别名 / 概念 / 领域内前置 / 历史索引，本地检查后写成可单独校验、可手改的片段 `seed/gen/fields/FIELD.yaml` 并用 019 的校验打印前置清单；`cross FIELD` 再调一次 agy 补跨领域直接前置（候选限于课程体系的直接先修领域，重跑只替换跨领域边、保留作者注释）；`merge -p` 拼成 `seed/skeleton.yaml` 并跑全部校验。`prompt FIELD` 只写 prompt 与 schema 供手动运行。
- prompt 模板带版本号：`backend/src/theroadnottaken/prompts/seed-field.v1.md`、`seed-cross.v1.md`。
- 测试按命令行缝，agy 走 `PATH` 上的假 agy（`backend/tests/test_seedgen_cli.py`，含 exit 3 / 无 `structured_output` / schema 违规 / 序号与前缀错误 / 跨领域 id 混入等故障用例）。`test_seed_skeleton_when_present_passes_validation_with_22_fields` 在 `seed/skeleton.yaml` 出现后生效。
- 作者步骤见 [seed/README.md](../seed/README.md)「生成流程」：对 22 个领域各跑一次 `run`、审片段，再各跑一次 `cross`、审前置清单，最后 `merge -p`，把 `seed/skeleton.yaml` 与 `seed/gen/fields/*.yaml` 一起提交，然后按验收条件勾选并关闭本票。
