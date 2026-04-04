#!/usr/bin/env python3
"""
Whole-project i18n audit (read-only).
- Parity: en / ar / tr keys in app/i18n/*.json
- Placeholders: {name} sets must match across locales per key
- Referenced keys: static tr()/strictT() in frontend; selected Python patterns
- Hardcoded English heuristic (noisy — flagged as "suspect")
- Fallback markers: [missing:], [invalid_lang:], [format_error:], [narrative_
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N_DIR = ROOT / "app" / "i18n"
LOCALES = ("en", "ar", "tr")


def _configure_stdout_utf8() -> None:
    """Avoid UnicodeEncodeError when printing reports on Windows (cp125x)."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", "htmlcov", "coverage", "terminals",
}
SCAN_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def load_locale_maps() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for loc in LOCALES:
        p = I18N_DIR / f"{loc}.json"
        if not p.exists():
            print(f"WARN: missing {p}", file=sys.stderr)
            continue
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise SystemExit(f"{p} root must be object")
        flat: dict[str, str] = {}
        for k, v in data.items():
            if isinstance(v, str):
                flat[k] = v
            elif isinstance(v, dict):
                for sk, sv in v.items():
                    if isinstance(sv, str):
                        flat[f"{k}.{sk}"] = sv
        out[loc] = flat
    return out


_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


def placeholders_in(s: str) -> frozenset[str]:
    return frozenset(_PLACEHOLDER_RE.findall(s or ""))


def audit_key_parity(maps: dict[str, dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """Returns (missing_key_reports, placeholder_mismatch_reports)."""
    en = maps.get("en", {})
    ar = maps.get("ar", {})
    tr = maps.get("tr", {})
    all_keys = set(en) | set(ar) | set(tr)

    missing: list[dict] = []
    for k in sorted(all_keys):
        row: dict = {"key": k, "missing_in": []}
        if k not in en:
            row["missing_in"].append("en")
        if k not in ar:
            row["missing_in"].append("ar")
        if k not in tr:
            row["missing_in"].append("tr")
        if row["missing_in"]:
            missing.append(row)

    ph_mismatch: list[dict] = []
    for k in sorted(set(en) & set(ar) & set(tr)):
        pe, pa, pt = placeholders_in(en[k]), placeholders_in(ar[k]), placeholders_in(tr[k])
        if pe != pa or pe != pt:
            ph_mismatch.append({
                "key": k,
                "en": sorted(pe),
                "ar": sorted(pa),
                "tr": sorted(pt),
            })
    return missing, ph_mismatch


# --- source scan ---

FRONTEND_KEY_PATTERNS = [
    re.compile(r"\btr\s*\(\s*['\"]([a-zA-Z][a-zA-Z0-9_.]*)['\"]"),
    re.compile(r"\bstrictT\s*\(\s*[^,]+,\s*[^,]+,\s*['\"]([a-zA-Z][a-zA-Z0-9_.]*)['\"]"),
    re.compile(r"\bstrictTParams\s*\(\s*[^,]+,\s*[^,]+,\s*['\"]([a-zA-Z][a-zA-Z0-9_.]*)['\"]"),
]

PY_KEY_PATTERNS = [
    # realize_ref({"key": "board.foo", ...})
    re.compile(r"""['\"]key['\"]\s*:\s*['\"]([a-zA-Z][a-zA-Z0-9_.]*)['\"]"""),
    # _t("template_key", lang
    re.compile(r"""\b_t\s*\(\s*['\"]([a-zA-Z][a-zA-Z0-9_.]*)['\"]"""),
    # format_simple_narrative("key"
    re.compile(r"""\bformat_simple_narrative\s*\(\s*['\"]([a-zA-Z][a-zA-Z0-9_.]*)['\"]"""),
]

# Exclude obvious false positives for Python "key": patterns
PY_KEY_FALSE_PREFIX = (
    "id", "type", "role", "mode", "status", "name", "path", "method", "level",
    "source", "topic", "severity", "action", "domain", "error", "code", "field",
    "basis", "window", "lang", "token", "email", "password", "message", "detail",
)


def should_skip_path(p: Path) -> bool:
    parts = set(p.parts)
    if parts & SKIP_DIRS:
        return True
    if "agent-transcripts" in parts:
        return True
    return False


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for base in (ROOT / "frontend-react" / "src", ROOT / "app"):
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in SCAN_EXT and not should_skip_path(p):
                files.append(p)
    for p in (ROOT / "scripts",):
        if p.exists():
            for f in p.rglob("*.py"):
                if not should_skip_path(f):
                    files.append(f)
    return sorted(set(files))


def extract_frontend_keys(text: str, path: Path) -> dict[str, list[int]]:
    found: dict[str, list[int]] = defaultdict(list)
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        # skip comments
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("*"):
            continue
        for pat in FRONTEND_KEY_PATTERNS:
            for m in pat.finditer(line):
                key = m.group(1)
                if "." in key or "_" in key or key.islower():
                    found[key].append(i)
    return found


def extract_python_i18n_keys(text: str, path: Path) -> dict[str, list[int]]:
    found: dict[str, list[int]] = defaultdict(list)
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("#"):
            continue
        for pat in PY_KEY_PATTERNS:
            for m in pat.finditer(line):
                key = m.group(1)
                if key.split(".")[0] in PY_KEY_FALSE_PREFIX and "." not in key:
                    continue
                # keep dotted keys (board.*, decision.causal.*, narrative.*, etc.)
                if "." in key or key.startswith(("warn_", "reconcile_", "trend_", "prev_", "whatif_", "board.", "cmd_", "narr_")):
                    found[key].append(i)
                elif "_" in key and len(key) > 4:
                    found[key].append(i)
    return found


FALLBACK_MARKERS = [
    "[missing:",
    "[invalid_lang:",
    "[format_error:",
    "[narrative_",
    "[missing_template:",
    "[missing_key:",
    "[locale_not_supported",
]

# Heuristic: likely sentence-like English in user-facing files
HARDCODE_EXCLUDE_LINE = re.compile(
    r"(logger\.|logging\.|console\.(log|debug|warn|error)|print\(|# noqa|"
    r"eslint-disable|@ts-ignore|import |from |require\(|describe\(|it\(|test\(|"
    r"http[s]?://|application/json|Bearer |Content-Type|multipart|"
    r"rgba?\(|var\(--|linear-gradient|keyframes|fontFamily:\s*['\"]monospace)",
    re.I,
)

HARDCODE_STRING_RE = re.compile(
    r"['\"]([A-Za-z][^'\"]{34,})['\"]"
)


def looks_like_prose_english(s: str) -> bool:
    s2 = s.strip()
    if len(s2) < 35:
        return False
    letters = sum(c.isalpha() for c in s2)
    if letters < len(s2) * 0.5:
        return False
    # mostly ASCII letters + punctuation
    non_ascii_letters = sum(1 for c in s2 if c.isalpha() and ord(c) > 127)
    if non_ascii_letters > letters * 0.35:
        return False  # likely Arabic etc. — not "English hardcode"
    words = s2.split()
    if len(words) < 5:
        return False
    return True


def scan_hardcoded_and_markers(path: Path, text: str) -> tuple[list[dict], list[dict]]:
    hard: list[dict] = []
    marks: list[dict] = []
    rel = str(path.relative_to(ROOT))
    is_test = "test" in path.parts or path.name.startswith("test_")
    is_internal = is_test or "scripts" in path.parts and path.suffix == ".py"

    skip_marker_scan = path.name == "i18n_audit.py" and path.parent.name == "scripts"
    for i, line in enumerate(text.splitlines(), 1):
        if not skip_marker_scan:
            for mk in FALLBACK_MARKERS:
                if mk in line:
                    marks.append({
                        "file": rel,
                        "line": i,
                        "marker": mk,
                        "snippet": line.strip()[:200],
                        "likely_internal": "causal_realize" in rel or "narrative_engine" in rel or "vcfo_ai_advisor" in rel,
                    })
        if HARDCODE_EXCLUDE_LINE.search(line):
            continue
        if path.suffix.lower() not in (".jsx", ".js", ".tsx", ".py"):
            continue
        for m in HARDCODE_STRING_RE.finditer(line):
            inner = m.group(1)
            if "tr(" in line or "strictT(" in line:
                continue
            if not looks_like_prose_english(inner):
                continue
            # skip if only template interpolation
            if inner.count("{") > 2:
                continue
            hard.append({
                "file": rel,
                "line": i,
                "snippet": inner[:120] + ("..." if len(inner) > 120 else ""),
                "likely_user_visible": path.suffix.lower() in (".jsx", ".tsx") and "test" not in rel,
                "likely_internal": is_internal or "migrations" in rel or "api" in rel and "test" not in rel,
            })
    return hard, marks


def main() -> int:
    _configure_stdout_utf8()
    maps = load_locale_maps()
    if len(maps) < 3:
        print("Expected en, ar, tr in app/i18n/", file=sys.stderr)
        return 2

    missing_keys, ph_mismatch = audit_key_parity(maps)
    en_keys = set(maps["en"])

    ref_frontend: dict[str, list[tuple[str, int]]] = defaultdict(list)
    ref_py: dict[str, list[tuple[str, int]]] = defaultdict(list)
    all_hard: list[dict] = []
    all_markers: list[dict] = []

    for path in iter_source_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = str(path.relative_to(ROOT))
        if "frontend-react" in rel and path.suffix.lower() in (".jsx", ".js", ".tsx", ".ts"):
            for k, lines in extract_frontend_keys(text, path).items():
                for ln in lines:
                    ref_frontend[k].append((rel, ln))
        if path.suffix.lower() == ".py":
            for k, lines in extract_python_i18n_keys(text, path).items():
                for ln in lines:
                    ref_py[k].append((rel, ln))
        h, m = scan_hardcoded_and_markers(path, text)
        all_hard.extend(h)
        all_markers.extend(m)

    def _is_narrative_internal(locs: list[tuple[str, int]]) -> bool:
        return all(
            "narrative_engine.py" in f.replace("\\", "/")
            for f, _ in locs
        )

    # Referenced keys missing from en.json (canonical app/i18n catalog)
    missing_refs_fe: list[dict] = []
    missing_refs_py: list[dict] = []
    internal_py_templates: list[dict] = []

    for key, locs in sorted(ref_frontend.items()):
        if key not in en_keys:
            missing_refs_fe.append({
                "key": key,
                "source": "frontend",
                "locations": [{"file": f, "line": ln} for f, ln in sorted(set(locs))[:12]],
                "count": len(set(locs)),
            })
    for key, locs in sorted(ref_py.items()):
        if key in en_keys:
            continue
        ulocs = list(set(locs))
        if _is_narrative_internal(ulocs):
            internal_py_templates.append({
                "key": key,
                "count": len(ulocs),
                "sample_line": ulocs[0][1] if ulocs else 0,
            })
            continue
        missing_refs_py.append({
            "key": key,
            "source": "python",
            "locations": [{"file": f, "line": ln} for f, ln in sorted(ulocs)[:12]],
            "count": len(ulocs),
        })

    # --- Report output ---
    lines_out: list[str] = []
    lines_out.append("# i18n audit report (whole project)")
    lines_out.append("")
    lines_out.append("## Summary counts")
    lines_out.append(f"- Missing keys (any locale vs union): **{len(missing_keys)}**")
    lines_out.append(f"- Placeholder mismatches (en/ar/tr): **{len(ph_mismatch)}**")
    lines_out.append(
        f"- Frontend `tr`/`strictT` keys not in en.json: **{len(missing_refs_fe)}** | "
        f"Python (excl. narrative_engine-only): **{len(missing_refs_py)}** | "
        f"narrative_engine `_t` keys (not i18n): **{len(internal_py_templates)}**"
    )
    lines_out.append(f"- Suspect hardcoded English strings (heuristic): **{len(all_hard)}**")
    lines_out.append(f"- Fallback marker occurrences: **{len(all_markers)}**")
    lines_out.append("")

    lines_out.append("## a) Missing keys (en / ar / tr parity)")
    lines_out.append("")
    blockers_mk = [x for x in missing_keys if len(x["missing_in"]) >= 2]
    single_mk = [x for x in missing_keys if len(x["missing_in"]) == 1]
    lines_out.append(f"### Severe (missing in 2+ locales): **{len(blockers_mk)}**")
    for item in blockers_mk[:80]:
        lines_out.append(f"- `{item['key']}` -> missing: {', '.join(item['missing_in'])}")
    if len(blockers_mk) > 80:
        lines_out.append(f"- ... plus {len(blockers_mk) - 80} more")
    lines_out.append("")
    lines_out.append(f"### Missing in one locale only: **{len(single_mk)}**")
    for item in single_mk[:40]:
        lines_out.append(f"- `{item['key']}` -> missing: {', '.join(item['missing_in'])}")
    if len(single_mk) > 40:
        lines_out.append(f"- ... plus {len(single_mk) - 40} more")
    lines_out.append("")

    lines_out.append("## b) Placeholder mismatches")
    lines_out.append("")
    for item in ph_mismatch[:60]:
        lines_out.append(f"- `{item['key']}`")
        lines_out.append(f"  - en: {item['en']}")
        lines_out.append(f"  - ar: {item['ar']}")
        lines_out.append(f"  - tr: {item['tr']}")
    if len(ph_mismatch) > 60:
        lines_out.append(f"- ... plus {len(ph_mismatch) - 60} more")
    lines_out.append("")

    lines_out.append("## c) Source-referenced keys missing from en.json")
    lines_out.append("")
    lines_out.append("*Static extraction only; dynamic `tr(\\`k_${x}\\`)` not included.*")
    lines_out.append("")
    lines_out.append("### c.1 Frontend - likely blockers")
    for item in missing_refs_fe[:80]:
        lines_out.append(f"- **`{item['key']}`** (~{item['count']} refs)")
        for loc in item["locations"][:5]:
            lines_out.append(f"  - `{loc['file']}:{loc['line']}`")
    if len(missing_refs_fe) > 80:
        lines_out.append(f"- ... plus {len(missing_refs_fe) - 80} more")
    lines_out.append("")
    lines_out.append("### c.2 Python (excluding keys referenced only from narrative_engine.py)")
    for item in missing_refs_py[:80]:
        lines_out.append(f"- **`{item['key']}`** (~{item['count']} refs)")
        for loc in item["locations"][:5]:
            lines_out.append(f"  - `{loc['file']}:{loc['line']}`")
    if len(missing_refs_py) > 80:
        lines_out.append(f"- ... plus {len(missing_refs_py) - 80} more")
    lines_out.append("")
    lines_out.append("### c.3 narrative_engine `_t` keys (internal templates - not in app/i18n)")
    lines_out.append(f"*Count: {len(internal_py_templates)} unique keys (sample first 25)*")
    for item in internal_py_templates[:25]:
        lines_out.append(f"- `{item['key']}`")
    lines_out.append("")

    lines_out.append("## d) Suspect hardcoded English (heuristic)")
    lines_out.append("")
    lines_out.append("**Likely user-visible (jsx/tsx, non-test):**")
    uv = [x for x in all_hard if x.get("likely_user_visible") and not x.get("likely_internal")]
    for item in uv[:50]:
        lines_out.append(f"- `{item['file']}:{item['line']}` - {item['snippet']}")
    lines_out.append("")
    lines_out.append("**Likely internal / tests / API (still English prose):**")
    iv = [x for x in all_hard if x not in uv]
    for item in iv[:40]:
        lines_out.append(f"- `{item['file']}:{item['line']}` - {item['snippet']}")
    if len(iv) > 40:
        lines_out.append(f"- ... plus {len(iv) - 40} more")
    lines_out.append("")

    lines_out.append("## e) Fallback / error markers in source")
    lines_out.append("")
    user_mark = [x for x in all_markers if not x.get("likely_internal")]
    int_mark = [x for x in all_markers if x.get("likely_internal")]
    lines_out.append("### User-facing code paths (review)")
    for item in user_mark[:40]:
        lines_out.append(f"- `{item['file']}:{item['line']}` `{item['marker']}`")
    lines_out.append("")
    lines_out.append("### Internal realization / templates (expected)")
    for item in int_mark[:30]:
        lines_out.append(f"- `{item['file']}:{item['line']}` `{item['marker']}`")
    if len(int_mark) > 30:
        lines_out.append(f"- ... plus {len(int_mark) - 30} more")
    lines_out.append("")

    lines_out.append("## Blockers vs non-blocking (audit opinion)")
    lines_out.append("")
    lines_out.append("- **Blocker-class:** keys missing in 2+ locales; placeholder mismatches for keys used in UI; ")
    lines_out.append("  frontend `tr()` references to keys absent from `en.json`; user-visible hardcoded English in `.jsx`/`.tsx`.")
    lines_out.append("- **Non-blocking:** keys missing in only one locale (fix parity); Python `_t()` keys that belong to ")
    lines_out.append("  `narrative_engine` templates (not `app/i18n`); markers inside `causal_realize.py` / intentional placeholders; ")
    lines_out.append("  heuristic false positives in hardcoded scan.")
    lines_out.append("")

    report_text = "\n".join(lines_out)
    out_path = ROOT / "scripts" / "i18n_audit_report.md"
    out_path.write_text(report_text, encoding="utf-8")
    print(report_text)
    print(f"\n---\nWrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
