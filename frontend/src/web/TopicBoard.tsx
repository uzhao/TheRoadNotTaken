import type { FieldView, TopicView } from '../api'
import { KIND_NAMES, STATUS_NAMES } from './labels'

interface Props {
  field: FieldView
  topics: TopicView[] | null
}

/** 看板：选中领域的主题卡片网格。 */
export function TopicBoard({ field, topics }: Props) {
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
            <TopicCard key={t.id} topic={t} />
          ))}
        </div>
      )}
    </section>
  )
}

/** 一张主题卡：名称、状态标签、概念提纲；不可学时列出缺失的前置。 */
function TopicCard({ topic }: { topic: TopicView }) {
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
    </article>
  )
}
