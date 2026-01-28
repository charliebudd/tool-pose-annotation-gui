# Tool Pose Annotation GUI
Pose annotation GUI for laparoscopic surgical tools.

[//]: # (![]&#40;demo.gif&#41;)

# Usage
Clone this repo and install the dependancies...
```bash
git clone https://github.com/charliebudd/tool-pose-annotation-gui.git
cd tool-pose-annotation-gui
pip install -r requirements.txt
```
and then run the app...
```bash
python annotate_polygon.py --pairs-json ./images/pairs.json
```

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

[//]: # (The images are found using the glob pattern provided with the `--image-glob` argument while the `--visualise-only` can be used to prevent accidently editing when reviewing annotations. The `Left Arrow` and `Right Arrow` keys scrolls through the images and the `Scroll Wheel` can be used to zoom out from the image to allow point placement outside the image. `Left Click` starts a new pose annotation or places a keypoint if one has begun. `Right Click` places an estimated point and then allows a point to be placed along the edge to this new estimated point. `Middle Click` ends the current pose annotation. `Clicking an edge` of an existing skeleton places a new visible/occluded transition point and updates the rest of the tags to fit. Finally `Backspace` can be used to delete the last image annotation. When you are finsihed annotating, the `Esc` key quits the application.)
