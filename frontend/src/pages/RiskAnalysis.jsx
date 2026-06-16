import { useEffect, useState } from 'react'
import Header from '../components/Layout/Header'
import PlotlyChart from '../components/PlotlyChart'
import { getRisk } from '../api/client'

export default function RiskAnalysis() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getRisk().then(r => { setData(r.data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="main-area">
      <Header title="Risk Analysis" subtitle="SHAP Explainability & Credit Risk Intelligence" />
      <div className="page-content"><div className="loading-state"><div className="spinner" /><span>Computing risk factors…</span></div></div>
    </div>
  )

  const m = data?.model_metrics || {}
  return (
    <div className="main-area">
      <Header title="Risk Analysis" subtitle="SHAP-powered credit risk intelligence" />
      <div className="page-content">
        <div className="page-header">
          <h1>Credit Risk Intelligence</h1>
          <p>SHAP feature importance, risk scoring, and segment-level exposure analysis</p>
        </div>

        {/* Model metrics */}
        <div className="kpi-grid" style={{ marginBottom: 24 }}>
          {[
            { label: 'AUC-ROC Score',  value: m.auc_roc,   icon: '🎯', variant: m.auc_roc > 0.8 ? 'success' : 'warning' },
            { label: 'Model Accuracy', value: `${(m.accuracy*100).toFixed(1)}%`, icon: '✅', variant: 'success' },
            { label: 'Precision',      value: `${(m.precision*100).toFixed(1)}%`, icon: '🔬' },
            { label: 'Recall',         value: `${(m.recall*100).toFixed(1)}%`,    icon: '📡' },
            { label: 'F1 Score',       value: m.f1?.toFixed(3), icon: '⚖️' },
          ].map((item, i) => (
            <div key={i} className={`kpi-card kpi-${item.variant || 'primary'}`} style={{ animationDelay: `${i*60}ms` }}>
              <div className="kpi-icon">{item.icon}</div>
              <div className="kpi-label">{item.label}</div>
              <div className="kpi-value">{item.value || '—'}</div>
              <div className="kpi-sub">RandomForest Classifier</div>
            </div>
          ))}
        </div>

        {/* SHAP + Scatter */}
        <div className="dashboard-grid grid-2" style={{ marginBottom: 20 }}>
          <div className="chart-container">
            <PlotlyChart spec={data?.shap_importance} style={{ minHeight: 380 }} />
          </div>
          <div className="chart-container">
            <PlotlyChart spec={data?.dti_vs_score_scatter} style={{ minHeight: 380 }} />
          </div>
        </div>

        {/* Risk distribution + Segment risk */}
        <div className="dashboard-grid grid-2">
          <div className="chart-container">
            <PlotlyChart spec={data?.risk_distribution} />
          </div>
          <div className="chart-container">
            <PlotlyChart spec={data?.segment_risk} />
          </div>
        </div>

        {/* SHAP interpretation */}
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-title">🔬 How to Interpret SHAP Values</div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            SHAP (SHapley Additive exPlanations) quantifies each feature's contribution to the model's default prediction.
            A higher percentage means the feature is more important in determining whether a customer defaults.
            <strong style={{ color: 'var(--danger)' }}> Previous Defaults</strong> and
            <strong style={{ color: 'var(--warning)' }}> Debt-to-Income Ratio</strong> are the top drivers,
            consistent with industry credit risk literature. SHAP values here are global (portfolio-average) —
            per-customer SHAP breakdowns are available in the AI Assistant.
          </p>
        </div>
      </div>
    </div>
  )
}
