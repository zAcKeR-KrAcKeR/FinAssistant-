import { useState, useRef, useEffect, useCallback } from 'react'
import { voiceQuery } from '../api/client'

const HINDI_CLOSING = 'Kya main aapki aur koi madad kar sakti hoon?'
const ENGLISH_CLOSING = 'Is there anything else I can help you with?'

function detectHindi(text) {
  // Devanagari unicode range OR common Hindi romanized words
  if (/[ऀ-ॿ]/.test(text)) return true
  const hindiWords = /\b(kya|hai|mera|meri|ka|ki|ko|se|aaj|kal|kitna|kitni|batao|bolo|hota|hoti|karo|kaise|kaun|kahan|kyun|woh|yeh|aur|nahi|haan|theek|bahut|bohot|accha|zyada|kam|sab|kuch|paise|rupay|loan|default|portfolio|segment|risk)\b/i
  return hindiWords.test(text)
}

function pickVoice(synth, isHindi) {
  const voices = synth.getVoices()
  if (isHindi) {
    // Try Hindi voices first
    const hindiVoice = voices.find(v => v.lang === 'hi-IN') ||
                       voices.find(v => v.lang.startsWith('hi'))
    if (hindiVoice) return hindiVoice
  }
  // English Indian voice
  return voices.find(v => v.lang === 'en-IN' && (v.name.includes('Google') || v.name.includes('Neural') || v.name.includes('Natural'))) ||
         voices.find(v => v.lang === 'en-IN') ||
         voices.find(v => v.lang.startsWith('en') && v.name.includes('Google')) ||
         voices.find(v => v.lang.startsWith('en')) ||
         null
}

export default function VoiceOrb({ onResponse, conversationId = 'default', disabled = false }) {
  const [status, setStatus]       = useState('idle')   // idle | listening | processing | speaking
  const [transcript, setTranscript] = useState('')
  const [error, setError]         = useState('')
  const [supported, setSupported] = useState(true)
  const [isHindi, setIsHindi]     = useState(false)
  const [continuous, setContinuous] = useState(false)   // continuous mode toggle

  const recognitionRef  = useRef(null)
  const synthRef        = useRef(window.speechSynthesis)
  const transcriptRef   = useRef('')
  const continuousRef   = useRef(false)   // ref mirror for callbacks
  const statusRef       = useRef('idle')

  // Keep refs in sync
  useEffect(() => { continuousRef.current = continuous }, [continuous])
  useEffect(() => { statusRef.current = status }, [status])

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      setSupported(false)
      setError('Voice not supported. Use Chrome or Edge.')
    }
    // Pre-load voices
    synthRef.current?.getVoices()
  }, [])

  useEffect(() => {
    return () => {
      synthRef.current?.cancel()
      recognitionRef.current?.abort()
    }
  }, [])

  // ── Speak ─────────────────────────────────────────────────
  const speak = useCallback((text, hindi, onDone) => {
    if (!text || !synthRef.current) { onDone?.(); return }
    synthRef.current.cancel()

    const utt = new SpeechSynthesisUtterance(text)
    const voice = pickVoice(synthRef.current, hindi)
    if (voice) utt.voice = voice

    utt.lang   = hindi ? 'hi-IN' : 'en-IN'
    utt.rate   = hindi ? 0.88 : 0.90
    utt.pitch  = hindi ? 1.05 : 1.0
    utt.volume = 1.0

    utt.onstart = () => setStatus('speaking')
    utt.onend   = () => { onDone?.() }
    utt.onerror = () => { onDone?.() }

    synthRef.current.speak(utt)
    setStatus('speaking')
  }, [])

  const stopSpeaking = useCallback(() => {
    synthRef.current?.cancel()
    setStatus('idle')
  }, [])

  // ── Start listening (defined after processTranscript via ref) ─
  const startListeningRef = useRef(null)

  // ── Process transcript ────────────────────────────────────
  const processTranscript = useCallback(async (text) => {
    if (!text.trim()) { setStatus('idle'); return }

    const hindi = detectHindi(text)
    setIsHindi(hindi)
    setStatus('processing')
    setTranscript(text)

    try {
      const res = await voiceQuery(text, conversationId)
      const data = res.data

      if (onResponse) onResponse({ transcript: text, response: data })

      const voiceText = data.voice_text || data.answer?.replace(/[*#_`•→↳]/g, '') || ''
      const closing = hindi ? HINDI_CLOSING : ENGLISH_CLOSING
      const fullSpoken = voiceText + '  ' + closing

      speak(fullSpoken, hindi, () => {
        // After speaking — if continuous mode, restart listening
        if (continuousRef.current) {
          setTimeout(() => {
            setStatus('idle')
            setTranscript('')
            startListeningRef.current?.()
          }, 600)
        } else {
          setStatus('idle')
        }
      })

    } catch (err) {
      console.error('Voice query error:', err)
      const errMsg = isHindi
        ? 'Maafi chahti hoon, kuch galat ho gaya. Dobara try karein.'
        : 'Sorry, something went wrong. Please try again.'
      speak(errMsg, isHindi, () => setStatus('idle'))
    }
  }, [conversationId, onResponse, speak, isHindi])

  // ── Start listening ───────────────────────────────────────
  const startListening = useCallback(() => {
    if (!supported || statusRef.current !== 'idle') return
    setError('')
    setTranscript('')
    transcriptRef.current = ''

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SR()
    recognitionRef.current = recognition

    // Accept both Hindi and English
    recognition.lang            = 'hi-IN'   // hi-IN handles Hinglish too
    recognition.interimResults  = true
    recognition.continuous      = false
    recognition.maxAlternatives = 3

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
      else {
        setStatus('idle')
        // In continuous mode, restart even on silence
        if (continuousRef.current) {
          setTimeout(() => startListeningRef.current?.(), 500)
        }
      }
    }

    recognition.onerror = (e) => {
      if (e.error === 'no-speech') {
        setStatus('idle')
        setTranscript('')
        if (continuousRef.current) {
          setTimeout(() => startListeningRef.current?.(), 500)
        }
      } else if (e.error === 'not-allowed') {
        setError('Microphone permission denied. Please allow mic access.')
        setStatus('idle')
        setContinuous(false)
      } else {
        setStatus('idle')
      }
    }

    recognition.start()
  }, [supported, processTranscript])

  // Keep ref updated
  useEffect(() => { startListeningRef.current = startListening }, [startListening])

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  // ── Toggle continuous mode ────────────────────────────────
  const toggleContinuous = useCallback(() => {
    setContinuous(prev => {
      const next = !prev
      if (next && statusRef.current === 'idle') {
        setTimeout(() => startListeningRef.current?.(), 100)
      }
      if (!next) {
        recognitionRef.current?.stop()
        synthRef.current?.cancel()
        setStatus('idle')
      }
      return next
    })
  }, [])

  // ── Orb click ─────────────────────────────────────────────
  const handleOrbClick = useCallback(() => {
    if (continuous) { toggleContinuous(); return }
    if (status === 'speaking')  { stopSpeaking(); return }
    if (status === 'listening') { stopListening(); return }
    if (status === 'idle')      { startListening(); return }
  }, [status, continuous, startListening, stopListening, stopSpeaking, toggleContinuous])

  // ── Icons & text ──────────────────────────────────────────
  const orbIcon = {
    idle:       continuous ? '🔁' : '🎙️',
    listening:  '🔴',
    processing: '⚡',
    speaking:   '🔊',
  }[status]

  const statusText = {
    idle:       continuous ? 'Continuous mode — tap to stop' : 'Tap to speak',
    listening:  isHindi ? 'Sun rahi hoon… boliye' : 'Listening… speak now',
    processing: isHindi ? 'Soch rahi hoon…' : 'FinSight AI is thinking…',
    speaking:   isHindi ? 'Bol rahi hoon — tap to stop' : 'Speaking — tap to stop',
  }[status]

  if (!supported) {
    return (
      <div style={{ textAlign: 'center', padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>
        🎙️ Voice not supported — use Chrome or Edge
      </div>
    )
  }

  return (
    <div className="voice-orb-container">
      {/* Waveform */}
      {(status === 'listening' || status === 'speaking') && (
        <div className="voice-waveform">
          {[...Array(7)].map((_, i) => (
            <div
              key={i}
              className="wave-bar"
              style={status === 'speaking' ? { background: 'var(--success)' } : {}}
            />
          ))}
        </div>
      )}

      {/* Main Orb */}
      <button
        className={`voice-orb ${status !== 'idle' ? status : ''} ${continuous ? 'continuous' : ''}`}
        onClick={handleOrbClick}
        disabled={disabled || status === 'processing'}
        title={statusText}
      >
        <span style={{ pointerEvents: 'none' }}>{orbIcon}</span>
      </button>

      {/* Continuous toggle button */}
      <button
        onClick={toggleContinuous}
        style={{
          background: continuous ? 'var(--accent)' : 'rgba(255,255,255,0.07)',
          border: `1px solid ${continuous ? 'var(--accent)' : 'rgba(255,255,255,0.15)'}`,
          borderRadius: 20,
          padding: '4px 14px',
          fontSize: 11,
          color: continuous ? '#fff' : 'var(--text-muted)',
          cursor: 'pointer',
          marginTop: 4,
          transition: 'all 0.2s',
        }}
        title="Keep mic on continuously after each answer"
      >
        {continuous ? '🔁 Continuous ON' : '🔁 Go Continuous'}
      </button>

      <div className="voice-status">{statusText}</div>

      {transcript && (
        <div className="voice-transcript">"{transcript}"</div>
      )}

      {status === 'processing' && (
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
          <div className="thinking">
            <div className="thinking-dot" />
            <div className="thinking-dot" />
            <div className="thinking-dot" />
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {isHindi ? 'Vishleshan ho raha hai…' : 'Running AI modules…'}
          </span>
        </div>
      )}

      {error && (
        <div style={{ fontSize: 11, color: 'var(--danger)', textAlign: 'center', maxWidth: 240 }}>
          {error}
        </div>
      )}

      {status === 'idle' && !error && !continuous && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', maxWidth: 260, lineHeight: 1.6 }}>
          Hindi mein bhi pooch sakte hain 🇮🇳<br />
          <em>"Sabse zyada default kaun sa segment hai?"</em>
        </div>
      )}
    </div>
  )
}
