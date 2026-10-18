# Triage Labels

各 skill 用五个规范的 triage 角色来描述 issue 状态。本文件把这些角色映射到本仓库实际使用的标签字符串。

标签写在 issue 文件 frontmatter 的 `labels` 列表里，例如 `labels: [ready-for-agent]`。本仓库使用默认名称，不做改写。

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

当 skill 提到某个角色（如"apply the AFK-ready triage label"）时，使用上表对应的标签字符串。

注意：wayfinder 的地图与子工单只带 `wayfinder:*` 标签（`wayfinder:map`、`wayfinder:research`、`wayfinder:prototype`、`wayfinder:grilling`、`wayfinder:task`），不带 triage 标签。
