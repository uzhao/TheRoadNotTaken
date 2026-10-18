# TheRoadNotTaken

一个由 agent 驱动的交互式数学学习工具。项目语言为中文；术语以 [GLOSSARY.md](./GLOSSARY.md) 为准。

## Agent skills

### Issue tracker

本仓库不用远程 issue tracker，所有 issue 以 markdown 文件存放在 `issues/`（含规格、地图与子工单）。See `docs/agents/issue-tracker.md`.

### Triage labels

使用默认的五个 triage 标签（`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`），写在 issue 文件的 `labels` frontmatter 里。See `docs/agents/triage-labels.md`.

### Domain docs

单上下文（single-context）：仓库根目录一份 `GLOSSARY.md`，ADR 放在 `docs/adr/`。See `docs/agents/domain.md`.
