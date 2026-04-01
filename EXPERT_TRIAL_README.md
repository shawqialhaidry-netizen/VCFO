# VCFO — Expert Trial Build
## Virtual CFO Intelligence Platform

---

## What is VCFO?

VCFO transforms a raw accounting trial balance into:
- Full financial statements (IS / BS / CF)
- AI-powered insights with causes, actions, and forecasts
- CFO-level decisions with urgency and expected impact
- Interactive AI CFO assistant

---

## Quick Start (Local)

### Backend
```bash
cd vcfo
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend-react
npm install
npm run dev
# Open http://localhost:5173
```

### Production Build
```bash
cd frontend-react
npm run build
# Serve dist/ with any static server
# Backend must be accessible at /api or set VITE_API_BASE_URL
```

---

## Getting Started

1. Register a new account on the login screen
2. Create your company profile
3. Upload a trial balance CSV (monthly `YYYY-MM` or annual `YYYY`)
4. All screens and AI analysis update automatically

---

## Navigation Flow for Reviewers

| Screen | URL | What to check |
|--------|-----|---------------|
| Dashboard | `/` | KPI cards, sparklines, AI insight+cause+forecast |
| Executive | `/executive` | Health score, decisions, root causes, domain grid |
| Statements | `/statements` | IS/BS/CF comparison, balance status, reliability badge |
| Analysis | `/analysis` | Ratios, trends, MetricCards with insight chain |
| Upload | `/upload` | TB upload, period management, auto-detect |
| AI CFO | Click 🧠 in top bar | Natural language financial Q&A |

---

## Expert Evaluation Areas

1. **Statements Accuracy** — Do IS/BS/CF values match the uploaded trial balance?
2. **AI Insight Quality** — Is the insight → cause → action → forecast chain coherent?
3. **Decision Relevance** — Are CFO decisions specific, urgent, and backed by ratios?
4. **Forecast Reliability** — Are confidence levels transparent and risk-labeled?
5. **UX & Navigation** — Is the platform easy to navigate and data easy to read?

---

## Environment Variables

Copy `.env.example` to `.env.local`:
```
VITE_API_BASE_URL=https://your-backend.example.com
VITE_APP_VERSION=1.0.0
VITE_DEMO_MODE=true
```

---

## Architecture Summary

```
Trial Balance CSV
       ↓
financial_statements.py   → IS / BS / CF
analysis_engine.py        → Ratios / Trends
fin_intelligence.py       → Health Score / Ratios Status
cashflow_engine.py        → OCF (indirect method)
cfo_decision_engine.py    → Prioritised actions
root_cause_engine.py      → Root causes
forecast_engine.py        → Base / Optimistic / Risk scenarios
statement_engine.py       → Statement bundle for UI
       ↓
/executive endpoint       → Single source of truth for all screens
```

---

*Version: 1.0.0 · Expert Trial Build · Phase 6.9*
