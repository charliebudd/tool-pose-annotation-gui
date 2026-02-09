from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label

from .constants import (
    ENTER_KEYCODE,
    HELP_TEXT,
    LEFT_KEYCODE,
    RIGHT_KEYCODE,
    R_KEYCODE,
    U_KEYCODE,
)
from .mask_ops import blit_numpy_to_texture, composite_overlay, get_rgb_from_texture
from .pairs import get_motion_blur_from_payload, load_pairs_payload, update_motion_blur_in_json
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
    ):
        super().__init__()
        self.ref_files = ref_files
        self.target_files = target_files
        self.target_root = target_root
        self.mask_root = mask_root
        self.allow_editing = allow_editing
        self.video_files = video_files or [None] * len(target_files)
        self.pairs_json_path = pairs_json_path
        self.index = 0
        self.ref_base_rgb = None
        self._updating_motion_blur_checkbox = False

    def _mask_path_getter(self, target_path: str, hw: tuple[int, int]):
        del hw
        return mask_path_for_target(
            target_path=target_path,
            images_root="images",
            masks_root="masks",
        )

    def build(self):
        self.root = FloatLayout()
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
        self.open_biopsy_button = Button(
            text="Open Biopsy Video",
            size_hint=(0.22, 0.04),
            pos_hint={"right": 0.99, "top": 0.10},
        )
        self.motion_blur_label = Label(
            text="Motion Blur",
            size_hint=(0.12, 0.04),
            pos_hint={"right": 0.15, "top": 0.10},
            color=(1, 1, 1, 1),
        )
        self.motion_blur_checkbox = CheckBox(
            size_hint=(0.04, 0.04),
            pos_hint={"right": 0.17, "top": 0.10},
            disabled=(not self.allow_editing) or (not self.pairs_json_path),
        )

        self.revert_mask_button.bind(on_press=lambda *_: self._on_revert())
        self.undo_vertex_button.bind(on_press=lambda *_: self.ann_view.undo_vertex())
        self.open_biopsy_button.bind(on_press=lambda *_: self.open_biopsy_video())
        self.motion_blur_checkbox.bind(active=self._on_motion_blur_toggled)

        self.root.add_widget(self.revert_mask_button)
        self.root.add_widget(self.undo_vertex_button)
        self.root.add_widget(self.open_biopsy_button)
        self.root.add_widget(self.motion_blur_label)
        self.root.add_widget(self.motion_blur_checkbox)

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
        self.info.text = f"{self.index+1}/{len(self.target_files)} | REF: {ref} | TGT: {tgt}"

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

    def load(self):
        ref_path = self.ref_files[self.index]
        tgt_path = self.target_files[self.index]

        self.ref_view.set_image(ref_path)
        Clock.schedule_once(self._cache_ref_base, 0)

        self.ann_view.current_target_path = tgt_path
        self.ann_view.set_image(tgt_path)
        self._sync_motion_blur_checkbox()
        self._update_info()

        def _after_loaded(*_):
            if self.ann_view.mask is not None and np.any(self.ann_view.mask > 0):
                self._refresh_ref_overlay()
            else:
                self._refresh_ref_clear()

        Clock.schedule_once(_after_loaded, 0)

    def _sync_motion_blur_checkbox(self):
        value = False
        if self.pairs_json_path:
            try:
                payload = load_pairs_payload(self.pairs_json_path)
                value = get_motion_blur_from_payload(payload, self.index)
            except Exception as e:
                print(f"[Motion Blur] Could not load state from {self.pairs_json_path}: {e}")
                value = False

        self._updating_motion_blur_checkbox = True
        try:
            self.motion_blur_checkbox.active = value
        finally:
            self._updating_motion_blur_checkbox = False

    def _on_motion_blur_toggled(self, _checkbox, value):
        if self._updating_motion_blur_checkbox:
            return
        if not self.allow_editing:
            return
        if not self.pairs_json_path:
            print("[Motion Blur] No pairs.json configured. Use --pairs-json to persist metadata.")
            return

        try:
            update_motion_blur_in_json(self.pairs_json_path, self.index, value)
            print(f"[Motion Blur] Saved pair {self.index}: motion_blur={bool(value)}")
        except Exception as e:
            print(f"[Motion Blur] Failed to save motion_blur in {self.pairs_json_path}: {e}")

    def save(self):
        self.ann_view.save_current_mask()

    def _on_revert(self):
        self.ann_view.revert_mask()
        Clock.schedule_once(lambda *_: self._refresh_ref_clear(), 0)
        self._update_info()

    def open_biopsy_video(self, *args):
        del args
        if not self.target_files:
            print("[Open Biopsy Video] No target files loaded.")
            return

        current_target = self.target_files[self.index]
        video_path = None
        if self.video_files and self.index < len(self.video_files):
            candidate = self.video_files[self.index]
            if candidate:
                video_path = candidate
                if not os.path.isabs(video_path):
                    video_path = os.path.abspath(video_path)
                if not os.path.exists(video_path):
                    print(f"[Open Biopsy Video] Video path not found: {video_path}")
                    video_path = None

        if video_path:
            print(f"[Open Biopsy Video] Opening: {video_path}")
            try:
                if sys.platform == "win32":
                    os.startfile(video_path)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.call(("open", video_path))
                else:
                    subprocess.call(("xdg-open", video_path))
            except Exception as e:
                print(f"[Open Biopsy Video] Error opening video: {e}")
            return

        search_path = os.path.dirname(os.path.abspath(current_target))
        video_extensions = [".mp4", ".avi", ".mov", ".mkv"]

        biopsy_candidate = None
        fallback_candidate = None

        for _ in range(3):
            if not os.path.exists(search_path):
                break

            try:
                for fname in os.listdir(search_path):
                    lower = fname.lower()
                    if any(lower.endswith(ext) for ext in video_extensions):
                        full_path = os.path.join(search_path, fname)
                        if "biopsy" in lower and biopsy_candidate is None:
                            biopsy_candidate = full_path
                        if fallback_candidate is None:
                            fallback_candidate = full_path
            except Exception as e:
                print(f"[Open Biopsy Video] Error listing {search_path}: {e}")

            if biopsy_candidate:
                break

            parent = os.path.dirname(search_path)
            if parent == search_path:
                break
            search_path = parent

        video_path = biopsy_candidate or fallback_candidate
        if not video_path:
            print("[Open Biopsy Video] No video found near:", current_target)
            return

        print(f"[Open Biopsy Video] Opening: {video_path}")
        try:
            if sys.platform == "win32":
                os.startfile(video_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.call(("open", video_path))
            else:
                subprocess.call(("xdg-open", video_path))
        except Exception as e:
            print(f"[Open Biopsy Video] Error opening video: {e}")

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
