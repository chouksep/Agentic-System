import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

const API_BASE_URL = '/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const { token } = useAuthStore.getState()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().clearAuth()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authAPI = {
  register: (email: string, password: string, displayName: string) =>
    apiClient.post('/auth/register', { email, password, display_name: displayName }),
  login: (email: string, password: string) =>
    apiClient.post('/auth/login', { email, password }),
  getMe: () => apiClient.get('/auth/me'),
}

export const profilesAPI = {
  create: (data: any) => apiClient.post('/profiles', data),
  list: () => apiClient.get('/profiles'),
  get: (id: string) => apiClient.get(`/profiles/${id}`),
  update: (id: string, data: any) => apiClient.put(`/profiles/${id}`, data),
  delete: (id: string) => apiClient.delete(`/profiles/${id}`),
}

export const callsAPI = {
  start: (profileId: string, callType: string, participantName?: string) =>
    apiClient.post('/calls/start', {
      profile_id: profileId,
      call_type: callType,
      external_participant_name: participantName,
    }),
  end: (callId: string) => apiClient.post(`/calls/${callId}/end`),
  addMetrics: (callId: string, metrics: any) =>
    apiClient.post(`/calls/${callId}/metrics`, metrics),
  addTranscript: (callId: string, transcript: string) =>
    apiClient.post(`/calls/${callId}/transcript`, { transcript }),
  get: (callId: string) => apiClient.get(`/calls/${callId}`),
  list: (limit?: number, offset?: number) =>
    apiClient.get('/calls', { params: { limit, offset } }),
}

export const analyticsAPI = {
  getSummary: () => apiClient.get('/analytics/summary'),
  getTrends: (days?: number) => apiClient.get('/analytics/trends', { params: { days } }),
  getCallSummary: (callId: string) => apiClient.get(`/analytics/call/${callId}/summary`),
}

export default apiClient
