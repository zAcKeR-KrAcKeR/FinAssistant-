import { useEffect, useState } from 'react'
import Header from '../components/Layout/Header'
import PlotlyChart from '../components/PlotlyChart'
import { getSegmentation } from '../api/client'

export default function CustomerSegmentation() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSegmentation().then(r => { setData(r.data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="main-area">
      <Header title="Customer Segmentation" subtitle="Behavioural & Risk Profiling" />
      <div className="page-content"><div className="loading-state"><div className="spinner" /><span>Analysing segments…</span></div></div>
    </div>
  )

  const matrix = data?.segment_matrix || []
  const riskColors = { CRITICAL: 'var(--danger)', HIGH: 'var(--warning)', MEDIUM: 'var(--primary-l)', LOW: 'var(--success)' }

  return (
    <div className="main-area">
      <Header title="Customer Segmentation" subtitle="Behavioural analysis across 5 customer segments" />
      <div className="page-content">
        <div className="page-header">
          <h1>Customer Behaviour & Risk Profiling</h1>
          <p>Segmentation-level analysis to identify at-risk cohorts and opportunity segments</p>
        </div>

        {/* Charts row 1 */}
        <div className="dashboard-grid grid-2" style={{ marginBottom: 20 }}>
          <div className="chart-container">
            <PlotlyChart spec={data?.segment_distribution} />
          </div>
          <div className="chart-container">
            <PlotlyChart spec={data?.income_by_segment} />
          </div>
        </div>

        {/* Charts row 2 */}
        <div className="dashboard-grid grid-2" style={{ marginBottom: 20 }}>
          <div className="chart-container">
            <PlotlyChart spec={data?.age_distribution} />
          </div>
          <div className="chart-container">
            <PlotlyChart spec={data?.employment_default_rates} />
          </div>
        </div>

        {/* Segment matrix table */}
        <div className="card">
          <div className="card-title">📋 Segment Risk Matrix</div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Segment</th><th>Count</th><th>Default Rate</th>
                  <th>Avg Income</th><th>Avg DTI</th><th>Avg Util</th><th>Avg Score</th><th>Risk</th>
                </tr>
              </thead>
              <tbody>
                {matrix.map((row, i) => {
                  const dr = row.default_rate_pct
                  const tier = dr > 15 ? 'CRITICAL' : dr > 12 ? 'HIGH' : dr > 8 ? 'MEDIUM' : 'LOW'
                  return (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{row.customer_segment}</td>
                      <td>{row.count?.toLocaleString()}</td>
                      <td style={{ color: riskColors[tier], fontWeight: 700 }}>{dr?.toFixed(1)}%</td>
                      <td>₹{(row.avg_income/100000).toFixed(1)}L</td>
                      <td>{row.avg_dti?.toFixed(1)}%</td>
                      <td>{row.avg_util?.toFixed(1)}%</td>
                      <td>{row.avg_score?.toFixed(0)}</td>
                      <td><span className={`badge badge-${tier === 'CRITICAL' || tier === 'HIGH' ? 'danger' : tier === 'MEDIUM' ? 'warning' : 'success'}`}>{tier}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
