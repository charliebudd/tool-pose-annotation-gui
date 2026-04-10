"""Build `pairs.json` for a prepared `stage2_paired` image dataset.

The script scans `case*/timepoint*` folders under `ROOT`, keeps only
timepoints that contain both `white.png` and `blue.png`, and emits one entry per
pair. Each output record includes relative image paths, the matching `Kinevo`
folder when present, a default `motion_blur` flag, and any fields loaded from
`MetaData.json`.
"""

import json
from pathlib import Path

# ROOT = Path(r"C:\Users\Junwen\Desktop\datasets\neuroppeye\stage2_paired")
ROOT = Path("images")
OUT_JSON = ROOT / "pairs.json"


def to_rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def load_metadata(metadata_path: Path) -> dict:
    if not metadata_path.is_file():
        return {}
    try:
        with metadata_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"metadata_value": data}
    except json.JSONDecodeError:
        return {"metadata_parse_error": "Invalid JSON"}


def build_pairs(root: Path) -> list[dict]:
    pairs = []
    for case_dir in sorted(root.glob("case*")):
        if not case_dir.is_dir():
            continue

        kinevo_dir = case_dir / "Kinevo"
        kinevo_rel = to_rel_posix(kinevo_dir, root) if kinevo_dir.exists() else None

        for tp_dir in sorted(case_dir.glob("timepoint*")):
            if not tp_dir.is_dir():
                continue

            white = tp_dir / "white.png"
            blue = tp_dir / "blue.png"
            if not (white.is_file() and blue.is_file()):
                continue

            item = {
                "white": to_rel_posix(white, root),
                "blue": to_rel_posix(blue, root),
                "kinevo": kinevo_rel,
                "motion_blur": False,
            }

            metadata = load_metadata(tp_dir / "MetaData.json")
            if metadata:
                item.update(metadata)

            pairs.append(item)
    return pairs


def main() -> None:
    pairs = build_pairs(ROOT)
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(pairs)} pairs -> {OUT_JSON}")


if __name__ == "__main__":
    main()
