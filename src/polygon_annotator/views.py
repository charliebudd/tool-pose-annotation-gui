from __future__ import annotations

import os

from src import ImageAnnotator

from .io_utils import load_mask_or_blank, load_vertices_json, save_mask, save_vertices_json
from .mask_ops import (
    blit_numpy_to_texture,
    composite_overlay,
    draw_poly_preview,
    fill_polygon_in_mask,
    texture_to_numpy,
)
from .pathing import mask_path_to_vertices_json_path


class ReferenceViewer(ImageAnnotator):
    def __init__(self, on_click_callback=None, on_cursor_moved_callback=None):
        super().__init__(zoom_min=1.0)
        self.on_click_callback = on_click_callback
        self.on_cursor_moved_callback = on_cursor_moved_callback

    def on_click(self, position, button):
        if self.on_click_callback:
            self.on_click_callback(position, button)

    def on_cursor_moved(self, position):
        if self.on_cursor_moved_callback:
            self.on_cursor_moved_callback(position)

    def on_draw(self):
        return

    def new_image(self):
        return


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

        self._undo_stack = []
        self.poly_points = []
        self.cursor_xy = None
        self.finalized_polygons = []

    def on_draw(self):
        return

    def new_image(self):
        tex = texture_to_numpy(self.texture)
        if tex is None:
            return

        if tex.ndim == 3 and tex.shape[2] == 4:
            rgb = tex[..., :3]
        elif tex.ndim == 3 and tex.shape[2] == 3:
            rgb = tex
        elif tex.ndim == 2:
            rgb = tex[..., None].repeat(3, axis=2)
        else:
            raise ValueError(f"Unexpected texture format: {tex.shape}")

        self.base_rgb = rgb.astype("uint8")
        h, w = self.base_rgb.shape[:2]

        self.current_mask_path = self.mask_path_getter(self.current_target_path, (h, w))
        self.mask = load_mask_or_blank(self.current_mask_path, (h, w))

        self._undo_stack.clear()
        self.poly_points.clear()
        self.cursor_xy = None
        self.finalized_polygons.clear()

        vertices_json_path = mask_path_to_vertices_json_path(self.current_mask_path)
        self.finalized_polygons = load_vertices_json(vertices_json_path)
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
        if self.base_rgb is None or self.mask is None:
            return

        if self.current_mask_path and os.path.exists(self.current_mask_path):
            try:
                os.remove(self.current_mask_path)
            except Exception:
                pass
        if self.current_mask_path:
            vpath = mask_path_to_vertices_json_path(self.current_mask_path)
            if os.path.exists(vpath):
                try:
                    os.remove(vpath)
                except Exception:
                    pass

        self.mask[:] = 0
        self._undo_stack.clear()
        self.poly_points.clear()
        self.cursor_xy = None
        self.finalized_polygons.clear()
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

        mask_path = self.current_mask_path
        if not mask_path:
            return
        save_mask(self.mask, mask_path)
        vertices_json_path = mask_path_to_vertices_json_path(mask_path)
        save_vertices_json(self.finalized_polygons, vertices_json_path)
