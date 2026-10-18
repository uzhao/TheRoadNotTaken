---
id: 3
title: "数学插图方案调研"
labels: [wayfinder:research]
parent: 1
blocked_by: []
assignee:
status: open
---

## Question

讲义中的插图（函数图像、几何示意、向量场、概率分布等）由 agy 产出时，有哪些可行形式，各自的优劣？候选至少包括：

- agy 运行代码生成静态图：Python + matplotlib 输出 SVG/PNG。
- agy 输出声明式规格，由前端渲染（可交互）：function-plot、JSXGraph、Plotly、Desmos API、Mafs 等。
- TikZ / PGFPlots 编译为 SVG。
- 内联 SVG 由 agy 直接手写。

比较维度：LLM 生成的正确率、交互性（拖动参数、缩放）、覆盖的图形类型（2D/3D、几何构造、动画）、渲染与依赖成本、能否嵌入 markdown 讲义并缓存。
