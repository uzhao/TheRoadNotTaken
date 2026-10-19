import { useEffect, useState } from 'react'

import { fetchRecommendation, type RecommendationResponse, type TopicAction } from '../api'

interface Props {
  /** 状态每变一次加一，推荐随之重取。 */
  version: number
  onAction: (topicId: string, action: TopicAction) => void
  busy: boolean
}

/** 知识网页顶部唯一一张推荐卡：要么学一个主题，要么验证一个声称掌握的主题。 */
export function RecommendationCard({ version, onAction, busy }: Props) {
  const [data, setData] = useState<RecommendationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchRecommendation()
      .then((body) => {
        if (!cancelled) {
          setData(body)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(String(err))
      })
    return () => {
      cancelled = true
    }
  }, [version])

  if (error) return <p className="error">无法读取推荐：{error}</p>
  if (!data) return <div className="rec muted">加载推荐…</div>

  const rec = data.recommendation
  if (!rec) {
    return (
      <div className="rec" aria-label="推荐">
        <p className="muted">{data.hint}</p>
      </div>
    )
  }

  const { topic } = rec
  const verify = rec.kind === 'verify'
  return (
    <section className="rec hero" aria-label="推荐">
      <span className="kind">
        {verify ? '待验证 · 你声称已掌握' : `下一步 · ${topic.field_name}`}
        {rec.was_deferred && <span className="tag deferred">之前暂不学</span>}
      </span>
      <span className="title">{topic.name}</span>
      <span className="muted small">{topic.concepts.join(' · ')}</span>
      <span className="reason">{rec.reason}</span>
      <div className="acts">
        {verify ? (
          <>
            {/* 验证流程由工单 026 接入 */}
            <button type="button" className="primary" disabled title="验证尚未接入">
              开始验证
            </button>
            <button type="button" disabled={busy} onClick={() => onAction(topic.id, 'unclaim')}>
              其实没学过
            </button>
          </>
        ) : (
          <>
            {/* 讲义生成由工单 024 接入 */}
            <button type="button" className="primary" disabled title="讲义生成尚未接入">
              {topic.status === 'learning' ? '继续学习' : '开始学习'}
            </button>
            <button type="button" disabled={busy} onClick={() => onAction(topic.id, 'claim')}>
              我已掌握
            </button>
            {topic.status !== 'deferred' && (
              <button
                type="button"
                className="ghost"
                disabled={busy}
                onClick={() => onAction(topic.id, 'defer')}
              >
                暂不学
              </button>
            )}
          </>
        )}
      </div>
    </section>
  )
}
