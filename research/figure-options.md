# 数学插图方案调研

> 关联工单：[数学插图方案调研](../issues/003-figure-options.md)（后续选型工单：[插图方案选型](../issues/006-figure-choice.md)）  
> 术语约定：遵循 [GLOSSARY.md](../GLOSSARY.md)（主题、讲义、插图、例题、追问）。本文用「插图」指 agent 为讲义生成的数学图形，不用「图片/图表」。

> 调研日期：2026-10-18。所有事实均注明一手来源（官方文档、仓库 README/LICENSE、CTAN/PyPI/jsDelivr 包元数据、arXiv 论文原文）。网络经代理，个别页面抓不到时改用官方镜像并在「附录 A」注明。体积数字来自 jsDelivr/PyPI 实际响应（minified、未 gzip），只用于数量级比较。凡是没有一手数据、只是经验判断的地方，均明确标注「**无一手数据，仅为经验判断**」。

---

## 一、问题与候选方案分类

讲义中的插图（函数图像、几何示意、向量场、概率分布、3D 曲面、动画等）由 `agy -p` 产出。agy 能执行 Python、读写文件，因此候选方案按「谁来渲染」分四类：

| 类别 | 机制 | 候选 |
| :--- | :--- | :--- |
| **A. 后端执行代码产出静态图** | agy 跑代码，把 SVG/PNG 写到数据目录，讲义用 `![]()` 引用 | matplotlib、Plotly + kaleido、Asymptote、Manim（动画/帧）、TikZ/PGFPlots 本地编译链 |
| **B. agy 输出声明式规格，前端渲染（可交互）** | agy 在 markdown 里写围栏代码块（JSON / DSL），前端 markdown 渲染器插件把它交给 JS 库 | JSXGraph（JessieCode / JS）、function-plot（JSON）、Mafs（React JSX）、Plotly.js（JSON）、Desmos API（LaTeX 表达式 + state JSON）、GeoGebra Apps（命令串 / base64）、Vega-Lite（JSON）、Observable Plot / d3（JS）、Three.js（JS） |
| **C. TeX 在浏览器内编译** | TikZJax：TeX 的 WebAssembly 版在浏览器里把 TikZ 编成 SVG | TikZJax |
| **D. agy 直接手写矢量图** | agy 直接输出内联 `<svg>` | 内联 SVG；Penrose（声明式 → SVG，归入 B 亦可） |
| （对照） | 文本型示意图 | Mermaid（预期不适合数学图形，仅做排除性评估） |

比较维度（来自工单原文）：LLM 生成正确率、交互性（拖动参数、缩放）、覆盖的图形类型（2D/3D、几何构造、动画）、渲染与依赖成本、能否嵌入 markdown 讲义并缓存；本文再加：公式标注（LaTeX）能力、中文文本支持、离线可用性、许可证。

---

## 二、逐方案评估

每个方案给出：一手来源、许可证、依赖与安装体积、输出格式、交互、图形覆盖、公式标注、中文、嵌入与缓存方式、离线可用性、备注。

### 1. matplotlib（Python，静态 SVG/PNG）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | "License agreement for matplotlib versions 1.3.0 and later"，PSF 风格的宽松许可（PyPI classifier：Python Software Foundation License） | <https://raw.githubusercontent.com/matplotlib/matplotlib/main/LICENSE/LICENSE>，<https://pypi.org/project/matplotlib/> |
| 依赖与体积 | 3.11.2（2026-09）；wheel 约 9–11 MB；Python ≥ 3.11；numpy 等由 pip 自动带入 | <https://pypi.org/project/matplotlib/> |
| 输出格式 | SVG / PNG / PDF 等；SVG 后端 `svg.fonttype` 默认 `'path'`（字形转路径，与查看端字体无关，但文本不可编辑、文件更大），可选 `'none'`（保留文本，外观依赖查看端字体） | <https://matplotlib.org/stable/users/explain/text/fonts.html> |
| 交互 | 无（静态文件） | — |
| 图形覆盖 | 2D 函数曲线/散点/柱状、直方图 `hist`、箱线/小提琴、`contour`/`contourf`、向量场 `quiver`/`streamplot`、`imshow`；3D（`mpl_toolkits.mplot3d`）`plot_surface`、`plot_wireframe`、3D `quiver`、`voxels`。几何构造需手工用 patches/线段画；动画需 `FuncAnimation`（输出 GIF/MP4，需 pillow/ffmpeg） | <https://matplotlib.org/stable/plot_types/index.html> |
| 公式标注 | **mathtext**：内置 TeX 子集解析器，"TeX does *not* need to be installed"；支持上下标、`\frac`、`\sqrt`、`\sum`/`\int`、希腊字母、`\mathbb`（需 STIX 字体集）等；限制：`\sqrt` 的被开方式不能含分式/上下标，字面 `$` 须转义。**usetex**：需要完整 LaTeX 安装，Agg(PNG) 另需 dvipng，SVG/PDF 后端只需 LaTeX；字体族只支持 PSNFSS 的少数几种，非 ASCII 字符"supported to the extent that they are supported by inputenc" | <https://matplotlib.org/stable/users/explain/text/mathtext.html>，<https://matplotlib.org/stable/users/explain/text/usetex.html> |
| 中文 | 默认字体 DejaVu Sans 无 CJK 字形；3.6 起 Agg/SVG/PDF/PS 后端支持按 `family=['DejaVu Sans','Noto Sans CJK JP','Noto Sans TC']` 列表逐字形回退；文档提醒 CJK 字体全量内嵌会使文件很大 | <https://matplotlib.org/stable/users/explain/text/fonts.html> |
| 嵌入与缓存 | agy 把 `.svg/.png` 写入数据目录，讲义 markdown 以 `![alt](figures/xxx.svg)` 引用；文件即缓存 | — |
| 离线 | 完全离线（mathtext 不需要 TeX） | 同上 |
| 备注 | 若用 `usetex`，公式与 LaTeX 讲义完全一致，但引入整套 TeX 依赖；若用 mathtext + 中文字体回退，需在机器上装 Noto Sans CJK 并写进 rcParams | — |

### 2. Plotly（plotly.py + plotly.js，JSON 规格；静态导出需 kaleido）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | plotly.js、plotly.py、kaleido 均为 MIT | <https://github.com/plotly/plotly.js>，<https://pypi.org/project/plotly/>，<https://pypi.org/project/kaleido/> |
| 依赖与体积 | plotly.py 7.1.0 wheel 9.7 MB；plotly.js 完整包 minified **4.83 MB**，部分包：cartesian 1.51 MB、gl3d 1.76 MB、basic 1.2 MB、strict（避免 Function 构造器，适配严格 CSP）5.18 MB；实测 `plotly.js-dist-min/plotly.min.js` 4,834,409 B | <https://github.com/plotly/plotly.js/blob/master/dist/README.md>，jsDelivr 实测 |
| 静态导出 | 需 **kaleido ≥ 1.0**；kaleido 1.x 自身 wheel 仅 55.8 kB，但**不再捆绑 Chrome**，必须有本机 Chrome/Chromium（可用 `plotly_get_chrome` 安装）；支持 PNG/JPEG/WebP/SVG/PDF；WebGL trace 在矢量导出时会"include encapsulated rasters" | <https://plotly.com/python/static-image-export/>，<https://pypi.org/project/kaleido/> |
| 输出格式 | 图的本质是 JSON（data + layout），可以 (a) 存 JSON 由前端 plotly.js 渲染，(b) `fig.to_html()` 出 HTML 片段，(c) kaleido 出 SVG/PNG | 同上 |
| 交互 | 内置缩放、平移、悬停、图例开关；参数滑块需用 `layout.sliders`/`updatemenus` 预先生成多帧 | — |
| 图形覆盖 | 2D 曲线/散点/直方图/等高线/热力图，3D `surface`/`mesh3d`/`scatter3d`/`cone`(向量场)/`isosurface`，动画帧；几何构造无原生支持（只能用 shapes 画线段/圆） | dist/README 列出各包 trace 类型 |
| 公式标注 | LaTeX 仅在标题/轴标签/注释中、整段被 `$...$` 包住时生效，且**依赖页面加载 MathJax**（"must be loaded in the environment where figures are being rendered"）；plotly.py v7 支持 MathJax 3/4。kaleido 静态导出的配置项 `mathjax` 默认指向 CDN，"If fully offline export is required, set this to a local MathJax bundle" | <https://plotly.com/python/LaTeX/>，<https://plotly.com/python/static-image-export/> |
| 中文 | 浏览器字体渲染，中文无特殊问题（kaleido 走 Chrome，同样依赖系统字体） | 经验判断 |
| 嵌入与缓存 | JSON 规格可作为 ```` ```plotly ```` 围栏块存进讲义；或静态 SVG 落盘 | — |
| 离线 | plotly.js 可本地托管；LaTeX 要本地 MathJax；kaleido 要本地 Chrome | 同上 |
| 备注 | 前端体积最大的一档；数学教学常用的"几何构造 + 可拖动点"不是它的强项 | — |

### 3. function-plot（JSON 规格 → d3 渲染）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | MIT | <https://github.com/mauriciopoppe/function-plot>，`package.json` |
| 依赖与体积 | 1.26.0；UMD 包 `dist/function-plot.js` 实测 211,430 B；依赖 d3 子模块（axis/scale/zoom/shape 等）、`built-in-math-eval`、`interval-arithmetic-eval`；无 peer 依赖 | <https://cdn.jsdelivr.net/npm/function-plot/package.json> |
| 输出格式 | 浏览器内 SVG；输入是一个纯对象（可 JSON 序列化） | README |
| 交互 | 缩放/平移（`disableZoom` 可关），悬停提示 `tip`，视窗变化时函数**重新求值**（"whenever the graph scale is modified the function is evaluated again"）；导数线可随鼠标更新 `updateOnMouseMove`；**无参数滑块**（需外部 UI 改 options 重绘） | README |
| 图形覆盖 | `fnType: 'linear' \| 'parametric' \| 'implicit' \| 'polar' \| 'points' \| 'vector'`；`graphType: 'polyline' \| 'interval' \| 'scatter' \| 'text'`；`sampler: 'interval' \| 'builtIn' \| 'asyncInterval'`（区间算术采样可正确处理奇点）；`derivative`、`secants`、`closed`（函数下方区域/积分）、`annotations`（竖/横参考线）、`range`、`nSamples`。**仅 2D 函数**：无几何构造、无 3D、无动画、无直方图 | <https://raw.githubusercontent.com/mauriciopoppe/function-plot/master/src/types.ts> |
| 公式标注 | 无 TeX 支持（`title`、annotation 文本为纯字符串） | types.ts、README |
| 中文 | SVG `<text>`，依赖页面字体，无特殊问题 | 经验判断 |
| 嵌入与缓存 | ```` ```function-plot ```` 围栏 JSON；`fn` 为字符串表达式（如 `"x^2"`），由 `built-in-math-eval` / `interval-arithmetic-eval` 解析，**不是 JS `eval`**（依赖清单可证，但本文未逐行审阅其求值器源码） | `package.json` |
| 离线 | 可本地托管 | — |
| 备注 | 规格最小、最像"纯数据"，LLM 几乎不可能写出有副作用的代码；代价是覆盖面窄 | — |

### 4. JSXGraph（JS API / JessieCode / `<script type="text/jessiecode">`）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | 双许可 **MIT OR LGPL-3.0-or-later**（JessieCode 同） | <https://github.com/jsxgraph/jsxgraph>，<https://cdn.jsdelivr.net/npm/jsxgraph/package.json>，<https://github.com/jsxgraph/JessieCode> |
| 依赖与体积 | 1.14.0；运行时**零依赖**；`distrib/jsxgraphcore.js` 实测 993,978 B（≈0.97 MB minified），`jsxgraph.css` 4.8 KB；KaTeX 另加 `katex.min.js` 272,868 B + CSS/字体 | jsDelivr 实测 |
| 输出格式 | 浏览器内 SVG 或 canvas；"standalone and needs no server-side processing" | 官方 docs 首页 |
| 交互 | 可拖动点、滑块（`slider` 元素）、缩放/平移、多点触控、动画；3D 视图可用虚拟轨迹球旋转（`trackball`），或方位角/仰角滑块（`az`/`el`，支持键盘） | <https://cdn.jsdelivr.net/npm/jsxgraph@1.14.0/distrib/docs/View3D.html> |
| 图形覆盖 | "Euclidean and projective geometry in 2D and 3D, curve and surface plotting, vector fields"；函数图、参数曲线、隐函数曲线、向量场、微分方程、统计图（charts）、符号运算；3D 元素含 `Functiongraph3D`、`ParametricSurface3D`、`Curve3D`、`Plane3D`、`Sphere3D`、`Polyhedron3D`、`Vectorfield3D`、`Text3D` 等；View3D 投影 `parallel`（默认）/`central`，深度排序默认关闭（开启后"elements closer to the screen are drawn over elements further"，按图层排序，非真正的隐面消除） | 官方 docs 首页，View3D 文档 |
| 公式标注 | `Text` 元素 `display: 'html'`（默认）时"HTML, MathJaX, KaTeX, ASCIIMathML, and GEONExT syntax can be handled"；`useKatex: true` 需页面自带 `katex.min.js/css`；`display: 'internal'` 用 SVG `<text>`，不支持 MathJax/KaTeX/HTML | <https://cdn.jsdelivr.net/npm/jsxgraph@1.14.0/distrib/docs/Text.html> |
| 中文 | HTML 文本模式下即普通网页文本，无问题 | 同上 |
| 声明式描述能力 | **JessieCode**："similar to JavaScript, but prevents access to the DOM"，设计目标是"restrict the user's access to the DOM"，面向"community driven web sites"；`board.jc.parse(code)` 解析整段脚本，`board.jc.snippet("3+4")` 解析单个表达式并可包装成函数（官方示例用它把用户输入的函数项变成 `functiongraph`）；jsxgraphcore.js 源码中可见对 `<script type="text/jessiecode">`（及 `text/jessiescript`）标签的识别。`Text` 的 `parse: true`（默认）会把字符串当 JessieCode 表达式求值 | <https://github.com/jsxgraph/JessieCode>，<https://cdn.jsdelivr.net/npm/jsxgraph@1.14.0/distrib/docs/JXG.JessieCode.html>，jsxgraphcore.js 源码 grep |
| 安全 | JessieCode 只承诺"阻止访问 DOM"，README 未使用"sandbox"一词；`Text` 的 HTML 模式会把字符串插入 DOM，文档提供 `useCaja` 选项（需自行引入 Caja 的 `sanitizeHTML`）。因此 LLM 产出的 JessieCode 比直接执行 JS 安全得多，但文本内容仍应过一层 HTML 消毒 | Text 文档、JessieCode README |
| 嵌入与缓存 | ```` ```jsxgraph ```` 围栏块（JessieCode 或 JSON 包装）存于讲义；前端插件建 board 后 `board.jc.parse()` | — |
| 离线 | 单文件本地托管即可 | — |
| 备注 | 覆盖面最接近"大学数学教学插图"（几何构造 + 函数 + 向量场 + 简易 3D）的单一库；代价是约 1 MB 的前端体积和一门 LLM 不太熟的 DSL（见第三节） | — |

### 5. Mafs（React 组件）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | MIT | <https://github.com/stevenpetryk/mafs>，`package.json` |
| 依赖与体积 | 0.21.0；`build/index.js` 实测 64,421 B；依赖 `katex ^0.16`、`computer-modern`（可选字体，"will add about 220kB to your page load"）、`@use-gesture/react`；**peer 依赖 react ≥ 18、react-dom ≥ 18** | <https://cdn.jsdelivr.net/npm/mafs/package.json>，<https://mafs.dev/guides/get-started/installation> |
| 输出格式 | React 组件 → SVG；输入是 **JSX**，不是数据 | 同上 |
| 交互 | `MovablePoint` 可拖动；缩放/平移由 `<Mafs zoom pan>` 控制；参数滑块需自己用 React state 做 | mafs.dev guides |
| 图形覆盖 | `Plot.OfX`、`Plot.OfY`、`Plot.Parametric`、`Plot.VectorField`、`Plot.Inequality`、点/线/多边形/圆/椭圆/向量/变换；采样为递归细分（"far from perfect"，`sin(1/x)` 仍渲染不完美）；**无 3D、无几何构造求交、无直方图**；动画为实验特性 | <https://mafs.dev/guides/display/plots> |
| 公式标注 | `LaTeX` 组件包装 KaTeX，标注为 **Experimental**，且"does not work properly in Safari due to ... SVG foreignObject" | <https://mafs.dev/guides/experimental/latex> |
| 中文 | SVG 文本，无特殊问题 | 经验判断 |
| 嵌入与缓存 | 要让 agy 的输出可渲染，必须要么让 LLM 写 JSX 并在前端动态编译（极不安全），要么自定义一层 JSON → 组件映射（等于自己造 DSL） | 分析 |
| 离线 | 可 | — |
| 备注 | 适合**开发者手写**交互组件（例如前端自带的固定可视化），不适合作为 LLM 的输出目标 | — |

### 6. Desmos API

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可/条款 | 专有服务。"In order to include the Desmos API in your page, you must supply an API key as a URL parameter"；文档中的 demo key（`dcb31709b452b1cf9dc26972add0fda6`）"provided for use during development"；"If you plan to use the API in production, you should contact us by e-mailing partnerships@desmos.com to obtain your own API key"；官方示例仓库同样写明 demo key 仅供开发，上线须联系 Desmos。**API Terms of Service 页面为 JS 动态渲染，本次未能读取其条文**；<https://www.desmos.com/terms> 目录中有 "Personal, Non-Commercial Use Only" 一节，但同样未能读取正文 | <https://www.desmos.com/api/v1.8/docs/index.html>，<https://www.desmos.com/api/v1.11/docs/index.html>，<https://github.com/desmosinc/desmos-sample-cms> |
| 依赖与体积 | 从 `desmos.com/api/v1.11/calculator.js?apiKey=...` 加载；自托管（"host the Desmos API on their own servers"）仅对合作伙伴开放，通过"private shared github repository"提供离线构建 | v1.8/v1.11 docs |
| 输出格式 | 嵌入式计算器（HTML 片段）；状态为 `getState()/setState()` 的 JSON；表达式用 LaTeX 字符串（"Desmos uses LaTeX for passing expressions back and forth"） | v1.11 docs |
| 交互 | 最强：滑块默认可创建、缩放平移、表达式列表可编辑；3D 与几何工具"must be separately enabled per API key" | v1.11 docs |
| 图形覆盖 | 2D 函数/参数/极坐标/隐函数/不等式/统计分布、几何工具、3D（按 key 开通） | v1.11 docs |
| 公式标注 | 原生 LaTeX | 同上 |
| 中文 | `updateSettings({language})`，翻译需用 `lang=zh-CN` / `zh-TW` 参数请求，"translation coverage varies" | v1.11 docs |
| 嵌入与缓存 | ```` ```desmos ```` 围栏块存 LaTeX 表达式列表或 state JSON | — |
| 离线 | **非合作伙伴无法离线**（脚本必须从 desmos.com 加载） | v1.8 docs |
| 备注 | 对本项目（单用户、本地运行）而言：需联网、需 API key、条款未读到、不可自托管，是硬伤；但 LLM 对 Desmos 风格的 LaTeX 表达式非常熟悉，生成正确率可能是所有方案中最高的（**无一手数据，仅为经验判断**） | — |

### 7. GeoGebra Apps（embedding API）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | 源码 **EUPL v1.2**；安装包与 web 服务（含 apps）**仅限非商业用途**（"We allow you to use the installers and web services for non-commercial purposes only"）；语言文件、UI 图像与样式 CC BY-NC-SA 4.0；须署名"Made with GeoGebra®"并链接官网；"Any use of GeoGebra for a commercial purpose is subject to and requires a special license" | <https://www.geogebra.org/license> |
| 依赖与体积 | `deployggb.js` 37 KB（CDN）；自托管用 **GeoGebra Math Apps Bundle**，zip 实测 **33.45 MB**（5.4.932），`setHTML5Codebase()` 指向本地 | <https://geogebra.github.io/docs/reference/en/GeoGebra_Apps_Embedding/>，<https://download.geogebra.org/package/geogebra-math-apps-bundle> |
| 输出格式 | 嵌入式 app（HTML 片段）；`evalCommand()` 执行 GeoGebra 命令串（"you must use English commands names"，多条用 `\n` 分隔）；`setBase64()/getBase64()` 读写 `.ggb`；`exportSVG()` 可导出 2D 视图（"The value is null if the active view is 3D"），`getPNGBase64()` | <https://geogebra.github.io/docs/reference/en/GeoGebra_Apps_API/> |
| 交互 | 完整动态几何：拖点、滑块、`enable3D`、透视切换 | 同上 |
| 图形覆盖 | 几何构造（最强）、函数、参数/隐函数、向量、3D、概率计算器、CAS | 同上 |
| 公式标注 | 原生 LaTeX 文本对象 | GeoGebra 手册（常识，未单独引用） |
| 中文 | 有中文界面；界面语言文件属 CC BY-NC-SA | license 页 |
| 嵌入与缓存 | ```` ```geogebra ```` 围栏块存命令串（每行一条 `evalCommand`） | — |
| 离线 | 自托管 bundle 可离线 | embedding 文档 |
| 备注 | 命令语言成熟、LLM 相对熟悉；但 33 MB bundle、非商业许可（本项目单用户自用可满足，但若日后分发需注意）、iframe 风格的重量级 UI 与"讲义旁的小插图"气质不合 | — |

### 8. TikZ / PGFPlots

**8a. 本地编译链（pdflatex/lualatex → dvisvgm 或 pdf2svg）**

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | PGF/TikZ 3.1.12：GFDL / GPLv2 / LPPL 1.3c 三选一；PGFPlots 1.18.3：GPLv3+；dvisvgm：GPLv3+；pdf2svg：GPLv2 | <https://ctan.org/pkg/pgf>，<https://ctan.org/pkg/pgfplots>，<https://dvisvgm.de/>，<https://github.com/dawbarton/pdf2svg> |
| 依赖与体积 | 需要 TeX 发行版。TeX Live 官方指南："the full TeX Live needs several gigabytes"；Debian bookworm `texlive-pictures`（含 pgf 与 pgfplots）下载 15.4 MB、安装 76.5 MB，但依赖 `texlive-base`、`texlive-binaries`、`texlive-latex-recommended`，整体通常数百 MB 量级（**本句为经验判断**）；中文另需 `ctex`/`xeCJK` 与中文字体 | <https://tug.org/texlive/doc/texlive-en/texlive-en.html>，<https://packages.debian.org/bookworm/texlive-pictures>，其文件列表 |
| 输出格式 | PDF → SVG：dvisvgm `--pdf` 需要 Ghostscript < 10.01 或 mutool（"As of Ghostscript 10.01.0, this will no longer work"）；DVI 路径（`latex` + `dvisvgm`）无此限制，字体可选 `--font-format=svg/ttf/woff/woff2` 或 `--no-fonts` 转路径（"larger but ... more compatible"）；pdf2svg 依赖 poppler + cairo，仓库活动极少（版权年份 2007–2013） | <https://dvisvgm.de/Manpage/>，pdf2svg README |
| 交互 | 无 | — |
| 图形覆盖 | 2D 几何构造（TikZ 的交点、角度、坐标计算最强）、交换图、函数曲线、PGFPlots 的 2D/3D 函数与数据图（"line, scatter, bar, area, and surface/mesh plots"，含对数轴）；3D 为投影绘制，无交互；动画无 | CTAN 页面 |
| 公式标注 | 原生 LaTeX，与讲义正文公式完全一致 | — |
| 中文 | 需 xelatex/lualatex + xeCJK/ctex；pdflatex 路线中文支持差（**经验判断**） | — |
| 嵌入与缓存 | agy 写 `.tex` → 编译 → `.svg` 落盘，讲义 `![]()` 引用 | — |
| 离线 | 完全离线 | — |
| 备注 | 是 LLM 唯一有大规模一手评测的格式（见第三节），且训练语料最多；代价是最重的本地依赖与最慢的生成（编译 + 转换） | — |

**8b. TikZJax（浏览器内编译）**

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | LPPL-1.3c | <https://github.com/kisonecat/tikzjax> |
| 机制 | "the Pascal source of TeX is compiled to WebAssembly"，加载不含连字数据的 LaTeX 格式与 TikZ 预载内核，"All of this happens in the browser"，用 PGF 的 SVG 驱动 + dvi2html 转 SVG；页面只需 `<script type="text/tikz">` | <https://tikzjax.com/> |
| 体积 | `tikzjax.js` 实测 458,758 B，`fonts.css` 10 KB；其引用的 `.wasm` 与 `.gz` 内核转储本次 HEAD 请求被 403 拒绝，**未能测得体积** | jsDelivr/tikzjax.com 实测 |
| 限制 | 官方页面与 README 未列出支持的宏包清单，未提及 pgfplots；仓库 9 次提交、27 个 open issue，维护状态不明 | README |
| 备注 | 概念上最优雅（TikZ 源码即缓存、零后端依赖），但生态成熟度与可用宏包不确定，需要原型验证后才可依赖 | — |

### 9. Asymptote

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | LGPLv3+（Windows 可执行文件因捆绑 GSL/Readline 为 GPL） | <https://github.com/vectorgraphics/asymptote>，<https://ctan.org/pkg/asymptote> |
| 输出格式 | 手册：EPS、PDF、SVG、WebGL、V3D 及 legacy PRC；SVG 经 dvisvgm；PNG 经 ImageMagick | <https://raw.githubusercontent.com/vectorgraphics/asymptote/master/doc/asymptote.texi>（第 274、481、591 行附近） |
| 依赖 | 需 TeX（标签用 LaTeX 排版）、Ghostscript、dvisvgm；3.15 版 | CTAN，texi |
| 覆盖 | 2D/3D 矢量图、3D 可交互 WebGL 输出；几何构造能力强（MetaPost 血统） | texi |
| 备注 | 依赖链与 TikZ 相当甚至更重；LLM 熟悉度远低于 TikZ（**无一手数据，经验判断**）；不推荐作为主方案 | — |

### 10. Manim（动画，可选项）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可证 | MIT（3b1b LLC 与 Manim Community 双版权） | <https://github.com/ManimCommunity/manim> |
| 依赖 | `pip install manim`；Linux 需从源码构建 ManimPango/pycairo：`build-essential python3-dev libcairo2-dev libpango1.0-dev`；0.19.0（2025-01-20）起"Replaced external ffmpeg dependency with pyav"，不再需要命令行 ffmpeg；LaTeX 可选（公式需要，官方建议 `texlive-full` 或 TinyTeX），也支持 Typst | <https://docs.manim.community/en/stable/installation/uv.html>，<https://docs.manim.community/en/stable/changelog/0.19.0-changelog.html> |
| 输出 | 视频（`-ql` 低质量快渲）、`-s` 仅输出最后一帧（PNG）；README 称项目处于大规模重构、暂不接受新功能贡献 | README |
| 备注 | 渲染慢、依赖重、输出是视频文件；只有在"动画"是明确需求时才值得引入；可缓存 mp4/gif 文件并用 `<video>` 嵌入 | — |

### 11. Mermaid（排除性评估）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 图类型 | 流程图、时序、类、状态、ER、甘特、饼、象限、XY chart、桑基、思维导图、时间线、块图、雷达、维恩等 | <https://mermaid.js.org/intro/> |
| XY chart | "Presently, it includes two fundamental chart types: the bar chart and the line chart"；数据必须是显式数组（`line [2.3, 45, .98]`），**不能写公式**，y 轴只能是数值范围 | <https://mermaid.js.org/syntax/xyChart.html> |
| 公式 | KaTeX 仅在 flowchart 与 sequence 图里支持 `$$...$$` | <https://mermaid.js.org/config/math.html> |
| 体积 | `mermaid.min.js` 实测 5,494,801 B | jsDelivr 实测 |
| 结论 | **不适合数学插图**（无函数、无几何、无坐标系控制）；只适合讲义中偶尔出现的概念关系图/流程图（例如证明结构、定理依赖），可作为旁路而非插图方案 | — |

### 12. 内联手写 SVG（agy 直接输出 `<svg>`）

| 项目 | 事实 | 一手来源 |
| :--- | :--- | :--- |
| 许可/依赖 | 零依赖，零体积 | — |
| 输出 | SVG 文本，可内联在 markdown 中或落盘为 `.svg` | — |
| 交互 | 无（除非 LLM 写 `<script>`，应禁止） | — |
| 安全 | 通过 `<img src="x.svg">` 引用时浏览器"JavaScript is disabled"、"External resources ... cannot be loaded"；若内联进 DOM 则无此保护，需 DOMPurify（Apache-2.0/MPL-2.0，"XSS sanitizer for HTML, MathML and SVG"，`USE_PROFILES: {svg: true}`）消毒 | <https://developer.mozilla.org/en-US/docs/Web/SVG/Guides/SVG_as_an_image>，<https://github.com/cure53/DOMPurify> |
| 公式 | SVG 原生无 LaTeX；可用 `<foreignObject>` 放 KaTeX 输出（KaTeX MIT，`renderToString` 可在 Node 端预渲染），但 foreignObject 在 `<img>` 上下文中外部资源受限，且 Safari 兼容性差（Mafs 文档所述问题相同） | <https://github.com/KaTeX/KaTeX>，Mafs LaTeX 文档 |
| 覆盖 | 理论上任意 2D 图形；实际上 LLM 需要自己算坐标，曲线要手写 `<path>` 采样点——函数图像、向量场、概率密度等"需要数值计算"的图形极易画错；适合极简示意图（数轴、集合关系、简单三角形、交换图） | 经验判断，见第三节 VGBench 数据 |
| 备注 | 作为**兜底**（其他方案失败时）或**极简示意**可用；不应作为函数图像类插图的主方案 | — |

### 13. 补充候选（简评）

| 库 | 许可证 | 体积（实测） | 定位 | 对本项目的判断 |
| :--- | :--- | :--- | :--- | :--- |
| d3 | ISC | `d3.min.js` 279,706 B | 通用可视化底层 | 需 LLM 写命令式 JS，安全与正确率都差；不作为输出目标（<https://github.com/d3/d3>） |
| Observable Plot | ISC | `plot.umd.min.js` 209,183 B | 表格数据的图形语法 | 面向数据图而非数学函数/几何；JS API 非 JSON（<https://github.com/observablehq/plot>） |
| Vega-Lite | BSD-3-Clause | vega-lite 257,954 B + vega 521,123 B | **纯 JSON** 的交互图形语法；参数可 `bind` 到滑块等输入控件 | 安全性好、可做概率分布直方图与带滑块的数据图；但无几何构造、无隐函数、无 3D，函数需先用 `sequence`+`calculate` 生成数据（<https://github.com/vega/vega-lite>，<https://vega.github.io/vega-lite/docs/parameter.html>） |
| Penrose | MIT | npm `@penrose/core` | Domain/Substance/Style 三段式声明 → SVG，面向"数学记号 → 图" | 概念契合（集合图、几何命题图），但需为每类图先写 Style 库，LLM 语料极少；观望（<https://github.com/penrose/penrose>） |
| Three.js | MIT | `three.module.min.js` 392,831 B | 通用 3D | 需 LLM 写命令式 JS；若 3D 需求超出 JSXGraph/Plotly 再考虑（<https://github.com/mrdoob/three.js>） |

---

## 三、LLM 生成正确率：一手证据

> 说明：没有任何公开基准是"用 Claude 生成大学数学讲义插图"这个任务本身；下面是最接近的一手论文数据。所有数字都来自论文原文（arXiv HTML 版），指标含义以原文为准。

| 格式 | 基准 / 论文 | 规模 | 关键数据 | 对本项目的含义 |
| :--- | :--- | :--- | :--- | :--- |
| **TikZ** | AutomaTikZ / DaTikZ（Belouadi et al., arXiv:2310.00367） | 120k 图-说明对（另有 >120k 从 arXiv 抽出但**编译失败**而被剔除的样本） | 附录 Table 3 的 CSR（每张可编译图平均需要的采样次数，越低越好）：GPT-4 **1.147**，Claude 2 **1.758**，LLaMA-13b 1.178，CLiMA-13b 1.184；正文："all models require approximately 1.2 samples per caption to generate a compilable TikZ drawing ... except for Claude 2, which needs noticeably more samples"；对 GPT-4/Claude 2 采用宽松计数（"counting a sample as successful if it results in an image, even if there are errors"）；通用模型"tend to produce simpler figures" | 通用 LLM 写 TikZ 一次编译通过率大致在 85% 量级（由 CSR 反推，**非论文原话**），必须设计"编译失败→重试"的循环 |
| TikZ | DeTikZify（arXiv:2405.15306） | DaTikZv2 >360k | 专用模型"outperforms commercial Claude 3 and GPT-4V in synthesizing TikZ programs"；MCTS 迭代精化显著提升 | 专用小模型 + 迭代反馈比单次生成好得多；但本项目用 agy（通用模型 + 可执行反馈），机制上接近其 MCTS 思路 |
| TikZ | TikZero（arXiv:2503.11509，ICCV 2025） | — | 文到 TikZ；"matches or exceeds ... GPT-4o" | 同上 |
| **matplotlib 代码** | MatPlotAgent / MatPlotBench（arXiv:2402.11453） | 100 个人工验证用例，GPT-4V 自动评分（与人工评分 Pearson r=0.876） | 0–100 分：GPT-4 直接生成 **48.86**，加"代码执行 + 视觉反馈"的 agent 流程 **61.16**（+12.30）；去掉视觉反馈 53.44 | 即便是 GPT-4，一次生成的科学图质量只有一半分；**执行 + 看图 + 修正**的闭环价值很大——这正是 agy 跑代码路径天然具备的 |
| matplotlib 代码 | Plot2Code（arXiv:2405.07990） | 132 张 matplotlib 图 | 代码**执行通过率**（Direct / Conditional）：GPT-4V 84.1 / 81.8，**Claude-3-Opus 84.1 / 78.0**，Gemini-Pro 68.2 / 55.3；GPT-4V 评分 1–10：Claude-3-Opus 4.37 / 7.68 | Claude 系列写 matplotlib 代码约 8 成能跑通，但"像不像要求的图"差距大；需要重试与自检 |
| 统计图代码 | ChartMimic（arXiv:2406.09961，ICLR 2025） | 4,800 三元组 | GPT-4o 82.2，最好开源模型 61.6 | 前沿模型显著优于开源模型；任务是复现已有图，比"从概念出发画图"容易 |
| **SVG vs TikZ** | VGBench（arXiv:2407.10972） | 5,845 生成样本 | 摘要："LLMs show strong capability ... while exhibiting less desirable performance on low-level formats (SVG)"；GPT-4 CLIP 分数 SVG 23.97 / TikZ 24.42（真值 25.61 / 24.63）；FID（越低越好）GPT-4 SVG 44.81 / TikZ 39.38 | **同一模型写 TikZ 比直接写 SVG 更接近目标**；低层级格式（手写 SVG）正确率最差 |
| SVG | StarVector / SVG-Bench（arXiv:2312.11556） | SVG-Stack 2M 训练样本，10 个数据集 3 个任务 | 需要专门训练的多模态模型；"pixel-based metrics like MSE fail to capture the unique qualities of vector graphics" | 通用 LLM 手写 SVG 没有可引用的高分一手数据 |
| JessieCode / function-plot JSON / Desmos LaTeX / GeoGebra 命令 | — | — | **无一手数据，仅为经验判断**：Desmos 式 LaTeX 表达式与 GeoGebra 英文命令在网络语料中大量出现，LLM 熟悉度高；function-plot 的 JSON 很小、字段少，靠 schema + 示例即可约束；JessieCode 语料稀少，但其语法与 JS 相近、且 JSXGraph 的 JS API 语料较多，用 few-shot 与 JSON Schema（`--json-schema`，见工单 002）约束后可用性需原型验证 | 任何声明式规格都应配一个**前端可报告的校验/渲染结果**，否则生成错误只在学习者打开讲义时才暴露 |
| Claude 直接写 SVG | — | — | 本次未找到 Anthropic 发布的关于 SVG 生成正确率的一手数据；Claude 产品的 artifacts 功能支持展示 SVG，但这不是正确率证据。**无一手数据，仅为经验判断**：简单示意（数轴、集合、几个点线）可靠，涉及曲线采样、透视、精确角度的图不可靠 | 只做兜底 |

综合：一手证据一致指向两点——(1) **有执行反馈的代码路径（matplotlib、TikZ）比一次性生成的低层格式（SVG）可靠得多**；(2) 无论哪种格式，**首次正确率都不足以免去重试**，方案必须把"失败→重试/降级"设计进去。

---

## 四、结合 agy 的两条集成路径

前提（来自工单 002 的待实测项）：agy 以 `-p` 运行，可在 `--add-dir` 指定的数据目录读写文件、执行 Python；是否能"看"自己生成的图（多模态读取 PNG）尚待实测，这直接影响路径 (a) 的自检能力。

### 路径 (a)：agy 执行代码 → 数据目录静态 SVG/PNG → 讲义 `![]()` 引用

| 维度 | 分析 |
| :--- | :--- |
| 缓存 | 讲义 markdown 与插图文件同目录（如 `lectures/<topic-id>/figures/fig-01.svg`），一起缓存、一起失效；文件名用内容哈希或序号即可，无需额外存储层 |
| 重新生成 | 重新生成讲义 = 重跑 agy，旧图目录整体丢弃或版本化；也可只让 agy 重画某一张图（把生成脚本 `fig-01.py` 一并保存，重画只需重跑脚本或改脚本） |
| 出错处理 | 代码报错发生在**生成时**，agy 看得到 stderr，可以自行修正重试（MatPlotBench 证明这个闭环收益最大）；讲义交付时图已经存在，前端不会遇到渲染失败。若多次失败，agy 可降级为"不插图 + 文字描述"，或退回手写极简 SVG |
| 安全性 | 前端只展示静态文件，**不执行任何 LLM 生成的代码**；风险全部在后端沙箱（agy 本来就能执行代码，属工单 002 的沙箱/权限问题，不是插图方案新增的风险）。SVG 若以 `<img>` 引用，浏览器自动禁用脚本与外部资源（MDN）；若要内联，需 DOMPurify |
| 交互性 | **无**。这是该路径的根本代价：缩放、拖动参数都做不到 |
| 公式与中文 | matplotlib mathtext + Noto Sans CJK 回退可离线解决大部分；需要与正文一致的 LaTeX 时走 usetex 或 TikZ |
| 延迟 | 多一次 Python 启动与渲染（matplotlib 通常秒级）；TikZ 编译链更慢 |

### 路径 (b)：agy 在 markdown 中输出围栏代码块规格 → 前端 markdown 渲染器插件渲染

| 维度 | 分析 |
| :--- | :--- |
| 缓存 | 规格就是讲义文本的一部分，随讲义缓存，无额外文件；体积极小 |
| 重新生成 | 与正文一起重生成；也可以只重生成某个代码块（把代码块原文发回 agy 做追问式修改） |
| 出错处理 | 错误发生在**渲染时**（学习者浏览器里）：JSON 解析失败、JessieCode 语法错、函数表达式求值异常、库版本不兼容。生成时 agy **看不到**这些错误，除非后端增加一道校验（JSON Schema 校验很便宜；真正渲染校验需要 headless 浏览器或 Node 环境跑一次库，成本显著）。前端必须有**降级 UI**：渲染失败时显示错误提示 + 原始规格（折叠），并提供"让 agy 重画"按钮 |
| 安全性 | 取决于规格语言的表达力：<br>• **纯数据 JSON**（function-plot、Vega-Lite、Plotly JSON、Desmos 表达式列表、GeoGebra 命令串）：LLM 无法注入代码，风险只剩字符串被当 HTML 插入（需消毒）与资源耗尽（如 `nSamples` 过大）<br>• **受限 DSL**（JessieCode）：官方只承诺"prevents access to the DOM"，Text 元素默认 HTML 模式仍会把字符串插入 DOM，需关闭 `parse`/开启消毒或改用 `display:'internal'`<br>• **任意 JS/JSX**（d3、Three.js、Mafs JSX、JSXGraph 原生 JS API）：等于前端 `eval` LLM 输出，即便是单用户本地应用，也会让 agy 在读取网页/文档时遭遇的提示注入直接变成浏览器里的任意代码执行（可访问本地服务 API、localStorage 等）。**不建议** |
| 交互性 | 有：缩放、拖点、滑块、3D 旋转（取决于库） |
| 公式与中文 | 浏览器渲染，中文零成本；LaTeX 走 KaTeX/MathJax（JSXGraph、Desmos、GeoGebra 支持；function-plot 不支持） |
| 依赖 | 前端多一个 0.2–1 MB 的库（JSXGraph ≈ 1 MB、function-plot ≈ 0.2 MB、Plotly ≈ 1.5–4.8 MB、Vega ≈ 0.8 MB），本地托管即可离线 |

### 两条路径的组合（供工单 006 参考）

- **按图形类型分流**：可交互价值高的（函数随参数变化、几何构造、向量场、3D 曲面）走 (b)；需要数值计算/统计/精细排版的（概率分布直方图、复杂等高线、与正文一致的 LaTeX 排版图）走 (a)。
- **(b) + 后端校验**：agy 产出规格后，后端用 JSON Schema 校验字段，并可用 `--json-schema`（工单 002）直接约束 agy 输出结构；若引入 Node，可在后端用同一个库做一次"干跑"（JSXGraph 可在无 DOM 的环境下解析 JessieCode 的程度需原型验证）。
- **(b) 失败降级到 (a)**：前端渲染失败 → 请求后端让 agy 用 matplotlib 重画为静态图。
- **规格与静态图双写**：agy 先写规格，再用后端渲染（Plotly + kaleido 可直接把同一份 JSON 出 SVG；JSXGraph 没有官方服务端渲染）生成预览图作为 `<noscript>`/失败兜底。成本最高，不建议 v1 采用。

---

## 五、对比总表

评级：● 强 / ◐ 一般 / ○ 弱或无。"LLM 正确率"一列：有一手数据的标注来源，其余为经验判断（标 †）。

| 方案 | 许可证 | 依赖/体积 | 输出 | 交互 | 2D 函数 | 参数/极坐标/隐函数 | 向量场 | 3D 曲面 | 几何构造 | 概率直方图 | 动画 | LaTeX 标注 | 中文 | 嵌入缓存 | 离线 | LLM 正确率 | 前端安全 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| matplotlib (a) | PSF 式 | Python 包 ~10 MB | SVG/PNG 文件 | ○ | ● | ● | ●（quiver/streamplot） | ◐（mplot3d 静态） | ◐（手工 patches） | ● | ◐（GIF/MP4） | ◐ mathtext / ● usetex（需 TeX） | ◐（需 CJK 字体回退） | 文件 + `![]()` | ● | ◐–●（MatPlotBench 48.86→61.16 带反馈；Plot2Code Claude-3-Opus 通过率 84.1） | ●（不执行） |
| Plotly JSON (b) / +kaleido (a) | MIT | 前端 1.5–4.8 MB；静态导出需 Chrome | JSON / HTML / SVG | ●（缩放悬停；滑块需预生成帧） | ● | ◐ | ◐（cone 3D；2D 需手工箭头） | ●（surface/mesh/isosurface） | ○ | ● | ◐（帧动画） | ◐（需 MathJax） | ● | JSON 围栏 / 文件 | ◐（LaTeX 需本地 MathJax） | ◐† | ●（纯 JSON；strict 包适配 CSP） |
| function-plot JSON (b) | MIT | 0.2 MB | 浏览器 SVG | ◐（缩放平移、悬停；无滑块） | ● | ●（parametric/polar/implicit） | ◐（单个 vector） | ○ | ○ | ○ | ○ | ○ | ● | JSON 围栏 | ● | ◐†（规格极小，易约束） | ●（纯数据） |
| JSXGraph / JessieCode (b) | MIT 或 LGPL-3.0+ | ~1 MB（+KaTeX 0.27 MB） | 浏览器 SVG/canvas | ●（拖点、滑块、缩放、3D 旋转） | ● | ● | ● | ◐（投影式 3D，深度排序简化） | ●（动态几何） | ◐（charts） | ●（内置动画） | ●（KaTeX/MathJax，HTML 模式） | ● | DSL/JSON 围栏 | ● | ◐†（JS API 语料多、JessieCode 少） | ◐（DSL 禁 DOM；文本需消毒） |
| Mafs (b) | MIT | 64 KB + React ≥18 + KaTeX | React SVG | ●（MovablePoint） | ● | ◐（Parametric；无隐函数） | ● | ○ | ◐ | ○ | ◐（实验） | ◐（实验，Safari 问题） | ● | **需自建 JSON→JSX 映射** | ● | ○†（输出目标是 JSX） | ○（JSX 不可直接执行） |
| Desmos API (b) | 专有；需 API key；demo key 仅开发 | 远程脚本 | HTML 片段 + LaTeX/state JSON | ●（最强） | ● | ● | ◐ | ◐（按 key 开通） | ◐（几何工具按 key） | ● | ◐ | ● | ●（zh-CN 需 lang 参数） | 表达式围栏 | **○**（非合作伙伴不能自托管） | ●†（LaTeX 表达式最熟） | ●（表达式是数据） |
| GeoGebra Apps (b) | EUPL 源码；app 仅非商业；须署名 | 自托管 bundle 33 MB | HTML 片段 + 命令串/ggb | ●（完整动态几何） | ● | ● | ● | ● | ●（最强） | ●（概率计算器） | ◐ | ● | ● | 命令串围栏 | ●（自托管） | ◐–●†（命令语料多） | ◐（命令串是数据；app 本身重） |
| TikZ/PGFPlots 本地编译 (a) | LPPL/GPL/GFDL；pgfplots GPLv3 | TeX 发行版（数百 MB 至数 GB）+ dvisvgm | SVG/PDF 文件 | ○ | ● | ● | ◐ | ◐（PGFPlots 静态 3D） | ●（交点/角度/标注最强） | ◐ | ○ | ●（原生） | ◐（需 xeCJK/ctex） | 文件 + `![]()` | ● | ●有一手数据（CSR：GPT-4 1.147，Claude 2 1.758；VGBench TikZ 优于 SVG） | ●（不执行） |
| TikZJax (c) | LPPL-1.3c | 0.46 MB JS + wasm/内核（未测得） | 浏览器 SVG | ○ | ● | ● | ◐ | ○/？（pgfplots 支持未确认） | ● | ◐ | ○ | ● | ？ | TikZ 源码围栏 | ●（可自托管） | 同 TikZ | ◐（TeX 在 wasm 内运行，无 DOM；需原型确认） |
| Asymptote (a) | LGPLv3 | TeX + Ghostscript + dvisvgm | EPS/PDF/SVG/WebGL | ○（WebGL 3D 可转） | ● | ● | ◐ | ●（3D 为强项） | ● | ◐ | ○ | ● | ◐ | 文件 | ● | ○†（语料少） | ● |
| Manim (a) | MIT | Python + cairo/pango 构建依赖；LaTeX 可选 | MP4/GIF/PNG 帧 | ○ | ● | ● | ● | ● | ● | ● | ●（本职） | ●（需 TeX） | ◐ | `<video>` 文件 | ● | ◐†（语料较多，但渲染慢、API 变动大） | ● |
| Mermaid | MIT | 5.5 MB | 浏览器 SVG | ○ | ○（XY chart 只吃数组） | ○ | ○ | ○ | ○ | ◐（柱状） | ○ | ◐（仅 flowchart/sequence） | ● | 围栏 | ● | ●†（语料极多，但做不了数学图） | ● |
| 内联手写 SVG (d) | — | 0 | SVG 文本 | ○ | ◐（需自算采样点） | ○ | ○ | ○ | ◐（简单图形） | ○ | ○ | ○（foreignObject 变通） | ● | 内联或文件 | ● | ○（VGBench：SVG 是 LLM 表现最差的格式） | ◐（`<img>` 引用安全；内联需 DOMPurify） |
| Vega-Lite (b) | BSD-3 | 0.8 MB | JSON | ●（滑块 bind、选择） | ◐（需 sequence+calculate 造数据） | ○ | ○ | ○ | ○ | ● | ○ | ○ | ● | JSON 围栏 | ● | ◐† | ●（纯 JSON） |

---

## 六、初步建议（仅供选型工单参考）

> 以下只是调研层面的建议，**最终选型由 [插图方案选型](../issues/006-figure-choice.md) 决定**，且依赖 [agy print 模式实测](../issues/002-agy-print-mode.md) 对"agy 能否在数据目录执行 Python、能否读回自己生成的图"的结论。

**主方案（建议）：路径 (a) matplotlib 静态 SVG，由 agy 执行代码产出，讲义 `![]()` 引用。**
理由：(1) 唯一同时满足"一手评测证明代码执行 + 反馈闭环显著提升正确率"（MatPlotBench）、"零前端依赖、零前端执行风险"、"完全离线"、"缓存即文件"四点的方案；(2) 覆盖工单列出的全部图形类型（函数、几何示意、向量场、概率分布、静态 3D）；(3) 中文与公式通过 Noto Sans CJK 回退 + mathtext 可离线解决，不必装 TeX。代价是**没有交互**。

**备选方案（建议，用于需要交互的插图）：路径 (b) JSXGraph，agy 输出 ```` ```jsxgraph ```` 围栏块（JessieCode，或后端定义的受限 JSON 再映射到 JSXGraph API），前端 markdown 插件渲染。**
理由：单库覆盖动态几何、函数/参数/隐函数、向量场、滑块与简易 3D，MIT 许可、零依赖、约 1 MB、可离线、KaTeX 标注、JessieCode 禁 DOM。前提条件：(1) 原型验证 LLM 写 JessieCode 的正确率（无一手数据）；(2) 前端必须有渲染失败的降级 UI 与"重画"按钮；(3) 文本元素关闭 `parse` 或做 HTML 消毒；(4) 若只需要函数图像的交互，**function-plot** 是更轻（0.2 MB）、更安全（纯 JSON）的替代，但没有几何与滑块。

**可选项（按需引入）**：
- **TikZ/PGFPlots 本地编译链**：当讲义需要与正文完全一致的 LaTeX 排版图或精确的几何构造标注，且机器上本就有 TeX 时；LLM 正确率有最充分的一手数据，但依赖最重、最慢。建议作为 (a) 的第二引擎而非默认。
- **Manim**：仅当"动画"成为明确的学习需求；v1 不建议。
- **Mermaid**：不用于数学插图，但可保留给证明结构/概念关系这类流程图。

**不建议的方案及原因**：
- **Desmos API**：需联网加载、需 API key、demo key 仅限开发、非合作伙伴不能自托管、API 条款本次未能读取——与"本地运行、离线可用"的项目前提冲突。
- **GeoGebra Apps**：能力最全，但 33 MB bundle、非商业许可与署名要求、重量级 UI 与"讲义旁的插图"定位不符；若日后需要完整动态几何环境可再评估。
- **Mafs**：输出目标是 React JSX，LLM 无法安全地直接产出；只适合前端开发者手写固定组件。
- **内联手写 SVG 作为主方案**：VGBench 表明 SVG 是通用 LLM 表现最差的矢量格式，需要数值采样的图几乎必错；只保留为极简示意或最终兜底。
- **让前端执行 LLM 生成的任意 JS（d3、Three.js、JSXGraph 原生 JS API）**：等价于把提示注入升级为浏览器内任意代码执行，不值得。
- **Asymptote**：依赖不比 TikZ 轻，LLM 熟悉度却低得多。

---

## 附录 A：未能直接读取的来源与替代

| 原始来源 | 问题 | 替代 |
| :--- | :--- | :--- |
| <https://matplotlib.org/stable/users/project/license.html> | 抓取为空 | GitHub 原始 LICENSE 文件 |
| <https://www.npmjs.com/package/function-plot>、npm 其他页面 | 403 | jsDelivr 上的 `package.json` 与实测文件体积 |
| <https://jsxgraph.org/wiki/...>、<https://jsxgraph.org/docs/symbols/*.html> | 404 / 返回索引页 | jsDelivr 镜像的 `distrib/docs/*.html`（与 1.14.0 包同源） |
| <https://www.desmos.com/api/terms>、<https://www.desmos.com/terms>、<https://www.desmos.com/my-api> | 404 或 JS 动态渲染无正文 | v1.8 / v1.11 API 文档中关于 demo key、生产用途、自托管的原文；官方示例仓库 README |
| <https://asymptote.sourceforge.io/> | 403 | GitHub 仓库 README/LICENSE、CTAN 页面、仓库内 `doc/asymptote.texi` |
| <https://tug.org/texlive/quickinstall.html> | WebFetch 403，curl 可达但无容量数字 | TeX Live 官方指南 `texlive-en.html`（"several gigabytes"）；Debian 包页面给出 texlive-pictures 的具体容量 |
| TikZJax 的 `.wasm` / `.gz` 内核 | HEAD 请求 403 | 未测得体积，已在正文标注 |
| Anthropic 关于 Claude SVG 生成能力的一手数据 | 未找到 | 标注为"无一手数据" |
