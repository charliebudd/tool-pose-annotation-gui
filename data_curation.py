import os
import json
from glob import glob

# ROOT = r"C:\Users\Junwen\Desktop\datasets\neuroppeye\stage2_paired"
ROOT = r"images"
OUT_JSON = os.path.join(ROOT, "pairs.json")

pairs = []
for case_dir in sorted(glob(os.path.join(ROOT, "case*"))):
    for tp_dir in sorted(glob(os.path.join(case_dir, "timepoint*"))):
        ref = os.path.join(tp_dir, "white.png")
        tgt = os.path.join(tp_dir, "blue.png")
        if os.path.isfile(ref) and os.path.isfile(tgt):
            pairs.append({
                "ref": ref.replace("\\", "/"),
                "target": tgt.replace("\\", "/"),
            })

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(pairs, f, indent=2)

print(f"Wrote {len(pairs)} pairs -> {OUT_JSON}")