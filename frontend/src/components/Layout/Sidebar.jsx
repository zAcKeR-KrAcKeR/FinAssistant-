import { NavLink, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { getHealth } from '../../api/client'

const NAV = [
  { to: '/',            icon: '📊', label: 'Executive Overview' },
  { to: '/risk',        icon: '🛡️', label: 'Risk Analysis' },
  { to: '/segments',    icon: '👥', label: 'Customer Segments' },
  { to: '/quality',     icon: '🔬', label: 'Data Quality' },
  { to: '/assistant',   icon: '🤖', label: 'AI Assistant' },
]

export default function Sidebar() {
  const [health, setHealth] = useState(null)
  const location = useLocation()

  useEffect(() => {
    getHealth().then(r => setHealth(r.data)).catch(() => {})
    const id = setInterval(() => {
      getHealth().then(r => setHealth(r.data)).catch(() => {})
    }, 30000)
    return () => clearInterval(id)
  }, [])

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <NavLink to="/" className="logo-mark" style={{ textDecoration: 'none' }}>
          <div className="logo-icon">💎</div>
          <div>
            <div className="logo-text">FinSight AI</div>
            <div className="logo-sub">Intelligence Copilot</div>
          </div>
        </NavLink>
      </div>

      {/* Nav */}
      <nav className="sidebar-nav">
        <div className="nav-section">Dashboard</div>
        {NAV.slice(0, 4).map(n => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="nav-icon">{n.icon}</span>
            {n.label}
          </NavLink>
        ))}

        <div className="nav-section" style={{ marginTop: 8 }}>AI Copilot</div>
        <NavLink
          to="/assistant"
          className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
        >
          <span className="nav-icon">🤖</span>
          AI Assistant
          <span className="nav-badge">NEW</span>
        </NavLink>

        <div className="nav-section" style={{ marginTop: 8 }}>Analysis</div>
        <NavLink
          to="/whatif"
          className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
        >
          <span className="nav-icon">🔮</span>
          What-If Simulator
        </NavLink>
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div style={{ marginBottom: 6, fontSize: 11 }}>
          {health?.status === 'ready' ? (
            <span style={{ color: '#10b981' }}>● System Ready</span>
          ) : (
            <span style={{ color: '#f59e0b' }}>● Initialising…</span>
          )}
        </div>
        {health && (
          <>
            <div>{health.records?.toLocaleString()} records</div>
            <div style={{ marginTop: 4 }}>
              <span className="provider-badge">
                🤖 {health.llm_provider?.split('(')[0].trim()}
              </span>
            </div>
          </>
        )}
      </div>
    </aside>
  )
}
