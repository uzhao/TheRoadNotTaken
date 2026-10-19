import { useEffect, useState } from 'react'

import { fetchHealth } from './api'

const NAV_ITEMS = ['知识网', '学习', '验证'] as const

function App() {
  const [version, setVersion] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchHealth()
      .then((health) => {
        if (!cancelled) setVersion(health.version)
      })
      .catch(() => {
        if (!cancelled) setVersion(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <header className="topbar">
        <span className="brand">The Road Not Taken</span>
        <nav aria-label="主导航">
          {NAV_ITEMS.map((item) => (
            <span key={item} className="nav-item">
              {item}
            </span>
          ))}
        </nav>
        <span className="version">{version ? `v${version}` : '…'}</span>
      </header>
      <main className="shell">
        <p className="placeholder">空壳页面：知识网、推荐卡与讲义将在后续工单中出现。</p>
      </main>
    </>
  )
}

export default App
