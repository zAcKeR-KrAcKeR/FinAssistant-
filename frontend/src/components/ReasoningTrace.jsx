import { useState } from 'react'

export default function ReasoningTrace({ steps = [], agents = [] }) {
  const [open, setOpen] = useState(false)
  if (!steps || steps.length === 0) return null

  return (
    <div className="reasoning-trace">
      <button className="reasoning-toggle" onClick={() => setOpen(!open)}>
        <span>{open ? '▾' : '▸'}</span>
        <span>Show reasoning trace</span>
        <span style={{ marginLeft: 4, color: 'var(--secondary)' }}>
          {steps.length} modules ran
        </span>
      </button>

      {open && (
        <div className="reasoning-steps">
          {steps.map((step, i) => (
            <div key={i} className="reasoning-step">
              <div style={{ color: 'var(--secondary)', fontSize: 16 }}>
                {i === 0 ? '🔍' : i === steps.length - 1 ? '✅' : '⚙️'}
              </div>
              <div style={{ flex: 1 }}>
                <div className="step-module">{step.module}</div>
                <div className="step-action">{step.action}</div>
              </div>
              <div className="step-time">{step.duration_ms}ms</div>
            </div>
          ))}

          {/* Module badges */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
            {agents.map((a, i) => (
              <span key={i} className="badge badge-primary" style={{ fontSize: 10 }}>
                {a}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
