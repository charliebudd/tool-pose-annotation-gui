from __future__ import annotations

import json
import os


def load_pairs_from_json(pairs_json_path: str) -> tuple[list[str], list[str], list[str | None]]:
    with open(pairs_json_path, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    ref = [p["ref"] for p in pairs]
    tgt = [p["target"] for p in pairs]
    base_dir = os.path.dirname(os.path.abspath(pairs_json_path))
    video = []
    for p in pairs:
        v = p.get("video")
        if v:
            v = os.path.join(base_dir, v) if not os.path.isabs(v) else v
        video.append(v)
    return ref, tgt, video


def infer_ref_from_target(target_files: list[str], ref_root: str, target_root: str) -> list[str]:
    out = []
    for t in target_files:
        rel = os.path.relpath(t, target_root) if target_root else os.path.basename(t)
        out.append(os.path.join(ref_root, rel))
    return out
