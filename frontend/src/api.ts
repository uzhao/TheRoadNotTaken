/** 后端 JSON REST 的最小客户端，每个端点一个函数。 */

export interface Health {
  name: string
  version: string
  data_dir: string
}

export async function fetchHealth(): Promise<Health> {
  const resp = await fetch('/api/health')
  if (!resp.ok) throw new Error(`GET /api/health → ${resp.status}`)
  return (await resp.json()) as Health
}
