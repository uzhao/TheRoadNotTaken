import type { JobEvent } from './api'
import type { useConnectionCheck } from './useConnectionCheck'

type ConnectionCheck = ReturnType<typeof useConnectionCheck>

/** 顶栏的「重试连接」：跑一个最小 agy 任务。 */
export function ConnectionButton({ check }: { check: ConnectionCheck }) {
  return (
    <span className="connection-check">
      <button type="button" onClick={check.start} disabled={check.running}>
        重试连接
      </button>
      {check.running ? (
        <button type="button" onClick={check.cancel}>
          取消
        </button>
      ) : null}
    </span>
  )
}

/** 「重试连接」任务的事件流，原样逐条列出。 */
export function ConnectionLog({ check }: { check: ConnectionCheck }) {
  if (check.job === null && check.error === null) return null
  return (
    <section className="connection-log">
      {check.error ? <p className="banner-error">{check.error}</p> : null}
      <ol className="event-log">
        {check.events.map((e, i) => (
          <li key={i}>
            <code>{e.event}</code> {describe(e)}
          </li>
        ))}
      </ol>
    </section>
  )
}

function describe(e: JobEvent): string {
  switch (e.event) {
    case 'queued':
      return `排队中（第 ${e.data.position} 位）`
    case 'started':
      return '已启动'
    case 'conversation':
      return `会话 ${e.data.conversation_id}`
    case 'delta':
      return e.data.text
    case 'tool':
      return `${e.data.name} ${e.data.state === 'ACTIVE' ? '执行中' : '完成'}`
    case 'done': {
      const { status, response, error } = e.data
      if (status === 'succeeded') return `成功：${response ?? ''}`
      if (status === 'cancelled') return '已取消'
      const reason = error?.short_error ?? error?.message ?? error?.kind ?? ''
      return `失败：${reason}${error?.error_id ? `（${error.error_id}）` : ''}`
    }
  }
}
