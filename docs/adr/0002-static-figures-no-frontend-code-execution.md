---
status: accepted
---

# 插图是 agent 产出的静态文件，前端不执行任何 agent 生成的代码

讲义里的插图由 agent 在生成任务目录里执行 Python + matplotlib 产出 SVG（例外情形 PNG），讲义以 `![图注](figures/<名>.svg)` 引用，前端用 `<img>` 显示后端提供的静态文件；v1 不做交互插图，也不引入任何在浏览器里渲染 agent 输出规格或代码的库（JSXGraph、function-plot、Desmos、Mermaid 等）。理由见 [数学插图方案调研](../../research/figure-options.md)：有执行反馈的代码路径（matplotlib）是唯一有一手评测数据支撑、同时满足零前端依赖、零前端执行风险、完全离线、缓存即文件的方案；交互方案的 LLM 正确率没有数据，并且会把提示注入升级为浏览器内代码执行。

## Considered Options

- JSXGraph / function-plot 围栏块由前端渲染：可交互，但需要前端插件、渲染失败只在学习者打开讲义时暴露、与"校验只放行目录内文件"的规则冲突。记为将来可选升级，前提是讲义本身已跑顺且确有拖动参数的学习需求。
- Desmos / GeoGebra：需联网或 33 MB 自托管包、许可限制，与本地离线前提冲突。
- agent 手写内联 SVG：LLM 在 SVG 这种低层格式上表现最差，只能画极简示意。

## Consequences

- 要上交互插图必须同时改 prompt 契约、搬运校验与前端，这是有意设置的门槛。
- 插图质量完全取决于 agent 写 matplotlib 代码的能力与后端给的绘图环境（统一的 `matplotlibrc`、CJK 字体）。
- 一张图的生成时间不可预测（实测 15 秒至 6 分钟），因此每份讲义限制插图数量。
