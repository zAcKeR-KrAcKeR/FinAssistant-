const ICONS = { CRITICAL: '🔴', HIGH: '🟠', MEDIUM: '🟡', LOW: '🟢' }

export default function AlertCard({ alert }) {
  const { severity = 'MEDIUM', title, message, records_affected, detected_at } = alert
  return (
    <div className={`alert-card alert-${severity}`}>
      <div className="alert-icon">{ICONS[severity] || '⚠️'}</div>
      <div style={{ flex: 1 }}>
        <div className="alert-title">
          <span className={`badge badge-${severity === 'CRITICAL' || severity === 'HIGH' ? 'danger' : severity === 'MEDIUM' ? 'warning' : 'success'}`}>
            {severity}
          </span>
          {' '}{title}
        </div>
        <div className="alert-message">{message}</div>
        <div className="alert-meta">
          {records_affected && `${records_affected.toLocaleString()} records affected`}
          {detected_at && ` · ${new Date(detected_at).toLocaleTimeString()}`}
        </div>
      </div>
    </div>
  )
}
