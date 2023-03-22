import os
os.environ['KIVY_NO_ARGS'] = '1'
# os.environ['KIVY_NO_CONSOLELOG'] = '1'

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.image import AsyncImage, Image
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Ellipse, Line
from kivy.core.window import Window
from kivy.config import Config
from kivy import clock

from os import remove
from random import random
from glob import glob
import json
import argparse
import numpy as np

Window.maximize()
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

ESCAPE_KEYCODE = 41
BACKSPACE_KEYCODE = 42
RIGHT_KEYCODE = 79
LEFT_KEYCODE = 80

MOUSE_BUTTON_MAP = {
    "left": "visible",
    "right": "occluded",
    "middle": "missing"
}

TAG_COLOR_VALUE_MAP = {
    "visible": 1.0,
    "occluded": 0.6,
    "missing": 0.2
}

POINT_RADIUS = 3

def position_on_line(p, a, b):
    p, a, b = tuple(map(np.array, (p, a, b)))
    ap = p-a
    ab = b-a
    abl = np.linalg.norm(ab)
    abu = ab / abl
    return tuple(a + abu * np.clip(np.dot(ap, abu), 0, abl))

class Skeleton(Widget):

    def __init__(self, position):
        super().__init__()
        self.point_size = 3
        self.hue = random()
        self.points = [position]
        self.point_index = 0
        self.edges = [[0, 1], [1, 2], [2, 3], [1, 4], [4, 5]]
        self.interpolating = False

    def add_point(self, occluded=False):
        if self.interpolating:
            self.interpolating = False
        else:
            self.points.append(self.points[-1])
            self.point_index += 1
            if self.point_index == 3 or self.point_index == 5:
                self.points.append(self.points[-1])
                self.point_index += 1
                self.interpolating = occluded
            
    def must_stop(self):
        return self.point_index > 4 and not self.interpolating
    
    def can_stop(self):
        return self.point_index > 1 and not self.interpolating
    
    def finish(self):
        self.points = self.points[:-1]
        self.edges = [e for e in self.edges if e[1] < len(self.points)]
        self.draw()

    def set_position(self, position):
        if self.interpolating:
            a = self.points[1]
            b = self.points[self.point_index-1]
            position = position_on_line(position, a, b)
            self.points[self.point_index-2] = position
        self.points[self.point_index] = position
        self.draw()

    def draw(self):
        self.canvas.clear()
        with self.canvas:
            
            for edge in self.edges:
                if edge[1] == 3 or edge[1] == 5:
                    Color(self.hue, 0.2, 0.5, mode='hsv')
                else:
                    Color(self.hue, 0.2, 1.0, mode='hsv')
                if edge[0] < len(self.points) and edge[1] < len(self.points):
                    start, end = self.points[edge[0]], self.points[edge[1]]
                    Line(points=[start, end])
                    
            for i in [0, 1, 3, 2, 5, 4, 6]:
                if i < len(self.points):
                    point = self.points[i]
                    if i == 3 or i == 5:
                        Color(self.hue, 0.2, 0.5, mode='hsv')
                    else:
                        Color(self.hue, 0.2, 1.0, mode='hsv')
                    Ellipse(pos=(point[0] - POINT_RADIUS, point[1] - POINT_RADIUS), size=(2 * POINT_RADIUS, 2 * POINT_RADIUS))

    def get_data(self):
        return {'nodes': self.points, 'edges': self.edges}

class SkeletonAnnotator(Widget):

    def __init__(self):
        super().__init__()
        self.skeletons = []
        Window.bind(mouse_pos=self.mouse_pos)
        self.waiting = False

    def on_touch_down(self, touch):
        
        if self.waiting:
            return

        position = (touch.x, touch.y)

        if touch.button in MOUSE_BUTTON_MAP:

            if len(self.skeletons) == 0:
                self.skeletons.append(Skeleton(position))
                self.add_widget(self.skeletons[-1])
            
            if touch.button == "left":
                self.skeletons[-1].add_point()
            elif touch.button == "right":
                self.skeletons[-1].add_point(occluded=True)
            elif touch.button == "middle" and self.skeletons[-1].can_stop():
                self.skeletons[-1].finish()
                self.skeletons.append(Skeleton(position))
                self.add_widget(self.skeletons[-1])
                
            if self.skeletons[-1].must_stop():
                self.skeletons[-1].finish()
                self.skeletons.append(Skeleton(position))
                self.add_widget(self.skeletons[-1])

    def mouse_pos(self, window, pos):
        if self.waiting:
            return
        position = (pos[0], pos[1])
        if len(self.skeletons) > 0:
            self.skeletons[-1].set_position(position)

    
    def set_data(self, data):
        
        for skel in data:
            self.skeletons.append(Skeleton((0, 0)))
            self.add_widget(self.skeletons[-1])
            self.skeletons[-1].points = skel["nodes"]
            self.skeletons[-1].draw()
        
        self.skeletons.append(Skeleton((0, 0)))
        self.add_widget(self.skeletons[-1])
        
        return [skel.get_data() for skel in self.skeletons if len(skel.points) > 1]

    def get_data(self):
        return [skel.get_data() for skel in self.skeletons if len(skel.points) > 1]

    def reset(self):
        for skeleton in self.skeletons:
            self.remove_widget(skeleton)
        self.skeletons = []

class AnnotationApp(App):

    def __init__(self, image_files, annotation_files):
        super().__init__()
        self.image_files = image_files
        self.annotation_files = annotation_files
        self.index = 0
        self.key_code = None
        self.key_held = False
    
    def build(self):
        root = FloatLayout()
        self.image_display = AsyncImage(allow_stretch=True)
        root.add_widget(self.image_display)
        self.annotator = SkeletonAnnotator()
        root.add_widget(self.annotator)
        Window.bind(on_key_down=self.key_down)
        self.image_display.source = self.image_files[self.index]
        return root
    
    def on_start(self):
        self.load()

    def key_down(self, instance, keyboard, keycode, text, modifiers):
        if keycode == BACKSPACE_KEYCODE:
            self.annotator.reset()
        elif keycode == LEFT_KEYCODE and self.index > 0:
            self.save()
            self.index -= 1
            self.load()
        elif keycode == RIGHT_KEYCODE and self.index < len(self.image_files) - 1:
            self.save()
            self.index += 1
            self.load()

    def load(self):
        self.image_display.source = self.image_files[self.index]
        self.annotator.reset()
        if os.path.exists(self.annotation_files[self.index]):
            self.annotator.waiting = True
            self.load_annotations()
       
    def load_annotations(self):
        if self.image_display.texture_size == [32, 32]:
            clock.Clock.schedule_once(lambda x:AnnotationApp.load_annotations(self), 0.01)
            return
        with open(self.annotation_files[self.index], 'r') as file:
            data = json.load(file)
        for skel in data:
            skel['nodes'] = [self.image_to_gui(pos) for pos in skel['nodes']]
        self.annotator.set_data(data)
        self.annotator.waiting = False
        
    def save(self):
        data = self.annotator.get_data()
        for skel in data:
            skel['nodes'] = [self.gui_to_image(pos) for pos in skel['nodes']]
        with open(self.annotation_files[self.index], 'w') as file:
            json.dump(data, file)
            
    def gui_to_image(self, point):
        x_shift = self.image_display.pos[0] + int((self.image_display.size[0] - self.image_display.norm_image_size[0]) / 2)
        y_shift = self.image_display.pos[1] + int((self.image_display.size[1] - self.image_display.norm_image_size[1]) / 2)
        x_scale = self.image_display.texture.size[0] / self.image_display.norm_image_size[0]
        y_scale = self.image_display.texture.size[1] / self.image_display.norm_image_size[1]
        x = (point[0] - x_shift) * x_scale
        y = (point[1] - y_shift) * y_scale
        return [x, y]
        
    def image_to_gui(self, point):
        x_shift = self.image_display.pos[0] + int((self.image_display.size[0] - self.image_display.norm_image_size[0]) / 2)
        y_shift = self.image_display.pos[1] + int((self.image_display.size[1] - self.image_display.norm_image_size[1]) / 2)
        x_scale = self.image_display.texture.size[0] / self.image_display.norm_image_size[0]
        y_scale = self.image_display.texture.size[1] / self.image_display.norm_image_size[1]
        x = (point[0] / x_scale) + x_shift
        y = (point[1] / y_scale) + y_shift
        return [x, y]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--image-glob', required=True, type=str,
        help='glob pattern for finding images'
    )
    parser.add_argument(
        '--skip-annotated', action="store_true",
        help='filters out images that have already been annotated'
    )
    args = parser.parse_args()

    images = sorted(glob(args.image_glob, recursive=True))
    
    if args.skip_annotated:
        images = [i for i in images if not os.path.exists(i.split("."[0] + ".json"))]
        
    assert len(images) > 0, 'No images found!'

    annotations = [i.split(".")[0] + ".json" for i in images]

    AnnotationApp(images, annotations).run()
    