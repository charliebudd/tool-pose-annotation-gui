import numpy as np

from src.polygon_annotator.mask_ops import composite_overlay, fill_polygon_in_mask


def test_fill_polygon_in_mask_fills_when_three_or_more_points():
    mask = np.zeros((20, 20), dtype=np.uint8)
    points = [(5, 5), (15, 5), (10, 15)]
    out = fill_polygon_in_mask(mask, points, value=255)
    assert out[10, 10] == 255


def test_fill_polygon_in_mask_noop_with_less_than_three_points():
    mask = np.zeros((10, 10), dtype=np.uint8)
    out = fill_polygon_in_mask(mask, [(1, 1), (2, 2)], value=255)
    assert np.array_equal(out, mask)


def test_composite_overlay_noop_for_empty_mask():
    base = np.full((4, 4, 3), 100, dtype=np.uint8)
    mask = np.zeros((4, 4), dtype=np.uint8)
    out = composite_overlay(base, mask, alpha=0.45)
    assert np.array_equal(out, base)


def test_composite_overlay_changes_masked_pixels():
    base = np.full((2, 2, 3), 100, dtype=np.uint8)
    mask = np.array([[0, 255], [0, 255]], dtype=np.uint8)
    out = composite_overlay(base, mask, alpha=0.5)
    assert np.array_equal(out[0, 0], base[0, 0])
    assert out[0, 1, 0] > base[0, 1, 0]
