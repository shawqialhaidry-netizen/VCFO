import json
import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "app" / "i18n" / "ar.json"
text = p.read_text(encoding="utf-8")
keys = re.findall(r'"([^"]+)"\s*:', text)
from collections import Counter

c = Counter(keys)
dups = [k for k, v in c.items() if v > 1]
print("duplicate key names in raw file:", len(dups))
if dups:
    print(dups[:40])

data = json.loads(text)
for k in [
    "cmd_dec_meta_impact",
    "cmd_decisions",
    "cmd_secondary_tile_forecast",
    "cmd_dec_badge_med",
]:
    v = data.get(k)
    print(k, "=>", repr(v)[:100] if v is not None else "MISSING")
