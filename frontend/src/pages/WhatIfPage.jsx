import { useState, useEffect } from 'react'
import Header from '../components/Layout/Header'
import PlotlyChart from '../components/PlotlyChart'
import { runWhatIf } from '../api/client'

const PARAMS = [
  { value: 'income',            label: 'Minimum Income Threshold', icon: '💰', dir: 'raise',
    description: 'Raise the income floor for loan eligibility' },
  { value: 'credit_score',      label: 'Minimum Credit Score', icon: '🎯', dir: 'raise',
    description: 'Tighten credit score eligibility threshold' },
  { value: 'dti',               label: 'Maximum DTI Ratio Cap', icon: '📊', dir: 'lower',
    description: 'Reduce maximum allowable debt-to-income ratio' },
  { value: 'credit_utilization', label: 'Credit Utilization Cap', icon: '💳', dir: 'lower',
    description: 'Cap credit utilization for approval eligibility' },
]

export default function WhatIfPage() {
  const [param, setParam]         = useState('income')
  const [changePct, setChangePct] = useState(15)
  const [result, setResult]       = useState(null)
  const [loading, setLoading]     = useState(false)

  const selectedParam = PARAMS.find(p => p.value === param)

  const simulate = async () => {
    setLoading(true)
    try {
      const res = await runWhatIf(param, selectedParam.dir, changePct)
      setResult(res.data)
    } finally {
      setLoading(false)
    }
  }

  // Chart comparing baseline vs scenario
  const comparisonChart = result ? {
    data: [
      {
        type: 'bar', name: 'Baseline',
        x: ['Default Rate (%)', 'Approval Rate (%)'],
        y: [result.comparison.baseline.default_rate_pct, result.comparison.baseline.approval_rate_pct],
        marker: { color: '#6366f1' },
      },
      {
        type: 'bar', name: 'Scenario',
        x: ['Default Rate (%)', 'Approval Rate (%)'],
        y: [result.comparison.scenario.default_rate_pct, result.comparison.scenario.approval_rate_pct],
        marker: { color: result.default_rate_change_pp < 0 ? '#10b981' : '#ef4444' },
      },
    ],
    layout: {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#e2e8f0', family: 'Inter, sans-serif' },
      xaxis: { gridcolor: 'rgba(255,255,255,0.06)', color: '#94a3b8' },
      yaxis: { gridcolor: 'rgba(255,255,255,0.06)', color: '#94a3b8', title: 'Percentage (%)' },
      barmode: 'group',
      legend: { bgcolor: 'rgba(0,0,0,0)' },
      margin: { l: 50, r: 20, t: 30, b: 40 },
      title: { text: 'Baseline vs. Scenario Impact', font: { size: 14, color: '#e2e8f0' } },
    },
  } : null

  return (
    <div className="main-area">
      <Header title="What-If Simulator" subtitle="Simulate policy changes and measure portfolio impact" />
      <div className="page-content">
        <div className="page-header">
          <h1>Policy What-If Simulator</h1>
          <p>Simulate underwriting policy changes and quantify the impact on default rates, approval rates, and portfolio composition</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: 20 }}>
          {/* Control panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="card">
              <div className="card-title">🔧 Simulation Parameters</div>

              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>Select Policy Parameter</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {PARAMS.map(p => (
                    <button
                      key={p.value}
                      onClick={() => setParam(p.value)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '10px 12px', borderRadius: 10, cursor: 'pointer',
                        border: `1px solid ${param === p.value ? 'var(--primary)' : 'var(--border)'}`,
                        background: param === p.value ? 'rgba(99,102,241,0.12)' : 'var(--bg-card)',
                        color: param === p.value ? 'var(--primary-l)' : 'var(--text-secondary)',
                        textAlign: 'left',
                      }}
                    >
                      <span>{p.icon}</span>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>{p.label}</div>
                        <div style={{ fontSize: 11, opacity: 0.7 }}>{p.description}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="slider-row">
                <div className="slider-label">
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    {selectedParam?.dir === 'raise' ? 'Raise by' : 'Reduce by'}
                  </span>
                  <span style={{ fontWeight: 800, color: 'var(--primary-l)', fontSize: 16 }}>{changePct}%</span>
                </div>
                <input
                  type="range" min="5" max="50" step="5"
                  value={changePct} onChange={e => setChangePct(Number(e.target.value))}
                  className="slider" style={{ margin: '8px 0' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)' }}>
                  <span>5%</span><span>50%</span>
                </div>
              </div>

              <button
                className="btn btn-primary"
                style={{ width: '100%', marginTop: 12, justifyContent: 'center' }}
                onClick={simulate}
                disabled={loading}
              >
                {loading ? <><div className="spinner" style={{ width: 16, height: 16 }} /> Simulating…</> : '🔮 Run Simulation'}
              </button>
            </div>
          </div>

          {/* Results */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {!result && !loading && (
              <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300, color: 'var(--text-muted)', flexDirection: 'column', gap: 12 }}>
                <span style={{ fontSize: 48 }}>🔮</span>
                <div style={{ fontSize: 14 }}>Select a parameter and run simulation to see impact</div>
              </div>
            )}

            {loading && (
              <div className="card loading-state"><div className="spinner" /><span>Running portfolio simulation…</span></div>
            )}

            {result && (
              <>
                {/* Interpretation */}
                <div className="card" style={{ background: 'rgba(99,102,241,0.06)', borderColor: 'rgba(99,102,241,0.25)' }}>
                  <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6 }}>
                    💡 {result.interpretation}
                  </div>
                </div>

                {/* Impact metrics */}
                <div className="impact-row">
                  <div className="impact-item">
                    <div className={`impact-val ${result.default_rate_change_pp < 0 ? 'impact-down' : 'impact-up'}`}>
                      {result.default_rate_change_pp > 0 ? '+' : ''}{result.default_rate_change_pp?.toFixed(1)}pp
                    </div>
                    <div className="impact-label">Default Rate Change</div>
                  </div>
                  <div className="impact-item">
                    <div className="impact-val impact-up">-{result.applications_rejected?.toLocaleString()}</div>
                    <div className="impact-label">Applications Rejected</div>
                  </div>
                  <div className="impact-item">
                    <div className="impact-val impact-down">+{result.defaults_prevented?.toLocaleString()}</div>
                    <div className="impact-label">Defaults Prevented</div>
                  </div>
                  <div className="impact-item">
                    <div className="impact-val">{result.comparison.scenario.approval_rate_pct?.toFixed(1)}%</div>
                    <div className="impact-label">New Approval Rate</div>
                  </div>
                </div>

                {/* Comparison chart */}
                <div className="chart-container">
                  <PlotlyChart spec={comparisonChart} />
                </div>

                {/* Metric comparison table */}
                <div className="card">
                  <div className="card-title">📋 Baseline vs Scenario Metrics</div>
                  <div className="metric-compare">
                    <div className="metric-col">
                      <div className="metric-col-label">📊 Baseline (Current)</div>
                      {Object.entries(result.comparison.baseline).map(([k, v]) => (
                        <div key={k} className="metric-row">
                          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                            {k.replace(/_/g, ' ').replace('pct', '%')}
                          </span>
                          <span style={{ fontWeight: 600 }}>
                            {typeof v === 'number' ? (k.includes('income') ? `₹${(v/100000).toFixed(1)}L` : `${v.toFixed(2)}${k.includes('pct') || k.includes('score') ? '' : ''}`) : v}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="metric-col">
                      <div className="metric-col-label">🔮 Scenario (After)</div>
                      {Object.entries(result.comparison.scenario).map(([k, v]) => {
                        const base = result.comparison.baseline[k]
                        const changed = typeof v === 'number' && typeof base === 'number' && Math.abs(v - base) > 0.01
                        const better = k === 'default_rate_pct' ? v < base : v > base
                        return (
                          <div key={k} className="metric-row">
                            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                              {k.replace(/_/g, ' ').replace('pct', '%')}
                            </span>
                            <span style={{ fontWeight: 600, color: changed ? (better ? 'var(--success)' : 'var(--danger)') : 'var(--text-primary)' }}>
                              {typeof v === 'number' ? (k.includes('income') ? `₹${(v/100000).toFixed(1)}L` : `${v.toFixed(2)}`) : v}
                              {changed && (better ? ' ↑' : ' ↓')}
                            </span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
