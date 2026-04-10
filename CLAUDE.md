# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
python3 -m pip install --upgrade pip
python3 -m pip install -e .[dev]

# Run the app
python3 annotate_polygon.py --pairs-json ./images/pairs.json

# Run all tests
python3 -m pytest

# Run a single test file
python3 -m pytest tests/test_pairs.py

# Run with coverage
python3 -m pytest --cov=src --cov-report=term-missing
```

## Architecture

The app is a Kivy-based two-panel polygon annotation GUI for labeling image pairs (REF + TAR).

**Entry flow**: `annotate_polygon.py` → `src/polygon_annotator/cli.py:main()` → `TwoPanelApp.run()`

### Layer overview

| Layer | File | Role |
|-------|------|------|
| Base widget | `src/imageannotator.py` | Abstract Kivy `Widget` — zoom, mouse→image coordinate transform, touch dispatch |
| Views | `src/polygon_annotator/views.py` | `ReferenceViewer` (left panel, read-only display + event delegation) and `PolygonSegAnnotator` (right panel, polygon drawing, mask I/O, undo stack) |
| App | `src/polygon_annotator/app.py` | `TwoPanelApp` — pair navigation, keyboard shortcuts, REF overlay sync, metadata widgets |
| CLI | `src/polygon_annotator/cli.py` | Argument parsing, path resolution, app launch |
| Pairs | `src/polygon_annotator/pairs.py` | Load `pairs.json`, read/write `motion_blur` and `Biopsy` metadata |
| Mask ops | `src/polygon_annotator/mask_ops.py` | numpy/PIL: polygon fill, overlay compositing, texture↔numpy conversion |
| I/O utils | `src/polygon_annotator/io_utils.py` | Save/load `mask.png` and `mask.json` (polygon vertices) |
| Pathing | `src/polygon_annotator/pathing.py` | Derives `masks/<rel_path>/mask.png` from target image path |
| Constants | `src/polygon_annotator/constants.py` | Keycodes, help text |

### Key design points

- **Coordinate system**: Kivy's Y-axis is bottom-up; `ImageAnnotator.window2image()` flips Y when converting window→image coords. The app stores and saves polygon vertices in image-space (top-left origin).
- **REF overlay sync**: `TwoPanelApp` caches the REF panel's raw RGB (`ref_base_rgb`) after load, then re-composites the mask overlay on top whenever the annotation changes. The REF panel itself is passive — it just displays what `TwoPanelApp` pushes to its texture.
- **Undo**: `PolygonSegAnnotator` maintains a mask undo stack (max 30 entries, trimmed to 20). Each `finalize_polygon()` call pushes before mutating.
- **Output**: Each pair writes two files — `mask.png` (binary) and `mask.json` (polygon vertices). The JSON path is derived from the mask path by swapping the extension (`pathing.mask_path_to_vertices_json_path`).
- **pairs.json schemas**: Supports both `{"ref": ..., "target": ...}` and `{"white": ..., "blue": ...}` key conventions.
