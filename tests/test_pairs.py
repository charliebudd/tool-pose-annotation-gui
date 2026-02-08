import json
import os

from src.polygon_annotator.pairs import infer_ref_from_target, load_pairs_from_json


def test_load_pairs_from_json_with_and_without_video(tmp_path):
    pairs_path = tmp_path / "pairs.json"
    payload = [
        {"ref": "images/case1/white.png", "target": "images/case1/blue.png", "video": "videos/a.mp4"},
        {"ref": "images/case2/white.png", "target": "images/case2/blue.png"},
    ]
    pairs_path.write_text(json.dumps(payload), encoding="utf-8")

    ref, tgt, video = load_pairs_from_json(str(pairs_path))
    assert ref == ["images/case1/white.png", "images/case2/white.png"]
    assert tgt == ["images/case1/blue.png", "images/case2/blue.png"]
    assert video[0] == os.path.join(str(tmp_path), "videos", "a.mp4")
    assert video[1] is None


def test_infer_ref_from_target_preserves_relative_structure():
    targets = [
        os.path.join("targets", "case1", "tp1", "blue.png"),
        os.path.join("targets", "case2", "tp9", "blue.png"),
    ]
    out = infer_ref_from_target(targets, ref_root="refs", target_root="targets")
    assert out == [
        os.path.join("refs", "case1", "tp1", "blue.png"),
        os.path.join("refs", "case2", "tp9", "blue.png"),
    ]
