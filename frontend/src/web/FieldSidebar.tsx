import type { FieldKind, FieldView } from '../api'
import { KIND_NAMES } from './labels'

interface Props {
  fields: FieldView[]
  selected: string | null
  onSelect: (fieldId: string) => void
  onToggleIncluded: (fieldId: string, included: boolean) => void
  busy: boolean
}

/**
 * 左侧领域侧栏：按主干 / 分支分组，每行名称、已掌握 / 总数与三色进度条；
 * 分支领域另有「纳入推荐」开关（默认关闭）。
 */
export function FieldSidebar({ fields, selected, onSelect, onToggleIncluded, busy }: Props) {
  const groups: FieldKind[] = ['core', 'branch']
  return (
    <aside className="side" aria-label="领域">
      {groups.map((kind) => {
        const rows = fields.filter((f) => f.kind === kind)
        if (rows.length === 0) return null
        return (
          <section key={kind}>
            <h3>{KIND_NAMES[kind]}</h3>
            {rows.map((f) => (
              <div key={f.id}>
                <FieldRow field={f} on={f.id === selected} onSelect={onSelect} />
                {f.kind === 'branch' && (
                  <label className="include">
                    <input
                      type="checkbox"
                      aria-label={`${f.name}：纳入推荐`}
                      checked={f.included}
                      disabled={busy}
                      onChange={(e) => onToggleIncluded(f.id, e.target.checked)}
                    />
                    纳入推荐
                  </label>
                )}
              </div>
            ))}
          </section>
        )
      })}
    </aside>
  )
}

function FieldRow({
  field,
  on,
  onSelect,
}: {
  field: FieldView
  on: boolean
  onSelect: (fieldId: string) => void
}) {
  const pct = (n: number) => (field.total ? `${(n / field.total) * 100}%` : '0%')
  return (
    <button
      type="button"
      className={`frow${on ? ' on' : ''}`}
      aria-pressed={on}
      onClick={() => onSelect(field.id)}
    >
      <span className="name">{field.name}</span>
      <span className="n">
        {field.mastered}/{field.total}
      </span>
      <span
        className="bar"
        role="img"
        aria-label={`已掌握 ${field.mastered}，学习中 ${field.learning}，声称掌握 ${field.claimed}，共 ${field.total}`}
      >
        <i className="mastered" style={{ width: pct(field.mastered) }} />
        <i className="learning" style={{ width: pct(field.learning) }} />
        <i className="claimed" style={{ width: pct(field.claimed) }} />
      </span>
    </button>
  )
}
