from __future__ import annotations

import argparse
import os

os.environ["KIVY_NO_ARGS"] = "1"

from kivy.config import Config

Config.set("input", "mouse", "mouse,multitouch_on_demand")
Config.set("graphics", "fullscreen", "1")

from .app import TwoPanelApp
from .io_utils import ensure_dir
from .pairs import load_pairs_from_json


def _resolve_pair_paths(paths: list[str], root: str | None) -> list[str]:
    resolved = []
    for p in paths:
        norm = p.replace("/", os.path.sep)
        if root and not os.path.isabs(norm):
            norm = os.path.join(root, norm)
        resolved.append(norm)
    return resolved


def _resolve_mask_root(mask_out_arg: str) -> str:
    raw = mask_out_arg.replace("/", os.path.sep)
    normalized = os.path.normpath(raw)

    if os.path.basename(normalized).lower() == "masks":
        return normalized
    if raw.endswith(("/", "\\")) or os.path.isdir(normalized):
        return os.path.join(normalized, "masks")
    return normalized


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--pairs-json",
        type=str,
        default="./images/pairs.json",
        help="JSON list of pairs (supports ref/target or white/blue keys).",
    )
    parser.add_argument(
        "--mask-out",
        type=str,
        default="masks",
        help="Output folder for masks. Default: ./masks",
    )
    args = parser.parse_args()

    pairs_json_path = args.pairs_json
    pairs_root = os.path.dirname(os.path.abspath(pairs_json_path))
    ref_files, target_files, video_files = load_pairs_from_json(pairs_json_path)
    ref_files = _resolve_pair_paths(ref_files, pairs_root)
    target_files = _resolve_pair_paths(target_files, pairs_root)

    if len(ref_files) != len(target_files):
        raise SystemExit("Reference and target lists differ in length.")

    missing_ref = [p for p in ref_files if not os.path.exists(p)]
    if missing_ref:
        raise SystemExit(f"Missing reference files (first 5): {missing_ref[:5]}")
    missing_target = [p for p in target_files if not os.path.exists(p)]
    if missing_target:
        raise SystemExit(f"Missing target files (first 5): {missing_target[:5]}")

    mask_root = _resolve_mask_root(args.mask_out)
    ensure_dir(mask_root)

    TwoPanelApp(
        ref_files=ref_files,
        target_files=target_files,
        target_root=pairs_root,
        mask_root=mask_root,
        allow_editing=True,
        video_files=video_files,
        pairs_json_path=pairs_json_path,
        pairs_root=pairs_root,
    ).run()
