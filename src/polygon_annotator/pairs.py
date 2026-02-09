from __future__ import annotations

import json
import os


def load_pairs_payload(pairs_json_path: str) -> list[dict]:
    with open(pairs_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise ValueError(f"pairs.json must contain a list, got {type(payload).__name__}")
    for i, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"pairs[{i}] must be an object, got {type(item).__name__}")
    return payload


def save_pairs_payload(pairs_json_path: str, payload: list[dict]) -> None:
    with open(pairs_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def get_ref_target_from_pair(pair: dict) -> tuple[str, str]:
    ref = pair.get("ref", pair.get("white"))
    target = pair.get("target", pair.get("blue"))
    if not ref or not target:
        raise KeyError("Each pair must provide either ref/target or white/blue.")
    return ref, target


def get_motion_blur_from_pair(pair: dict) -> bool:
    return bool(pair.get("motion_blur", False))


def get_biopsy_from_pair(pair: dict) -> bool | None:
    value = pair.get("Biopsy")
    if value is None:
        return None
    return bool(value)


def get_motion_blur_from_payload(payload: list[dict], index: int) -> bool:
    if index < 0 or index >= len(payload):
        raise IndexError(f"Pair index out of range: {index}")
    return get_motion_blur_from_pair(payload[index])


def get_biopsy_from_payload(payload: list[dict], index: int) -> bool | None:
    if index < 0 or index >= len(payload):
        raise IndexError(f"Pair index out of range: {index}")
    return get_biopsy_from_pair(payload[index])


def set_motion_blur_in_payload(payload: list[dict], index: int, value: bool) -> None:
    if index < 0 or index >= len(payload):
        raise IndexError(f"Pair index out of range: {index}")
    payload[index]["motion_blur"] = bool(value)


def update_motion_blur_in_json(pairs_json_path: str, index: int, value: bool) -> None:
    payload = load_pairs_payload(pairs_json_path)
    set_motion_blur_in_payload(payload, index, value)
    save_pairs_payload(pairs_json_path, payload)


def load_pairs_from_json(pairs_json_path: str) -> tuple[list[str], list[str], list[str | None]]:
    pairs = load_pairs_payload(pairs_json_path)
    ref = []
    tgt = []
    for pair in pairs:
        ref_path, tgt_path = get_ref_target_from_pair(pair)
        ref.append(ref_path)
        tgt.append(tgt_path)
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
