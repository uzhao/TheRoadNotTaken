import type { FieldKind, TopicStatus } from '../api'

/** 状态与领域类型的中文显示名，以 GLOSSARY.md 为准。 */
export const STATUS_NAMES: Record<TopicStatus, string> = {
  unlearned: '未学',
  learning: '学习中',
  deferred: '暂不学',
  claimed: '声称掌握',
  mastered: '已掌握',
}

export const KIND_NAMES: Record<FieldKind, string> = {
  core: '主干',
  branch: '分支',
}
