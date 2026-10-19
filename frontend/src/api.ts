/** 后端 JSON REST 的最小客户端，每个端点一个函数。 */

export type FieldKind = 'core' | 'branch'

export type TopicStatus = 'unlearned' | 'learning' | 'deferred' | 'claimed' | 'mastered'

/** 领域及其进度（侧栏一行）。 */
export interface FieldView {
  id: string
  name: string
  kind: FieldKind
  order: number
  total: number
  mastered: number
  learning: number
  claimed: number
}

export interface FieldsResponse {
  fields: FieldView[]
  mastered: number
  total: number
}

export interface PrerequisiteRef {
  id: string
  name: string
}

/** 主题及其状态（看板一张卡）。 */
export interface TopicView {
  id: string
  name: string
  field: string
  concepts: string[]
  prerequisites: string[]
  status: TopicStatus
  weak_points: string[]
  locked: boolean
  missing_prerequisites: PrerequisiteRef[]
}

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(path)
  if (!resp.ok) throw new Error(`GET ${path} → ${resp.status}`)
  return (await resp.json()) as T
}

export function fetchFields(): Promise<FieldsResponse> {
  return getJson<FieldsResponse>('/api/fields')
}

export async function fetchTopics(field: string): Promise<TopicView[]> {
  const body = await getJson<{ topics: TopicView[] }>(
    `/api/topics?field=${encodeURIComponent(field)}`,
  )
  return body.topics
}
