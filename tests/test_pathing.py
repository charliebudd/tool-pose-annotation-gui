import os

from src.polygon_annotator.pathing import mask_path_for_target, mask_path_to_vertices_json_path


def test_mask_path_for_target_uses_case_relative_layout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "images" / "case035" / "timepoint003" / "blue.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")

    out = mask_path_for_target(str(target), images_root="images", masks_root="masks")
    assert out == os.path.join("masks", "case035", "timepoint003", "mask.png")


def test_mask_path_to_vertices_json_path():
    mask_path = os.path.join("masks", "case035", "timepoint003", "mask.png")
    out = mask_path_to_vertices_json_path(mask_path)
    assert out.endswith(os.path.join("masks", "case035", "timepoint003", "mask.json"))


def test_mask_path_for_target_handles_mixed_separators(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "images" / "case001" / "tp1" / "blue.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")

    mixed = str(target).replace(os.path.sep, "/")
    out = mask_path_for_target(mixed, images_root="images", masks_root="masks")
    assert out == os.path.join("masks", "case001", "tp1", "mask.png")
