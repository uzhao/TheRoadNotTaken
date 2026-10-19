---
id: 19
title: "骨架校验脚本与样例骨架"
labels: [ready-for-agent]
parent: 17
blocked_by: [18]
assignee:
status: closed
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

作者能对一份骨架 YAML 运行独立的校验命令，得到通过或带定位的错误列表，以及每个领域的 markdown 前置清单，供逐领域审核使用。骨架的数据结构按规格定义（`version`、`fields`、`topics`、`retired`；主题字段 id/name/field/concepts/prerequisites/history/references/aliases）。随票交付一份 6 个主题左右、含主干与分支、含跨领域前置的样例骨架，后续票的测试都用它。

## Acceptance criteria

- [x] 校验规则全部实现：id 唯一且与退役 id 不重复、前置存在、无环、每主题属于已定义领域、主干主题的前置只能是主干、除初始前沿外每主题至少一条入边、所有主题从初始前沿可达、概念 3–5 个、`version` 为正整数
- [x] 每条规则各有一个最小违规用例，断言错误信息包含主题或领域 id
- [x] 命令行输出每领域的 markdown 前置清单（主题名 → 直接前置名）
- [x] 样例骨架通过校验并提交到仓库

## Resolution

校验脚本是后端包里的独立命令 `theroadnottaken-skeleton PATH [-p|--prerequisites]`（模块 `backend/src/theroadnottaken/skeleton.py`，也可 `python -m theroadnottaken.skeleton`），用 ruamel.yaml 读入以保留行号；后续工单的启动校验直接复用 `load_skeleton` / `validate`。退出码 0 通过、1 校验失败、2 文件无法读取或解析。README 写明用法。

- **错误定位**：每条错误形如 `第 N 行 主题 <id>：…` 或 `领域 <id>：…`；结构错误（缺字段、类型不对）与规则错误一次全部列出，不在第一条就停。
- **规则**（每条各有最小违规用例，`backend/tests/test_skeleton_cli.py` 按命令行方式断言退出码与错误里的 id）：`version` 正整数；主题 id 唯一且不与退役 id 重复；前置存在（指向退役主题时额外列出其后继）；领域已定义；主干主题的前置只能是主干；无环（按学习顺序列出整条环）；概念 3–5 个；除初始前沿外每主题至少一条有效入边；所有主题从初始前沿可达。
- **初始前沿**按规格取「前置为空的主题」。在此定义下后两条连通性规则只会在前置缺失或成环时被触发，于是脚本把它们实现为"后果"提示并去重：一个主题的前置全部无效时报"没有有效入边"；环上的主题只在环的错误里出现，环或缺失前置下游的主题才报"从初始前沿不可达"，让作者一眼看到哪些主题被上游问题挡住。
- **前置清单**：`-p` 输出每领域一节 markdown（主干在前、按 `order`），每行 `主题名 ← 直接前置名；…`，跨领域前置附领域 id，初始前沿标 `（初始前沿）`；校验失败时也照样输出并把缺失的前置标为 `（不存在）`，供生成阶段审核只含领域内前置的片段。
- **样例骨架**：`backend/tests/fixtures/sample-skeleton.yaml`，7 个主题、3 个主干领域 + 1 个分支领域，含领域内链、主干→主干与分支→主干的跨领域前置、一个 `aliases`、一条退役记录；通过校验。conftest 提供 `sample_skeleton` 夹具供后续工单使用。

未做、留给后续工单：应用启动时的校验与拒绝启动（021）；种子骨架复制到数据目录（021）；正式 209 主题种子骨架（020）。
