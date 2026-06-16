import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

export const chat = (message, conversationId = 'default', mode = 'normal', voiceMode = false) =>
  api.post('/api/chat', { message, conversation_id: conversationId, mode, voice_mode: voiceMode })

export const voiceQuery = (transcript, conversationId = 'default') =>
  api.post('/api/voice/query', { transcript, conversation_id: conversationId })

export const getOverview      = () => api.get('/api/dashboard/overview')
export const getRisk          = () => api.get('/api/dashboard/risk')
export const getSegmentation  = () => api.get('/api/dashboard/segmentation')
export const getQuality       = () => api.get('/api/dashboard/quality')
export const getExecutive     = () => api.get('/api/executive')
export const getExamples      = () => api.get('/api/examples')
export const getHealth        = () => api.get('/health')

export const runWhatIf = (parameter, direction, changePct) =>
  api.post('/api/whatif', { parameter, direction, change_pct: changePct })

export default api
