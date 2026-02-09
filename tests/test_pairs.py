import json
import os

from src.polygon_annotator.pairs import (
    get_biopsy_from_pair,
    get_motion_blur_from_pair,
    infer_ref_from_target,
    load_pairs_from_json,
    update_motion_blur_in_json,
)


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


def test_load_pairs_from_json_supports_white_blue_schema(tmp_path):
    pairs_path = tmp_path / "pairs.json"
    payload = [
        {"white": "case1/timepoint01/white.png", "blue": "case1/timepoint01/blue.png", "video": "videos/a.mp4"},
        {"white": "case2/timepoint09/white.png", "blue": "case2/timepoint09/blue.png"},
    ]
    pairs_path.write_text(json.dumps(payload), encoding="utf-8")

    ref, tgt, video = load_pairs_from_json(str(pairs_path))
    assert ref == ["case1/timepoint01/white.png", "case2/timepoint09/white.png"]
    assert tgt == ["case1/timepoint01/blue.png", "case2/timepoint09/blue.png"]
    assert video[0] == os.path.join(str(tmp_path), "videos", "a.mp4")
    assert video[1] is None


def test_motion_blur_defaults_false_when_missing():
    assert get_motion_blur_from_pair({"white": "a", "blue": "b"}) is False


def test_biopsy_reads_true_false_and_missing():
    assert get_biopsy_from_pair({"Biopsy": True}) is True
    assert get_biopsy_from_pair({"Biopsy": False}) is False
    assert get_biopsy_from_pair({"white": "a", "blue": "b"}) is None


def test_update_motion_blur_in_json_updates_only_targeted_item(tmp_path):
    pairs_path = tmp_path / "pairs.json"
    payload = [
        {"white": "case1/timepoint01/white.png", "blue": "case1/timepoint01/blue.png", "Biopsy": True},
        {"white": "case2/timepoint02/white.png", "blue": "case2/timepoint02/blue.png", "motion_blur": False},
    ]
    pairs_path.write_text(json.dumps(payload), encoding="utf-8")

    update_motion_blur_in_json(str(pairs_path), 1, True)
    saved = json.loads(pairs_path.read_text(encoding="utf-8"))

    assert saved[1]["motion_blur"] is True
    assert "motion_blur" not in saved[0]
    assert saved[0]["Biopsy"] is True
    assert saved[1]["white"] == "case2/timepoint02/white.png"


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
