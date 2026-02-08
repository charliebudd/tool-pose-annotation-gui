from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image


def ensure_dir(path: str):
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def load_mask_or_blank(mask_path: str, shape_hw: tuple[int, int]) -> np.ndarray:
    h, w = shape_hw
    if os.path.exists(mask_path):
        m = Image.open(mask_path)
        arr = np.array(m, dtype=np.uint8)
        if arr.ndim == 3:
            arr = arr[..., 0]
        if arr.shape[:2] != (h, w):
            raise ValueError(f"Mask size {arr.shape[:2]} != image size {(h, w)}: {mask_path}")
        return arr
    return np.zeros((h, w), dtype=np.uint8)


def save_mask(mask: np.ndarray, path: str):
    ensure_dir(os.path.dirname(path))
    Image.fromarray(mask.astype(np.uint8), mode="L").save(path)


def save_vertices_json(polygons: list[list[tuple[int, int]]], path: str):
    ensure_dir(os.path.dirname(path))
    payload = {
        "polygons": [
            {"vertices": [[int(x), int(y)] for (x, y) in poly]}
            for poly in polygons
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def load_vertices_json(path: str) -> list[list[tuple[int, int]]]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        polys = payload.get("polygons", []) if isinstance(payload, dict) else []
        out: list[list[tuple[int, int]]] = []
        for poly in polys:
            verts = poly.get("vertices") if isinstance(poly, dict) else None
            if not verts:
                continue
            pts: list[tuple[int, int]] = []
            for v in verts:
                if isinstance(v, (list, tuple)) and len(v) == 2:
                    pts.append((int(v[0]), int(v[1])))
            if len(pts) >= 3:
                out.append(pts)
        return out
    except Exception:
        return []
