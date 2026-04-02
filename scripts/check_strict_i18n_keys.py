"""List strictT/st static string keys in frontend-react/src vs locale JSON."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend-react" / "src"
I18N = ROOT / "app" / "i18n"

pat_strict = re.compile(r"strictT\s*\(\s*tr\s*,\s*lang\s*,\s*['\"]([^'\"]+)['\"]\s*\)")
pat_st = re.compile(r"\bst\s*\(\s*tr\s*,\s*lang\s*,\s*['\"]([^'\"]+)['\"]\s*\)")


def main():
    keys: set[str] = set()
    for p in SRC.rglob("*.jsx"):
        t = p.read_text(encoding="utf-8")
        keys.update(pat_strict.findall(t))
        keys.update(pat_st.findall(t))

    for lang in ("en", "ar", "tr"):
        data = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
        missing = sorted(k for k in keys if k not in data)
        print(f"{lang}: {len(data)} keys in file, {len(keys)} static strict keys, missing {len(missing)}")
        for k in missing[:120]:
            print(f"  - {k}")
        if len(missing) > 120:
            print(f"  ... and {len(missing) - 120} more")


if __name__ == "__main__":
    main()
