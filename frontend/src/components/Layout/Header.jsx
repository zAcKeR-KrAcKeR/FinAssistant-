export default function Header({ title, subtitle, actions }) {
  return (
    <header className="header">
      <div>
        <div className="header-title">{title}</div>
        {subtitle && <div className="header-subtitle">{subtitle}</div>}
      </div>
      <div className="header-actions">
        {actions}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div className="status-dot" title="System Online" />
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Live</span>
        </div>
      </div>
    </header>
  )
}
