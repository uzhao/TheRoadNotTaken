import { useState } from 'react'

import { ConnectionButton, ConnectionLog } from './ConnectionCheck'
import { PermissionBanner } from './PermissionBanner'
import { useConnectionCheck } from './useConnectionCheck'
import { KnowledgeWeb } from './web/KnowledgeWeb'
import { useFields } from './web/useFields'

const NAV_ITEMS = ['知识网', '学习', '验证'] as const

function App() {
  // 状态每写入一次加一：领域、看板与推荐据此重取
  const [version, setVersion] = useState(0)
  const { data, error } = useFields(version)
  const connection = useConnectionCheck()

  return (
    <>
      <header className="topbar">
        <span className="brand">The Road Not Taken</span>
        <nav aria-label="主导航">
          {NAV_ITEMS.map((item) => (
            <span key={item} className={`nav-item${item === '知识网' ? ' on' : ''}`}>
              {item}
            </span>
          ))}
        </nav>
        <span className="mastered-count" aria-live="polite">
          {data ? `已掌握 ${data.mastered} / ${data.total} 个主题` : '…'}
        </span>
        <ConnectionButton check={connection} />
      </header>
      <PermissionBanner />
      <ConnectionLog check={connection} />
      {error ? (
        <main className="shell-plain">
          <p className="error">无法读取知识网：{error}</p>
        </main>
      ) : data ? (
        <KnowledgeWeb
          fields={data.fields}
          version={version}
          onChanged={() => setVersion((v) => v + 1)}
        />
      ) : (
        <main className="shell-plain">
          <p className="placeholder">加载中…</p>
        </main>
      )}
    </>
  )
}

export default App
