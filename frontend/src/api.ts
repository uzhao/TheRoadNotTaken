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

async function json<T>(resp: Response, what: string): Promise<T> {
  if (!resp.ok) {
    const body = (await resp.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `${what} → ${resp.status}`)
  }
  return (await resp.json()) as T
}

// ---- agy 权限规则 ----

export interface AgyPermissions {
  ok: boolean
  missing: string[]
  settings_path: string
  /** 要追加到 settings 的 JSON 片段 */
  snippet: string
  /** settings 文件存在但无法解析时的原因（此时后端不会写入） */
  error: string | null
}

export async function fetchAgyPermissions(): Promise<AgyPermissions> {
  return json(await fetch('/api/agy/permissions'), 'GET /api/agy/permissions')
}

export async function writeAgyPermissions(): Promise<AgyPermissions> {
  return json(await fetch('/api/agy/permissions', { method: 'POST' }), 'POST /api/agy/permissions')
}

// ---- 生成任务 ----

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface Job {
  id: string
  kind: string
  status: JobStatus
  /** 排队位次（从 1 起），未排队时为 null */
  position: number | null
}

export interface JobError {
  kind: 'agy_error' | 'timeout' | 'exit' | 'no_result' | 'result' | 'spawn' | 'validation' | 'postprocess'
  message?: string
  /** 搬运校验未通过时的逐条错误 */
  errors?: string[]
  short_error?: string
  error_id?: string
  retryable?: boolean
}

/** 任务事件流里的事件；`done` 是终止事件，收到后流结束。 */
export type JobEvent =
  | { event: 'queued'; data: { position: number } }
  | { event: 'started'; data: Record<string, never> }
  | { event: 'conversation'; data: { conversation_id: string } }
  | { event: 'delta'; data: { text: string } }
  | {
      event: 'tool'
      /** `detail`：命令行或目标文件，如 `python3 figures/secant.py` */
      data: { step_index: number; name: string; state: 'ACTIVE' | 'DONE'; detail: string }
    }
  /** 产出没通过校验，同一会话再试一次；之后的正文从头重新流出 */
  | { event: 'retry'; data: { attempt: number; errors: string[] } }
  | {
      event: 'done'
      data: {
        status: 'succeeded' | 'failed' | 'cancelled'
        response?: string
        error?: JobError
      }
    }

const JOB_EVENTS = ['queued', 'started', 'conversation', 'delta', 'tool', 'retry', 'done'] as const

export async function createPingJob(): Promise<Job> {
  const resp = await fetch('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'ping' }),
  })
  return json(resp, 'POST /api/jobs')
}

export async function cancelJob(id: string): Promise<void> {
  const resp = await fetch(`/api/jobs/${id}`, { method: 'DELETE' })
  if (!resp.ok && resp.status !== 409) throw new Error(`DELETE /api/jobs/${id} → ${resp.status}`)
}

/** 订阅任务事件；收到 `done` 后自动关闭。返回取消订阅函数。 */
export function subscribeJob(id: string, onEvent: (event: JobEvent) => void): () => void {
  const source = new EventSource(`/api/jobs/${id}/events`)
  for (const name of JOB_EVENTS) {
    source.addEventListener(name, (msg) => {
      const event = { event: name, data: JSON.parse((msg as MessageEvent<string>).data) } as JobEvent
      if (event.event === 'done') source.close()
      onEvent(event)
    })
  }
  return () => source.close()
}

// ---- 讲义 ----

export interface LectureMeta {
  generated_at: string
  model: string | null
  effort: string
  template: string
  definition_hash: string
  weak_points: string[]
  regenerations: number
  job_id: string
  conversation_id: string | null
  /** 第几次尝试通过了搬运校验（1 或 2） */
  attempts: number
}

/** 学习页：主题（状态与薄弱点）、缓存的讲义、在跑的讲义任务。 */
export interface LecturePage {
  topic: TopicView
  lecture: { markdown: string; meta: LectureMeta } | null
  job: Job | null
}

/** 开始学习：未学 / 暂不学 → 学习中；有缓存直接返回讲义，否则返回讲义任务。 */
export function startLecture(topicId: string): Promise<LecturePage> {
  return request<LecturePage>('POST', `/api/lectures/${encodeURIComponent(topicId)}`)
}

export function fetchLecture(topicId: string): Promise<LecturePage> {
  return getJson<LecturePage>(`/api/lectures/${encodeURIComponent(topicId)}`)
}

/** 讲义里 `figures/<名>` 对应的插图地址。 */
export function figureUrl(topicId: string, name: string): string {
  return `/api/lectures/${encodeURIComponent(topicId)}/figures/${encodeURIComponent(name)}`
}
