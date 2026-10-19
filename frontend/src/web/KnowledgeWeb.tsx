import { useEffect, useState } from 'react'

import { fetchTopics, type FieldView, type TopicView } from '../api'
import { FieldSidebar } from './FieldSidebar'
import { TopicBoard } from './TopicBoard'

interface Props {
  fields: FieldView[]
}

interface LoadedTopics {
  fieldId: string
  topics: TopicView[]
}

/** 知识网页：左侧领域侧栏 + 右侧选中领域的看板。 */
export function KnowledgeWeb({ fields }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [loaded, setLoaded] = useState<LoadedTopics | null>(null)
  const [error, setError] = useState<string | null>(null)

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
  }, [currentId])

  if (!current) return <p className="placeholder">骨架里没有领域。</p>

  // 切换领域后、新数据到达前显示加载中，而不是上一领域的卡片
  const topics = loaded?.fieldId === current.id ? loaded.topics : null

  return (
    <div className="shell">
      <FieldSidebar fields={fields} selected={current.id} onSelect={setSelected} />
      <main className="main">
        {error ? <p className="error">{error}</p> : <TopicBoard field={current} topics={topics} />}
      </main>
    </div>
  )
}
