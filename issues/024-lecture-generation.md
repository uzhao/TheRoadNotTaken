---
id: 24
title: "讲义生成与学习页"
labels: [ready-for-agent]
parent: 17
blocked_by: [22, 23]
assignee:
status: closed
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

学习者点「开始学习」后进入学习页：讲义正文逐字流式出现，顶部步骤条显示「生成正文 / 画图 xxx（第 n 次尝试）/ 讲义已缓存」，插图位置先是占位框、画好后以 `<img>` 显示；公式用 KaTeX 渲染。生成完成后讲义被校验并搬入正式位置，再次打开秒开。prompt 由后端按规格拼装（画像、主题定义、前置名、薄弱点、历史索引、插图契约、提议规则），模板带版本；每个任务目录放统一的 `matplotlibrc`；`meta.json` 记录全部元数据。底部「我学完了，去验证」（占位）与「稍后再学」。

## Acceptance criteria

- [x] 讲义任务用假 agy 跑通：SSE 文本增量、工具步状态、完成后 `lecture.md`、`figures/`（含 `.py`）、`meta.json` 落盘并 git 提交
- [x] 搬运校验每条规则各有失败用例，失败触发同会话一次重试（prompt 含错误与「修图或删引用」两个出口），再失败任务目录保留、主题仍为学习中
- [x] 缓存命中时不启动 agy；讲义页顶部显示状态与薄弱点
- [x] 插图经静态路由返回，越界路径返回 404；前端不内联 SVG、不渲染原始 HTML
- [x] 主题从未学进入学习中并产生 git 提交；「稍后再学」回到知识网

## Resolution

按 TDD 在主缝（真实 FastAPI 应用 + 假 agy + 临时数据目录）上实现，测试在 `backend/tests/test_lecture.py`。

- **开始学习**（`lecture_api.py`）：`POST /api/lectures/{主题id}`——未学 / 暂不学 → 学习中并提交 git（`actions.start`；已在学、声称掌握、已掌握只打开讲义不改状态）；前置未掌握且需改状态时 409；有缓存直接返回讲义、不启动 agy；否则提交讲义任务，同一主题已有在跑的就返回它。`GET /api/lectures/{主题id}` 只读：主题（状态与薄弱点）、缓存讲义与 `meta`、在跑任务。
- **prompt**（`prompts/lecture.v1.md`、`lecture-fix.v1.md`，`string.Template`）：画像、主题名与领域、概念提纲、已掌握的直接前置名、薄弱点、历史动机索引、插图契约、提议规则、输出格式；插图上限由代码常量代入。effort `high`，硬超时 10 分钟。任务目录在启动前放统一 `matplotlibrc`（`JobSpec.files`）；启动时用 `fc-list` 查 Noto Sans CJK，缺则警告。
- **运行器扩展**（`jobs.py`）：`JobSpec.postprocess` 在 agy 成功后于线程中执行，返回通过（并入 `done`）/ `Retry`（同目录再调一次 agy，发 `retry` 事件）/ `Reject`（失败、目录保留）；`agy.ndjson`、`agy.stderr` 改为追加。工具事件带 `detail`（命令行或目标文件，DONE 沿用 ACTIVE 的），供步骤条显示「画图 xxx」。
- **搬运校验**（`lecture.check`）：回复非空且以一级标题开头；只允许行内图片写法，路径取括号内第一个词（任意标题写法都会被检查）；路径须为 `figures/<名>.svg|png`、非绝对、无 `..`；文件存在且非符号链接；≤ 500 KB；SVG 可解析且根为 `<svg>`、PNG 文件头正确；0–4 张；图注非空。失败在同一会话重试一次，prompt 列错误并给「修好这张图 / 删掉引用并改写」两个出口；再失败 `done.error.kind = validation`，目录保留、状态不动。
- **搬入**（`lecture.install` + `DataDir.replace_dir`）：在暂存目录备好 `lecture.md`、被引用的插图与同名 `.py`、`meta.json`（生成时间、模型、effort、模板版本、定义哈希、薄弱点快照、重生成次数 0、任务 id、会话 id、尝试次数），保留旧的 `followups.jsonl`，在写锁内整目录替换并提交「生成讲义：…」；其余文件（含 `proposals.yaml`）丢弃，任务目录随后删除。`model` 暂记 `null`（= agy 全局默认模型），可配置模型留给 030。
- **插图路由**：`GET /api/lectures/{主题id}/figures/{文件名}` 先找缓存讲义、再找在跑任务目录（画好即可显示），文件名白名单 + resolve 后父目录比对，越界、子目录、符号链接、脚本一律 404；响应带 CSP `sandbox` 与 `nosniff`。
- **前端**：推荐卡与看板卡的「开始学习 / 继续学习」进入学习页（`learn/`）：顶部状态与薄弱点、步骤条（排队 / 生成正文 / 画图 xxx（第 n 次尝试）/ 讲义已缓存）、约 100 ms 节流的流式正文、`react-markdown` + `remark-math` + `rehype-katex`（`throwOnError: false`，不启用 `rehype-raw`），插图先占位、画好或缓存后以 `<img>` 显示，只认 `figures/` 下的文件；失败时列出错误并可重试；底部「我学完了，去验证」（占位，026）与「稍后再学」。

留给后续：追问（025）、去验证（026）、提议摄入（028，现在 `proposals.yaml` 被丢弃）、过时与重新生成（029，`regenerations` 计数）、完整错误面板与重试矩阵、模型配置（030）。
