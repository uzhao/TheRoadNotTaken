---
id: 6
title: "插图方案选型"
labels: [wayfinder:grilling]
parent: 1
blocked_by: [2, 3]
assignee: Jianyang Zhao
status: closed
---

## Question

v1 的插图采用哪种（或哪几种）形式？基于「agy print 模式实测」中 agy 执行代码与写文件的能力，以及「数学插图方案调研」的对比结论，决定：主方案、是否需要备选方案、插图在讲义中的嵌入与缓存方式、插图出错时的处理。

## Resolution

经两轮 grilling 定下（核心取舍记为 [ADR-0002](../docs/adr/0002-static-figures-no-frontend-code-execution.md)）：

1. **主方案**：agy 在生成任务目录里执行 Python + matplotlib 产出静态文件，讲义用 `![图注](figures/<名>.svg)` 引用，前端只显示文件、不执行任何 agy 生成的代码。
2. **不做备选交互方案**：v1 没有交互插图，不引入 JSXGraph / function-plot / Mermaid；JSXGraph 记为将来可选升级。
3. **格式**：默认 SVG；PNG 仅限 SVG 会膨胀的情形（3D 曲面、密集散点、热力图），由 agy 在 prompt 约束下选择；不允许动画。
4. **脚本并排保存**：`figures/<名>.py` 与 `figures/<名>.svg|png` 同目录，005 的搬运校验放行 `.py`，便于改参数重跑与排错。
5. **绘图环境由后端给**：每个生成任务目录放一份后端统一的 `matplotlibrc`：Noto Sans CJK（后端启动时检查，缺则警告）、`svg.fonttype: none`、固定画布与 dpi、mathtext、不依赖 TeX；prompt 要求 agy 直接使用、不自行改字体。
6. **插图契约**（写进 prompt，并由校验强制）：每份讲义 0–4 张，追问单次 ≤ 2 张；每张 ≤ 500 KB；文件名为语义化英文 slug；`![...]` 说明必须是能独立成立的一句中文（兼作 alt 与图注）；图中标签优先数学记号；坐标轴有标签；白底浅色，不考虑深色模式。
7. **不强制视觉自检**：只要求脚本执行成功、文件存在；"渲染 PNG 后 `view_file` 看图修正"记为将来可按需打开的开关。
8. **失败处理**：校验不过时按 005 在同一主题会话重试一次，重试 prompt 给两个出口——修好这张图，或删掉引用并改写相应段落；再失败整份讲义标记失败。
9. **显示与最小校验**：后端以静态文件路由提供插图，前端 `<img src>` 引用、不内联 SVG；校验增加"SVG 可被 XML 解析且根元素为 `<svg>`、PNG 文件头正确"两条，不引入消毒库。
10. **重新生成**：整体替换 `lecture.md`、`figures/`、`meta.json`，`followups.jsonl` 保留；旧版本不另存，需要时查 git 历史。
