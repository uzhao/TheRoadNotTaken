---
id: 3
title: "数学插图方案调研"
labels: [wayfinder:research]
parent: 1
blocked_by: []
assignee: Jianyang Zhao
status: closed
---

## Question

讲义中的插图（函数图像、几何示意、向量场、概率分布等）由 agy 产出时，有哪些可行形式，各自的优劣？候选至少包括：

- agy 运行代码生成静态图：Python + matplotlib 输出 SVG/PNG。
- agy 输出声明式规格，由前端渲染（可交互）：function-plot、JSXGraph、Plotly、Desmos API、Mafs 等。
- TikZ / PGFPlots 编译为 SVG。
- 内联 SVG 由 agy 直接手写。

比较维度：LLM 生成的正确率、交互性（拖动参数、缩放）、覆盖的图形类型（2D/3D、几何构造、动画）、渲染与依赖成本、能否嵌入 markdown 讲义并缓存。

## Resolution

完整调研报告已整理至 [research/figure-options.md](../research/figure-options.md)，核心结论如下：

1. **候选方案按「谁来渲染」分四类**：(a) agy 执行代码产出静态文件（matplotlib、TikZ/PGFPlots 本地编译、Asymptote、Manim）；(b) agy 输出声明式规格、前端渲染（function-plot、JSXGraph/JessieCode、Plotly JSON、Vega-Lite、Desmos、GeoGebra、Mafs）；(c) 浏览器内编译 TeX（TikZJax）；(d) 内联手写 SVG。逐方案记录了许可证、体积、输出格式、交互、图形类型覆盖、LaTeX 与中文支持、嵌入缓存方式、离线可用性，汇总为 17 维 × 14 方案的对比总表。
2. **LLM 生成正确率的一手证据**一致指向：有执行反馈的代码路径（matplotlib、TikZ）远比一次性生成的低层格式（手写 SVG）可靠——MatPlotBench 中 GPT-4 直接生成 48.86 分、加执行与视觉反馈 61.16；Plot2Code 中 Claude-3-Opus 的 matplotlib 代码执行通过率 84.1%；AutomaTikZ 的每张可编译图平均采样次数 GPT-4 1.147、Claude 2 1.758；VGBench 指出 SVG 是 LLM 表现最差的矢量格式。但任何格式的首次正确率都不足以免去重试，方案必须内置「失败→重试/降级」。JessieCode、function-plot JSON、Desmos、GeoGebra 命令均无一手数据，已标注为经验判断。
3. **两条集成路径对比**：路径 (a) 静态文件 + `![]()` 引用——零前端依赖、零前端执行风险、完全离线、缓存即文件、出错在生成时即暴露且 agy 可自修；路径 (b) 围栏代码块规格 + 前端插件渲染——可交互，但错误只在学习者打开讲义时暴露，需前端降级 UI，且绝不能让前端执行 LLM 生成的任意 JS。
4. **初步建议**（最终由 [插图方案选型](./006-figure-choice.md) 决定）：主方案为 matplotlib 静态 SVG（mathtext + CJK 字体回退可免装 TeX）；需要交互时以 JSXGraph 围栏块为备选（MIT 许可、约 1 MB、零依赖、JessieCode 禁 DOM，需原型验证正确率），只画函数图像时 function-plot 更轻更安全；TikZ 本地编译链与 Manim 仅按需引入；不建议 Desmos（需联网与 API key、不能自托管）、GeoGebra（33 MB、非商业许可）、Mafs（输出 JSX）、手写 SVG 作主方案、Asymptote；Mermaid 不适合数学插图。
