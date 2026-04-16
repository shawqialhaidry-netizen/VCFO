import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { PeriodScopeProvider } from './context/PeriodScopeContext.jsx'
import { LangProvider } from './context/LangContext.jsx'
import { CompanyProvider } from './context/CompanyContext.jsx'
import './index.css'
import './styles/premiumCharts.css'
import './styles/arabicFinancialTypography.css'

const AUTH_STORAGE_KEY = 'vcfo_auth'

function readStoredToken() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed?.token || parsed?.access_token || null
  } catch {
    return null
  }
}

function isApiRequest(input) {
  if (typeof input === 'string') return input.startsWith('/api/') || input.includes('/api/')
  if (input instanceof Request) return input.url.startsWith('/api/') || input.url.includes('/api/')
  return false
}

const nativeFetch = window.fetch.bind(window)
window.fetch = async (input, init = {}) => {
  if (!isApiRequest(input)) {
    return nativeFetch(input, init)
  }

  const token = readStoredToken()
  const request = input instanceof Request ? input : null
  const headers = new Headers(init.headers || (request ? request.headers : undefined))

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  if (request) {
    const nextRequest = new Request(request, { ...init, headers })
    return nativeFetch(nextRequest)
  }

  return nativeFetch(input, { ...init, headers })
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <AuthProvider>
      <PeriodScopeProvider>
        <CompanyProvider>
          <LangProvider>
            <App />
          </LangProvider>
        </CompanyProvider>
      </PeriodScopeProvider>
    </AuthProvider>
  </BrowserRouter>
)
