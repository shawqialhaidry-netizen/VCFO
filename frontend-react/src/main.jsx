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

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
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
  </React.StrictMode>
)
