import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import Header from '../components/Layout/Header'
import PlotlyChart from '../components/PlotlyChart'
import ReasoningTrace from '../components/ReasoningTrace'
import VoiceOrb from '../components/VoiceOrb'
import { chat, getExecutive, getExamples } from '../api/client'

// ── Suggested questions ───────────────────────────────────
const SUGGESTED = [
  "Which customer segment has the highest default rate?",
  "How has the default rate changed from 2022 to 2024?",
  "What are the top risk drivers using SHAP analysis?",
  "Which state has the highest default rate and why?",
  "Give me an executive summary of the portfolio",
  "Show me anomalies detected in the data",
]

// ── Message component ──────────────────────────────────────
function AIMessage({ msg }) {
  const [showExec, setShowExec] = useState(false)
  const exec = msg.executive_summary

  const confidencePct = Math.round((msg.confidence || 0) * 100)

  return (
    <div className="message ai animate-in">
      <div className="message-avatar">🤖</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="message-bubble">
          {/* Main answer */}
          <ReactMarkdown>{msg.answer || ''}</ReactMarkdown>

          {/* Executive summary panel */}
          {exec && (
            <div className="exec-banner" style={{ marginTop: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <span className={`exec-health-badge health-${exec.portfolio_health?.replace(' ', '_')}`}>
                  {exec.portfolio_health === 'GOOD' ? '🟢' : exec.portfolio_health === 'AT RISK' ? '🟡' : '🔴'}
                  {' '}{exec.portfolio_health}
                </span>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Portfolio Health</span>
              </div>

              {exec.top_concerns?.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--danger)', marginBottom: 6, letterSpacing: 1, textTransform: 'uppercase' }}>
                    🔴 Top Concerns
                  </div>
                  {exec.top_concerns.map((c, i) => (
                    <div key={i} style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginBottom: 4 }}>
                      {i + 1}. {c}
                    </div>
                  ))}
                </div>
              )}

              {exec.recommended_actions?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--success)', marginBottom: 6, letterSpacing: 1, textTransform: 'uppercase' }}>
                    ✅ Recommended Actions
                  </div>
                  {exec.recommended_actions.map((a, i) => (
                    <div key={i} style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginBottom: 4 }}>
                      {i + 1}. {a}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Inline chart */}
          {msg.chart && (
            <div style={{ marginTop: 14, borderRadius: 12, overflow: 'hidden' }}>
              <PlotlyChart spec={msg.chart} style={{ minHeight: 280 }} />
            </div>
          )}

          {/* Data used */}
          {msg.data_used && (
            <div className="data-used" style={{ marginTop: 12 }}>
              <strong>📊 Data Used:</strong> {msg.data_used.records_analyzed?.toLocaleString()} records ·{' '}
              {msg.data_used.time_period} · {msg.data_used.missing_data_note}
            </div>
          )}

          {/* Confidence */}
          {msg.confidence > 0 && (
            <div className="confidence-row" style={{ marginTop: 10 }}>
              <div className="confidence-label">Confidence</div>
              <div className="confidence-bar">
                <div className="confidence-fill" style={{ width: `${confidencePct}%` }} />
              </div>
              <div className="confidence-pct">{confidencePct}%</div>
            </div>
          )}

          {/* Limitations */}
          {msg.limitations?.length > 0 && (
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
              ⚠️ Limitations: {msg.limitations.join(' · ')}
            </div>
          )}

          {/* Reasoning trace */}
          {msg.reasoning_steps && (
            <ReasoningTrace steps={msg.reasoning_steps} agents={msg.agents_used} />
          )}

          {/* Voice response played indicator */}
          {msg.voice_text && (
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--success)' }}>
              🔊 Voice response played
            </div>
          )}

          {/* Timing */}
          {msg.total_duration_ms > 0 && (
            <div style={{ marginTop: 6, fontSize: 10, color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
              ⚡ {msg.total_duration_ms}ms
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── What-If Panel ──────────────────────────────────────────
function WhatIfPanel({ onSend }) {
  const [param, setParam]     = useState('income')
  const [dir, setDir]         = useState('raise')
  const [changePct, setChangePct] = useState(15)

  const PARAMS = [
    { value: 'income',            label: 'Income Threshold' },
    { value: 'credit_score',      label: 'Credit Score Min' },
    { value: 'dti',               label: 'DTI Ratio Cap' },
    { value: 'credit_utilization', label: 'Credit Utilization Cap' },
  ]

  const handleSend = () => {
    const dirLabel = dir === 'raise' ? 'raised' : 'lowered'
    onSend(`What if the ${PARAMS.find(p=>p.value===param)?.label} is ${dirLabel} by ${changePct}%?`)
  }

  return (
    <div className="whatif-panel">
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 14 }}>
        🔮 What-If Simulator
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 5 }}>Parameter</div>
          <select
            value={param} onChange={e => setParam(e.target.value)}
            className="input" style={{ padding: '7px 10px' }}
          >
            {PARAMS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 5 }}>Direction</div>
          <select
            value={dir} onChange={e => setDir(e.target.value)}
            className="input" style={{ padding: '7px 10px' }}
          >
            <option value="raise">Raise / Tighten</option>
            <option value="lower">Lower / Relax</option>
          </select>
        </div>
      </div>
      <div className="slider-row">
        <div className="slider-label">
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Change Amount</span>
          <span style={{ fontWeight: 700, color: 'var(--primary-l)' }}>{changePct}%</span>
        </div>
        <input
          type="range" min="5" max="50" step="5"
          value={changePct} onChange={e => setChangePct(Number(e.target.value))}
          className="slider"
        />
      </div>
      <button className="btn btn-primary btn-sm" onClick={handleSend} style={{ width: '100%', marginTop: 8 }}>
        🔮 Simulate Impact
      </button>
    </div>
  )
}

// ── Main Assistant Page ────────────────────────────────────
export default function Assistant() {
  const [messages, setMessages]     = useState([])
  const [input, setInput]           = useState('')
  const [loading, setLoading]       = useState(false)
  const [mode, setMode]             = useState('normal')    // normal | executive | voice
  const [showVoice, setShowVoice]   = useState(false)
  const [showWhatIf, setShowWhatIf] = useState(false)
  const [convId]                    = useState(() => `conv_${Date.now()}`)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Add welcome message
  useEffect(() => {
    setMessages([{
      id: 'welcome',
      role: 'ai',
      answer: `**Welcome to FinSight AI — Your Financial Intelligence Copilot** 🎯\n\nI'm powered by **Mistral AI** with a 5-module analytical pipeline:\n\n• 🔍 **Query Understanding** — I classify what you're asking\n• 📊 **Data Analysis** — I run pandas computations on 30,000 records\n• 💡 **Insight Generation** — I identify patterns and causes\n• 🛡️ **Risk Assessment** — I apply SHAP-based risk scoring\n• 📋 **Recommendation Engine** — I suggest data-backed business actions\n\nAsk me anything about the credit portfolio — or tap the **🎙️ Voice** button to speak your question!`,
      reasoning_steps: [],
      agents_used: [],
    }])
  }, [])

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || loading) return
    const userMsg = { id: Date.now(), role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await chat(text, convId, mode, mode === 'voice')
      const aiMsg = { id: Date.now() + 1, role: 'ai', ...res.data }
      setMessages(prev => [...prev, aiMsg])
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1, role: 'ai',
        answer: `**Error:** ${err.response?.data?.error || err.message || 'Something went wrong. Is the backend running?'}`,
        reasoning_steps: [], agents_used: [],
      }])
    } finally {
      setLoading(false)
    }
  }, [loading, convId, mode])

  const handleVoiceResponse = useCallback(({ transcript, response }) => {
    const userMsg = { id: Date.now(), role: 'user', content: `🎙️ ${transcript}` }
    const aiMsg   = { id: Date.now() + 1, role: 'ai', ...response }
    setMessages(prev => [...prev, userMsg, aiMsg])
  }, [])

  const handleExecutive = async () => {
    setLoading(true)
    try {
      const res = await getExecutive()
      const aiMsg = { id: Date.now(), role: 'ai', ...res.data }
      setMessages(prev => [...prev, aiMsg])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) }
  }

  return (
    <div className="main-area">
      <Header
        title="AI Assistant"
        subtitle="Mistral AI · 5-Module Pipeline · Voice Enabled"
        actions={
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className={`btn btn-sm ${showVoice ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setShowVoice(!showVoice)}
            >🎙️ Voice</button>
            <button
              className={`btn btn-sm ${showWhatIf ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setShowWhatIf(!showWhatIf)}
            >🔮 What-If</button>
            <button className="btn btn-sm btn-ghost" onClick={handleExecutive} disabled={loading}>
              👔 CEO Summary
            </button>
          </div>
        }
      />

      <div style={{ display: 'flex', height: 'calc(100vh - var(--header-h))', overflow: 'hidden' }}>
        {/* Main chat */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Messages */}
          <div className="chat-messages">
            {messages.map(msg => (
              <div key={msg.id}>
                {msg.role === 'user' ? (
                  <div className="message user animate-in">
                    <div className="message-avatar">👤</div>
                    <div className="message-bubble">{msg.content}</div>
                  </div>
                ) : (
                  <AIMessage msg={msg} />
                )}
              </div>
            ))}

            {loading && (
              <div className="message ai">
                <div className="message-avatar">🤖</div>
                <div className="message-bubble">
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                    Running analytical pipeline…
                  </div>
                  <div className="thinking">
                    <div className="thinking-dot" /><div className="thinking-dot" /><div className="thinking-dot" />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Suggested queries */}
          {messages.length <= 1 && (
            <div style={{ padding: '0 20px 12px', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {SUGGESTED.map((q, i) => (
                <button
                  key={i}
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: 11 }}
                  onClick={() => sendMessage(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {/* Input area */}
          <div className="chat-input-area">
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
              <div style={{ flex: 1, position: 'relative' }}>
                <textarea
                  className="input"
                  style={{ resize: 'none', minHeight: 44, maxHeight: 120, paddingRight: 44 }}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about the credit portfolio… or use 🎙️ Voice"
                  rows={1}
                />
              </div>

              <div style={{ display: 'flex', gap: 6 }}>
                {/* Mode selector */}
                <select
                  value={mode}
                  onChange={e => setMode(e.target.value)}
                  className="input"
                  style={{ width: 'auto', padding: '10px 8px', fontSize: 12 }}
                >
                  <option value="normal">Normal</option>
                  <option value="executive">CEO Mode</option>
                </select>

                <button
                  className="btn btn-primary"
                  onClick={() => sendMessage(input)}
                  disabled={loading || !input.trim()}
                  style={{ minWidth: 44, justifyContent: 'center' }}
                >
                  {loading ? <div className="spinner" style={{ width: 18, height: 18 }} /> : '→'}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Side panel */}
        {(showVoice || showWhatIf) && (
          <div style={{
            width: 300, borderLeft: '1px solid var(--border-light)',
            background: 'var(--bg-surface)', display: 'flex', flexDirection: 'column', gap: 0,
          }}>
            {showVoice && (
              <div style={{ padding: 16, borderBottom: '1px solid var(--border-light)' }}>
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--primary-l)' }}>
                  🎙️ Voice Assistant
                </div>
                <VoiceOrb
                  onResponse={handleVoiceResponse}
                  conversationId={convId}
                  disabled={loading}
                />
              </div>
            )}
            {showWhatIf && (
              <div style={{ padding: 16 }}>
                <WhatIfPanel onSend={sendMessage} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
