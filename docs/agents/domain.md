# Domain Docs

工程类 skill 在探索代码库之前应如何使用本仓库的领域文档。本仓库是单上下文（single-context）布局。

## 探索之前先读

- **`GLOSSARY.md`**（仓库根目录）：项目术语表，中文术语附英文对照，每条带 _Avoid_ 列出不要使用的同义词。
- **`docs/adr/`**：与你将要改动的区域相关的 ADR。

若其中某个文件或目录不存在，**静默继续**。不要指出它缺失，也不要建议先去创建。`/domain-modeling`（经 `/grill-with-docs` 与 `/improve-codebase-architecture` 触发）会在术语或决策真正敲定时按需创建它们。

## 文件结构

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-<slug>.md
│   └── 0002-<slug>.md
├── issues/        ← 本地 issue tracker（见 issue-tracker.md）
└── research/      ← 调研产出
```

## 使用术语表的词汇

输出中涉及领域概念时（issue 标题、重构提案、假设、测试名），使用 `GLOSSARY.md` 定义的术语，不要滑向它明确 _Avoid_ 的同义词。例如用"主题"而非"知识点"，用"验证"而非"测验"，用"已掌握"而非"已完成"。

如果需要的概念尚未进入术语表，这是一个信号：要么你在发明项目不用的语言（请重新考虑），要么术语表确有缺口（记下来交给 `/domain-modeling`）。

## 标出与 ADR 的冲突

若输出与已有 ADR 冲突，要明确说出来，而不是悄悄推翻：

> _与 ADR-0007（……）冲突，但值得重新讨论，因为……_
