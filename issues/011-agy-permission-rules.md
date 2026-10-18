---
id: 11
title: "agy 权限规则配置实测"
labels: [wayfinder:research]
parent: 1
blocked_by: []
assignee: Jianyang Zhao
status: closed
---

## Question

[agy print 模式实测](./002-agy-print-mode.md) 表明 print 模式下需要权限的工具会被自动拒绝，放行只能靠 settings 的 `permissions.allow` 规则或 `--dangerously-skip-permissions`。后端以生成任务目录为 cwd 调用 agy 时（见 [ADR-0001](../docs/adr/0001-agent-writes-content-not-state.md)），应该用哪种放行方式？需要实测并记录：

- `permissions.allow` 规则所在的 settings 文件路径（候选 `~/.config/antigravity/` 或 `~/.gemini/`；日志显示共享配置在 `~/.gemini/config/config.json`），以及是否支持按项目/工作目录的配置文件（日志有 `ApplyProjectPermissionGrants`）。
- `command(python3)` 能否匹配 agy 实际使用的调用形式（`python3 -c "..."`、`python3 - <<'EOF'` heredoc、`mkdir -p data && python3 ...` 复合命令）；`write_to_file` / `replace_file_content` 在工作目录内是否需要规则。
- 最小规则集能否让"画一张 matplotlib 插图并写 markdown"全程不被拒绝；与 `--dangerously-skip-permissions` 相比的取舍（后者会放行 `search_web`、`read_url_content`、浏览器工具等）。
- 能否用 `Deny` 规则禁掉网络类工具，使讲义生成完全离线。

注意：需要在作者本机的 shell 中运行 agy，沙箱终端无此命令。

## Resolution

实测记录见 [research/agy-print-mode.md 第九节](../research/agy-print-mode.md#九补充实测权限规则配置2026-10-18工单-011)。结论：

1. **规则文件**：唯一生效的是 `~/.gemini/antigravity-cli/settings.json` 的 `permissions.allow` / `permissions.deny`；`~/.gemini/settings.json`、`~/.gemini/config/config.json` 与项目目录下的任何 settings 文件均不被读取，不存在按工作目录的规则配置。
2. **最小规则集**：`command(python3)`、`command(python3 *)`、`command(mkdir)`、`write_file(*)`。它让 `python3 -c`、heredoc、`mkdir && python3` 复合命令、写文件工具与完整 matplotlib 出图全部通过；规则外的 `curl`、`read_url` 自动拒绝。`write_file` 与 `command` 是两类独立权限。
3. **Deny 优先级最高**：deny 规则在 `--dangerously-skip-permissions` 下仍生效，可用来禁网络类工具；但它是全局配置，会影响作者的交互使用。
4. **v1 采用**：后端不用 `--dangerously-skip-permissions`，依赖上述 allow 规则；启动时校验该文件，缺规则则横幅提示并提供页内确认的"写入规则"；不写 deny（headless 下网络类工具默认已拒）。[故障处理](./015-failure-handling.md) 中 `denied_actions` 的提示指向这条配置。
