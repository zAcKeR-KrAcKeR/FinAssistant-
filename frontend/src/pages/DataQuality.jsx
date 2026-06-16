import { useEffect, useState } from 'react'
import Header from '../components/Layout/Header'
import PlotlyChart from '../components/PlotlyChart'
import AlertCard from '../components/AlertCard'
import { getQuality } from '../api/client'

export default function DataQuality() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getQuality().then(r => { setData(r.data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="main-area">
      <Header title="Data Quality" subtitle="Enterprise Data Health Monitor" />
      <div className="page-content"><div className="loading-state"><div className="spinner" /><span>Running quality checks…</span></div></div>
    </div>
  )

  const qr = data?.quality_report || {}
  const health = qr.overall_health_score || 0
  const healthColor = health > 80 ? 'var(--success)' : health > 60 ? 'var(--warning)' : 'var(--danger)'
  const alerts = data?.alerts || []

  return (
    <div className="main-area">
      <Header title="Data Quality" subtitle="Enterprise Data Health & Anomaly Monitoring" />
      <div className="page-content">
        <div className="page-header">
          <h1>Data Quality Monitor</h1>
          <p>Comprehensive data health assessment with anomaly detection and risk alerts</p>
        </div>

        {/* Health scorecard */}
        <div className="kpi-grid" style={{ marginBottom: 24 }}>
          <div className="kpi-card" style={{ borderColor: healthColor }}>
            <div className="kpi-label">Overall Health Score</div>
            <div className="kpi-value" style={{ color: healthColor }}>{health.toFixed(1)}</div>
            <div className="kpi-sub">Out of 100</div>
          </div>
          <div className="kpi-card"><div className="kpi-label">Total Records</div><div className="kpi-value">{qr.total_records?.toLocaleString()}</div><div className="kpi-sub">Ingested records</div></div>
          <div className="kpi-card kpi-warning"><div className="kpi-label">Rows with Missing</div><div className="kpi-value">{qr.total_missing_pct}%</div><div className="kpi-sub">At least one null field</div></div>
          <div className="kpi-card"><div className="kpi-label">Duplicate Records</div><div className="kpi-value kpi-value">{qr.duplicate_records}</div><div className="kpi-sub">Exact row duplicates</div></div>
          <div className="kpi-card"><div className="kpi-label">Date Range</div><div className="kpi-value" style={{ fontSize: 14, paddingTop: 4 }}>{qr.date_range_start}</div><div className="kpi-sub">to {qr.date_range_end}</div></div>
          <div className="kpi-card kpi-danger"><div className="kpi-label">Default Rate</div><div className="kpi-value">{qr.default_rate_pct}%</div><div className="kpi-sub">Portfolio default rate</div></div>
        </div>

        {/* Risk Alerts */}
        {alerts.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h2 style={{ fontSize: 15, marginBottom: 12, color: 'var(--danger)' }}>
              🚨 Active Risk Alerts ({alerts.length})
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {alerts.map((a, i) => <AlertCard key={i} alert={a} />)}
            </div>
          </div>
        )}

        {/* Charts */}
        <div className="dashboard-grid grid-2" style={{ marginBottom: 20 }}>
          {data?.missing_values_chart && (
            <div className="chart-container"><PlotlyChart spec={data.missing_values_chart} /></div>
          )}
          {data?.outlier_chart && (
            <div className="chart-container"><PlotlyChart spec={data.outlier_chart} /></div>
          )}
        </div>

        <div className="dashboard-grid grid-2" style={{ marginBottom: 20 }}>
          <div className="chart-container">
            <PlotlyChart spec={data?.freshness_chart} />
          </div>
          {data?.anomaly_timeline && (
            <div className="chart-container">
              <PlotlyChart spec={data.anomaly_timeline} />
            </div>
          )}
        </div>

        {/* Missing values detail */}
        {qr.missing_by_column && Object.keys(qr.missing_by_column).length > 0 && (
          <div className="card">
            <div className="card-title">🔍 Missing Values Detail</div>
            <table className="data-table">
              <thead><tr><th>Column</th><th>Missing %</th><th>Imputation Strategy</th><th>Impact</th></tr></thead>
              <tbody>
                {Object.entries(qr.missing_by_column).map(([col, pct]) => (
                  <tr key={col}>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{col}</td>
                    <td style={{ color: pct > 5 ? 'var(--warning)' : 'var(--text-primary)' }}>{pct.toFixed(2)}%</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      {col === 'income' ? 'Segment median' : col === 'savings_ratio' ? 'Fill with 0' : 'Mode imputation'}
                    </td>
                    <td><span className={`badge badge-${pct > 5 ? 'warning' : 'success'}`}>{pct > 5 ? 'Moderate' : 'Low'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
