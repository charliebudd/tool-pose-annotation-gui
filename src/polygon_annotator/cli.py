from __future__ import annotations

import argparse
import os
from glob import glob

os.environ["KIVY_NO_ARGS"] = "1"

from kivy.config import Config

Config.set("input", "mouse", "mouse,multitouch_on_demand")
Config.set("graphics", "fullscreen", "1")

from .app import TwoPanelApp
from .io_utils import ensure_dir
from .pairs import infer_ref_from_target, load_pairs_from_json


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--pairs-json",
        type=str,
        default="./images/pairs.json",
        help="JSON list of {'ref':..., 'target':...} objects.",
    )
    parser.add_argument(
        "--target-glob",
        type=str,
        default=None,
        help="Glob for target images to annotate (e.g., targets/**/*.png).",
    )
    parser.add_argument(
        "--target-root",
        type=str,
        default=None,
        help="Root folder for targets (preserve relative paths).",
    )
    parser.add_argument(
        "--ref-root",
        type=str,
        default=None,
        help="Root folder for reference images (same rel paths as targets).",
    )
    parser.add_argument(
        "--mask-root",
        type=str,
        default="masks",
        help="Output folder for masks. Default: ./masks",
    )
    parser.add_argument(
        "--visualise-only",
        action="store_true",
        help="Disable editing and saving.",
    )
    args = parser.parse_args()

    if args.pairs_json:
        ref_files, target_files, video_files = load_pairs_from_json(args.pairs_json)
    else:
        if not args.target_glob or not args.ref_root:
            raise SystemExit("Provide --pairs-json OR (--target-glob AND --ref-root).")
        target_files = sorted(glob(args.target_glob, recursive=True))
        if len(target_files) == 0:
            raise SystemExit("No target images found.")
        target_root = args.target_root
        if target_root is None:
            target_root = os.path.commonpath(target_files)
        ref_files = infer_ref_from_target(target_files, args.ref_root, target_root)
        video_files = [None] * len(target_files)

    ref_files = [p.replace("/", os.path.sep) for p in ref_files]
    target_files = [p.replace("/", os.path.sep) for p in target_files]

    if len(ref_files) != len(target_files):
        raise SystemExit("Reference and target lists differ in length.")
    missing_ref = [p for p in ref_files if not os.path.exists(p)]
    if missing_ref:
        raise SystemExit(f"Missing reference files (first 5): {missing_ref[:5]}")

    mask_root = args.mask_root.replace("/", os.path.sep)
    ensure_dir(mask_root)

    target_root = args.target_root.replace("/", os.path.sep) if args.target_root else None

    TwoPanelApp(
        ref_files=ref_files,
        target_files=target_files,
        target_root=target_root,
        mask_root=mask_root,
        allow_editing=(not args.visualise_only),
        video_files=video_files,
    ).run()
