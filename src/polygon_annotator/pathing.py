from __future__ import annotations

import os

from .io_utils import ensure_dir


def mask_path_to_vertices_json_path(mask_path: str) -> str:
    base, _ = os.path.splitext(mask_path)
    return base + ".json"


def mask_path_for_target(target_path: str, images_root: str = "images", masks_root: str = "masks") -> str:
    images_root_abs = os.path.abspath(images_root)
    target_abs = os.path.abspath(target_path)
    rel = os.path.relpath(target_abs, start=images_root_abs)
    rel_dir = os.path.dirname(rel)
    out_path = os.path.join(masks_root, rel_dir, "mask.png")
    ensure_dir(os.path.dirname(out_path))
    return out_path
