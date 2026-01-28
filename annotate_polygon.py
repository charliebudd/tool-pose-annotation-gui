"""
two_panel_polygon_annotator.py

Two-panel, image-in mask-out polygon annotator.

UI
- Left panel : reference image (view-only)
- Right panel: target image with polygon annotation -> mask saved to disk

Annotation
- Left click       : add polygon vertex (on RIGHT panel only)
- Right click/Enter: finalize polygon + fill (needs >= 3 vertices)
- u                : undo last vertex
- r                : DELETE saved mask + clear overlays (left & right)
- Left/Right arrows: prev/next sample (auto-save current mask on navigation)

Mask
- uint8 PNG, mode "L"
- 0 = background, 255 = foreground

Assumptions
- You have src.ImageAnnotator with set_image(), texture, draw(), and event routing.
"""

import os
import json
import argparse
from glob import glob

import numpy as np
from PIL import Image, ImageDraw

os.environ["KIVY_NO_ARGS"] = "1"

from kivy.config import Config
Config.set("input", "mouse", "mouse,multitouch_on_demand")
Config.set("graphics", "fullscreen", "auto")

from kivy.core.window import Window
from kivy.clock import Clock
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from src import ImageAnnotator


# Keycodes (Kivy)
LEFT_KEYCODE = 80
RIGHT_KEYCODE = 79
R_KEYCODE = 21
U_KEYCODE = 24
ENTER_KEYCODE = 40

HELP_TEXT = (
    "[b]Controls[/b]\n"
    "- Left click        : add polygon vertex (RIGHT panel)\n"
    "- Right click/Enter : finalize polygon + fill (>= 3 vertices)\n"
    "- u                 : undo last vertex\n"
    "- r                 : delete saved mask + clear overlays\n"
    "- Left / Right      : prev / next sample (auto-save)\n"
)


def ensure_dir(path: str):
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


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


def mask_path_to_vertices_json_path(mask_path: str) -> str:
    """Return the JSON path for vertices corresponding to a mask PNG path."""
    base, _ = os.path.splitext(mask_path)
    return base + ".json"


def save_vertices_json(polygons: list[list[tuple[int, int]]], path: str):
    """Save polygon vertices for a mask.

    Format:
      {
        "polygons": [
          {"vertices": [[x,y], [x,y], ...]},
          ...
        ]
      }

    Coordinates are image pixel coordinates.
    """
    ensure_dir(os.path.dirname(path))
    payload = {
        "polygons": [
            {"vertices": [[int(x), int(y)] for (x, y) in poly]}
            for poly in polygons
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def composite_overlay(base_rgb: np.ndarray, mask: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    alpha = float(np.clip(alpha, 0.0, 1.0))
    out = base_rgb.copy()

    m = mask > 0
    if not np.any(m):
        return out

    overlay = np.zeros_like(out, dtype=np.uint8)
    overlay[..., 0] = 255  # red

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


# -------------------------
# Left panel: reference view
# -------------------------
class ReferenceViewer(ImageAnnotator):
    """View-only image panel."""
    def __init__(self):
        super().__init__(zoom_min=1.0)

    def on_click(self, position, button):
        return

    def on_cursor_moved(self, position):
        return


# -------------------------
# Right panel: target annotator
# -------------------------
class PolygonSegAnnotator(ImageAnnotator):
    def __init__(self, allow_editing: bool, mask_path_getter, overlay_alpha: float = 0.45):
        super().__init__(zoom_min=1.0)
        self.allow_editing = allow_editing
        self.mask_path_getter = mask_path_getter
        self.overlay_alpha = overlay_alpha

        self.current_target_path = None
        self.current_mask_path = None

        self.base_rgb = None
        self.mask = None

        self._undo_stack: list[np.ndarray] = []
        self.poly_points: list[tuple[int, int]] = []
        self.cursor_xy: tuple[int, int] | None = None

        # Accumulate polygons that were finalized into the current mask.
        # Each polygon is a list of (x, y) vertices in image pixel coordinates.
        self.finalized_polygons: list[list[tuple[int, int]]] = []

    def new_image(self):
        tex = texture_to_numpy(self.texture)
        if tex is None:
            return

        if tex.ndim == 3 and tex.shape[2] == 4:
            rgb = tex[..., :3]
        elif tex.ndim == 3 and tex.shape[2] == 3:
            rgb = tex
        elif tex.ndim == 2:
            rgb = np.repeat(tex[..., None], 3, axis=2)
        else:
            raise ValueError(f"Unexpected texture format: {tex.shape}")

        self.base_rgb = rgb.astype(np.uint8)
        h, w = self.base_rgb.shape[:2]

        self.current_mask_path = self.mask_path_getter(self.current_target_path, (h, w))
        self.mask = load_mask_or_blank(self.current_mask_path, (h, w))

        self._undo_stack.clear()
        self.poly_points.clear()
        self.cursor_xy = None
        self.finalized_polygons.clear()

        self._refresh_display()

    def _refresh_display(self):
        if self.base_rgb is None or self.mask is None:
            return
        disp = composite_overlay(self.base_rgb, self.mask, alpha=self.overlay_alpha)
        if len(self.poly_points) > 0:
            draw_poly_preview(disp, self.poly_points, self.cursor_xy)
        blit_numpy_to_texture(disp, self.texture)
        self.draw()

    def push_undo(self):
        if self.mask is None:
            return
        if len(self._undo_stack) > 30:
            self._undo_stack = self._undo_stack[-20:]
        self._undo_stack.append(self.mask.copy())

    def undo_mask(self):
        if not self.allow_editing:
            return
        if len(self._undo_stack) == 0:
            return
        self.mask = self._undo_stack.pop()
        self._refresh_display()

    def revert_mask(self):
        """
        BUTTON/KEY 'r' semantics (as requested):
          1) Delete the saved mask on disk (if it exists)
          2) Clear the current in-memory mask (all zeros)
          3) Clear transient polygon/undo state
          4) Refresh RIGHT panel (left panel is handled by the App)
        """
        if self.base_rgb is None or self.mask is None:
            return

        # 1) Delete saved mask file
        if self.current_mask_path and os.path.exists(self.current_mask_path):
            try:
                os.remove(self.current_mask_path)
            except Exception:
                # If deletion fails (permissions/locked), still clear in-memory state
                pass

        # 2) Clear in-memory mask
        self.mask[:] = 0

        # 3) Clear states
        self._undo_stack.clear()
        self.poly_points.clear()
        self.cursor_xy = None
        self.finalized_polygons.clear()

        # 4) Refresh right view
        self._refresh_display()

    def clear_polygon(self):
        self.poly_points.clear()
        self.cursor_xy = None
        self._refresh_display()

    def undo_vertex(self):
        if len(self.poly_points) > 0:
            self.poly_points.pop()
            self._refresh_display()

    def finalize_polygon(self):
        if not self.allow_editing or self.mask is None:
            return
        if len(self.poly_points) < 3:
            return
        self.push_undo()
        pts = [(int(x), int(y)) for (x, y) in self.poly_points]
        self.mask = fill_polygon_in_mask(self.mask, pts, value=255)

        # Store vertices for JSON export.
        self.finalized_polygons.append(pts)

        self.poly_points.clear()
        self.cursor_xy = None
        self._refresh_display()

    def on_cursor_moved(self, position):
        if self.base_rgb is None:
            return
        self.cursor_xy = (int(position[0]), int(position[1]))
        if len(self.poly_points) > 0:
            self._refresh_display()

    def on_click(self, position, button):
        if not self.allow_editing or self.base_rgb is None or self.mask is None:
            return

        x, y = map(int, position)
        w, h = self.texture.size
        if not (0 <= x < w and 0 <= y < h):
            return

        if button == "left":
            self.poly_points.append((x, y))
            self.cursor_xy = (x, y)
            self._refresh_display()
        elif button == "right":
            self.finalize_polygon()
        elif button == "middle":
            self.clear_polygon()

    def save_current_mask(self):
        if not self.allow_editing:
            return
        if self.mask is None or self.current_target_path is None:
            return

        images_root = os.path.abspath("images")
        t_abs = os.path.abspath(self.current_target_path)

        rel = os.path.relpath(t_abs, start=images_root)  # case035/timepoint003/blue.png
        rel_dir = os.path.dirname(rel)                   # case035/timepoint003

        rel = os.path.join(rel_dir, "mask.png")
        mask_path = os.path.join("masks", rel)           # masks/case035/timepoint003/mask.png

        ensure_dir(os.path.dirname(mask_path))
        save_mask(self.mask, mask_path)

        # Also export polygon vertices as JSON alongside mask.png
        vertices_json_path = mask_path_to_vertices_json_path(mask_path)
        save_vertices_json(self.finalized_polygons, vertices_json_path)


# -------------------------
# App: two-panel
# -------------------------
class TwoPanelApp(App):
    def __init__(self, ref_files, target_files, target_root, mask_root, allow_editing: bool):
        super().__init__()
        self.ref_files = ref_files
        self.target_files = target_files
        self.target_root = target_root
        self.mask_root = mask_root
        self.allow_editing = allow_editing
        self.index = 0

        # Cache pristine reference pixels so left overlay is reversible
        self.ref_base_rgb: np.ndarray | None = None

    def _mask_path_getter(self, target_path: str, hw: tuple[int, int]):
        # target: images/case035/timepoint003/blue.png
        # mask  : masks/case035/timepoint003/mask.png
        images_root = os.path.abspath("images")
        t_abs = os.path.abspath(target_path)

        rel = os.path.relpath(t_abs, start=images_root)  # case035/timepoint003/blue.png
        rel_dir = os.path.dirname(rel)                   # case035/timepoint003

        out_path = os.path.join("masks", rel_dir, "mask.png")
        ensure_dir(os.path.dirname(out_path))
        return out_path

    def build(self):
        self.root = FloatLayout()

        # Two panels
        self.layout = BoxLayout(orientation="horizontal")
        self.ref_view = ReferenceViewer()
        self.ann_view = PolygonSegAnnotator(
            allow_editing=self.allow_editing,
            mask_path_getter=self._mask_path_getter,
            overlay_alpha=0.45,
        )
        self.layout.add_widget(self.ref_view)
        self.layout.add_widget(self.ann_view)
        self.root.add_widget(self.layout)

        # Status line + buttons
        self.info = Label(size_hint=(0.98, 0.04), pos_hint={"x": 0.01, "top": 0.98})
        self.root.add_widget(self.info)

        self.help_label = Label(
            text=HELP_TEXT,
            markup=True,
            size_hint=(None, None),
            halign="left",
            valign="bottom",
            color=(1, 1, 1, 1),
            font_size=15
        )
        self.help_label.bind(texture_size=lambda inst, val: setattr(inst, "size", val))
        self.help_label.pos_hint = {"x": 0.01, "top": 0.99}
        self.root.add_widget(self.help_label)

        self.revert_mask_button = Button(
            text="Delete Mask + Clear (r)",
            size_hint=(0.22, 0.04),
            pos_hint={"right": 0.99, "top": 0.98},
        )
        self.undo_vertex_button = Button(
            text="Undo Vertex (u)",
            size_hint=(0.22, 0.04),
            pos_hint={"right": 0.99, "top": 0.94},
        )

        self.revert_mask_button.bind(on_press=lambda *_: self._on_revert())
        self.undo_vertex_button.bind(on_press=lambda *_: self.ann_view.undo_vertex())

        self.root.add_widget(self.revert_mask_button)
        self.root.add_widget(self.undo_vertex_button)

        Window.bind(on_key_down=self.key_down)
        Window.bind(on_request_close=self.on_request_close)
        return self.root

    def on_start(self):
        self.load()

    def _update_info(self):
        ref = self.ref_files[self.index]
        tgt = self.target_files[self.index]
        self.info.text = (
            f"{self.index+1}/{len(self.target_files)} | "
            f"REF: {ref} | TGT: {tgt}"
        )

    def _cache_ref_base(self, *_):
        rgb = get_rgb_from_texture(self.ref_view.texture)
        self.ref_base_rgb = rgb.copy() if rgb is not None else None

    def _refresh_ref_clear(self):
        # Restore pristine reference pixels (no overlay)
        if self.ref_base_rgb is None or self.ref_view.texture is None:
            return
        blit_numpy_to_texture(self.ref_base_rgb, self.ref_view.texture)
        self.ref_view.draw()

    def _refresh_ref_overlay(self):
        # Render overlay from pristine base (never from already-overlaid texture)
        if self.ref_base_rgb is None or self.ref_view.texture is None:
            return
        if self.ann_view.mask is None:
            return

        mask = self.ann_view.mask
        if mask.shape[:2] != self.ref_base_rgb.shape[:2]:
            return

        disp = composite_overlay(self.ref_base_rgb, mask, alpha=0.45)
        blit_numpy_to_texture(disp, self.ref_view.texture)
        self.ref_view.draw()

    def load(self):
        ref_path = self.ref_files[self.index]
        tgt_path = self.target_files[self.index]

        # Load left (reference) panel
        self.ref_view.set_image(ref_path)

        # Cache pristine ref after Kivy updates the texture
        Clock.schedule_once(self._cache_ref_base, 0)

        # Load right (target) panel + mask
        self.ann_view.current_target_path = tgt_path
        self.ann_view.set_image(tgt_path)

        self._update_info()

        # After both textures/mask are ready, render left based on whether mask exists
        def _after_loaded(*_):
            if self.ann_view.mask is not None and np.any(self.ann_view.mask > 0):
                self._refresh_ref_overlay()
            else:
                self._refresh_ref_clear()

        Clock.schedule_once(_after_loaded, 0)

    def save(self):
        self.ann_view.save_current_mask()

    def _on_revert(self):
        # 1) Delete saved mask + clear right panel mask
        self.ann_view.revert_mask()

        # 2) Clear left overlay (restore pristine ref)
        # Schedule to next tick to avoid any texture timing issues
        Clock.schedule_once(lambda *_: self._refresh_ref_clear(), 0)

        self._update_info()

    def key_down(self, instance, keyboard, keycode, text, modifiers):
        if keycode == ENTER_KEYCODE:
            self.ann_view.finalize_polygon()
            self._refresh_ref_overlay()
            self._update_info()
            return

        if keycode == U_KEYCODE:
            self.ann_view.undo_vertex()
            self._update_info()
            return

        if keycode == R_KEYCODE:
            self._on_revert()
            return

        # Navigation
        if keycode == LEFT_KEYCODE and self.index > 0:
            self.save()
            self.index -= 1
            self.load()
            return

        if keycode == RIGHT_KEYCODE and self.index < len(self.target_files) - 1:
            self.save()
            self.index += 1
            self.load()
            return

    def on_request_close(self, *args, **kwargs):
        self.save()
        return False


def load_pairs_from_json(pairs_json_path: str) -> tuple[list[str], list[str]]:
    """
    pairs.json format:
    [
      {"ref": ".../ref.png", "target": ".../tgt.png"},
      {"ref": "...",        "target": "..."}
    ]
    """
    with open(pairs_json_path, "r", encoding="utf-8") as f:
        pairs = json.load(f)
    ref = [p["ref"] for p in pairs]
    tgt = [p["target"] for p in pairs]
    return ref, tgt


def infer_ref_from_target(target_files: list[str], ref_root: str, target_root: str) -> list[str]:
    out = []
    for t in target_files:
        rel = os.path.relpath(t, target_root) if target_root else os.path.basename(t)
        out.append(os.path.join(ref_root, rel))
    return out


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--pairs-json", type=str, default="./images/pairs.json",
                        help="JSON list of {'ref':..., 'target':...} objects.")
    parser.add_argument("--target-glob", type=str, default=None,
                        help="Glob for target images to annotate (e.g., targets/**/*.png).")
    parser.add_argument("--target-root", type=str, default=None,
                        help="Root folder for targets (preserve relative paths).")
    parser.add_argument("--ref-root", type=str, default=None,
                        help="Root folder for reference images (same rel paths as targets).")
    parser.add_argument("--mask-root", type=str, default="masks",
                        help="Output folder for masks. Default: ./masks")
    parser.add_argument("--visualise-only", action="store_true",
                        help="Disable editing and saving.")
    args = parser.parse_args()

    if args.pairs_json:
        ref_files, target_files = load_pairs_from_json(args.pairs_json)
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
    ).run()


if __name__ == "__main__":
    main()
