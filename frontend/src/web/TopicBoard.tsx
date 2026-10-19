import type { ReactNode } from 'react'

import type { FieldView, TopicAction, TopicView } from '../api'
import { KIND_NAMES, STATUS_NAMES } from './labels'

type OnAction = (topicId: string, action: TopicAction) => void

interface Props {
  field: FieldView
  topics: TopicView[] | null
  onAction: OnAction
  busy: boolean
}

/** 看板：选中领域的主题卡片网格。 */
export function TopicBoard({ field, topics, onAction, busy }: Props) {
  return (
    <section aria-labelledby="board-title">
      <div className="board-head">
        <h2 id="board-title">{field.name}</h2>
        <span className="muted">
          {KIND_NAMES[field.kind]} · {field.total} 个主题 · 已掌握 {field.mastered}
        </span>
      </div>
      {topics === null ? (
        <p className="muted">加载中…</p>
      ) : (
        <div className="grid">
          {topics.map((t) => (
            <TopicCard key={t.id} topic={t} onAction={onAction} busy={busy} />
          ))}
        </div>
      )}
    </section>
  )
}

/** 一张主题卡：名称、状态标签、概念提纲；不可学时列出缺失的前置，否则给出状态操作。 */
function TopicCard({
  topic,
  onAction,
  busy,
}: {
  topic: TopicView
  onAction: OnAction
  busy: boolean
}) {
  return (
    <article
      className={`tcard ${topic.status}${topic.locked ? ' locked' : ''}`}
      id={`card-${topic.id}`}
      aria-label={topic.name}
    >
      <div className="tcard-head">
        <span className="nm">{topic.name}</span>
        <span className={`tag ${topic.status}`}>{STATUS_NAMES[topic.status]}</span>
      </div>
      <span className="cc">{topic.concepts.join(' · ')}</span>
      {topic.locked && (
        <span className="missing">
          前置未掌握：{topic.missing_prerequisites.map((p) => p.name).join('、')}
        </span>
      )}
      <TopicActions topic={topic} onAction={onAction} busy={busy} />
    </article>
  )
}

/** 卡片上可做的状态操作；暂不学的主题即使不可学也能恢复推荐。 */
function TopicActions({
  topic,
  onAction,
  busy,
}: {
  topic: TopicView
  onAction: OnAction
  busy: boolean
}) {
  const button = (action: TopicAction, label: string, ghost = false) => (
    <button
      key={action}
      type="button"
      className={ghost ? 'ghost' : undefined}
      disabled={busy}
      onClick={() => onAction(topic.id, action)}
    >
      {label}
    </button>
  )
  let buttons: ReactNode[] = []
  if (topic.status === 'deferred') buttons = [button('restore', '恢复推荐')]
  else if (topic.status === 'claimed') buttons = [button('unclaim', '其实没学过')]
  else if (!topic.locked && (topic.status === 'unlearned' || topic.status === 'learning'))
    buttons = [button('claim', '我已掌握'), button('defer', '暂不学', true)]
  if (buttons.length === 0) return null
  return <div className="acts">{buttons}</div>
}
