import json

from prepare_dataset.prepare_stage2_paired_metadata import build_pairs


def test_build_pairs_sets_motion_blur_false_and_keeps_metadata(tmp_path):
    root = tmp_path / "images"
    tp_dir = root / "case001" / "timepoint000"
    tp_dir.mkdir(parents=True)
    (tp_dir / "white.png").write_bytes(b"w")
    (tp_dir / "blue.png").write_bytes(b"b")
    (root / "case001" / "Kinevo").mkdir(parents=True)
    (tp_dir / "MetaData.json").write_text(
        json.dumps({"Biopsy": True, "Comment": "example"}),
        encoding="utf-8",
    )

    pairs = build_pairs(root)

    assert len(pairs) == 1
    assert pairs[0]["white"] == "case001/timepoint000/white.png"
    assert pairs[0]["blue"] == "case001/timepoint000/blue.png"
    assert pairs[0]["kinevo"] == "case001/Kinevo"
    assert pairs[0]["motion_blur"] is False
    assert pairs[0]["Biopsy"] is True
    assert pairs[0]["Comment"] == "example"
