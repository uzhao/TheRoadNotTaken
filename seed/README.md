# seed — 种子骨架

随仓库分发的种子骨架（`skeleton.yaml`）放在这里；首次启动时复制到数据目录，此后数据目录副本为权威（见规格 [017](../issues/017-spec-v1.md) 的「骨架」一节）。

- 骨架校验脚本（`uv run --project backend theroadnottaken-skeleton <yaml> [-p]`，见根 README）与样例骨架（`backend/tests/fixtures/sample-skeleton.yaml`）由工单 [019](../issues/019-skeleton-validator.md) 交付。
- 209 主题的正式种子骨架由工单 [020](../issues/020-seed-skeleton.md) 交付：生成工具 `theroadnottaken-seed` 与输入在 `gen/`，流程见下。

## 生成流程（工单 020）

输入是调研报告 [research/curriculum-references.md](../research/curriculum-references.md) 的 22 领域 209 主题清单；生成按领域逐个进行，由作者在本机用真实 `agy` 跑、在编辑器里审。命令都带 `uv run --project backend` 前缀，下面省略。

```
gen/input.yaml        extract 从调研报告提取：领域（kind、order、上游领域、历史素材来源）与主题清单（名称、概念提示）
gen/fields/<领域>.yaml 每领域一份骨架片段（可单独校验、可手改），run 生成、cross 补跨领域前置
gen/work/<领域>/      prompt、schema 与 agy 原始输出（git 忽略）
skeleton.yaml         merge 把全部片段拼成的种子骨架
```

1. **提取输入**（已提交，改了调研报告才需重跑）：`theroadnottaken-seed extract`。测试会检查提交的 `gen/input.yaml` 与当前调研报告一致。
2. **领域内一轮**：对每个领域 `theroadnottaken-seed run c01`（`--effort high`，`--` 之后的参数原样传给 agy）。它用 `--json-schema` 让 agy 产出每个主题的稳定 id、名称与别名、3–5 个概念、领域内直接前置与历史动机索引；本地检查序号对齐、id 前缀、不含跨领域 id，再用 019 的校验跑片段并打印该领域的前置清单；校验通过的片段才进 `gen/fields/`，没通过的留在 `gen/work/<领域>/fragment.yaml` 供手改。片段已存在时不覆盖，重生成加 `--force`。agy 以 `gen/work/<领域>/` 为工作目录运行。
   - 不想让工具调 agy 时，`theroadnottaken-seed prompt c01` 只写出 prompt 与 schema 并打印等价命令行。
   - 审核：在编辑器里改 `gen/fields/c01.yaml`，然后 `theroadnottaken-skeleton seed/gen/fields/c01.yaml -p` 复核。
3. **跨领域一轮**：所有领域的片段都有了之后，对每个领域 `theroadnottaken-seed cross c02`。候选前置缺省限于课程体系中该领域的上游领域（`input.yaml` 的 `upstream`，来自调研报告的领域前置图）——这是工具为了让 prompt 聚焦、避免乱连而加的约束，不是规格要求；要让某领域直接引用别的领域（如 b07 直接引用 c14 的主题），用 `--upstream c14,c04,b02` 指定候选，或在片段里手加。agy 只为确实需要的主题补 0–3 条跨领域直接前置；工具保留领域内前置、替换全部旧的跨领域前置（包括手加的）并写回片段，作者注释保留，然后打印带领域标注的前置清单。主干领域的候选会过滤掉分支领域。
4. **合并**：`theroadnottaken-seed merge -p` 把片段按主干→分支、`order` 顺序拼成 `seed/skeleton.yaml`，跑 019 的全部校验（无环、所有主题从初始前沿可达、主干主题的前置只能是主干、概念 3–5 个等）并输出每领域前置清单。片段缺失或片段里混入别的领域的主题时不写出；某领域的主题数与输入清单不一致时提醒一下（审核时拆分或合并主题是允许的）；校验失败仍写出以便定位，但不要提交失败的骨架。
5. **提交**：`seed/skeleton.yaml`（`version: 1`）与审定的 `gen/fields/*.yaml` 一起提交。测试 `test_seed_skeleton_when_present_passes_validation_with_22_fields` 会守住它。

agy 调用形态与故障处理按规格「agent 调用」一节：`--output-format json --json-schema=<schema> --disable-slash-commands --effort=<effort> --print=<prompt>`，自备硬超时（`--timeout`，缺省 600 秒）；退出码 3 时带出 stderr 的 `AGY_ERROR:` 行；`status` 为 SUCCESS 但无 `structured_output` 视为失败并打印模型的解释。prompt 模板是带版本号的文件：`backend/src/theroadnottaken/prompts/seed-field.v1.md`、`seed-cross.v1.md`；结构化输出的 pydantic 模型与导出的 JSON schema 在 `backend/src/theroadnottaken/seedgen.py`。
