from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from .constants import (
    ENTER_KEYCODE,
    HELP_TEXT,
    LEFT_KEYCODE,
    RIGHT_KEYCODE,
    R_KEYCODE,
    U_KEYCODE,
)
from .mask_ops import blit_numpy_to_texture, composite_overlay, draw_poly_preview, get_rgb_from_texture
from .pairs import (
    get_biopsy_from_payload,
    get_motion_blur_from_payload,
    load_pairs_payload,
    update_motion_blur_in_json,
)
from .pathing import mask_path_for_target
from .views import PolygonSegAnnotator, ReferenceViewer


class TwoPanelApp(App):
    def __init__(
        self,
        ref_files,
        target_files,
        target_root,
        mask_root,
        allow_editing: bool,
        video_files: list[str | None] | None = None,
        pairs_json_path: str | None = None,
        pairs_root: str | None = None,
    ):
        super().__init__()
        self.ref_files = ref_files
        self.target_files = target_files
        self.target_root = target_root
        self.mask_root = mask_root
        self.allow_editing = allow_editing
        self.video_files = video_files or [None] * len(target_files)
        self.pairs_json_path = pairs_json_path
        self.pairs_root = pairs_root
        self.index = 0
        self.ref_base_rgb = None
        self._updating_motion_blur_checkbox = False

    @staticmethod
    def _new_checkbox(disabled: bool):
        cb = ToggleButton(
            text="",
            size_hint=(None, None),
            size=(dp(34), dp(34)),
            background_normal="",
            background_down="",
            background_disabled_normal="",
            background_disabled_down="",
            background_color=(0.10, 0.10, 0.10, 1),
            color=(1, 1, 1, 1),
            bold=True,
            font_size=dp(22),
            disabled=disabled,
        )
        with cb.canvas.after:
            cb._border_color = Color(1, 1, 1, 1)
            cb._border_line = Line(rectangle=(cb.x, cb.y, cb.width, cb.height), width=1.5)
        cb.bind(pos=TwoPanelApp._update_checkbox_border)
        cb.bind(size=TwoPanelApp._update_checkbox_border)
        cb.bind(state=TwoPanelApp._style_checkbox)
        cb.bind(disabled=TwoPanelApp._style_checkbox)
        TwoPanelApp._style_checkbox(cb, cb.state)
        return cb

    @staticmethod
    def _update_checkbox_border(cb, _value):
        cb._border_line.rectangle = (cb.x, cb.y, cb.width, cb.height)

    @staticmethod
    def _style_checkbox(cb, _value):
        is_active = cb.state == "down"
        is_disabled = bool(cb.disabled)
        if is_active:
            cb.text = "Y"
            cb.background_color = (0.05, 0.65, 0.25, 1) if not is_disabled else (0.22, 0.35, 0.25, 1)
            cb._border_color.rgba = (0.95, 0.95, 0.95, 1) if not is_disabled else (0.65, 0.65, 0.65, 1)
        else:
            cb.text = ""
            cb.background_color = (0.10, 0.10, 0.10, 1) if not is_disabled else (0.07, 0.07, 0.07, 1)
            cb._border_color.rgba = (0.95, 0.95, 0.95, 1) if not is_disabled else (0.45, 0.45, 0.45, 1)

    def _mask_path_getter(self, target_path: str, hw: tuple[int, int]):
        del hw
        return mask_path_for_target(
            target_path=target_path,
            images_root=(self.target_root or "images"),
            masks_root=self.mask_root,
        )

    def build(self):
        self.root = FloatLayout()
        self.layout = BoxLayout(orientation="horizontal")
        self.ref_view = ReferenceViewer(
            on_click_callback=self._on_ref_click,
            on_cursor_moved_callback=self._on_ref_cursor_moved,
        )
        self.ann_view = PolygonSegAnnotator(
            allow_editing=self.allow_editing,
            mask_path_getter=self._mask_path_getter,
            overlay_alpha=0.45,
            mask_cleanup_root=self.mask_root,
        )
        self.layout.add_widget(self.ref_view)
        self.layout.add_widget(self.ann_view)
        self.root.add_widget(self.layout)

        self.info = Label(size_hint=(0.98, 0.04), pos_hint={"x": 0.01, "top": 0.98})
        self.root.add_widget(self.info)

        self.help_label = Label(
            text=HELP_TEXT,
            markup=True,
            size_hint=(None, None),
            halign="left",
            valign="bottom",
            color=(1, 1, 1, 1),
            font_size=15,
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
        self.open_kinevo_button = Button(
            text="Open Kinevo Folder",
            size_hint=(0.22, 0.04),
            pos_hint={"right": 0.99, "top": 0.10},
        )
        self.frame_id_label = Label(
            text="Frame ID",
            size_hint=(0.10, 0.04),
            pos_hint={"right": 0.52, "top": 0.10},
            color=(1, 1, 1, 1),
        )
        self.frame_id_input = TextInput(
            multiline=False,
            size_hint=(0.08, 0.04),
            pos_hint={"right": 0.58, "top": 0.10},
            input_filter="int",
            hint_text="1-based",
        )
        self.jump_button = Button(
            text="Go",
            size_hint=(0.06, 0.04),
            pos_hint={"right": 0.65, "top": 0.10},
        )
        self.motion_blur_label = Label(
            text="Motion Blur",
            size_hint=(0.12, 0.04),
            pos_hint={"right": 0.15, "top": 0.10},
            color=(1, 1, 1, 1),
        )
        self.motion_blur_checkbox = self._new_checkbox(
            disabled=(not self.allow_editing) or (not self.pairs_json_path)
        )
        self.motion_blur_checkbox.pos_hint = {"right": 0.17, "top": 0.10}
        self.biopsy_label = Label(
            text="Biopsy",
            size_hint=(0.12, 0.04),
            pos_hint={"right": 0.31, "top": 0.10},
            color=(1, 1, 1, 1),
        )
        self.biopsy_checkbox = self._new_checkbox(disabled=True)
        self.biopsy_checkbox.pos_hint = {"right": 0.33, "top": 0.10}

        self.revert_mask_button.bind(on_press=lambda *_: self._on_revert())
        self.undo_vertex_button.bind(on_press=lambda *_: self.ann_view.undo_vertex())
        self.open_kinevo_button.bind(on_press=lambda *_: self.open_kinevo_folder())
        self.jump_button.bind(on_press=lambda *_: self.jump_to_frame_id())
        self.frame_id_input.bind(on_text_validate=lambda *_: self.jump_to_frame_id())
        self.motion_blur_checkbox.bind(state=self._on_motion_blur_toggled)

        self.root.add_widget(self.revert_mask_button)
        self.root.add_widget(self.undo_vertex_button)
        self.root.add_widget(self.open_kinevo_button)
        self.root.add_widget(self.frame_id_label)
        self.root.add_widget(self.frame_id_input)
        self.root.add_widget(self.jump_button)
        self.root.add_widget(self.motion_blur_label)
        self.root.add_widget(self.motion_blur_checkbox)
        self.root.add_widget(self.biopsy_label)
        self.root.add_widget(self.biopsy_checkbox)

        Window.bind(on_key_down=self.key_down)
        Window.bind(on_request_close=self.on_request_close)
        return self.root

    def on_start(self):
        Window.fullscreen = "auto"   # reliable borderless fullscreen on desktop
        # or, if you want maximized (not fullscreen):
        # Window.maximize()
        self.load()

    def _update_info(self):
        ref = self.ref_files[self.index]
        tgt = self.target_files[self.index]
        self.info.text = f"{self.index+1}/{len(self.target_files)} \n REF: {ref} \n TGT: {tgt}"

    def _cache_ref_base(self, *_):
        rgb = get_rgb_from_texture(self.ref_view.texture)
        self.ref_base_rgb = rgb.copy() if rgb is not None else None

    def _refresh_ref_clear(self):
        if self.ref_base_rgb is None or self.ref_view.texture is None:
            return
        blit_numpy_to_texture(self.ref_base_rgb, self.ref_view.texture)
        self.ref_view.draw()

    def _refresh_ref_overlay(self):
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

    def _refresh_ref_preview(self):
        if self.ref_base_rgb is None or self.ref_view.texture is None:
            return

        disp = self.ref_base_rgb.copy()
        if self.ann_view.mask is not None:
            mask = self.ann_view.mask
            if mask.shape[:2] == disp.shape[:2]:
                disp = composite_overlay(disp, mask, alpha=0.45)

        if len(self.ann_view.poly_points) > 0:
            draw_poly_preview(disp, self.ann_view.poly_points, self.ann_view.cursor_xy)

        blit_numpy_to_texture(disp, self.ref_view.texture)
        self.ref_view.draw()

    def load(self):
        ref_path = self.ref_files[self.index]
        tgt_path = self.target_files[self.index]

        self.ref_view.set_image(ref_path)
        Clock.schedule_once(self._cache_ref_base, 0)

        self.ann_view.current_target_path = tgt_path
        self.ann_view.set_image(tgt_path)
        self._sync_pair_metadata_widgets()
        self._update_info()

        def _after_loaded(*_):
            if self.ann_view.mask is not None and np.any(self.ann_view.mask > 0):
                self._refresh_ref_overlay()
            else:
                self._refresh_ref_clear()

        Clock.schedule_once(_after_loaded, 0)

    def _sync_pair_metadata_widgets(self):
        motion_blur = False
        biopsy = None
        if self.pairs_json_path:
            try:
                payload = load_pairs_payload(self.pairs_json_path)
                motion_blur = get_motion_blur_from_payload(payload, self.index)
                biopsy = get_biopsy_from_payload(payload, self.index)
            except Exception as e:
                print(f"[Pair Metadata] Could not load state from {self.pairs_json_path}: {e}")
                motion_blur = False
                biopsy = None

        self._updating_motion_blur_checkbox = True
        try:
            self.motion_blur_checkbox.state = "down" if motion_blur else "normal"
        finally:
            self._updating_motion_blur_checkbox = False

        self.biopsy_checkbox.state = "down" if bool(biopsy) else "normal"

    def _on_motion_blur_toggled(self, _checkbox, value):
        if self._updating_motion_blur_checkbox:
            return
        if not self.allow_editing:
            return
        if not self.pairs_json_path:
            print("[Motion Blur] No pairs.json configured. Use --pairs-json to persist metadata.")
            return

        is_active = value == "down"
        try:
            update_motion_blur_in_json(self.pairs_json_path, self.index, is_active)
            print(f"[Motion Blur] Saved pair {self.index}: motion_blur={is_active}")
        except Exception as e:
            print(f"[Motion Blur] Failed to save motion_blur in {self.pairs_json_path}: {e}")

    def save(self):
        self.ann_view.save_current_mask()

    def _on_revert(self):
        self.ann_view.revert_mask()
        Clock.schedule_once(lambda *_: self._refresh_ref_clear(), 0)
        self._update_info()

    def _on_ref_cursor_moved(self, position):
        if self.ann_view.base_rgb is None or self.ann_view.mask is None:
            return
        self.ann_view.cursor_xy = (int(position[0]), int(position[1]))
        if len(self.ann_view.poly_points) > 0:
            self._refresh_ref_preview()

    def _on_ref_click(self, position, button):
        if not self.allow_editing or self.ann_view.base_rgb is None or self.ann_view.mask is None:
            return

        x, y = map(int, position)
        w, h = self.ref_view.texture.size
        if not (0 <= x < w and 0 <= y < h):
            return

        if button == "left":
            self.ann_view.poly_points.append((x, y))
            self.ann_view.cursor_xy = (x, y)
            self._refresh_ref_preview()
        elif button == "right":
            self.ann_view.finalize_polygon()
            self._refresh_ref_overlay()
            self._update_info()
        elif button == "middle":
            self.ann_view.poly_points.clear()
            self.ann_view.cursor_xy = None
            if self.ann_view.mask is not None and np.any(self.ann_view.mask > 0):
                self._refresh_ref_overlay()
            else:
                self._refresh_ref_clear()
            self._update_info()

    def jump_to_frame_id(self, *args):
        del args
        value = self.frame_id_input.text.strip()
        if not value:
            print("[Jump] Please enter a frame ID.")
            return

        try:
            frame_id = int(value)
        except ValueError:
            print(f"[Jump] Invalid frame ID: {value}")
            return

        if frame_id < 1 or frame_id > len(self.target_files):
            print(f"[Jump] Frame ID out of range: {frame_id} (valid: 1-{len(self.target_files)})")
            return

        new_index = frame_id - 1
        if new_index == self.index:
            return

        self.save()
        self.index = new_index
        self.load()

    def open_kinevo_folder(self, *args):
        del args
        if not self.pairs_json_path:
            print("[Open Kinevo Folder] No pairs.json configured.")
            return

        try:
            payload = load_pairs_payload(self.pairs_json_path)
            if self.index >= len(payload):
                print(f"[Open Kinevo Folder] Pair index out of range: {self.index}")
                return
            kinevo_path = payload[self.index].get("kinevo")
            if not kinevo_path:
                print("[Open Kinevo Folder] No 'kinevo' path for this pair.")
                return

            if not os.path.isabs(kinevo_path):
                base_root = self.pairs_root or os.path.dirname(os.path.abspath(self.pairs_json_path))
                kinevo_path = os.path.join(base_root, kinevo_path.replace("/", os.path.sep))
            kinevo_path = os.path.abspath(kinevo_path)
            if not os.path.isdir(kinevo_path):
                print(f"[Open Kinevo Folder] Folder not found: {kinevo_path}")
                return

            print(f"[Open Kinevo Folder] Opening: {kinevo_path}")
            if sys.platform == "win32":
                os.startfile(kinevo_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.call(("open", kinevo_path))
            else:
                subprocess.call(("xdg-open", kinevo_path))
        except Exception as e:
            print(f"[Open Kinevo Folder] Error opening folder: {e}")
            return

    def key_down(self, instance, keyboard, keycode, text, modifiers):
        del instance, keyboard, text, modifiers
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
        del args, kwargs
        self.save()
        return False
