# Tool Pose Annotation GUI
Pose annotation GUI for laparoscopic surgical tools.

[//]: # (![]&#40;demo.gif&#41;)

# Usage
Clone this repo and install the dependencies:
```bash
git clone https://github.com/cai4cai/tool-pose-annotation-gui.git
cd tool-pose-annotation-gui
pip install -r requirements.txt
```

Run the app:
```bash
python annotate_polygon.py --pairs-json ./images/pairs.json
```

## Arguments
Only two CLI arguments are supported:

- `--pairs-json` (default: `./images/pairs.json`)
- `--mask-out` (default: `./masks`)

Example:
```bash
python annotate_polygon.py --pairs-json G:\NeuroPPEYE\stage2_paired\pairs.json --mask-out G:\NeuroPPEYE\stage2_paired\
```

`--pairs-json` root handling:
- Relative `ref/target` (or `white/blue`) paths are resolved from the parent folder of `pairs.json`.

`--mask-out` handling:
- If set to a parent folder (for example `...\stage2_paired\`), a `masks` subfolder is automatically used/created.
- If set directly to a `masks` folder (for example `...\stage2_paired\masks`), that folder is used.

## `pairs.json` format
The loader supports either schema:

```json
{"ref": "path/to/white.png", "target": "path/to/blue.png"}
```
or
```json
{"white": "path/to/white.png", "blue": "path/to/blue.png"}
```

Optional metadata fields used by the GUI:
- `motion_blur` (editable checkbox, persisted to `pairs.json`)
- `Biopsy` (read-only checkbox)
- `kinevo` (relative/absolute folder path, opened by button)

Example item:
```json
{
  "white": "case035/timepoint003/white.png",
  "blue": "case035/timepoint003/blue.png",
  "kinevo": "case035/Kinevo",
  "Biopsy": false,
  "motion_blur": false
}
```

## GUI features
- Annotate on **TAR** and **REF** panels.
- If annotating on REF, polygon preview is shown on REF.
- `Enter` finalizes polygon and updates overlay on both REF and TAR.
- Frame jump: input a 1-based frame ID (for example `11`) and click `Go`.
- Open corresponding Kinevo folder from current pair.
- Motion blur checkbox (editable, writes to `pairs.json`).
- Biopsy checkbox (read-only, from `pairs.json`).

## Output
This annotator exports **both**:
- `mask.png` (binary mask)
- `mask.json` (polygon vertex coordinates used to create the mask)

The JSON format is:
```json
{
  "polygons": [
    {"vertices": [[x, y], [x, y], [x, y]]}
  ]
}
```
