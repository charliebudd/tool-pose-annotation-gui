import json

import numpy as np
import pytest
from PIL import Image

from src.polygon_annotator.io_utils import (
    load_mask_or_blank,
    load_vertices_json,
    save_vertices_json,
)


def test_vertices_json_roundtrip(tmp_path):
    path = tmp_path / "mask.json"
    polygons = [[(1, 2), (3, 4), (5, 6)]]
    save_vertices_json(polygons, str(path))
    out = load_vertices_json(str(path))
    assert out == polygons


def test_load_vertices_json_missing_or_invalid(tmp_path):
    missing = tmp_path / "nope.json"
    assert load_vertices_json(str(missing)) == []

    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert load_vertices_json(str(bad)) == []


def test_load_mask_or_blank_missing_returns_zeros(tmp_path):
    out = load_mask_or_blank(str(tmp_path / "missing.png"), (3, 4))
    assert out.shape == (3, 4)
    assert out.dtype == np.uint8
    assert np.all(out == 0)


def test_load_mask_or_blank_shape_mismatch_raises(tmp_path):
    path = tmp_path / "mask.png"
    arr = np.zeros((2, 2), dtype=np.uint8)
    Image.fromarray(arr, mode="L").save(path)
    with pytest.raises(ValueError):
        load_mask_or_blank(str(path), (4, 4))
