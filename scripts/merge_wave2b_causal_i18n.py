"""One-off merge of Wave 2B causal i18n keys into en/ar/tr (run from repo root)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "app" / "i18n"

EN_CAUSAL: dict[str, str] = {}

# --- decision.causal.* (params per key from cfo_decision_engine._select_decision) ---
D = EN_CAUSAL
D["decision.causal.liq_immediate_cashflow.change"] = (
    "Liquidity stress: current ratio is {cr} — cash and working-capital coverage need immediate attention."
)
D["decision.causal.liq_immediate_cashflow.cause"] = (
    "Short-term solvency signals are weak; the current ratio {cr} sits below a prudent operating floor."
)
D["decision.causal.liq_immediate_cashflow.action"] = (
    "Prioritize cash conversion, AR/AP terms, and a rolling cash forecast; line up contingency funding if covenants are tight."
)

D["decision.causal.liq_strengthen_working_capital.change"] = (
    "Working capital should be strengthened to buffer operations and growth."
)
D["decision.causal.liq_strengthen_working_capital.cause"] = (
    "Liquidity ratios and trends in domain «{domain}» (priority rank {decision_priority_rank}) warrant a capital-structure review."
)
D["decision.causal.liq_strengthen_working_capital.action"] = (
    "Improve WC discipline (inventory, receivables, payables) and align financing with seasonal cash peaks."
)

D["decision.causal.prof_margin_recovery.change"] = (
    "Net margin at {nm} — incremental profit leverage of {per_pp} per point makes margin recovery a top CFO lever."
)
D["decision.causal.prof_margin_recovery.cause"] = (
    "Profitability sits below target; small margin moves translate into material P&L impact ({per_pp})."
)
D["decision.causal.prof_margin_recovery.action"] = (
    "Run a margin bridge (price, mix, COGS, OpEx); assign owners and a 30–60 day action plan."
)

D["decision.causal.prof_cost_structure_review.change"] = (
    "Gross margin context at {gm} — cost structure and pricing deserve executive scrutiny."
)
D["decision.causal.prof_cost_structure_review.cause"] = (
    "COGS and gross-margin profile suggest mix, procurement, or pricing pressure versus prior norms."
)
D["decision.causal.prof_cost_structure_review.action"] = (
    "Segment COGS by product/channel; benchmark suppliers; target quick wins on waste, terms, and discounting."
)

D["decision.causal.eff_cash_cycle_optimization.change"] = (
    "Cash conversion cycle is {ccc} days — operational cash is tied up in the business."
)
D["decision.causal.eff_cash_cycle_optimization.cause"] = (
    "CCC length indicates receivables, inventory, and/or payables policy are constraining liquidity ({freed} illustrative release at scale)."
)
D["decision.causal.eff_cash_cycle_optimization.action"] = (
    "Jointly attack DSO, inventory days, and DPO; align sales incentives with collectible cash timing."
)

D["decision.causal.eff_receivables_management.change"] = (
    "DSO is {dso} days — collections and credit quality need focused management."
)
D["decision.causal.eff_receivables_management.cause"] = (
    "Receivable duration increases working-capital risk and masks true cash earnings power."
)
D["decision.causal.eff_receivables_management.action"] = (
    "Segment aging, tighten limits for slow payers, automate dunning, and tie KPIs to cash collected."
)

D["decision.causal.lev_debt_reduction.change"] = (
    "Leverage at debt-to-equity {de} — balance-sheet risk is elevated versus prudent targets."
)
D["decision.causal.lev_debt_reduction.cause"] = (
    "Higher leverage raises sensitivity to rates, covenants, and downturn cash coverage."
)
D["decision.causal.lev_debt_reduction.action"] = (
    "Map maturities and covenants; retire highest-cost debt first; pause non-strategic spending until leverage improves."
)

D["decision.causal.growth_revenue_acceleration.change"] = (
    "Growth mode: reinvest behind demand while protecting margin and cash discipline (domain «{domain}», rank {decision_priority_rank})."
)
D["decision.causal.growth_revenue_acceleration.cause"] = (
    "Trends support selective acceleration if unit economics and capacity are validated."
)
D["decision.causal.growth_revenue_acceleration.action"] = (
    "Pick 1–2 levers, fund from operating cash where possible, and track weekly leading indicators."
)

D["decision.causal.growth_margin_expansion.change"] = (
    "Revenue momentum ({rev_ytd}) with headroom to widen margin through efficiency and mix."
)
D["decision.causal.growth_margin_expansion.cause"] = (
    "Top-line strength can fund process and procurement improvements that compound margin."
)
D["decision.causal.growth_margin_expansion.action"] = (
    "Pair growth investments with productivity targets; guard gross margin with price/mix rules."
)

# --- narrative.causal.* (domain, merged_count only — safe for all Phase-43 merges) ---
def _narr(prefix: str, change: str, cause: str, action: str) -> None:
    D[f"narrative.causal.{prefix}.change"] = change
    D[f"narrative.causal.{prefix}.cause"] = cause
    D[f"narrative.causal.{prefix}.action"] = action


_narr(
    "margin_pressure",
    "Margin pressure in «{domain}» context ({merged_count} merged signal(s)) — gross margin is under strain versus revenue momentum.",
    "COGS and revenue dynamics suggest gross-margin squeeze; multiple drivers may be active in the same domain.",
    "Address price, mix, and COGS concurrently; freeze non-essential OpEx until margin trajectory stabilizes.",
)
_narr(
    "cost_spike",
    "Operating cost intensity rose materially in «{domain}» ({merged_count} merged signal(s)).",
    "Expense ratio momentum outpaced revenue, compressing operating margin.",
    "Audit variable spend, renegotiate contracts, and reset OpEx budgets to a sustainable revenue share.",
)
_narr(
    "profit_growth_quality_issue",
    "Profit growth is lagging revenue in «{domain}» ({merged_count} merged signal(s)) — quality of growth is questionable.",
    "Incremental revenue is being absorbed by cost or weaker-margin mix.",
    "Trace margin by segment; tighten discounting; improve unit economics on new revenue.",
)
_narr(
    "strong_profitability",
    "Strong profitability signal in «{domain}» ({merged_count} merged signal(s)) — margins are healthy versus thresholds.",
    "Net margin strength indicates pricing power and/or cost control relative to peers.",
    "Protect margin through discipline; reinvest selectively in scalable growth and balance-sheet resilience.",
)
_narr(
    "cost_anomaly",
    "Cost anomaly flagged in «{domain}» ({merged_count} merged signal(s)) — COGS moved sharply versus revenue.",
    "Sudden COGS share shifts often reflect mix, input prices, or one-off items.",
    "Validate drivers within 2 weeks; correct pricing or sourcing; rule out misclassification.",
)
_narr(
    "margin_anomaly",
    "Margin anomaly in «{domain}» ({merged_count} merged signal(s)) — net margin is weak with deteriorating profit momentum.",
    "Low margin plus negative profit momentum raises operating-loss risk if uncorrected.",
    "Emergency margin diagnostic: pricing, variable cost pressure, and capacity utilization.",
)
_narr(
    "expense_outlier",
    "Expense load outlier in «{domain}» ({merged_count} merged signal(s)) — OpEx share of revenue is structurally high.",
    "Elevated OpEx ratio limits shock absorption and investment capacity.",
    "Line-item review with targets to restore a sub-threshold expense ratio within 2–3 quarters.",
)
_narr(
    "revenue_drop",
    "Revenue contraction signal in «{domain}» ({merged_count} merged signal(s)).",
    "Top-line decline pressures cash, fixed-cost coverage, and strategic flexibility.",
    "Activate pipeline recovery: customer retention, pricing, and quick cost flex tied to volume.",
)

# --- ai_cfo.decision.* (action_type, risk_score, priority, is_loss always in params) ---
def _ai(action: str, ch: str, ca: str, ac: str) -> None:
    D[f"ai_cfo.decision.{action}.change"] = ch
    D[f"ai_cfo.decision.{action}.cause"] = ca
    D[f"ai_cfo.decision.{action}.action"] = ac


_ai(
    "COST_REDUCTION",
    "Heuristic stance COST_REDUCTION — risk {risk_score}/100, priority {priority}, loss flag {is_loss}.",
    "Expense load and margin position imply cost takeout is the primary lever.",
    "Target 5–10% OpEx reduction on non-core lines; renegotiate suppliers; track weekly savings vs plan.",
)
_ai(
    "SCALE_UP",
    "Heuristic stance SCALE_UP — risk {risk_score}/100, priority {priority}, loss flag {is_loss}.",
    "Margins and growth momentum support controlled capacity or go-to-market expansion.",
    "Fund growth from operating cash; pilot before scale; monitor margin and WC weekly.",
)
_ai(
    "OPTIMIZE",
    "Heuristic stance OPTIMIZE — risk {risk_score}/100, priority {priority}, loss flag {is_loss}.",
    "Performance sits in a mid band where targeted efficiency beats broad cuts.",
    "Pick 2–3 KPIs (margin, CCC, OpEx ratio) and run 90-day improvement sprints.",
)
_ai(
    "RESTRUCTURE",
    "Heuristic stance RESTRUCTURE — risk {risk_score}/100, priority {priority}, loss flag {is_loss}.",
    "Margin and cost structure suggest a broken or overstretched operating model.",
    "Reset cost base, simplify SKUs/locations, and secure liquidity while restructuring.",
)
_ai(
    "CLOSE",
    "Heuristic stance CLOSE — risk {risk_score}/100, priority {priority}, loss flag {is_loss}.",
    "Persistent losses with critical expense load imply existential cash risk.",
    "Model wind-down vs turnaround; engage stakeholders; protect employee and creditor obligations legally.",
)
_ai(
    "MONITOR",
    "Heuristic stance MONITOR — risk {risk_score}/100, priority {priority}, loss flag {is_loss}.",
    "Signals are marginal; premature action could disturb a stabilizing trend.",
    "Watch revenue and margin for two more closes; pre-position contingency plans without executing yet.",
)

# --- expense_deep.pressure.* ---
for branch, ch, ca, ac in [
    (
        "cogs_material_vs_opex",
        "Full cost load materially exceeds OpEx-only view — COGS-inclusive base dominates versus operating expenses.",
        "Total cost ratio and OpEx ratio gap indicates gross-margin and direct-cost levers matter as much as OpEx.",
        "Joint review of COGS, pricing, and procurement alongside OpEx; avoid optimizing only one layer.",
    ),
    (
        "opex_elevated",
        "Operating expense ratio versus revenue is elevated versus internal SME thresholds.",
        "OpEx threshold status «{opex_threshold_status}» with total-cost status «{total_cost_threshold_status}».",
        "Line-item OpEx audit; contract renegotiation; defer discretionary programs until ratio normalizes.",
    ),
    (
        "total_cost_elevated",
        "Full cost load (COGS + OpEx + unclassified debits) versus revenue is elevated.",
        "Total-cost threshold status «{total_cost_threshold_status}»; pressure level {pressure_level}; {flag_count} structural flag(s).",
        "Holistic cost program: COGS, OpEx, and P&L classification hygiene with monthly steering reviews.",
    ),
    (
        "neutral_bands",
        "Cost ratios sit in neutral bands versus default SME thresholds; maintain monitoring.",
        "Pressure branch «{pressure_branch}»; OpEx status «{opex_threshold_status}»; total-cost status «{total_cost_threshold_status}».",
        "Continue category-level monitoring; escalate if any metric crosses warning thresholds for two consecutive closes.",
    ),
]:
    D[f"expense_deep.pressure.{branch}.change"] = ch
    D[f"expense_deep.pressure.{branch}.cause"] = ca
    D[f"expense_deep.pressure.{branch}.action"] = ac

# --- profitability_deep.note.* (note_id, operating_pressure, earnings_quality always) ---
for nid, ch, ca, ac in [
    (
        "operating_pressure_high",
        "Operating cost pressure is high — cost ratios worsened materially versus the prior period.",
        "Operating pressure «{operating_pressure}» with earnings quality «{earnings_quality}» (note {note_id}).",
        "Prioritize gross-margin and OpEx levers with a 30-day executive action list and weekly variance review.",
    ),
    (
        "volatile_earnings_vs_sales",
        "Profit volatility exceeds revenue volatility — earnings are less predictable than sales.",
        "Earnings quality «{earnings_quality}»; operating pressure «{operating_pressure}» (note {note_id}).",
        "Investigate one-offs, revenue mix, and timing; smooth lumpy items; tighten forecast ranges.",
    ),
    (
        "deteriorating_earnings_trend",
        "Several consecutive weak profit momentum readings — trend deterioration risk.",
        "Earnings quality «{earnings_quality}»; operating pressure «{operating_pressure}» (note {note_id}).",
        "Confirm cost and price discipline; stop-loss rules on negative-margin sales; weekly P&L bridge.",
    ),
]:
    D[f"profitability_deep.note.{nid}.change"] = ch
    D[f"profitability_deep.note.{nid}.cause"] = ca
    D[f"profitability_deep.note.{nid}.action"] = ac

# --- profitability_deep.exec.* (rule_id, revenue_trend_direction, net_profit_trend_direction, revenue_up_period) ---
for rid, ch, ca, ac in [
    (
        "strong_but_heavy",
        "Profitability is strong on net margin but the combined cost load versus revenue is heavy.",
        "Rule {rule_id}: revenue trend {revenue_trend_direction}, profit trend {net_profit_trend_direction}, period revenue up {revenue_up_period}.",
        "Protect margin while rationalizing cost structure; avoid growth that dilutes unit economics.",
    ),
    (
        "margins_declining_expenses",
        "Margins are declining with expense-ratio pressure in the window.",
        "Rule {rule_id}: revenue trend {revenue_trend_direction}, profit trend {net_profit_trend_direction}, period revenue up {revenue_up_period}.",
        "Target OpEx and COGS levers; reset pricing where justified; track margin weekly.",
    ),
    (
        "rev_not_profit",
        "Revenue momentum is not flowing through to profit — growth quality issue.",
        "Rule {rule_id}: revenue trend {revenue_trend_direction}, profit trend {net_profit_trend_direction}, period revenue up {revenue_up_period}.",
        "Margin diagnostics by segment; cut unprofitable volume; align incentives to net profit.",
    ),
    (
        "neutral",
        "Profitability metrics are within the observed band; maintain disciplined monitoring.",
        "Rule {rule_id}: revenue trend {revenue_trend_direction}, profit trend {net_profit_trend_direction}, period revenue up {revenue_up_period}.",
        "Keep standard margin and cost ratio reviews; no broad action until a threshold breach.",
    ),
]:
    D[f"profitability_deep.exec.{rid}.change"] = ch
    D[f"profitability_deep.exec.{rid}.cause"] = ca
    D[f"profitability_deep.exec.{rid}.action"] = ac

# --- Arabic (professional CFO MSA) ---
AR_CAUSAL: dict[str, str] = {}
# decision.causal (abbrev: mirror EN structure in Arabic)
AR = AR_CAUSAL
AR["decision.causal.liq_immediate_cashflow.change"] = "ضغط سيولة: النسبة الجارية {cr} — يتطلب الأمر إدارة فورية للنقد ورأس المال العامل."
AR["decision.causal.liq_immediate_cashflow.cause"] = "مؤشرات السيولة قصيرة الأجل ضعيفة؛ النسبة الجارية {cr} دون أرضية تشغيلية آمنة."
AR["decision.causal.liq_immediate_cashflow.action"] = "ركّز على تحصيل الذمم وشروط الدفع والمخزون وتوقعات نقدية متجددة؛ جهّز تمويلاً احتياطياً عند ضيق العهود."

AR["decision.causal.liq_strengthen_working_capital.change"] = "يجب تعزيز رأس المال العامل لامتصاص الصدمات ودعم التشغيل."
AR["decision.causal.liq_strengthen_working_capital.cause"] = "مؤشرات السيولة في المجال «{domain}» (ترتيب أولوية {decision_priority_rank}) تستدعي مراجعة هيكل رأس المال العامل."
AR["decision.causal.liq_strengthen_working_capital.action"] = "حسّن المخزون والذمم المدينة والذمم الدائنة ووائم التمويل مع ذروات النقد."

AR["decision.causal.prof_margin_recovery.change"] = "هامش صافٍ عند {nm} — قيمة {per_pp} لكل نقطة هامش تجعل استعادة الهامش أولوية قصوى."
AR["decision.causal.prof_margin_recovery.cause"] = "الربحية دون المستهدف؛ تحركات هامشية صغيرة تنعكس بأثر مادي ({per_pp})."
AR["decision.causal.prof_margin_recovery.action"] = "نفّذ جسر هامش (سعر، مزيج، تكلفة بضاعة، مصاريف) مع مسؤولين وخطة 30–60 يوماً."

AR["decision.causal.prof_cost_structure_review.change"] = "سياق هامش إجمالي عند {gm} — يستحق هيكل التكلفة والتسعير مراجعة تنفيذية."
AR["decision.causal.prof_cost_structure_review.cause"] = "ملف تكلفة البضاعة والهامش الإجمالي يشير لضغط مزيج أو توريد أو تسعير."
AR["decision.causal.prof_cost_structure_review.action"] = "قسّم تكلفة البضاعة حسب المنتج/القناة؛ قارن الموردين؛ استهدف خفض هدر وشروط أسرع."

AR["decision.causal.eff_cash_cycle_optimization.change"] = "دورة تحويل النقد {ccc} يوماً — النقد محبوس في التشغيل."
AR["decision.causal.eff_cash_cycle_optimization.cause"] = "طول الدورة يعني ضغطاً في الذمم أو المخزون أو سياسة الدفع ({freed} إفراج تقريبي عند التنفيذ)."
AR["decision.causal.eff_cash_cycle_optimization.action"] = "عالج أيام التحصيل والمخزون والدفع معاً؛ اربط المبيعات بتوقيت النقد المحصّل."

AR["decision.causal.eff_receivables_management.change"] = "أيام التحصيل {dso} — تستحق الإدارة المالية تركيزاً على التحصيل والائتمان."
AR["decision.causal.eff_receivables_management.cause"] = "طول الذمم يضغط رأس المال العامل ويخفي جودة الربح النقدي."
AR["decision.causal.eff_receivables_management.action"] = "قسّم الأعمار؛ شدود ائتمانية؛ أتمتة المطالبة؛ اربط المكافآت بالتحصيل."

AR["decision.causal.lev_debt_reduction.change"] = "الرافعة المالية عند دين/حقوق {de} — مخاطر ميزانية مرتفعة."
AR["decision.causal.lev_debt_reduction.cause"] = "الدين يرفع الحساسية للفائدة والعهد وتغطية النقد في الركود."
AR["decision.causal.lev_debt_reduction.action"] = "ارسم الاستحقاقات والعهد؛ سدد أعلى تكلفة أولاً؛ أوقف الإنفاق غير الاستراتيجي مؤقتاً."

AR["decision.causal.growth_revenue_acceleration.change"] = "وضع نمو: استثمر خلف الطلب مع ضبط الهامش والنقد (مجال «{domain}»، ترتيب {decision_priority_rank})."
AR["decision.causal.growth_revenue_acceleration.cause"] = "الاتجاهات تدعم تسارعاً انتقائياً إذا تُحسنت الوحدة الاقتصادية والطاقة."
AR["decision.causal.growth_revenue_acceleration.action"] = "اختر رافعة أو رافعتين؛موّل من التشغيل حيثما أمكن؛ تابع مؤشرات أسبوعية."

AR["decision.causal.growth_margin_expansion.change"] = "زخم إيرادات ({rev_ytd}) مع مجال لتوسيع الهامش عبر الكفاءة والمزيج."
AR["decision.causal.growth_margin_expansion.cause"] = "قوة الإيرادات يمكن أن تمول تحسينات عمليات ومشتريات تُركّب الهامش."
AR["decision.causal.growth_margin_expansion.action"] = "اربط الاستثمار بأهداف إنتاجية؛ احمِ الهامش الإجمالي بقواعد سعر/مزيج."

# narrative Arabic
_ar_narr = [
    ("margin_pressure", "ضغط هامش في سياق «{domain}» ({merged_count} إشارة مدمجة) — الهامش الإجمالي تحت ضغط.", "ديناميكيات التكلفة والإيراد تشير لضغط على الهامش الإجمالي.", "عالج السعر والمزيج وتكلفة البضاعة معاً؛ جمّد مصاريف غير أساسية حتى يستقر الهامش."),
    ("cost_spike", "ارتفعت كثافة التكلفة التشغيلية في «{domain}» ({merged_count} إشارة).", "زخم نسبة المصاريف تجاوز الإيراد، فيضغط هامش التشغيل.", "راجع بنود المصاريف المتغيرة؛ أعد التفاوض على العقود؛ أعد ميزانية OpEx لتناسب الإيراد."),
    ("profit_growth_quality_issue", "نمو الربح يتخلف عن الإيراد في «{domain}» ({merged_count} إشارة) — جودة النمو مشكوك فيها.", "الإيرادات الإضافية تمتصها التكلفة أو مزيج أضعف هامشاً.", "تتبع الهامش بالقطاع؛ شدّ الخصومات؛ حسّن اقتصاديات الوحدة على الإيراد الجديد."),
    ("strong_profitability", "إشارة ربحية قوية في «{domain}» ({merged_count} إشارة) — الهوامش صحية مقارنة بالعتبات.", "قوة هامش صافٍ تعكس تسعيراً و/أو ضبط تكلفة.", "احمِ الهامش بالانضباط؛ أعد استثماراً انتقائياً في نمو قابل للتوسع."),
    ("cost_anomaly", "شذوذ تكلفة في «{domain}» ({merged_count} إشارة) — تحرك حاد في تكلفة البضاعة مقابل الإيراد.", "قفزات مفاجئة في حصة التكلفة غالباً مزيج أو مدخلات أو لمرة واحدة.", "تحقق خلال أسبوعين؛ صحح التسعير أو التوريد؛ استبعد خطأ التصنيف."),
    ("margin_anomaly", "شذوذ هامش في «{domain}» ({merged_count} إشارة) — هامش ضعيف مع زخم ربح سلبي.", "هامش منخفض مع تراجع الربح يرفع خطر الخسارة التشغيلية.", "تشخيص هامش طارئ: تسعير، تكلفة متغيرة، استخدام الطاقة."),
    ("expense_outlier", "حمل مصاريف شاذ في «{domain}» ({merged_count} إشارة) — حصة OpEx من الإيراد مرتفعة هيكلياً.", "نسبة OpEx العالية تضيق هامش امتصاص الصدمات والاستثمار.", "مراجعة بنود مع أهداف لإعادة النسبة دون عتبة خلال 2–3 أرباع."),
    ("revenue_drop", "إشارة انكماش إيرادات في «{domain}» ({merged_count} إشارة).", "تراجع الإيراد يضغط النقد وتغطية التكلفة الثابتة.", "فعّل استعادة خط الأنابيب: احتفاظ، تسعير، مرونة تكلفة مرتبطة بالحجم."),
]
for p, c, ca, a in _ar_narr:
    AR[f"narrative.causal.{p}.change"] = c
    AR[f"narrative.causal.{p}.cause"] = ca
    AR[f"narrative.causal.{p}.action"] = a

# ai_cfo AR
_ar_ai = [
    ("COST_REDUCTION", "وضع استدلالي: خفض تكلفة — مخاطر {risk_score}/100، أولوية {priority}، خسارة {is_loss}.", "حمل المصاريف والهامش يجعل خفض التكلفة الرافعة الأولى.", "استهدف 5–10% من OpEx غير الأساسي؛ أعد التفاوض؛ تابع التوفير أسبوعياً."),
    ("SCALE_UP", "وضع استدلالي: توسعة — مخاطر {risk_score}/100، أولوية {priority}، خسارة {is_loss}.", "الهامش والنمو يدعمان توسعة ضبابية.", "موّل من التشغيل؛ نجّح تجريبياً قبل التوسع؛ راقب الهامش ورأس المال العامل أسبوعياً."),
    ("OPTIMIZE", "وضع استدلالي: تحسين — مخاطر {risk_score}/100، أولوية {priority}، خسارة {is_loss}.", "الأداء في نطقة متوسطة حيث الكفاءة المستهدفة أفضل من القص العريض.", "اختر 2–3 مؤشرات ونفّذ سباقات 90 يوماً."),
    ("RESTRUCTURE", "وضع استدلالي: إعادة هيكلة — مخاطر {risk_score}/100، أولوية {priority}، خسارة {is_loss}.", "الهامش والتكلفة يشيران لنموذج تشغيل ممتد أو مكسور.", "أعد ضبط قاعدة التكلفة؛ بسّط المنتجات/المواقع؛ أمّن سيولة أثناء إعادة الهيكلة."),
    ("CLOSE", "وضع استدلالي: إغلاق — مخاطر {risk_score}/100، أولوية {priority}، خسارة {is_loss}.", "خسائر مستمرة مع حمل مصاريف حرج يعني مخاطر وجودية للنقد.", "قارن الإغلاق مقابل الإنعاش؛ تفاعل مع أصحاب المصلحة؛ التزم قانونياً."),
    ("MONITOR", "وضع استدلالي: مراقبة — مخاطر {risk_score}/100، أولوية {priority}، خسارة {is_loss}.", "الإشارات هامشية؛ التصرف المبكر قد يزعزع استقراراً محتملاً.", "راقب الإيراد والهامش لدورتين إضافيتين؛ جهّز خططاً طارئة دون تنفيذ فوري."),
]
for t, c, ca, a in _ar_ai:
    AR[f"ai_cfo.decision.{t}.change"] = c
    AR[f"ai_cfo.decision.{t}.cause"] = ca
    AR[f"ai_cfo.decision.{t}.action"] = a

# expense AR
_ar_exp = [
    ("cogs_material_vs_opex", "حمل التكلفة الكامل يفوق منظور المصاريف التشغيلية وحدها — طبقة تكلفة البضاعة مهيمنة.", "فجوة نسبة التكلفة الكلية وOpEx تعني أن هامشاً مباشراً وتوريداً بنفس أهمية OpEx.", "مراجعة مشتركة لتكلفة البضاعة والتسعير والتوريد مع OpEx."),
    ("opex_elevated", "نسبة المصاريف التشغيلية مرتفعة مقارنة بالإيراد مقارنة بعتبات داخلية.", "حالة عتبة OpEx «{opex_threshold_status}» وحالة التكلفة الكلية «{total_cost_threshold_status}».", "تدقيق بنود OpEx؛ إعادة تفاوض؛ تأجيل برامج غير ضرورية حتى تعود النسبة."),
    ("total_cost_elevated", "حمل التكلفة الكامل مقابل الإيراد مرتفع.", "حالة عتبة التكلفة الكلية «{total_cost_threshold_status}»؛ مستوى الضغط {pressure_level}؛ {flag_count} علم(أعلام) هيكلية.", "برنامج تكلفة شمولي: تكلفة بضاعة وOpEx ونظافة تصنيف القوائم مع اجتماعات شهرية."),
    ("neutral_bands", "النسب في نطاق محايد مقارنة بالعتبات الافتراضية؛ استمر بالمراقبة.", "فرع الضغط «{pressure_branch}»؛ حالة OpEx «{opex_threshold_status}»؛ حالة التكلفة الكلية «{total_cost_threshold_status}».", "استمر بمراقبة الفئات؛ صعّد إذا تجاوزت أي مؤشرات تحذيراً لإغلاقين متتاليين."),
]
for b, c, ca, a in _ar_exp:
    AR[f"expense_deep.pressure.{b}.change"] = c
    AR[f"expense_deep.pressure.{b}.cause"] = ca
    AR[f"expense_deep.pressure.{b}.action"] = a

# prof note AR
_ar_pn = [
    ("operating_pressure_high", "ضغط تشغيلي مرتفع — سوءت نسب التكلفة مادياً مقارنة بالفترة السابقة.", "ضغط تشغيل «{operating_pressure}» وجودة أرباح «{earnings_quality}» (ملاحظة {note_id}).", "أولوية لهامش إجمالي وOpEx مع قائمة إجراءات تنفيذية 30 يوماً ومراجعة انحراف أسبوعية."),
    ("volatile_earnings_vs_sales", "تقلب أرباح يفوق تقلب إيراد — أرباح أقل قابلية للتنبؤ من المبيعات.", "جودة أرباح «{earnings_quality}»؛ ضغط «{operating_pressure}» (ملاحظة {note_id}).", "افحص لمرة واحدة والمزيج والتوقيت؛ نعّم البنود المتقطعة؛ ضيّق نطاق التوقعات."),
    ("deteriorating_earnings_trend", "عدة قراءات زخم ربح ضعيف — خطر اتجاه متدهور.", "جودة أرباح «{earnings_quality}»؛ ضغط «{operating_pressure}» (ملاحظة {note_id}).", "أكّد انضباط التكلفة والسعر؛ قواعد إيقاف للمبيعات سالبة الهامش؛ جسر P&L أسبوعي."),
]
for n, c, ca, a in _ar_pn:
    AR[f"profitability_deep.note.{n}.change"] = c
    AR[f"profitability_deep.note.{n}.cause"] = ca
    AR[f"profitability_deep.note.{n}.action"] = a

# prof exec AR
_ar_pe = [
    ("strong_but_heavy", "الربحية قوية على الهامش الصافي لكن الحمل التكلفي الإجمالي ثقيل مقابل الإيراد.", "قاعدة {rule_id}: اتجاه إيراد {revenue_trend_direction}، اتجاه ربح {net_profit_trend_direction}، إيراد الفترة صاعد {revenue_up_period}.", "احمِ الهامش مع ترشيد هيكل التكلفة؛ تجنّب نمو يخفض اقتصاديات الوحدة."),
    ("margins_declining_expenses", "الهوامش تتراجع مع ضغط نسبة المصاريف في النافذة.", "قاعدة {rule_id}: اتجاه إيراد {revenue_trend_direction}، اتجاه ربح {net_profit_trend_direction}، إيراد الفترة صاعد {revenue_up_period}.", "استهدف OpEx وتكلفة البضاعة؛ أعد التسعير حيث مبرر؛ تابع الهامش أسبوعياً."),
    ("rev_not_profit", "زخم الإيراد لا يتحول لربح — مشكلة جودة نمو.", "قاعدة {rule_id}: اتجاه إيراد {revenue_trend_direction}، اتجاه ربح {net_profit_trend_direction}، إيراد الفترة صاعد {revenue_up_period}.", "تشخيص هامش بالقطاع؛ أوقف حجماً غير مربح؛ اربط الحوافز بصافي الربح."),
    ("neutral", "مؤشرات الربحية ضمن النطاق الملاحظ؛ استمر بالمراقبة المنضبطة.", "قاعدة {rule_id}: اتجاه إيراد {revenue_trend_direction}، اتجاه ربح {net_profit_trend_direction}، إيراد الفترة صاعد {revenue_up_period}.", "استمر بمراجعات الهامش والتكلفة المعتادة؛ لا إجراء واسع حتى كسر عتبة."),
]
for r, c, ca, a in _ar_pe:
    AR[f"profitability_deep.exec.{r}.change"] = c
    AR[f"profitability_deep.exec.{r}.cause"] = ca
    AR[f"profitability_deep.exec.{r}.action"] = a

# Copy decision keys to AR from a compact loop - we already did liq and prof partially - need all decision keys in AR
for k, v in EN_CAUSAL.items():
    if k.startswith("decision.causal.") and k not in AR:
        AR[k] = v  # fallback same as EN for any missed - shouldn't happen

# Turkish (professional) — full parity with EN_CAUSAL keys
TR: dict[str, str] = {}
TR.update({
    "decision.causal.liq_immediate_cashflow.change": "Likidite baskısı: cari oran {cr} — nakit ve işletme sermayesi kapsamı acil yönetim gerektirir.",
    "decision.causal.liq_immediate_cashflow.cause": "Kısa vadeli ödeme gücü zayıf; cari oran {cr} güvenli işletme tabanının altında.",
    "decision.causal.liq_immediate_cashflow.action": "Tahsilat, vade koşulları, stok ve rolling nakit tahminine öncelik verin; kovenant riskinde yedek finansman hazırlayın.",
    "decision.causal.liq_strengthen_working_capital.change": "İşletme sermayesi operasyon ve büyüme için güçlendirilmelidir.",
    "decision.causal.liq_strengthen_working_capital.cause": "Likidite göstergeleri «{domain}» alanında (öncelik sırası {decision_priority_rank}) sermaye yapısı gözden geçirmesini gerektiriyor.",
    "decision.causal.liq_strengthen_working_capital.action": "Stok, alacak ve borçları sıkılaştırın; finansmanı nakit tepe dönemleriyle hizalayın.",
    "decision.causal.prof_margin_recovery.change": "Net marj {nm} — puan başına {per_pp} kaldıraç marj iyileştirmesini üst CFO önceliği yapar.",
    "decision.causal.prof_margin_recovery.cause": "Kârlılık hedefin altında; küçük marj hareketleri maddi P&L etkisi yaratır ({per_pp}).",
    "decision.causal.prof_margin_recovery.action": "Marj köprüsü (fiyat, karması, SMM, OpEx); sahipler ve 30–60 günlük plan.",
    "decision.causal.prof_cost_structure_review.change": "Brüt marj bağlamı {gm} — maliyet yapısı ve fiyatlandırma yönetici incelemesi gerektirir.",
    "decision.causal.prof_cost_structure_review.cause": "SMM ve brüt marj profili karması, tedarik veya fiyat baskısına işaret eder.",
    "decision.causal.prof_cost_structure_review.action": "SMM’yi ürün/kanal bazında bölün; tedarikçileri kıyaslayın; israf ve vade kazanımlarını hedefleyin.",
    "decision.causal.eff_cash_cycle_optimization.change": "Nakit dönüşüm döngüsü {ccc} gün — nakit operasyonda kilitli.",
    "decision.causal.eff_cash_cycle_optimization.cause": "Döngü uzunluğu alacak, stok ve/veya ödeme politikasını kısıtlıyor ({freed} ölçekte serbest nakit örneği).",
    "decision.causal.eff_cash_cycle_optimization.action": "DSO, stok günü ve DPO’yu birlikte ele alın; satışı tahsil edilen nakitle hizalayın.",
    "decision.causal.eff_receivables_management.change": "DSO {dso} gün — tahsilat ve kredi kalitesi odak gerektirir.",
    "decision.causal.eff_receivables_management.cause": "Alacak süresi işletme sermayesi riskini artırır.",
    "decision.causal.eff_receivables_management.action": "Yaşlandırma; limitler; otomatik tahsilat; KPI’ları tahsilata bağlayın.",
    "decision.causal.lev_debt_reduction.change": "Borç/özkaynak {de} — bilanço riski hedeflerin üzerinde.",
    "decision.causal.lev_debt_reduction.cause": "Yüksek kaldıraç faiz, kovenant ve durgunlukta nakit kapsamına duyarlılık artırır.",
    "decision.causal.lev_debt_reduction.action": "Vadeleri ve kovanları haritalayın; en yüksek maliyetli borcu önce kapatın; stratejik olmayan harcamayı durdurun.",
    "decision.causal.growth_revenue_acceleration.change": "Büyüme modu: talebi desteklerken marj ve nakit disiplinini koruyun («{domain}», sıra {decision_priority_rank}).",
    "decision.causal.growth_revenue_acceleration.cause": "Trendler birim ekonomi ve kapasite doğrulanırsa seçici hızlanmayı destekler.",
    "decision.causal.growth_revenue_acceleration.action": "1–2 kaldıraç seçin; mümkünse işletme nakdinden finanse edin; haftalık öncü göstergeleri izleyin.",
    "decision.causal.growth_margin_expansion.change": "Gelir ivmesi ({rev_ytd}) verimlilik ve karmasıyla marj genişletme alanı sunuyor.",
    "decision.causal.growth_margin_expansion.cause": "Üst hat gücü süreç ve tedarik iyileştirmelerini bileşik marja dönüştürebilir.",
    "decision.causal.growth_margin_expansion.action": "Yatırımı verimlilik hedefleriyle eşleştirin; brüt marjı fiyat/karması kurallarıyla koruyun.",
})

# TR narrative, ai_cfo, expense, profitability - add from EN with Turkish translations (abbrev set)
_tr_narr = [
    ("margin_pressure", "«{domain}» bağlamında marj baskısı ({merged_count} birleşik sinyal) — brüt marj gelir ivmesine göre gerilimli.", "SMM ve gelir dinamiği brüt marj sıkışması gösteriyor.", "Fiyat, karması ve SMM’yi birlikte ele alın; marj stabilize olana kadar gereksiz OpEx’i dondurun."),
    ("cost_spike", "«{domain}» içinde işletme gideri yoğunluğu belirgin şekilde arttı ({merged_count} sinyal).", "Gider oranı ivmesi geliri geçti, faaliyet marjını sıkıştırdı.", "Değişken gider kalemlerini denetleyin; sözleşmeleri yeniden konuşun; OpEx bütçesini sürdürülebilir paya çekin."),
    ("profit_growth_quality_issue", "Kar büyümesi gelirin gerisinde «{domain}» ({merged_count} sinyal) — büyüme kalitesi zayıf.", "Artan gelir maliyet veya düşük marjlı karması tarafından emiliyor.", "Marjı segment bazında izleyin; iskontoları sıkılaştırın; yeni gelirde birim ekonomiyi iyileştirin."),
    ("strong_profitability", "«{domain}» güçlü kârlılık sinyali ({merged_count} sinyal) — marjlar eşiklere göre sağlıklı.", "Net marj gücü fiyat gücü ve/veya maliyet kontrolüne işaret eder.", "Marjı disiplinle koruyun; ölçeklenebilir büyümeye seçici yeniden yatırım yapın."),
    ("cost_anomaly", "«{domain}» maliyet anomalisi ({merged_count} sinyal) — SMM gelire göre keskin hareket etti.", "Ani SMM payı değişimleri genelde karması, girdi fiyatı veya tek seferlik kalemlerden kaynaklanır.", "İki hafta içinde doğrulayın; fiyatlandırma veya tedariki düzeltin; sınıflandırma hatasını ekarte edin."),
    ("margin_anomaly", "«{domain}» marj anomalisi ({merged_count} sinyal) — zayıf net marj ve bozulmuş kar ivmesi.", "Düşük marj ve negatif kar ivmesi faaliyet zararı riskini yükseltir.", "Acil marj teşhisi: fiyatlandırma, değişken maliyet, kapasite kullanımı."),
    ("expense_outlier", "«{domain}» gider aşırılığı ({merged_count} sinyal) — OpEx’in gelire oranı yapısal olarak yüksek.", "Yüksek OpEx oranı şok emilimi ve yatırım kapasitesini daraltır.", "Kalem bazlı inceleme; 2–3 çeyrekte eşiğin altına oran hedefi."),
    ("revenue_drop", "«{domain}» gelir daralması sinyali ({merged_count} sinyal).", "Üst hat düşüşü nakdi, sabit maliyet kapsamını ve esnekliği baskılar.", "Boru hattı iyileştirmesi: müşteri tutma, fiyatlandırma, hacme bağlı maliyet esnekliği."),
]
for p, c, ca, a in _tr_narr:
    TR[f"narrative.causal.{p}.change"] = c
    TR[f"narrative.causal.{p}.cause"] = ca
    TR[f"narrative.causal.{p}.action"] = a

_tr_ai = [
    ("COST_REDUCTION", "Sezgisel duruş MALİYET AZALTMA — risk {risk_score}/100, öncelik {priority}, zarar bayrağı {is_loss}.", "Gider yükü ve marj pozisyonu maliyet kesimini birincil kaldıraç yapıyor.", "%5–10 çekirdek dışı OpEx; tedarikçi müzakeresi; haftalık tasarruf takibi."),
    ("SCALE_UP", "Sezgisel duruş ÖLÇEKLEME — risk {risk_score}/100, öncelik {priority}, zarar bayrağı {is_loss}.", "Marj ve büyüme ivmesi ölçü kontrollü genişlemeyi destekliyor.", "İşletme nakdinden finanse edin; ölçekten önce pilot; marj ve IS haftalık izlensin."),
    ("OPTIMIZE", "Sezgisel duruş OPTİMİZASYON — risk {risk_score}/100, öncelik {priority}, zarar bayrağı {is_loss}.", "Performans orta bantta; hedefli verimlilik genel kesimden iyi.", "2–3 KPI seçin; 90 günlük iyileştirme sprintleri."),
    ("RESTRUCTURE", "Sezgisel duruş YENİDEN YAPILANMA — risk {risk_score}/100, öncelik {priority}, zarar bayrağı {is_loss}.", "Marj ve maliyet yapısı kırık veya aşırı geniş bir modele işaret ediyor.", "Maliyet tabanını sıfırlayın; SKU/lokasyon sadeleştirin; likiditeyi koruyun."),
    ("CLOSE", "Sezgisel duruş KAPANIŞ — risk {risk_score}/100, öncelik {priority}, zarar bayrağı {is_loss}.", "Süregelen zarar ve kritik gider yükü varoluşsal nakit riski taşır.", "Kapanma vs toparlanma modeli; paydaşlar; yasal yükümlülükler."),
    ("MONITOR", "Sezgisel duruş İZLEME — risk {risk_score}/100, öncelik {priority}, zarar bayrağı {is_loss}.", "Sinyaller sınırda; erken müdahale istikrarı bozabilir.", "İki kapanış daha gelir ve marjı izleyin; acil planları hazır tutun."),
]
for t, c, ca, a in _tr_ai:
    TR[f"ai_cfo.decision.{t}.change"] = c
    TR[f"ai_cfo.decision.{t}.cause"] = ca
    TR[f"ai_cfo.decision.{t}.action"] = a

_tr_exp = [
    ("cogs_material_vs_opex", "Tam maliyet yükü yalnızca OpEx görünümünden belirgin şekilde büyük — SMM tabakası baskın.", "Toplam maliyet ile OpEx oranı farkı brüt marj ve doğrudan maliyet kollarının aynı derecede önemli olduğunu gösterir.", "SMM, fiyatlandırma ve tedarik ile OpEx’i birlikte gözden geçirin."),
    ("opex_elevated", "İşletme gideri oranı gelire göre iç eşiklerin üzerinde.", "OpEx eşik durumu «{opex_threshold_status}»; toplam maliyet durumu «{total_cost_threshold_status}».", "OpEx kalem denetimi; sözleşme müzakeresi; oran normale dönene kadar harcamayı erteleyin."),
    ("total_cost_elevated", "Tam maliyet yükü (SMM + OpEx + sınıflandırılmamış) gelire göre yüksek.", "Toplam maliyet eşik durumu «{total_cost_threshold_status}»; baskı seviyesi {pressure_level}; {flag_count} yapısal bayrak.", "Kapsamlı maliyet programı: SMM, OpEx ve P&L sınıflandırma hijyeni; aylık yönetişim."),
    ("neutral_bands", "Oranlar varsayılan eşiklere göre nötr bantta; izlemeye devam.", "Baskı kolu «{pressure_branch}»; OpEx durumu «{opex_threshold_status}»; toplam maliyet «{total_cost_threshold_status}».", "Kategori izlemesi; ardışık iki kapanışta uyarı aşılırsa yükseltin."),
]
for b, c, ca, a in _tr_exp:
    TR[f"expense_deep.pressure.{b}.change"] = c
    TR[f"expense_deep.pressure.{b}.cause"] = ca
    TR[f"expense_deep.pressure.{b}.action"] = a

_tr_pn = [
    ("operating_pressure_high", "İşletme maliyet baskısı yüksek — oranlar önceki döneme göre belirgin kötüleşti.", "İşletme baskısı «{operating_pressure}»; kazanç kalitesi «{earnings_quality}» (not {note_id}).", "Brüt marj ve OpEx önceliği; 30 günlük eylem listesi ve haftalık sapma incelemesi."),
    ("volatile_earnings_vs_sales", "Kar oynaklığı gelir oynaklığını aşıyor — kazançlar satıştan daha az öngörülebilir.", "Kazanç kalitesi «{earnings_quality}»; baskı «{operating_pressure}» (not {note_id}).", "Tek seferlikleri, karması ve zamanlamayı inceleyin; tahmin aralıklarını daraltın."),
    ("deteriorating_earnings_trend", "Ardışık zayıf kar ivmesi okumaları — bozulma trendi riski.", "Kazanç kalitesi «{earnings_quality}»; baskı «{operating_pressure}» (not {note_id}).", "Maliyet ve fiyat disiplinini doğrulayın; negatif marjlı satışa dur kuralları; haftalık P&L köprüsü."),
]
for n, c, ca, a in _tr_pn:
    TR[f"profitability_deep.note.{n}.change"] = c
    TR[f"profitability_deep.note.{n}.cause"] = ca
    TR[f"profitability_deep.note.{n}.action"] = a

_tr_pe = [
    ("strong_but_heavy", "Net marjda kârlılık güçlü ancak gelire göre toplam maliyet yükü ağır.", "Kural {rule_id}: gelir trendi {revenue_trend_direction}, kar trendi {net_profit_trend_direction}, dönem geliri yukarı {revenue_up_period}.", "Marjı korurken maliyet yapısını rasyonelize edin; birim ekonomiyi sulandıran büyümeden kaçının."),
    ("margins_declining_expenses", "Marjlar pencerede gider oranı baskısıyla düşüyor.", "Kural {rule_id}: gelir trendi {revenue_trend_direction}, kar trendi {net_profit_trend_direction}, dönem geliri yukarı {revenue_up_period}.", "OpEx ve SMM kollarını hedefleyin; gerekçeyle fiyatı gözden geçirin; marjı haftalık izleyin."),
    ("rev_not_profit", "Gelir ivmesi kara akmıyor — büyüme kalitesi sorunu.", "Kural {rule_id}: gelir trendi {revenue_trend_direction}, kar trendi {net_profit_trend_direction}, dönem geliri yukarı {revenue_up_period}.", "Segment bazında marj teşhisi; kârsız hacmi kesin; teşvikleri net kara bağlayın."),
    ("neutral", "Kârlılık göstergeleri gözlenen aralıkta; disiplinli izlemeye devam.", "Kural {rule_id}: gelir trendi {revenue_trend_direction}, kar trendi {net_profit_trend_direction}, dönem geliri yukarı {revenue_up_period}.", "Standart marj ve maliyet incelemeleri; eşik ihlali olmadan geniş müdahale yok."),
]
for r, c, ca, a in _tr_pe:
    TR[f"profitability_deep.exec.{r}.change"] = c
    TR[f"profitability_deep.exec.{r}.cause"] = ca
    TR[f"profitability_deep.exec.{r}.action"] = a


def merge(path: Path, extra: dict[str, str]) -> None:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    overlap = set(data) & set(extra)
    if overlap:
        raise SystemExit(f"Keys already exist in {path.name}: {sorted(overlap)[:10]}...")
    data.update(extra)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    if set(EN_CAUSAL) != set(AR_CAUSAL):
        raise SystemExit(
            "EN/AR causal key mismatch: "
            f"missing_in_AR={sorted(set(EN_CAUSAL) - set(AR_CAUSAL))[:12]}"
        )
    if set(EN_CAUSAL) != set(TR):
        raise SystemExit(
            "EN/TR causal key mismatch: "
            f"missing_in_TR={sorted(set(EN_CAUSAL) - set(TR))[:12]}"
        )
    merge(LOCALES / "en.json", EN_CAUSAL)
    merge(LOCALES / "ar.json", AR_CAUSAL)
    merge(LOCALES / "tr.json", TR)
    print("merged", len(EN_CAUSAL), "keys per locale (en, ar, tr)")


if __name__ == "__main__":
    main()
