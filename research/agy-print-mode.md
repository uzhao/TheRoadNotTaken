# agy print 模式实测

> 关联工单：[agy print 模式实测](../issues/002-agy-print-mode.md)  
> 术语约定：遵循 [GLOSSARY.md](../GLOSSARY.md)（主题、讲义、插图、追问、验证）。

> 实测日期：2026-10-18。环境：Ubuntu（Linux 7.0.0-38-generic, x86_64），agy **1.4.2**（`~/.local/bin/agy`，日志前缀为内部名 `jetski`，环境变量前缀 `ANTIGRAVITY_*`），Python 3.14.4，matplotlib 3.10.7。所有数字来自三轮脚本的实际输出（`~/agy-test-{1,2,3}.log`，保存在作者本机），单次测量，只用于数量级判断。命令由 agent 设计、作者在本机 shell 执行并回贴输出（沙箱终端的 PATH 里没有 `agy`）。

---

## 一、结论速览

| 问题 | 结论 |
| :--- | :--- |
| 命令行形态 | Go 风格 flag：`-p` / `--print` 的**下一个词就是 prompt**，必须写成 `--print='…'`，其它参数放在它前面；`-p --output-format json '…'` 会把 `--output-format` 当 prompt 并报错 |
| 最小延迟 | 短 prompt 端到端 **6–8 s**（其中模型侧 `duration_seconds` ≈ 4.4 s，其余是进程启动与鉴权） |
| 讲义规模延迟 | 1500 字无插图：默认模型 71 s、Gemini 3.8 Flash 51 s；800 字 + 一张 matplotlib 插图：88 s，**首个正文字出现在 72 s**；续接会话重画一张图：**379 s** |
| 会话续接 | 稳定。`conversation_id` 在 json 的顶层 / stream-json 的 `init` 事件里；`--conversation <id>` 续接 6 s、答案正确；`--continue` 只接"最近一条"，并发下接错 |
| 流式 | `--output-format stream-json` 的 `step_update` 在 `agent_response` 步上带 `text_delta`（几字到几十字一片）；工具调用只有 ACTIVE/DONE 两条；思考不流出 |
| 常驻进程 | `--input-format stream-json` 存在（changelog 有记载），但输入消息必须带 `event` 字段，`user_input` / `message` / `prompt` 均"unsupported"，**正确事件名未找到，未打通** |
| 结构化输出 | `--json-schema` 可用，结果在 `structured_output`；但会**混入 `toolAction`/`toolSummary` 两个 schema 外字段**；schema 不可满足时 `status` 仍为 `SUCCESS`、只是没有 `structured_output`，并且模型会循环尝试（本例 4 轮、87 s） |
| 并发 | 3 个进程同时跑，各 6 s，互不拖慢 |
| 权限 | print 模式遇到需确认的工具**不挂起、自动拒绝、exit 0**，stderr 一行 `jetski: … auto-denied`，json 的 `denied_actions` 列出；`--mode accept-edits` 不覆盖命令执行；`--mode auto` 本账号不可用；正规做法是 settings 的 `permissions.allow` 规则（`command(<target>)`、`read_url(<target>)`），或 `--dangerously-skip-permissions` |
| 沙箱 | **`--sandbox` 与 `--add-dir` 都不限制文件写入**：主目录、`/tmp`、工作区外目录全部可写；`--sandbox` 只挡了 Python 的 DNS 解析，`curl` 照通。"只碰数据目录"必须靠 agy 之外的手段 |
| 退出码 | 成功、权限拒绝、超时都是 **0**；模型/配额错误 **3**，stderr 一行 `AGY_ERROR: {…, "retryable": true}` |
| `--print-timeout` | 到期返回 `status: SUCCESS`、空 `response`、`duration_seconds: 0`，stderr 一行提示；文本模式没有部分正文。**不可当作可靠信号**，后端自己管超时 |
| `--disable-slash-commands` | 不加时 `/help` 在 print 模式会被展开成命令；加了之后 `/help` 被当普通 prompt |
| 模型 | 默认 **Gemini 4 Argon (High)**；可选 Gemini 3.8 Flash、Claude Opus/Sonnet 5.5、GPT-OSS 120B，各带 low/medium/high 后缀；Claude Sonnet 本次撞到个人配额（429, 1 h 后重置） |

---

## 二、命令行与输出格式

### 1. flag 解析

```
agy --output-format json --print='只回复两个字母：OK'       # 正确
agy -p --output-format json '只回复两个字母：OK'            # 错：-p 吞掉了 --output-format
```

错误信息原文："-p took "--output-format" as its prompt, so the intended prompt was left as an argument and ignored. Attach the prompt to the flag (-p='your prompt') and move --output-format elsewhere on the command line."

### 2. `--output-format json`

单个 JSON 对象写到 stdout：

```json
{"conversation_id":"1aa983e4-…","status":"SUCCESS","response":"OK\n",
 "duration_seconds":4.35,"num_turns":1,
 "usage":{"input_tokens":12803,"output_tokens":34,"thinking_tokens":29,"cache_read_tokens":0,"total_tokens":12837}}
```

- 带 `--json-schema` 时多出 `structured_output`（已解析对象）与 `json_schema`（原样回显）。
- 有工具被拒绝时多出 `denied_actions: [{"action":"command","display_name":"RunCommand"}]`。
- 出错时 `status: "ERROR"`、`error: "…"`；changelog 第 198 条说明 json 错误输出会带上部分 response。
- 每个全新会话的 `input_tokens` 约 **12.8k**（系统提示 + 工具定义），续接轮次会出现 `cache_read_tokens`。

### 3. `--output-format stream-json`

NDJSON，每行一个事件，三种 `event`：

| event | 字段 | 说明 |
| :--- | :--- | :--- |
| `init` | `conversation_id`、`init.cwd`、`init.tools[]`（60 个工具名）、`init.permission_mode`（默认 `request-review`） | 首行，约 2.3 s 后出现；**会话 id 从这里拿** |
| `step_update` | `step_update.step_index`、`state`（`ACTIVE`/`DONE`）、`step_type`（`user_input` / `agent_response` / `tool`） | `agent_response` 的 ACTIVE 事件带 `text_delta`；DONE 事件带最后一片 `text_delta` + `duration_seconds` + `usage`。`tool` 的 ACTIVE 带 `tool_name` 与 `tool_info.parameters`（如 `run_command` 的 `CommandLine`、`Cwd`、`BypassSandbox`），DONE 带 `duration_seconds`，**不带工具输出** |
| `result` | 与 json 模式的对象相同（全文 `response`、`usage` 等） | 末行 |

实测细节：

- 一次 800 字讲义 + 插图共 259 行事件：1 `init`、1 `user_input`、6 条 `tool`、250 条 `agent_response`、1 `result`。
- 工具调用之前的 `agent_response` 步只有一条 DONE 事件、没有 `text_delta`（那一步只产生了思考与工具调用）；正文从第 7 步才开始流出。
- `text_delta` 片段大小从 1 个汉字到约 30 字不等，间隔 0–0.5 s。
- **非 JSON 行会混在输出里**：权限被拒时的 `jetski: no output produced …` 提示与事件流在同一个管道里（本次 `2>&1` 合并，未区分 stdout/stderr）。后端解析必须逐行 try/except。
- `--json-schema` 对 stream-json 仅作用于最终 `result`（help 原文）。

### 4. 退出码与错误行

| 情形 | exit | 输出 |
| :--- | :--- | :--- |
| 正常 | 0 | — |
| 工具权限被拒 | 0 | stderr `jetski: no output produced — a tool required the "command" permission that headless mode cannot prompt for, so it was auto-denied. Add an allow-rule under permissions.allow in settings.json (e.g. command(<target>)). Alternatively, re-run with --dangerously-skip-permissions …` |
| `--print-timeout` 到期 | 0 | stderr `[agy] print timeout after 8s with turn in progress; returning partial output`；json `status: SUCCESS, response: ""` |
| 模型 / 配额错误 | 3 | stderr `error: Individual quota reached …` 与 `AGY_ERROR: {"short_error":"RESOURCE_EXHAUSTED (code 429): …","status":"RESOURCE_EXHAUSTED","error_code":429,"code_kind":"http","retryable":true,"error_id":"…"}` |
| stream-json 输入格式错 | 1 | `error: stream input message is missing the "event" field` + `result` 事件 `status: ERROR` |

changelog 第 435 条明确：headless 退出码"只反映 cascade 级失败"，工具错误与权限拒绝不算。

---

## 三、延迟

| 任务 | 模型 | 墙钟 | 模型侧 duration | 输出 | 备注 |
| :--- | :--- | ---: | ---: | ---: | :--- |
| 回复 "OK"（文本模式） | 默认 | 7.9 s | — | 2 字 | 冷启动 |
| 回复 "OK"（json） | 默认 | 7.2 s | 4.35 s | 2 字 | 启动开销 ≈ 3 s |
| `--conversation` 续接回复 "OK" | 默认 | 6.3 s | — | 2 字 | |
| 并发 3 × 回复数字 | 默认 | 5.9 / 6.0 / 6.2 s | — | | 无互相拖慢 |
| 300 字论证 `--effort=low` | 默认 | 11.4 s | — | 1445 B | |
| 300 字论证 `--effort=high` | 默认 | 19.4 s | — | 1487 B | effort 影响时间不影响长度 |
| 2 道验证题 + `--json-schema` | 默认 | 24.4 s | 22.0 s | | |
| 1500 字讲义，无插图（json） | Gemini 4 Argon High（默认） | 71.1 s | 67.7 s | 5569 字符 / 5888 out tok | |
| 1500 字讲义，无插图（json） | Gemini 3.8 Flash Medium | 50.8 s | 48.3 s | 4703 字符 | |
| 1500 字讲义，无插图（json） | Claude Sonnet 5.5 Medium | 3.0 s | — | — | 429 配额错误，exit 3 |
| 800 字讲义 + 1 张 matplotlib 插图（stream-json） | 默认 | 87.6 s | — | 2315 字符 | 首事件 2.3 s；三轮画图脚本各 1–2 s 执行、每轮前 14–15 s 思考；**首个正文 delta 72.5 s** |
| 续接上一会话，把切点改到 x=0.5 重画 | 默认 | 378.6 s | — | 7943 out tok、2 turns | 单次观察，但说明 agent 式画图时间无上界 |
| 画一张 y=x² SVG（`--dangerously-skip-permissions`） | 默认 | 15.3 s | — | 17 KB SVG | |

对 v1 的含义：

- 讲义主体文字只能靠流式降低体感等待；插图在 agy 内部迭代时前端什么都看不到，需要有"正在画图"的步事件展示（`tool` 步的 ACTIVE 事件可用）。
- 后端必须有**自己的硬超时**（例如 5–10 分钟）并能杀进程，不能依赖 `--print-timeout`。
- 验证评分、出题这类短任务 20–30 s 可接受。

---

## 四、会话

- **id 来源**：json 顶层 `conversation_id`；stream-json 的 `init` 事件（第一行，2 s 后即可拿到，可在生成完成前先写入主题 ↔ 会话映射）。
- **`--conversation <id>`**：跨进程续接成功，6.3 s；续接讲义会话后再要求改图也成功（`num_turns: 2`，`cache_read_tokens: 82074`）。
- **`--continue`**：只接"最近一条会话"，实测接到了另一个测试的会话，并且模型自述看到了"工具执行被取消 / server restart"的系统通知。**后端不要用它**。
- 会话状态不在本机：`~/.agy`、`~/.config/agy`、`~/.local/share/agy` 均不存在；日志显示密钥在 `~/.config/antigravity/plugin-secrets.json`，共享配置在 `~/.gemini/config/config.json`。会话很可能保存在服务端，**离线不可续接**（未直接测试断网）。
- `--project` / `--new-project`：日志显示 print 模式会话落在名为 "CLI Project" 的项目下；未测试按项目隔离会话。

---

## 五、权限、沙箱与数据目录

### 1. 四种组合实测（任务：在 `data/` 用 matplotlib 画 y=x² 存 SVG）

| 参数 | 结果 |
| :--- | :--- |
| 无 | 13 s 后自动拒绝 `command` 权限，无文件，exit 0 |
| `--mode accept-edits` | 同上（只放行文件编辑，不放行命令） |
| `--mode auto` | `warning: --mode auto is not available for this account; continuing in the default mode.`，同上 |
| `--dangerously-skip-permissions` | 15 s 成功，`data/x2.svg` 17 KB，回复了绝对路径 |

### 2. 允许规则

日志里 CLI 启动时打印了当前生效的规则集合，格式为 `permissions={Allow:[command(ps) command(grep) … command(go test -v *) …] Deny:[] Ask:[]}`，即 `command(<可执行名或带通配的命令前缀>)`；被拒提示还给出了 `read_url(<target>)` 的例子。规则来自 settings.json（具体路径本次未定位；候选是 `~/.config/antigravity/` 下或 `~/.gemini/`，`~/.claude/settings.json` 是另一个产品的）。changelog 提到旧的 `unsandboxed` 规则已弃用、应迁移为 `command` 规则，并且 URL 读取默认改为"先询问"。

对 v1 的含义：生产上应给后端专用的 settings 配 `permissions.allow: [command(python3), command(python3 *)]` 之类的最小集，而不是 `--dangerously-skip-permissions`；两者都需要在原型阶段验证 `python3 - <<EOF` 这种 heredoc 形式能否被 `command(python3)` 匹配。

### 3. `--sandbox` 与 `--add-dir` 的边界

| 场景 | 结果 |
| :--- | :--- |
| `--sandbox --dangerously-skip-permissions`，cwd = 工作区：写 `data/`、`outside/`、`/tmp/` | **三处全部成功** |
| cwd = `/tmp`，`--sandbox --add-dir <data>`：写 `data/` 与工作区外的 `outside/` | **两处都成功** |
| `--sandbox` 下 `cat /etc/hostname`、`ls ~`、`touch ~/x` | 全部成功（`touch` 出来的文件权限为 666） |
| `--sandbox` 下 `curl -sI https://example.com` | 成功（HTTP 200） |
| `--sandbox` 下 Python `socket.gethostbyname` | 失败：`Temporary failure in name resolution` |
| 工具参数 | `run_command` 带 `BypassSandbox:false` 字段，说明 agent 可以请求绕过 |

结论：**agy 的沙箱是"终端限制"（部分网络），不是文件系统边界**；`--add-dir` 只是把目录加进工作区上下文。要把 agy 限制在数据目录，只能靠外部手段：

1. 以单独的 Unix 用户运行 agy、只给数据目录写权限；
2. 或 bubblewrap / firejail / 容器挂载只读根 + 读写数据目录；
3. 或接受 agy 能碰整个主目录，用 git 管理数据目录 + 写前备份 + schema 校验兜底（[数据目录与状态归属](../issues/005-data-ownership.md) 需要决定）。

### 4. 其它

- `--disable-slash-commands`：不加时 `--print='/help'` 直接输出命令列表（说明 print 模式会展开 slash 命令和 skill）；加了之后 `/help` 被当普通文本，模型还试图调用 `read_url`。后端传入学习者输入时应加此参数。
- `list_permissions` 工具在工具列表里，但模型报告"当前环境中没有 list_permissions 工具"，可能对 print 模式不可见。

---

## 六、结构化输出

- schema 以字符串或文件路径传入 `--json-schema=schema.json`。
- 成功示例：嵌套 object/array、`minItems`/`maxItems`、`required` 都被遵守，`structured_output` 是解析好的对象。
- **污染字段**：`structured_output` 内多出 `"toolAction": "Submitting generated derivative questions"` 与 `"toolSummary": "…"`，说明结构化输出通过一个 `finish` 工具实现，这两个是工具元数据。后端解析时必须忽略未知键，**不要**在 schema 里写 `additionalProperties: false` 期待严格匹配（本次不可满足 schema 的测试里写了也未生效）。
- **不可满足的 schema**（`minimum: 1000, maximum: 1`）：模型反复尝试 4 轮、87 s、2.9k 输出 token，最终 `status: SUCCESS`、无 `structured_output` 键、`response` 里是模型的解释文字。后端判断成功的条件应是"`structured_output` 存在且通过本地校验"，而非 `status`。

---

## 七、常驻进程（未打通）

- help 原文：`--input-format stream-json reads one NDJSON message per line from stdin and runs a turn for each; it requires --output-format stream-json`。changelog 第 487 条：「reads newline-delimited JSON prompts from stdin and runs one turn per message in a single conversation, so a driver can keep a session open」。
- 实测：缺 `event` 字段报错退出（exit 1）；`event` 为 `user_input`、`message`、`prompt` 时均 `warning: ignoring unsupported stream input message event "…"` 后静默结束。**正确的事件名未找到**，官方文档未在本机找到。
- 影响评估：每请求起一个进程的固定开销约 3 s（json 模式 7.2 s 墙钟 − 4.35 s 模型侧），`--conversation` 续接 6 s。相对讲义生成的 1–6 分钟，这个开销可以接受；**v1 不依赖常驻进程**，把它留作优化项。若后续要打通，下一步是枚举 `user_message` / `turn` / `input` 等事件名，或在交互模式下抓包 Remote Control 的消息格式。

---

## 八、对后续工单的含义

- [数据目录与状态归属](../issues/005-data-ownership.md)：agy 自身不提供目录隔离，读写边界要靠 OS 用户 / 容器或"信任 + git 备份"来定；会话 id 需后端在 `init` 事件到达时立即持久化。
- [插图方案选型](../issues/006-figure-choice.md)：agy 执行 Python 画 SVG 可行且质量可用（matplotlib SVG 17–50 KB），但一张图可能触发多轮重试、耗时从 15 s 到 6 分钟不等；需要"正在画图"状态与硬超时。
- [技术栈](../issues/009-tech-stack.md)：每请求一个 `agy --output-format stream-json --conversation <id>` 子进程 + 逐行解析 NDJSON + SSE 转发 `text_delta`，即可满足流式；不需要常驻进程。需要容忍非 JSON 行、`SUCCESS` 但空输出、exit 3 的 `AGY_ERROR`。
- 新的雾区：模型选择与配额（默认 Gemini 4 Argon，Claude 系列有个人配额）；`permissions.allow` 的文件位置与命令匹配语义。

---

## 附录：复现脚本要点

三轮脚本的完整内容见本次会话记录；关键命令形态：

```bash
# json 与会话 id
agy --output-format json --print='…'
agy --conversation "$ID" --output-format json --print='…'
# 流式 + 放行工具
agy --output-format stream-json --dangerously-skip-permissions --print='…'
# 结构化输出
agy --output-format json --json-schema=schema.json --print='…'
# 常驻进程（尚未找到正确的 event 名）
printf '%s\n' '{"event":"?","…":"…"}' | agy --input-format stream-json --output-format stream-json
```
