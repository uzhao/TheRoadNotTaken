import { KnowledgeWeb } from './web/KnowledgeWeb'
import { useFields } from './web/useFields'

const NAV_ITEMS = ['知识网', '学习', '验证'] as const

function App() {
  const { data, error } = useFields()

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
      </header>
      {error ? (
        <main className="shell-plain">
          <p className="error">无法读取知识网：{error}</p>
        </main>
      ) : data ? (
        <KnowledgeWeb fields={data.fields} />
      ) : (
        <main className="shell-plain">
          <p className="placeholder">加载中…</p>
        </main>
      )}
    </>
  )
}

export default App
