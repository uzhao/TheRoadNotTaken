---
id: 21
title: "数据目录初始化与知识网看板（只读）"
labels: [ready-for-agent]
parent: 17
blocked_by: [19]
assignee: claude
status: closed
---

## Parent

[规格：交互式数学学习工具 v1](./017-spec-v1.md)

## What to build

学习者首次启动时，应用在数据目录里复制种子骨架、初始化 git 仓库、建立空的状态文件、会话映射与提议清单，并提交首个 commit；此后每次启动读入并校验骨架，不合法则拒绝启动并指出位置。知识网页显示：左侧按主干/分支分组的领域侧栏（名称、已掌握/总数、三色进度条），主区为选中领域的主题卡片网格（名称、概念提纲、状态标签、缺失的前置名），顶栏显示已掌握计数。用样例骨架即可演示。

## Acceptance criteria

- [x] 空目录启动后存在骨架副本、`state.json`（空对象）、`conversations.json`、`proposals.yaml`、`.git` 且 `jobs/` 被忽略
- [x] 已有数据目录再次启动不覆盖任何文件
- [x] 骨架校验失败时进程以非零退出并打印定位
- [x] API 提供领域、主题与状态的只读视图；前端侧栏与看板按规格布局渲染，锁定主题标出缺失前置
- [x] 状态文件读取经 pydantic 校验，非法内容拒绝启动并提示

## Resolution

- **数据目录初始化** `backend/src/theroadnottaken/datadir.py`：`open_data_dir` 在 `create_app` 里同步执行。缺什么补什么——复制种子骨架为 `skeleton.yaml`、写空对象的 `state.json` 与 `conversations.json`、空列表的 `proposals.yaml`、忽略 `jobs/` 的 `.gitignore`；无 `.git` 则 `git init` 并把目录里已有的文件一并纳入首个提交「初始化数据目录」；已有仓库只提交补齐的文件（「补齐数据目录缺失的文件：…」），学习者未提交的手改留在工作树里。已存在的文件一律不碰，再次启动不产生新提交。提交身份用 `-c user.name/user.email` 固定，不依赖机器的 git 配置。种子缺省取 `seed/skeleton.yaml`，`create_app(seed_skeleton=…)` 可换。
- **启动校验**：骨架复用 019 的 `load_skeleton` / `validate`（错误带行号与 id）；状态文件经 pydantic 严格模式（`backend/src/theroadnottaken/state.py`，按规格的条目结构：`status` 五态、`weak_points`、`verifications[]` 含题目 / 判分 / 申诉、`updated_at`；退役条目在 `archived` 段），只做读取，写入留给 022。任一不合法抛 `StartupError`，命令行入口以退出码 1 结束并在 stderr 打印文件与定位。
- **只读 API** `backend/src/theroadnottaken/web.py`：`GET /api/fields` 返回主干在前、按 `order` 排序的领域及已掌握 / 学习中 / 声称掌握计数与总计；`GET /api/topics?field=` 返回主题（名称、概念、前置、状态、薄弱点）与 `locked` / `missing_prerequisites`（未学 / 学习中 / 暂不学的主题有直接前置未掌握即不可学并列出；声称掌握的主题下一步是验证，按规格的候选规则不看前置，不算不可学），未知领域 404。骨架启动时读入一次（不热加载），状态文件每请求读取。
- **前端** `frontend/src/web/`：顶栏显示「已掌握 n / N 个主题」；左侧 `FieldSidebar` 按主干 / 分支分组，每行名称、已掌握/总数与三色进度条；主区 `TopicBoard` 为选中领域的卡片网格（名称、状态标签、概念提纲，不可学的卡变淡并写「前置未掌握：…」）。配色与布局沿用原型方案 D（含深色模式与窄屏布局）。按规格不做组件级单元测试，以真实后端 + Chromium 截图目测。
- **测试**：`backend/tests/test_datadir.py`（空目录初始化、`jobs/` 被忽略、再次启动不覆盖、补齐缺失文件不动手改、无 git 的已有目录、骨架与状态不合法时经命令行入口拒绝启动并定位）、`backend/tests/test_web_api.py`（领域进度、主题状态 / 不可学 / 缺失前置、声称掌握不锁、404）。夹具 `client` / `static_client` 改以样例骨架为种子。

术语表新增「初始前沿」「不可学」。

留给后续工单：状态写入（原子替换 + git 提交）、推荐卡与状态动作（022）、全图（031）。
