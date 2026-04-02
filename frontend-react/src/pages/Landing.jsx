/**
 * Landing.jsx — Phase 6.9: Expert Trial Readiness
 * Public entry screen — shown before login.
 * Explains VCFO, capabilities, and guides the expert reviewer.
 */
import { useState } from 'react'
import { useLang } from '../context/LangContext.jsx'

const T = {
  bg:      '#0B0F14',
  surface: '#111827',
  card:    '#111827',
  border:  '#1F2937',
  bright:  'rgba(255,255,255,0.10)',
  accent:  '#00d4aa',
  green:   '#34d399',
  amber:   '#fbbf24',
  blue:    '#60a5fa',
  violet:  '#a78bfa',
  text1:   '#ffffff',
  text2:   '#aab4c3',
  text3:   '#6b7280',
}

const CAPABILITIES = [
  {
    icon: '📊',
    color: T.accent,
    title: { en: 'Financial Statements', ar: 'القوائم المالية' },
    desc:  { en: 'Income Statement, Balance Sheet, and Cash Flow with period comparison, MoM/YoY variance, and balance status.', ar: 'قائمة الدخل والميزانية والتدفق النقدي مع مقارنة الفترات وتحليل التغيرات.' },
  },
  {
    icon: '🧠',
    color: T.violet,
    title: { en: 'AI-Powered Insights', ar: 'رؤى مدعومة بالذكاء الاصطناعي' },
    desc:  { en: 'Every KPI card shows an insight, root cause, recommended action, and next-period forecast — all derived from your data.', ar: 'كل مؤشر يعرض رؤية وسببًا جذريًا وإجراءً موصى به وتوقعًا — كل ذلك مستمد من بياناتك.' },
  },
  {
    icon: '🎯',
    color: T.amber,
    title: { en: 'CFO Decisions Engine', ar: 'محرك قرارات المدير المالي' },
    desc:  { en: 'Prioritised action list with urgency levels, expected impact, and timeframes — no generic advice, only what your numbers say.', ar: 'قائمة أولويات مع مستويات الإلحاح والتأثير المتوقع والإطار الزمني.' },
  },
  {
    icon: '📈',
    color: T.green,
    title: { en: 'Forecast & What-If', ar: 'التوقعات وتحليل السيناريوهات' },
    desc:  { en: 'Base / optimistic / risk scenarios for Revenue and Net Profit with confidence bands, plus interactive what-if modelling.', ar: 'سيناريوهات الإيرادات والأرباح مع نطاقات الثقة وتحليل ماذا لو.' },
  },
]

const SCREENS = [
  { path: '/',           icon: '🎯', color: T.accent,  label: { en: 'Command Center', ar: 'مركز القيادة' }, desc: { en: 'Main hub — health, KPIs, signals, branches, decisions; click through to detail views.', ar: 'المركز الرئيسي — الصحة والمؤشرات والقرارات؛ انتقل للتفاصيل بالنقر.' } },
  { path: '/statements', icon: '📋', color: T.blue,    label: { en: 'Statements',  ar: 'القوائم'        }, desc: { en: 'IS + BS + CF with comparison', ar: 'قوائم مالية مع مقارنة' } },
  { path: '/analysis',   icon: '🔬', color: T.violet,  label: { en: 'Full analysis (drill-down)', ar: 'تحليل كامل' }, desc: { en: 'Opened from Command Center — ratios, tabs, root causes.', ar: 'يُفتح من مركز القيادة — النسب والتبويبات.' } },
]

const EVAL_AREAS = [
  { icon: '📋', color: T.blue,   en: 'Statements Accuracy',  ar: 'دقة القوائم المالية',    desc_en: 'Verify IS / BS / CF values are consistent and correctly derived from uploaded TB.', desc_ar: 'تحقق من تطابق قيم قائمة الدخل والميزانية والتدفق النقدي مع ميزان المراجعة.' },
  { icon: '🧠', color: T.violet, en: 'AI Insight Quality',   ar: 'جودة الرؤى الذكية',      desc_en: 'Assess whether insight → cause → action → forecast chain is relevant and actionable.', desc_ar: 'قيّم سلسلة الرؤية ← السبب ← الإجراء ← التوقع.' },
  { icon: '🎯', color: T.amber,  en: 'Decision Relevance',   ar: 'ملاءمة القرارات',         desc_en: 'Check that CFO decisions are domain-specific, urgent, and backed by actual ratios.', desc_ar: 'تحقق من أن القرارات محددة ومدعومة بنسب فعلية.' },
  { icon: '📈', color: T.green,  en: 'Forecast Reliability', ar: 'موثوقية التوقعات',         desc_en: 'Review forecast confidence levels, risk labels, and method transparency.', desc_ar: 'راجع مستويات الثقة ومؤشرات المخاطر في التوقعات.' },
  { icon: '🖥️', color: T.accent, en: 'UX & Navigation',      ar: 'تجربة المستخدم والتنقل', desc_en: 'Evaluate ease of navigation, data clarity, and responsiveness of the interface.', desc_ar: 'قيّم سهولة التنقل ووضوح البيانات.' },
]

export default function Landing({ onEnter }) {
  const { lang } = useLang()
  const ar = lang === 'ar'
  const [showEval, setShowEval] = useState(false)

  const L = (obj) => obj?.[ar ? 'ar' : 'en'] || obj?.en || ''

  return (
    <div style={{ background: T.bg, minHeight: '100vh', color: T.text1,
      fontFamily: "'Manrope', sans-serif", direction: ar ? 'rtl' : 'ltr',
      overflowX: 'hidden' }}>

      <style>{`
        @keyframes fadeUp { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:none } }
        @keyframes pulse-glow { 0%,100% { opacity:.6 } 50% { opacity:1 } }
        .land-card { transition: transform .2s ease, box-shadow .2s ease; }
        .land-card:hover { transform: translateY(-3px); box-shadow: 0 12px 32px rgba(0,0,0,.5); }
        .land-btn { transition: all .2s ease; cursor: pointer; }
        .land-btn:hover { opacity: .88; transform: translateY(-1px); }
      `}</style>

      {/* ── Top nav bar ── */}
      <div style={{ position: 'sticky', top: 0, zIndex: 50,
        background: '#0B0F14',
        borderBottom: `1px solid ${T.border}`,
        padding: '0 32px', height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 9,
            background: 'linear-gradient(135deg,rgba(0,212,170,.2),rgba(124,92,252,.2))',
            border: `1px solid rgba(0,212,170,0.3)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>⬡</div>
          <span style={{ fontFamily: 'Outfit, sans-serif', fontSize: 18, fontWeight: 800,
            color: T.text1, letterSpacing: '-0.02em' }}>VCFO</span>
          <span style={{ fontSize: 9, fontWeight: 700, color: T.accent,
            background: 'rgba(0,212,170,0.1)', border: `1px solid rgba(0,212,170,0.25)`,
            borderRadius: 20, padding: '2px 8px', textTransform: 'uppercase', letterSpacing: '.06em' }}>
            {ar ? 'للخبراء' : 'Expert Review'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button className="land-btn" onClick={() => setShowEval(true)}
            style={{ fontSize: 11, padding: '6px 14px', borderRadius: 8,
              background: 'transparent', borderWidth: '1px', borderStyle: 'solid',
              borderColor: T.border, color: T.text2, fontFamily: 'inherit' }}>
            {ar ? '🔍 دليل التقييم' : '🔍 Evaluation Guide'}
          </button>
          <button className="land-btn" onClick={onEnter}
            style={{ fontSize: 12, padding: '7px 18px', borderRadius: 8,
              background: T.accent, border: 'none', color: '#000',
              fontWeight: 700, fontFamily: 'inherit' }}>
            {ar ? 'دخول المنصة →' : 'Enter Platform →'}
          </button>
        </div>
      </div>

      {/* ── HERO ── */}
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '80px 32px 60px',
        textAlign: 'center', animation: 'fadeUp .5s ease both' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '4px 14px', borderRadius: 20,
          background: 'rgba(0,212,170,0.08)', border: `1px solid rgba(0,212,170,0.2)`,
          fontSize: 11, color: T.accent, fontWeight: 600,
          letterSpacing: '.06em', marginBottom: 28, textTransform: 'uppercase' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: T.accent,
            animation: 'pulse-glow 2s ease-in-out infinite', display: 'inline-block' }}/>
          {ar ? 'منصة الذكاء المالي التنفيذي' : 'Virtual CFO Intelligence Platform'}
        </div>

        <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 'clamp(32px, 5vw, 54px)',
          fontWeight: 900, lineHeight: 1.1, letterSpacing: '-0.03em',
          margin: '0 0 20px', color: T.text1 }}>
          {ar
            ? <><span style={{ color: T.accent }}>قوائمك المالية</span> تشرح نفسها</>
            : <>Your financials<br/><span style={{ color: T.accent }}>explain themselves.</span></>}
        </h1>

        <p style={{ fontSize: 17, color: T.text2, lineHeight: 1.8,
          maxWidth: 620, margin: '0 auto 40px' }}>
          {ar
            ? 'VCFO يحوّل ميزان المراجعة إلى قرارات تنفيذية مدعومة بالذكاء الاصطناعي — بدون محاسب وبدون جداول إكسيل.'
            : 'VCFO transforms a trial balance into executive decisions powered by AI — no accountant required, no spreadsheets.'}
        </p>

        {/* CTA buttons */}
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button className="land-btn" onClick={onEnter}
            style={{ padding: '12px 28px', borderRadius: 10, border: 'none',
              background: `linear-gradient(135deg, ${T.accent}, #0099cc)`,
              color: '#000', fontSize: 14, fontWeight: 800, fontFamily: 'inherit',
              boxShadow: `0 0 24px rgba(0,212,170,0.3)` }}>
            {ar ? '🚀 ابدأ الاستكشاف' : '🚀 Start Exploring'}
          </button>
          {SCREENS.slice(0, 3).map(s => (
            <button key={s.path} className="land-btn" onClick={onEnter}
              style={{ padding: '12px 20px', borderRadius: 10,
                borderWidth: '1px', borderStyle: 'solid', borderColor: `${s.color}40`,
                background: `${s.color}0d`, color: s.color,
                fontSize: 13, fontWeight: 600, fontFamily: 'inherit' }}>
              {s.icon} {L(s.label)}
            </button>
          ))}
        </div>
      </div>

      {/* ── CAPABILITIES ── */}
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 32px 64px' }}>
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: T.text3,
            textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 10 }}>
            {ar ? 'القدرات الأساسية' : 'Core Capabilities'}
          </div>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 26, fontWeight: 800,
            color: T.text1, margin: 0 }}>
            {ar ? 'ماذا يمكنك اختبار؟' : "What can you test?"}
          </h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
          {CAPABILITIES.map((cap, i) => (
            <div key={i} className="land-card"
              style={{ background: T.card, borderWidth: '1px', borderStyle: 'solid',
                borderColor: T.border, borderRadius: 14, padding: '22px 20px',
                borderTop: `2px solid ${cap.color}`,
                animation: `fadeUp .4s ${i * .08}s ease both` }}>
              <div style={{ fontSize: 26, marginBottom: 12 }}>{cap.icon}</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text1, marginBottom: 8 }}>
                {L(cap.title)}
              </div>
              <div style={{ fontSize: 11, color: T.text2, lineHeight: 1.65 }}>
                {L(cap.desc)}
              </div>
            </div>
          ))}
        </div>
      </div>


      {/* ── HOW TO START ── */}
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '0 32px 64px' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: T.text3,
            textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 10 }}>
            {ar ? 'كيف تبدأ' : 'How to Start'}
          </div>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 22, fontWeight: 800,
            color: T.text1, margin: 0 }}>
            {ar ? 'أربع خطوات للتشغيل الكامل' : 'Four steps to full operation'}
          </h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
          {[
            { n:'1', color: T.accent,  icon:'🏢',
              en:'Create Company',   ar:'أنشئ شركة',
              desc_en:'Register and create your company profile inside the platform.',
              desc_ar:'سجّل وأنشئ ملف شركتك داخل المنصة.' },
            { n:'2', color: T.blue,   icon:'📁',
              en:'Upload Trial Balance', ar:'ارفع ميزان المراجعة',
              desc_en:'Upload a CSV trial balance — monthly (YYYY-MM) or annual (YYYY).',
              desc_ar:'ارفع ميزان المراجعة CSV — شهري أو سنوي.' },
            { n:'3', color: T.violet, icon:'📊',
              en:'Review Statements & Analysis', ar:'راجع القوائم والتحليل',
              desc_en:'Explore financial statements, ratios, decisions, and forecasts.',
              desc_ar:'استعرض القوائم المالية والنسب والقرارات والتوقعات.' },
            { n:'4', color: T.amber,  icon:'🧠',
              en:'Ask AI CFO',  ar:'اسأل AI CFO',
              desc_en:'Use the AI CFO button (🧠) to ask natural language questions about your data.',
              desc_ar:'استخدم زر 🧠 في الشريط العلوي لطرح أسئلة عن بياناتك.' },
          ].map((step, i) => (
            <div key={i} className="land-card"
              style={{ background: T.card,
                borderWidth: '1px', borderStyle: 'solid', borderColor: T.border,
                borderTop: `2px solid ${step.color}`,
                borderRadius: 13, padding: '18px 16px',
                animation: `fadeUp .4s ${i * .08}s ease both` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <div style={{ width: 22, height: 22, borderRadius: '50%', flexShrink: 0,
                  background: `${step.color}18`, border: `1px solid ${step.color}35`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 800, color: step.color }}>{step.n}</div>
                <span style={{ fontSize: 14 }}>{step.icon}</span>
              </div>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.text1, marginBottom: 6 }}>
                {ar ? step.ar : step.en}
              </div>
              <div style={{ fontSize: 11, color: T.text2, lineHeight: 1.6 }}>
                {ar ? step.desc_ar : step.desc_en}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── SCREEN MAP ── */}
      <div style={{ background: T.surface, borderTop: `1px solid ${T.border}`,
        borderBottom: `1px solid ${T.border}`, padding: '48px 32px' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: T.text3,
              textTransform: 'uppercase', letterSpacing: '.1em', marginBottom: 10 }}>
              {ar ? 'خريطة الاستكشاف' : 'Exploration Map'}
            </div>
            <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 22, fontWeight: 800,
              color: T.text1, margin: 0 }}>
              {ar ? 'كيف تستكشف المنصة؟' : 'How to explore the platform'}
            </h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            {SCREENS.map((sc, i) => (
              <div key={sc.path} onClick={onEnter} className="land-card"
                style={{ background: T.card, borderWidth: '1px', borderStyle: 'solid',
                  borderColor: `${sc.color}25`, borderRadius: 12,
                  padding: '16px 16px', cursor: 'pointer',
                  borderLeft: `3px solid ${sc.color}`,
                  animation: `fadeUp .4s ${i * .07}s ease both` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 }}>
                  <span style={{ fontSize: 18 }}>{sc.icon}</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: sc.color }}>
                    {L(sc.label)}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: T.text3, lineHeight: 1.5 }}>
                  {L(sc.desc)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── FOOTER ── */}
      <div style={{ padding: '32px', textAlign: 'center' }}>
        <p style={{ fontSize: 11, color: T.text3 }}>
          {ar
            ? 'VCFO — منصة الذكاء المالي التنفيذي · نسخة تجريبية للخبراء'
            : 'VCFO — Virtual CFO Intelligence Platform · Expert Trial Build'}
        </p>
      </div>

      {/* ── EVALUATION GUIDE MODAL ── */}
      {showEval && (
        <>
          <div onClick={() => setShowEval(false)}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
              zIndex: 900 }}/>
          <div style={{ position: 'fixed', top: '50%', left: '50%',
            transform: 'translate(-50%,-50%)',
            width: 'min(640px, 92vw)', maxHeight: '85vh',
            background: T.surface, border: `1px solid ${T.bright}`,
            borderRadius: 16, zIndex: 901, overflowY: 'auto',
            boxShadow: '0 32px 80px rgba(0,0,0,0.8)' }}>
            {/* Modal header */}
            <div style={{ padding: '20px 24px 16px', borderBottom: `1px solid ${T.border}`,
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              position: 'sticky', top: 0, background: T.surface, zIndex: 1 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 800, color: T.text1 }}>
                  {ar ? '🔍 دليل التقييم للخبراء' : '🔍 Expert Evaluation Guide'}
                </div>
                <div style={{ fontSize: 11, color: T.text3, marginTop: 3 }}>
                  {ar ? 'ما الذي يجب تقييمه وكيف' : 'What to assess and how'}
                </div>
              </div>
              <button onClick={() => setShowEval(false)}
                style={{ width: 32, height: 32, borderRadius: 8, border: `1px solid ${T.border}`,
                  background: T.card, color: T.text2, cursor: 'pointer', fontSize: 16 }}>✕</button>
            </div>
            {/* Modal body */}
            <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              <p style={{ fontSize: 12, color: T.text2, lineHeight: 1.7, margin: 0,
                padding: '10px 14px', background: 'rgba(0,212,170,0.05)',
                borderLeft: `3px solid ${T.accent}`, borderRadius: '0 8px 8px 0' }}>
                {ar
                  ? 'يرجى تقييم كل منطقة من المناطق التالية وتزويدنا بملاحظاتك. ركّز على الدقة المالية وجودة الرؤى الذكية وقابلية الاستخدام.'
                  : 'Please evaluate each area below and provide your feedback. Focus on financial accuracy, AI insight quality, and usability.'}
              </p>
              {EVAL_AREAS.map((area, i) => (
                <div key={i} style={{ background: T.card, borderRadius: 11,
                  padding: '14px 16px',
                  borderWidth: '1px', borderStyle: 'solid', borderColor: `${area.color}20`,
                  borderLeft: `3px solid ${area.color}` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: 16 }}>{area.icon}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: area.color }}>
                      {ar ? area.ar : area.en}
                    </span>
                    <span style={{ marginLeft: 'auto', fontSize: 9, color: T.text3,
                      background: `${area.color}14`, padding: '2px 8px',
                      borderRadius: 20, fontWeight: 600 }}>
                      {ar ? 'للتقييم' : 'Evaluate'}
                    </span>
                  </div>
                  <p style={{ fontSize: 11, color: T.text2, lineHeight: 1.6, margin: 0 }}>
                    {ar ? area.desc_ar : area.desc_en}
                  </p>
                </div>
              ))}
              <div style={{ marginTop: 4, padding: '12px 16px', borderRadius: 9,
                background: 'rgba(251,191,36,0.06)', border: `1px solid rgba(251,191,36,0.2)`,
                fontSize: 11, color: T.amber, lineHeight: 1.6 }}>
                {ar
                  ? 'ملاحظة: ارفع ميزان المراجعة الخاص بك للحصول على تحليل حقيقي. المنصة تشتغل بالكامل مع أي بيانات محاسبية.'
                  : 'Note: Upload your own trial balance to get real analysis. The platform works fully with any accounting data.'}
              </div>
              <button onClick={() => { setShowEval(false); onEnter() }}
                style={{ width: '100%', padding: '12px', borderRadius: 10,
                  background: T.accent, border: 'none', color: '#000',
                  fontSize: 14, fontWeight: 800, cursor: 'pointer',
                  fontFamily: 'inherit', marginTop: 4 }}>
                {ar ? 'دخول المنصة للتقييم →' : 'Enter Platform to Evaluate →'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
