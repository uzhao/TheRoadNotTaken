import { useEffect, useState } from 'react'

import { type AgyPermissions, fetchAgyPermissions, writeAgyPermissions } from './api'

/** agy 权限规则缺失时的顶栏横幅：给出要追加的 JSON 片段，页内确认后写入。 */
export function PermissionBanner() {
  const [permissions, setPermissions] = useState<AgyPermissions | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchAgyPermissions()
      .then((p) => {
        if (!cancelled) setPermissions(p)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (permissions === null || permissions.ok) return null

  const write = () => {
    setError(null)
    writeAgyPermissions()
      .then(setPermissions)
      .catch((e: Error) => setError(e.message))
      .finally(() => setConfirming(false))
  }

  return (
    <div className="banner" role="alert">
      <p>
        agy 权限规则缺失：生成讲义需要在 <code>{permissions.settings_path}</code> 的{' '}
        <code>permissions.allow</code> 中加入以下规则。
      </p>
      {permissions.error ? (
        <p className="banner-error">该文件无法解析，请手动修改：{permissions.error}</p>
      ) : null}
      <pre>{permissions.snippet}</pre>
      {error ? <p className="banner-error">{error}</p> : null}
      {permissions.error ? null : confirming ? (
        <p className="banner-actions">
          将把 {permissions.missing.length} 条规则追加到该文件，其它设置保持不变。
          <button type="button" onClick={write}>
            确认写入
          </button>
          <button type="button" onClick={() => setConfirming(false)}>
            取消
          </button>
        </p>
      ) : (
        <p className="banner-actions">
          <button type="button" onClick={() => setConfirming(true)}>
            写入规则
          </button>
        </p>
      )}
    </div>
  )
}
