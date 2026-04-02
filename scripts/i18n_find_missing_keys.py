"""
Find i18n keys referenced in frontend-react/src that are missing from app/i18n/en.json.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend-react" / "src"
I18N = ROOT / "app" / "i18n"

# strictT(tr, lang, 'key') or strictT(tr, lang, "key")
P_STRICT = re.compile(
    r"strictT\s*\(\s*tr\s*,\s*lang\s*,\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\)"
)
P_ST = re.compile(r"\bst\s*\(\s*tr\s*,\s*lang\s*,\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\)")
# tr('key') or tr("key") — avoid tr(' with newline
P_TR = re.compile(r"\btr\s*\(\s*['\"]([a-zA-Z0-9_]+)['\"]")
# t(translations, 'key') less common
P_T = re.compile(r"\bt\s*\(\s*translations?\s*,\s*['\"]([a-zA-Z0-9_]+)['\"]")

# Known prefix families from template literals (manual list from code scan)
PREFIX_SUFFIX = [
    ("dq_", []),  # codes from backend
    ("status_", ["excellent", "good", "warning", "risk", "neutral"], ["simple"]),
    ("urgency_", ["high", "medium", "low", "immediate", "this_quarter", "next_quarter", "soon", "monitor"]),
    ("impact_", ["critical", "high", "medium", "low", "profitability", "liquidity", "cost", "cashflow", "operational", "expected", "range_label", "based_on", "qualitative", "type_cash", "type_margin", "type_risk", "expected_label"]),
    ("ratio_", [
        "gross_margin_pct", "net_margin_pct", "operating_margin_pct", "ebitda_margin_pct",
        "current_ratio", "quick_ratio", "working_capital", "debt_to_equity", "debt_ratio_pct",
        "total_liabilities", "total_equity", "inventory_turnover", "dso_days", "dpo_days", "ccc_days",
        "strong", "adequate", "low", "status_good", "status_warning", "status_risk",
    ]),
    ("domain_", ["profitability", "liquidity", "efficiency", "leverage", "growth"]),
    ("domain_signal_", [f"{d}_{s}" for d in ["liquidity", "profitability", "efficiency", "leverage", "growth"] for s in ["good", "warn", "risk"]]),
    ("kpi_label_", ["revenue", "expenses", "net_profit", "cashflow", "net_margin", "working_capital"]),
    ("kpi_explain_", ["revenue", "net_profit", "cashflow", "net_margin", "expenses", "working_capital"]),
    ("cmd_dec_owner_", ["operations", "cfo", "finance", "hr", "it"]),
    ("cmd_dec_horizon_", ["immediate", "short", "medium", "long", "quarter"]),
    ("tab_", []),
]


def expand_prefix_keys(en_keys: set) -> set:
    extra = set()
    for prefix, mids, *rest in [
        ("status_", None, ["excellent", "good", "warning", "risk", "neutral"], ["simple"]),
    ]:
        pass  # use explicit below
    # status_{x}_simple
    for st in ["excellent", "good", "warning", "risk", "neutral"]:
        extra.add(f"status_{st}_simple")
    for u in ["high", "medium", "low", "immediate", "this_quarter", "next_quarter", "soon", "monitor"]:
        extra.add(f"urgency_{u}")
    for i in ["critical", "high", "medium", "low", "profitability", "liquidity", "cost", "cashflow", "operational", "expected", "range_label", "based_on", "qualitative", "type_cash", "type_margin", "type_risk", "expected_label"]:
        extra.add(f"impact_{i}")
    for r in [
        "gross_margin_pct", "net_margin_pct", "operating_margin_pct", "ebitda_margin_pct",
        "current_ratio", "quick_ratio", "working_capital", "debt_to_equity", "debt_ratio_pct",
        "total_liabilities", "total_equity", "inventory_turnover", "dso_days", "dpo_days", "ccc_days",
        "strong", "adequate", "low", "status_good", "status_warning", "status_risk",
    ]:
        extra.add(f"ratio_{r}")
    for d in ["profitability", "liquidity", "efficiency", "leverage", "growth"]:
        extra.add(f"domain_{d}")
        extra.add(f"domain_{d}_exp")
    for d in ["liquidity", "profitability", "efficiency", "leverage", "growth"]:
        for s in ["good", "warn", "risk"]:
            extra.add(f"domain_signal_{d}_{s}")
    for k in ["revenue", "expenses", "net_profit", "cashflow", "net_margin", "working_capital"]:
        extra.add(f"kpi_label_{k}")
        extra.add(f"kpi_explain_{k}")
    for o in ["operations", "cfo", "finance", "hr", "it"]:
        extra.add(f"cmd_dec_owner_{o}")
    for h in ["immediate", "short", "medium", "long", "quarter"]:
        extra.add(f"cmd_dec_horizon_{h}")
    # dq_ from en keys
    for k in en_keys:
        if k.startswith("dq_"):
            extra.add(k)
    return extra


def main():
    en_path = I18N / "en.json"
    en_data = json.loads(en_path.read_text(encoding="utf-8"))
    en_keys = set(en_data.keys())

    used = set()
    for p in SRC.rglob("*"):
        if p.suffix not in (".jsx", ".js", ".tsx", ".ts"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        used.update(P_STRICT.findall(text))
        used.update(P_ST.findall(text))
        used.update(P_TR.findall(text))
        used.update(P_T.findall(text))

    dynamic = expand_prefix_keys(en_keys)
    needed = used | dynamic
    missing = sorted(needed - en_keys)

    print("Static + heuristic keys referenced:", len(needed))
    print("Missing from en.json:", len(missing))
    for k in missing[:200]:
        print(" ", k)
    if len(missing) > 200:
        print(" ...", len(missing) - 200, "more")

    # Keys in code static extract only (not heuristic) missing
    static_missing = sorted(used - en_keys)
    print("\nStrict static-only missing:", len(static_missing))
    for k in static_missing:
        print(" ", k)


if __name__ == "__main__":
    main()
