"""
narrative_builder.py — Phase 43 Narrative Builder (CFO Layer)

Transforms root_cause_engine + anomaly_engine outputs into a unified,
executive-grade narrative list. No financial recalculation. No new logic.

Merge rule: root causes and anomalies that share a cost/margin/revenue domain
are merged into a single narrative to eliminate duplicates.

Wave 2B: build_narratives returns a list subclass that also exposes ``causal_items``
(structured causal contract fragments; no prose merge — realization is downstream).
"""
from __future__ import annotations

# ── Severity / priority maps ──────────────────────────────────────────────────

_HIGH_TYPES = {
    "margin_pressure", "revenue_drop",
    # anomalies auto-high when severity == "high"
}
_MEDIUM_TYPES = {
    "cost_spike", "margin_anomaly", "expense_outlier",
    "profit_growth_quality_issue",
}
_LOW_TYPES = {
    "strong_profitability",
}

# Domain grouping — used for merge logic
_COST_DOMAIN    = {"cost_anomaly", "cost_spike", "expense_outlier"}
_MARGIN_DOMAIN  = {"margin_pressure", "margin_anomaly"}
_REVENUE_DOMAIN = {"revenue_drop", "profit_growth_quality_issue"}

def _domain(t: str) -> str:
    if t in _COST_DOMAIN:    return "cost"
    if t in _MARGIN_DOMAIN:  return "margin"
    if t in _REVENUE_DOMAIN: return "revenue"
    return t  # unique domain for everything else


def _priority(item: dict) -> str:
    t   = item.get("type", "")
    sev = item.get("severity", "medium")
    if sev == "high" or t in _HIGH_TYPES:
        return "high"
    if t in _LOW_TYPES:
        return "low"
    return "medium"


def _urgency(priority: str, item: dict) -> str:
    if priority == "high":
        return "immediate"
    if priority == "medium":
        return "soon"
    return "monitor"


# ── Decision hints ────────────────────────────────────────────────────────────

_DECISION_HINTS: dict[str, dict[str, str]] = {
    "cost": {
        "en": "Review supplier contracts and variable cost structure immediately.",
        "ar": "مراجعة فورية لعقود الموردين وهيكل التكاليف المتغيرة.",
        "tr": "Tedarikçi sözleşmelerini ve değişken maliyet yapısını acil inceleyin.",
    },
    "margin": {
        "en": "Diagnose margin drivers: pricing, COGS mix, and fixed cost leverage.",
        "ar": "تشخيص محركات الهامش: التسعير، مزيج تكلفة البضاعة، والرافعة التشغيلية.",
        "tr": "Marj sürücülerini tanılayın: fiyatlandırma, SMM karışımı ve sabit maliyet kaldıracı.",
    },
    "revenue": {
        "en": "Identify revenue concentration risk and activate pipeline recovery actions.",
        "ar": "تحديد مخاطر تركّز الإيرادات وتفعيل إجراءات استعادة خط المبيعات.",
        "tr": "Gelir yoğunlaşma riskini belirleyin ve satış hattı kurtarma eylemlerini başlatın.",
    },
    "strong_profitability": {
        "en": "Protect margin discipline; assess capacity expansion with cost controls.",
        "ar": "الحفاظ على انضباط الهامش؛ تقييم توسع الطاقة مع ضوابط التكلفة.",
        "tr": "Marj disiplinini koruyun; maliyet kontrolleriyle kapasite genişlemesini değerlendirin.",
    },
    "profit_growth_quality_issue": {
        "en": "Audit incremental cost of revenue; benchmark margins on new business.",
        "ar": "تدقيق التكلفة الهامشية للإيرادات؛ قياس هوامش الأعمال الجديدة.",
        "tr": "Artımlı gelir maliyetini denetleyin; yeni iş marjlarını kıyaslayın.",
    },
}

def _hint(domain: str, lang: str) -> str:
    bucket = _DECISION_HINTS.get(domain, {})
    return bucket.get(lang) or bucket.get("en", "")


# ── Merge text from two items (prefer the longer / more detailed) ─────────────

def _best(field: str, primary: dict, secondary: dict) -> str:
    a = primary.get(field) or ""
    b = secondary.get(field) or ""
    return a if len(a) >= len(b) else b


# ── Wave 2B causal_items (deterministic; no prose merge) ─────────────────────

_NARRATIVE_CAUSAL_PREFIX = "narrative.causal"


class NarrativeBuildResult(list):
    """List of legacy narrative dicts with a parallel ``causal_items`` array."""

    __slots__ = ("causal_items",)

    def __init__(self, narratives: list, causal_items: list) -> None:
        super().__init__(narratives)
        object.__setattr__(self, "causal_items", causal_items)


def _topic_for_domain(domain: str) -> str:
    """Map merge domain to causal_contract-style topic (unknown domains pass through)."""
    if domain in ("cost", "margin", "revenue"):
        return domain
    if domain == "strong_profitability":
        return "growth"
    return domain


def _causal_severity_from_priority(priority: str) -> str:
    """Causal severities are low | medium | high (deterministic mapping)."""
    p = (priority or "medium").lower()
    if p == "high":
        return "high"
    if p == "low":
        return "low"
    return "medium"


def _causal_params(merged_metrics: dict, domain: str, merged_count: int) -> dict:
    """Flat params for template interpolation (metrics + structural facts only)."""
    params: dict = {}
    for k in sorted(merged_metrics.keys()):
        params[k] = merged_metrics[k]
    params["domain"] = domain
    params["merged_count"] = merged_count
    return params


def _causal_item_for_narrative(
    *,
    domain: str,
    items: list,
    primary: dict,
    priority: str,
    merged_metrics: dict,
) -> dict:
    primary_type = str(primary.get("type", "") or domain)
    merged_from = sorted({str(it.get("type", "") or "") for it in items if it})
    merged_from = [x for x in merged_from if x]
    template_ids = [f"phase43.{t}" for t in merged_from]
    mc = len(items)
    params = _causal_params(merged_metrics, domain, mc)
    sev = _causal_severity_from_priority(priority)
    cid = f"narrative:{domain}:{primary_type}"
    return {
        "id": cid,
        "topic": _topic_for_domain(domain),
        "change": {"key": f"{_NARRATIVE_CAUSAL_PREFIX}.{primary_type}.change", "params": params},
        "cause": {"key": f"{_NARRATIVE_CAUSAL_PREFIX}.{primary_type}.cause", "params": params},
        "action": {"key": f"{_NARRATIVE_CAUSAL_PREFIX}.{primary_type}.action", "params": params},
        "severity": sev,
        "source": "narrative",
        "evidence": {
            "source_metrics": dict(merged_metrics),
            "template_ids": template_ids,
            "merged_from": merged_from,
        },
    }


# ── Core builder ──────────────────────────────────────────────────────────────

def build_narratives(
    root_causes: list,
    anomalies:   list,
    lang:        str = "en",
) -> NarrativeBuildResult:
    """
    Merge root_cause + anomaly outputs into a unified CFO narrative list.

    Rules:
    - Items sharing the same domain are merged (one narrative per domain).
    - Max 5 narratives returned; sorted by priority (high → medium → low).
    - All text is returned in the selected language (en | ar | tr).
    - No financial recalculation; only structural transformation.

    Return value is a list (subclass) of narrative dicts; use ``result.causal_items``
    for the parallel causal contract rows (same order and length as narratives).
    """
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"

    # Pool all items from both engines
    all_items: list[dict] = list(root_causes) + list(anomalies)

    # ── Group by domain ───────────────────────────────────────────────────────
    groups: dict[str, list[dict]] = {}
    for item in all_items:
        d = _domain(item.get("type", ""))
        groups.setdefault(d, []).append(item)

    # ── Build one narrative per domain group ──────────────────────────────────
    narratives: list[dict] = []
    causal_items: list[dict] = []

    for domain, items in groups.items():
        # Primary = highest severity item in the group (legacy behavior unchanged)
        _sev_rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
        items_sorted = sorted(items, key=lambda x: _sev_rank.get(x.get("severity", "medium"), 4))
        primary   = items_sorted[0]
        secondary = items_sorted[1] if len(items_sorted) > 1 else {}

        pri  = _priority(primary)
        urg  = _urgency(pri, primary)
        hint = _hint(domain, safe_lang)

        # Merge source_metrics — legacy insertion order for collisions on duplicate keys
        merged_metrics: dict = {}
        for it in items:
            merged_metrics.update(it.get("source_metrics") or {})

        # Build narrative fields — prefer richer text from items
        what_happened  = _best("what_happened",  primary, secondary)
        why_it_matters = (
            _best("why_it_matters", primary, secondary)
            or _best("why",         primary, secondary)
        )
        # what_to_do: try all keys across all items in group, pick longest
        what_to_do = ""
        for it in items:
            for key in ("what_to_do", "action", "recommendation"):
                candidate = it.get(key) or ""
                if len(candidate) > len(what_to_do):
                    what_to_do = candidate
        # Final fallback: use decision_hint if still empty
        if not what_to_do:
            what_to_do = hint

        # Collect all drivers (deduplicated)
        drivers: list[str] = []
        for it in items:
            for d in (it.get("drivers") or []):
                if d not in drivers:
                    drivers.append(d)

        narrative = {
            "type":          primary.get("type", domain),
            "domain":        domain,
            "what_happened": what_happened,
            "why_it_matters":why_it_matters,
            "what_to_do":    what_to_do,
            "priority":      pri,
            "urgency":       urg,
            "decision_hint": hint,
            "drivers":       drivers,
            "source_metrics":merged_metrics,
            "target_scope":  "company",
            "merged_count":  len(items),
        }
        narratives.append(narrative)
        causal_items.append(
            _causal_item_for_narrative(
                domain=domain,
                items=items,
                primary=primary,
                priority=pri,
                merged_metrics=dict(merged_metrics),
            )
        )

    # ── Sort: high → medium → low, then by domain for stability ──────────────
    _pri_rank = {"high": 0, "medium": 1, "low": 2}
    order_key = lambda n: (_pri_rank.get(n["priority"], 3), n["domain"])
    combined = list(zip(narratives, causal_items))
    combined.sort(key=lambda pair: order_key(pair[0]))
    narratives = [p[0] for p in combined]
    causal_items = [p[1] for p in combined]

    # ── Cap at 5 (drop lowest-priority excess) ────────────────────────────────
    return NarrativeBuildResult(narratives[:5], causal_items[:5])
