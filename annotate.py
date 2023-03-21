import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONSOLELOG'] = '1'

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.image import AsyncImage
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Ellipse, Line
from kivy.core.window import Window
from kivy.config import Config

from os import remove
from random import random
from glob import glob
import json
import argparse
import numpy as np

Config.set('input', 'mouse', 'mouse,multitouch_on_demand')

ESCAPE_KEYCODE = 41
BACKSPACE_KEYCODE = 42

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
        # self.edges = [[0, 1], [1, 2], [1, 3]]
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

    def on_touch_down(self, touch):

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
        position = (pos[0], pos[1])
        if len(self.skeletons) > 0:
            self.skeletons[-1].set_position(position)

    def get_data(self):
        return [skel.get_data() for skel in self.skeletons if len(skel.points) > 1]

    def reset(self):
        for skeleton in self.skeletons:
            self.remove_widget(skeleton)
        self.skeletons = []

class AnnotationApp(App):

    def __init__(self, images, start_index, save_function):
        super().__init__()
        self.images = images
        self.index = start_index
        self.save_function = save_function
        self.key_code = None
        self.key_held = False
    
    def build(self):

        root = FloatLayout()

        self.image_display = AsyncImage()
        root.add_widget(self.image_display)

        self.annotator = SkeletonAnnotator()
        root.add_widget(self.annotator)

        Window.bind(on_key_down=self.key_down, on_key_up=self.key_up)

        self.image_display.source = self.images[self.index]

        return root

    def convert_position(self, point):
            x_shift = int((self.image_display.size[0] - self.image_display.norm_image_size[0]) / 2)
            y_shift = int((self.image_display.size[1] - self.image_display.norm_image_size[1]) / 2)
            x = (point[0] - (self.image_display.pos[0] + x_shift)) * self.image_display.texture_size[0] / self.image_display.norm_image_size[0]
            y = self.image_display.texture_size[1] - (point[1] - (self.image_display.pos[1] + y_shift)) * self.image_display.texture_size[1] / self.image_display.norm_image_size[1]
            return[int(x), int(y)]

    def key_up(self, instance, keyboard, keycode):
        if keycode == self.key_code:
            self.key_held = False

    def key_down(self, instance, keyboard, keycode, text, modifiers):
        
        if keycode == ESCAPE_KEYCODE or self.key_held:
            return

        self.key_held = True
        self.key_code = keycode

        if keycode == BACKSPACE_KEYCODE:
            self.go_to_previous()
        else:
            self.go_to_next()
            
    def go_to_previous(self):

        if len(self.annotator.skeletons) == 0:
            self.index -= 1
            self.image_display.source = self.images[self.index]
            
        self.annotator.reset()

    def go_to_next(self):

        data = self.annotator.get_data()

        for skel in data:
            skel['nodes'] = [self.convert_position(pos) for pos in skel['nodes']]

        self.save_function(self.images[self.index], data)

        self.index += 1
        self.image_display.source = self.images[self.index]

        self.annotator.reset()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--folder', dest='folder', required=True, metavar='',
        help='folder containing the images to be annotated'
    )
    parser.add_argument(
        '-i', '--image-suffix', dest='image_suffix', default='img', metavar='',
        help='time to leave between samples in seconds'
    )
    parser.add_argument(
        '-s', '--skeleton-suffix', dest='skeleton_suffix', default='skl', metavar='',
        help='folder to output the sampled images to'
    )
    args = parser.parse_args()

    def save_function(image_file, data):
        json_file = image_file.replace(f'{args.image_suffix}.png', f'{args.skeleton_suffix}.json')
        with open(json_file, 'w') as file:
            json.dump(data, file)

    images = sorted(glob(f'{args.folder}/*{args.image_suffix}.png'))
    start_index = len(glob(f'{args.folder}/*{args.skeleton_suffix}.json'))
    start_index = 0

    AnnotationApp(images, start_index, save_function).run()
    