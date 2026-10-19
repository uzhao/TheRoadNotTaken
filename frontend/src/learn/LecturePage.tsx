import { STATUS_NAMES } from '../web/labels'
import { LectureMarkdown } from './LectureMarkdown'
import { useLecture } from './useLecture'

interface Props {
  topicId: string
  /** 「稍后再学」：回到知识网 */
  onBack: () => void
}

/** 学习页：顶部状态、薄弱点与步骤条，讲义居中流式出现，底部去验证 / 稍后再学。 */
export function LecturePage({ topicId, onBack }: Props) {
  const lec = useLecture(topicId)
  const topic = lec.page?.topic
  const cached = lec.page?.lecture ?? null
  const markdown = cached?.markdown ?? lec.streamed

  return (
    <main className="learn">
      <header className="learn-head">
        {topic ? (
          <>
            <span className={`tag ${topic.status}`}>{STATUS_NAMES[topic.status]}</span>
            {topic.weak_points.length > 0 && (
              <div className="weak" aria-label="薄弱点">
                <span className="muted small">薄弱点（讲解会重点覆盖）</span>
                <ul>
                  {topic.weak_points.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          !lec.error && <span className="muted">打开讲义…</span>
        )}
        {(lec.steps.length > 0 || lec.queued !== null || (cached && !lec.generating)) && (
          <div className="steps" aria-live="polite">
            {lec.queued !== null && <span className="on">排队中（第 {lec.queued} 位）</span>}
            {lec.steps.map((s) => (
              <span key={s.key} className={s.done ? 'done' : 'on'}>
                {s.label}
              </span>
            ))}
            {cached && lec.steps.length === 0 && <span className="done">讲义已缓存</span>}
          </div>
        )}
      </header>

      {lec.error && (
        <p className="error" role="alert">
          {lec.error}
        </p>
      )}
      {lec.failure && (
        <section className="failure" role="alert">
          <p>
            讲义生成失败：
            {lec.failure.short_error ?? lec.failure.message ?? lec.failure.kind}
            {lec.failure.error_id && <code>（{lec.failure.error_id}）</code>}
          </p>
          {lec.failure.errors && (
            <ul>
              {lec.failure.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          <button type="button" onClick={lec.restart}>
            重试
          </button>
        </section>
      )}

      {markdown && (
        <LectureMarkdown
          topicId={topicId}
          markdown={markdown}
          cached={cached !== null}
          drawn={lec.drawn}
          streaming={lec.generating}
        />
      )}

      <div className="acts learn-foot">
        {/* 验证流程由工单 026 接入 */}
        <button type="button" className="primary" disabled title="验证尚未接入">
          我学完了，去验证
        </button>
        <button type="button" onClick={onBack}>
          稍后再学
        </button>
      </div>
    </main>
  )
}
