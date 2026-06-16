import { useEffect, useState } from 'react'
import Header from '../components/Layout/Header'
import KPICard from '../components/KPICard'
import PlotlyChart from '../components/PlotlyChart'
import { getOverview } from '../api/client'

export default function ExecutiveOverview() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getOverview().then(r => { setData(r.data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="main-area">
      <Header title="Executive Overview" subtitle="Portfolio Intelligence at a Glance" />
      <div className="page-content">
        <div className="loading-state"><div className="spinner" /><span>Loading portfolio data…</span></div>
      </div>
    </div>
  )

  const k = data?.kpis || {}
  return (
    <div className="main-area">
      <Header
        title="Executive Overview"
        subtitle="Jan 2022 – Dec 2024 · 30,000 records"
        actions={
          <span className="badge badge-primary">📊 Live Portfolio</span>
        }
      />
      <div className="page-content">
        <div className="page-header">
          <h1>Portfolio Intelligence</h1>
          <p>Real-time credit risk overview with AI-powered insights</p>
        </div>

        {/* KPIs */}
        <div className="kpi-grid" style={{ marginBottom: 24 }}>
          <KPICard label="Overall Default Rate" value={`${k.default_rate}%`} icon="📉" variant="danger" sub="Portfolio benchmark: <8% Good" delay={0} />
          <KPICard label="Total Records" value={k.total_records?.toLocaleString()} icon="👥" variant="primary" sub="Active applicants" delay={60} />
          <KPICard label="Portfolio Value" value={`₹${k.total_loan_value_cr} Cr`} icon="💰" variant="success" sub="Total loan amount" delay={120} />
          <KPICard label="Avg Credit Score" value={k.avg_credit_score?.toFixed(0)} icon="🎯" sub="CIBIL scale 300–900" delay={180} />
          <KPICard label="Repeat Defaulters" value={k.high_risk_count?.toLocaleString()} icon="⚠️" variant="warning" sub="2+ previous defaults" delay={240} />
          <KPICard label="High DTI Customers" value={k.high_dti_count?.toLocaleString()} icon="📊" variant="warning" sub="DTI ratio > 40%" delay={300} />
        </div>

        {/* Charts row 1 */}
        <div className="dashboard-grid grid-2" style={{ marginBottom: 20 }}>
          <div className="chart-container">
            <PlotlyChart spec={data?.default_trend} />
          </div>
          <div className="chart-container">
            <PlotlyChart spec={data?.disbursements} />
          </div>
        </div>

        {/* Charts row 2 */}
        <div className="dashboard-grid grid-1-2">
          <div className="chart-container">
            <PlotlyChart spec={data?.portfolio_by_purpose} />
          </div>
          <div className="chart-container">
            <PlotlyChart spec={data?.state_default_rates} style={{ minHeight: 420 }} />
          </div>
        </div>
      </div>
    </div>
  )
}
