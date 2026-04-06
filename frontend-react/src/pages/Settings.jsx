/**
 * Settings.jsx — Plan & account information
 * Shows company plan, trial status, and contact CTA.
 * No payment integration — structure only.
 */
import { useLang }    from '../context/LangContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'

export default function Settings() {
  const { tr, lang } = useLang()
  const { selectedCompany, plan, trialDaysLeft, trialEndsAt,
          isTrial, isSubscribed, isTrialExpired } = useCompany()

  const PLAN_LABEL = {
    trial:      tr('plan_trial'),
    active:     tr('plan_active'),
    enterprise: tr('plan_enterprise'),
  }

  const planColor = isTrialExpired ? 'var(--red)' : isTrial ? '#fbbf24' : 'var(--accent)'

  const fmtDate = (d) => {
    if (!d) return '—'
    const locale = lang === 'ar' ? 'ar-SA' : lang === 'tr' ? 'tr-TR' : 'en-US'
    return new Date(d).toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric' })
  }

  const s = {
    page: { maxWidth: 600, margin: '0 auto', padding: '28px 16px' },
    card: { background: 'var(--bg-surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-card)', padding: '20px 24px', marginBottom: 14 },
    row:  { display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,.04)' },
    label:{ fontSize: 12, color: 'var(--text-muted)' },
    value:{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' },
  }

  return (
    <div style={s.page}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
          {tr('settings_title')}
        </h1>
      </div>

      {/* Company info */}
      <div style={s.card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 14 }}>
          {tr('settings_company')}
        </div>
        {[
          { label: tr('company_name'),     value: selectedCompany?.name     || tr('na_label') },
          { label: tr('currency'),         value: selectedCompany?.currency || tr('na_label') },
          { label: tr('industry'),         value: selectedCompany?.industry || tr('na_label') },
        ].map(({ label, value }) => (
          <div key={label} style={s.row}>
            <span style={s.label}>{label}</span>
            <span style={s.value}>{value}</span>
          </div>
        ))}
      </div>

      {/* Plan info */}
      <div style={s.card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 14 }}>
          {tr('settings_plan')}
        </div>

        <div style={s.row}>
          <span style={s.label}>Plan</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: planColor,
            background: `${planColor}15`, padding: '2px 10px', borderRadius: 5,
            border: `1px solid ${planColor}33` }}>
            {PLAN_LABEL[plan] || plan}
            {isTrialExpired && ' (Expired)'}
          </span>
        </div>

        {isTrial && trialEndsAt && (
          <div style={s.row}>
            <span style={s.label}>{tr('settings_trial_ends')}</span>
            <span style={{ ...s.value, color: planColor }}>
              {fmtDate(trialEndsAt)}
              {trialDaysLeft !== null && !isTrialExpired && ` ${tr('settings_trial_short_days_left', { n: trialDaysLeft })}`}
            </span>
          </div>
        )}

        {/* Upgrade CTA */}
        <div style={{ marginTop: 18, padding: '14px 0 2px' }}>
          {isTrialExpired ? (
            <div style={{ padding: '12px 16px', borderRadius: 8, background: 'rgba(248,113,113,.06)',
              border: '1px solid rgba(248,113,113,.2)', fontSize: 12, color: 'var(--red)',
              marginBottom: 12 }}>
              ⛔ {tr('settings_trial_expired_notice')}
            </div>
          ) : isTrial ? (
            <div style={{ padding: '12px 16px', borderRadius: 8, background: 'rgba(251,191,36,.06)',
              border: '1px solid rgba(251,191,36,.2)', fontSize: 12, color: '#fbbf24',
              marginBottom: 12 }}>
              ⏱{' '}
              {trialDaysLeft !== null
                ? tr('settings_trial_days_remaining', { n: trialDaysLeft })
                : tr('settings_trial_active')}
            </div>
          ) : null}
          <a href="mailto:sales@vcfo.io" style={{
            display: 'inline-block', padding: '9px 22px', borderRadius: 8,
            background: 'var(--accent)', color: '#000', fontWeight: 700, fontSize: 12,
            textDecoration: 'none',
          }}>
            {tr('settings_contact_sales')}
          </a>
        </div>
      </div>
    </div>
  )
}
