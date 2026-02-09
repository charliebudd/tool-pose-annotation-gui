#!/usr/bin/env python3
"""Prepare stage2_paired data by copying Kinevo, biopsy, and metadata files."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def copy_kinevo(original_root: Path, paired_root: Path, dry_run: bool = False) -> int:
    """Copy Kinevo folders from NeuroPPEYEOriginal into stage2_paired/case0xx/Kinevo."""
    kinevo_targets = sorted(original_root.glob("NPPEye*/In_vivo/Kinevo"))
    if not kinevo_targets:
        # Support an alternative layout if present.
        kinevo_targets = sorted(original_root.glob("Stage_2_data/NPPEye*/In_vivo/Kinevo"))
    if not kinevo_targets:
        print(f"No Kinevo folders found under {original_root}")
        return 0

    copied = 0
    for src in kinevo_targets:
        npp_case = src.parents[1].name  # NPPEye0xx
        match = re.search(r"(\d+)$", npp_case)
        if not match:
            print(f"Skip Kinevo folder (cannot map to case0xx): {src}")
            continue

        case_id = f"case{match.group(1)}"
        dst = paired_root / case_id / "Kinevo"
        if not dry_run:
            shutil.copytree(src, dst, dirs_exist_ok=True)
        action = "Would copy" if dry_run else "Copied"
        print(f"{action} Kinevo folder: {src} -> {dst}")
        copied += 1

    return copied


def copy_biopsies(stage2_root: Path, paired_root: Path, dry_run: bool = False) -> int:
    """Copy biopsy0x folders from stage2/case0xx into stage2_paired/case0xx."""
    copied = 0
    for case_dir in sorted(stage2_root.glob("case*")):
        if not case_dir.is_dir():
            continue

        dst_case = paired_root / case_dir.name
        if not dry_run:
            dst_case.mkdir(parents=True, exist_ok=True)

        for biopsy_dir in sorted(case_dir.glob("biopsy*")):
            if not biopsy_dir.is_dir():
                continue
            dst = dst_case / biopsy_dir.name
            if not dry_run:
                shutil.copytree(biopsy_dir, dst, dirs_exist_ok=True)
            action = "Would copy" if dry_run else "Copied"
            print(f"{action} biopsy folder: {biopsy_dir} -> {dst}")
            copied += 1

    if copied == 0:
        print(f"No biopsy folders found under {stage2_root}")
    return copied


def copy_timepoint_metadata(original_root: Path, paired_root: Path, dry_run: bool = False) -> int:
    """Copy MetaData.json from HSI_data/TimePoint0xx into case0xx/timepoint0xx."""
    metadata_files = sorted(original_root.glob("NPPEye*/In_vivo/HSI_data/TimePoint*/MetaData.json"))
    if not metadata_files:
        # Support an alternative layout if present.
        metadata_files = sorted(
            original_root.glob("Stage_2_data/NPPEye*/In_vivo/HSI_data/TimePoint*/MetaData.json")
        )
    if not metadata_files:
        print(f"No MetaData.json files found under {original_root}")
        return 0

    copied = 0
    for src in metadata_files:
        npp_case = src.parents[3].name  # NPPEye0xx
        timepoint_name = src.parent.name  # TimePoint0xx

        case_match = re.search(r"(\d+)$", npp_case)
        tp_match = re.search(r"(\d+)$", timepoint_name)
        if not case_match or not tp_match:
            print(f"Skip MetaData.json (cannot map to case/timepoint): {src}")
            continue

        case_id = f"case{case_match.group(1)}"
        tp_id = f"timepoint{tp_match.group(1)}"
        dst = paired_root / case_id / tp_id / "MetaData.json"
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        action = "Would copy" if dry_run else "Copied"
        print(f"{action} MetaData.json: {src} -> {dst}")
        copied += 1

    return copied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy Kinevo and MetaData.json (from NeuroPPEYEOriginal) and biopsy folders "
            "(from NeuroPPEYE/stage2) into NeuroPPEYE/stage2_paired."
        )
    )
    parser.add_argument(
        "--original-root",
        type=Path,
        required=True,
        help="Path to NeuroPPEYEOriginal",
    )
    parser.add_argument(
        "--stage2-root",
        type=Path,
        required=True,
        help="Path to NeuroPPEYE/stage2",
    )
    parser.add_argument(
        "--paired-root",
        type=Path,
        required=True,
        help="Path to NeuroPPEYE/stage2_paired",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned copy operations without writing files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    original_root = args.original_root.resolve()
    stage2_root = args.stage2_root.resolve()
    paired_root = args.paired_root.resolve()

    if args.dry_run:
        print("Dry run enabled; no files will be copied.")

    kinevo_count = copy_kinevo(original_root, paired_root, dry_run=args.dry_run)
    biopsy_count = copy_biopsies(stage2_root, paired_root, dry_run=args.dry_run)
    metadata_count = copy_timepoint_metadata(original_root, paired_root, dry_run=args.dry_run)

    print("-")
    print(f"Kinevo folders copied: {kinevo_count}")
    print(f"Biopsy folders copied: {biopsy_count}")
    print(f"MetaData.json files copied: {metadata_count}")


if __name__ == "__main__":
    main()
