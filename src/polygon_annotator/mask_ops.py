from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw


def texture_to_numpy(texture) -> np.ndarray:
    if texture is None:
        return None
    w, h = texture.size
    raw = texture.pixels
    channels = len(raw) // (w * h)
    return np.frombuffer(raw, dtype=np.uint8).reshape((h, w, channels))


def blit_numpy_to_texture(array: np.ndarray, texture):
    if array is None or texture is None:
        return
    if array.dtype != np.uint8:
        array = array.astype(np.uint8)

    c = array.shape[2] if array.ndim == 3 else 1
    colorfmt = {1: "luminance", 3: "rgb", 4: "rgba"}.get(c)
    if colorfmt is None:
        raise ValueError(f"Unsupported channel count: {c}")
    texture.blit_buffer(array.tobytes(), colorfmt=colorfmt, bufferfmt="ubyte")


def composite_overlay(base_rgb: np.ndarray, mask: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    alpha = float(np.clip(alpha, 0.0, 1.0))
    out = base_rgb.copy()

    m = mask > 0
    if not np.any(m):
        return out

    overlay = np.zeros_like(out, dtype=np.uint8)
    overlay[..., 0] = 255

    out[m] = (
        out[m].astype(np.float32) * (1 - alpha) + overlay[m].astype(np.float32) * alpha
    ).astype(np.uint8)
    return out


def fill_polygon_in_mask(mask: np.ndarray, points_xy: list[tuple[int, int]], value: int = 255) -> np.ndarray:
    if len(points_xy) < 3:
        return mask
    pil = Image.fromarray(mask.astype(np.uint8), mode="L")
    draw = ImageDraw.Draw(pil)
    draw.polygon(points_xy, fill=int(value))
    return np.array(pil, dtype=np.uint8)


def draw_poly_preview(rgb: np.ndarray, points_xy: list[tuple[int, int]], cursor_xy: tuple[int, int] | None):
    if rgb is None or len(points_xy) == 0:
        return
    pil = Image.fromarray(rgb, mode="RGB")
    d = ImageDraw.Draw(pil)

    if len(points_xy) >= 2:
        d.line(points_xy, fill=(0, 255, 0), width=2)

    if cursor_xy is not None and len(points_xy) >= 1:
        d.line([points_xy[-1], cursor_xy], fill=(0, 255, 0), width=1)

    r = 3
    for (x, y) in points_xy:
        d.ellipse((x - r, y - r, x + r, y + r), outline=(0, 255, 0), width=2)

    rgb[:] = np.array(pil, dtype=np.uint8)


def get_rgb_from_texture(texture) -> np.ndarray | None:
    tex = texture_to_numpy(texture)
    if tex is None:
        return None
    if tex.ndim == 3 and tex.shape[2] == 4:
        return tex[..., :3].astype(np.uint8)
    if tex.ndim == 3 and tex.shape[2] == 3:
        return tex.astype(np.uint8)
    if tex.ndim == 2:
        return np.repeat(tex[..., None], 3, axis=2).astype(np.uint8)
    return None
