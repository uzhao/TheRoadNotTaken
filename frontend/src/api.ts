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
  /** 是否参与推荐：主干恒为 true，分支看「纳入推荐」开关。 */
  included: boolean
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

/** 推荐卡：唯一一个下一步。 */
export interface Recommendation {
  topic: {
    id: string
    name: string
    field: string
    field_name: string
    concepts: string[]
    status: TopicStatus
  }
  kind: 'learn' | 'verify'
  reason: string
  was_deferred: boolean
}

export interface RecommendationResponse {
  recommendation: Recommendation | null
  /** 没有推荐时的提示。 */
  hint: string | null
}

/** 学习者对主题状态的直接操作：我已掌握、其实没学过、暂不学、恢复推荐。 */
export type TopicAction = 'claim' | 'unclaim' | 'defer' | 'restore'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!resp.ok) {
    // 后端的 409 / 400 带中文说明，直接显示给学习者
    const detail = await resp
      .json()
      .then((b: { detail?: unknown }) => (typeof b.detail === 'string' ? b.detail : null))
      .catch(() => null)
    throw new Error(detail ?? `${method} ${path} → ${resp.status}`)
  }
  return (await resp.json()) as T
}

function getJson<T>(path: string): Promise<T> {
  return request<T>('GET', path)
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

export function fetchRecommendation(): Promise<RecommendationResponse> {
  return getJson<RecommendationResponse>('/api/recommendation')
}

export function postTopicAction(topicId: string, action: TopicAction): Promise<TopicView> {
  return request<TopicView>('POST', `/api/topics/${encodeURIComponent(topicId)}/${action}`)
}

export function putFieldIncluded(fieldId: string, included: boolean): Promise<FieldView> {
  return request<FieldView>('PUT', `/api/fields/${encodeURIComponent(fieldId)}/included`, {
    included,
  })
}
