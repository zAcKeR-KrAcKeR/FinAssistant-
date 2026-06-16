import { useState, useRef, useEffect, useCallback } from 'react'
import { voiceQuery } from '../api/client'

/**
 * VoiceOrb — Full voice interaction component
 * 
 * Flow:
 *   1. User taps orb → browser asks mic permission
 *   2. Web Speech API (SpeechRecognition) transcribes speech in real-time
 *   3. On silence/end → transcript sent to /api/voice/query
 *   4. Multi-agent pipeline processes → returns answer + voice_text
 *   5. SpeechSynthesis speaks the voice_text
 *   6. Chat messages updated with full response
 */
export default function VoiceOrb({ onResponse, conversationId = 'default', disabled = false }) {
  const [status, setStatus]     = useState('idle')  // idle | listening | processing | speaking
  const [transcript, setTranscript] = useState('')
  const [error, setError]       = useState('')
  const [supported, setSupported] = useState(true)

  const recognitionRef  = useRef(null)
  const synthRef        = useRef(window.speechSynthesis)
  const transcriptRef   = useRef('')

  // Check support on mount
  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      setSupported(false)
      setError('Voice not supported in this browser. Use Chrome or Edge.')
    }
  }, [])

  // Cancel speech on unmount
  useEffect(() => {
    return () => {
      synthRef.current?.cancel()
      recognitionRef.current?.stop()
    }
  }, [])

  // ── Speak text via SpeechSynthesis ───────────────────────
  const speak = useCallback((text) => {
    if (!text || !synthRef.current) return
    synthRef.current.cancel()
    const utt = new SpeechSynthesisUtterance(text)
    
    // Pick a good English voice
    const voices = synthRef.current.getVoices()
    const preferred = voices.find(v =>
      (v.lang.startsWith('en') && (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Neural')))
    ) || voices.find(v => v.lang.startsWith('en')) || null
    if (preferred) utt.voice = preferred

    utt.rate   = 0.92
    utt.pitch  = 1.0
    utt.volume = 1.0
    utt.lang   = 'en-IN'

    utt.onstart = () => setStatus('speaking')
    utt.onend   = () => setStatus('idle')
    utt.onerror = () => setStatus('idle')

    synthRef.current.speak(utt)
    setStatus('speaking')
  }, [])

  // ── Stop speaking ─────────────────────────────────────────
  const stopSpeaking = useCallback(() => {
    synthRef.current?.cancel()
    setStatus('idle')
  }, [])

  // ── Send transcript to backend ────────────────────────────
  const processTranscript = useCallback(async (text) => {
    if (!text.trim()) {
      setStatus('idle')
      return
    }
    setStatus('processing')
    setTranscript(text)

    try {
      const res = await voiceQuery(text, conversationId)
      const data = res.data
      
      // Notify parent with full response
      if (onResponse) onResponse({ transcript: text, response: data })

      // Speak the voice-optimised response
      const voiceText = data.voice_text || data.answer?.replace(/[*#_`]/g, '') || ''
      speak(voiceText)

    } catch (err) {
      console.error('Voice query error:', err)
      setError('Sorry, something went wrong. Please try again.')
      speak('Sorry, I encountered an error. Please try again.')
      setStatus('idle')
    }
  }, [conversationId, onResponse, speak])

  // ── Start listening ───────────────────────────────────────
  const startListening = useCallback(() => {
    if (!supported || status !== 'idle') return
    setError('')
    setTranscript('')
    transcriptRef.current = ''

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SR()
    recognitionRef.current = recognition

    recognition.lang            = 'en-IN'
    recognition.interimResults  = true
    recognition.continuous      = false
    recognition.maxAlternatives = 1

    recognition.onstart = () => setStatus('listening')

    recognition.onresult = (e) => {
      let interim = '', final = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) final += t
        else interim += t
      }
      const current = (transcriptRef.current + final) || interim
      setTranscript(current)
      if (final) transcriptRef.current += final
    }

    recognition.onend = () => {
      const finalText = transcriptRef.current.trim()
      if (finalText) processTranscript(finalText)
      else setStatus('idle')
    }

    recognition.onerror = (e) => {
      if (e.error === 'no-speech') {
        setStatus('idle')
        setTranscript('')
      } else if (e.error === 'not-allowed') {
        setError('Microphone permission denied. Please allow microphone access.')
        setStatus('idle')
      } else {
        setError(`Voice error: ${e.error}`)
        setStatus('idle')
      }
    }

    recognition.start()
  }, [supported, status, processTranscript])

  // ── Stop listening ────────────────────────────────────────
  const stopListening = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  // ── Handle orb click ──────────────────────────────────────
  const handleOrbClick = useCallback(() => {
    if (status === 'speaking') { stopSpeaking(); return }
    if (status === 'listening') { stopListening(); return }
    if (status === 'idle')      { startListening(); return }
  }, [status, startListening, stopListening, stopSpeaking])

  // ── UI ────────────────────────────────────────────────────
  const orbIcon = {
    idle:       '🎙️',
    listening:  '🔴',
    processing: '⚡',
    speaking:   '🔊',
  }[status]

  const statusText = {
    idle:       'Tap to speak',
    listening:  'Listening… speak your question',
    processing: 'FinSight AI is thinking…',
    speaking:   'Speaking response — tap to stop',
  }[status]

  if (!supported) {
    return (
      <div style={{ textAlign: 'center', padding: '16px', color: 'var(--text-muted)', fontSize: 12 }}>
        🎙️ Voice not supported — use Chrome or Edge
      </div>
    )
  }

  return (
    <div className="voice-orb-container">
      {/* Waveform animation when listening */}
      {status === 'listening' && (
        <div className="voice-waveform">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="wave-bar" style={{ height: `${8 + Math.random() * 20}px` }} />
          ))}
        </div>
      )}

      {/* Waveform when speaking */}
      {status === 'speaking' && (
        <div className="voice-waveform">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="wave-bar" style={{ background: 'var(--success)' }} />
          ))}
        </div>
      )}

      {/* The Orb */}
      <button
        className={`voice-orb ${status !== 'idle' ? status : ''}`}
        onClick={handleOrbClick}
        disabled={disabled || status === 'processing'}
        title={statusText}
      >
        <span style={{ pointerEvents: 'none' }}>{orbIcon}</span>
      </button>

      {/* Status text */}
      <div className="voice-status">{statusText}</div>

      {/* Live transcript */}
      {transcript && (
        <div className="voice-transcript">
          "{transcript}"
        </div>
      )}

      {/* Processing indicator */}
      {status === 'processing' && (
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
          <div className="thinking">
            <div className="thinking-dot" />
            <div className="thinking-dot" />
            <div className="thinking-dot" />
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Running through AI modules…
          </span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{ fontSize: 11, color: 'var(--danger)', textAlign: 'center', maxWidth: 240 }}>
          {error}
        </div>
      )}

      {/* Tips */}
      {status === 'idle' && !error && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', maxWidth: 260, lineHeight: 1.5 }}>
          Try: <em>"Which segment has the highest default rate?"</em>
          <br />or: <em>"Give me an executive summary"</em>
        </div>
      )}
    </div>
  )
}
