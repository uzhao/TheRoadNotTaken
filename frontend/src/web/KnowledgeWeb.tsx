import { useEffect, useState } from 'react'

import {
  fetchTopics,
  postTopicAction,
  putFieldIncluded,
  type FieldView,
  type TopicAction,
  type TopicView,
} from '../api'
import { FieldSidebar } from './FieldSidebar'
import { RecommendationCard } from './RecommendationCard'
import { TopicBoard } from './TopicBoard'

interface Props {
  fields: FieldView[]
  /** 状态版本：每次写入后由上层加一，看板与推荐据此重取。 */
  version: number
  onChanged: () => void
}

interface LoadedTopics {
  fieldId: string
  topics: TopicView[]
}

/** 知识网页：左侧领域侧栏 + 右侧推荐卡与选中领域的看板。 */
export function KnowledgeWeb({ fields, version, onChanged }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [loaded, setLoaded] = useState<LoadedTopics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const current = fields.find((f) => f.id === selected) ?? fields[0] ?? null
  const currentId = current?.id ?? null

  useEffect(() => {
    if (currentId === null) return
    let cancelled = false
    fetchTopics(currentId)
      .then((topics) => {
        if (!cancelled) setLoaded({ fieldId: currentId, topics })
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(String(err))
      })
    return () => {
      cancelled = true
    }
  }, [currentId, version])

  /** 一次状态写入：期间按钮置灰，成功后让上层重取全部视图，失败显示后端的说明。 */
  function write(op: () => Promise<unknown>) {
    setBusy(true)
    setActionError(null)
    op()
      .then(onChanged)
      .catch((err: unknown) => setActionError(err instanceof Error ? err.message : String(err)))
      .finally(() => setBusy(false))
  }
  const onAction = (topicId: string, action: TopicAction) =>
    write(() => postTopicAction(topicId, action))
  const onToggleIncluded = (fieldId: string, included: boolean) =>
    write(() => putFieldIncluded(fieldId, included))

  if (!current) return <p className="placeholder">骨架里没有领域。</p>

  // 切换领域后、新数据到达前显示加载中，而不是上一领域的卡片
  const topics = loaded?.fieldId === current.id ? loaded.topics : null

  return (
    <div className="shell">
      <FieldSidebar
        fields={fields}
        selected={current.id}
        onSelect={setSelected}
        onToggleIncluded={onToggleIncluded}
        busy={busy}
      />
      <main className="main">
        <RecommendationCard version={version} onAction={onAction} busy={busy} />
        {actionError && (
          <p className="error" role="alert">
            {actionError}
          </p>
        )}
        {error ? (
          <p className="error">{error}</p>
        ) : (
          <TopicBoard field={current} topics={topics} onAction={onAction} busy={busy} />
        )}
      </main>
    </div>
  )
}
