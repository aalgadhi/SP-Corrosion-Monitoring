import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
})

export const getReadings = (params = {}) => api.get('/readings', { params }).then(r => r.data)
export const getDiagnostics = (params = {}) => api.get('/diagnostics', { params }).then(r => r.data)
export const getAlerts = (params = {}) => api.get('/alerts', { params }).then(r => r.data)
export const getStats = () => api.get('/stats').then(r => r.data)

export default api
