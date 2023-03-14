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

class Skeleton(Widget):

    def __init__(self, position):
        super().__init__()
        self.point_size = 3
        self.hue = random()
        self.points = [position, position]
        self.point_index = 0
        self.edges = [[0, 1], [1, 2], [1, 3]]
        self.tags = []

    def add_point(self, tag):
        self.tags.append(tag)
        self.points.append(self.points[-1])
        self.point_index += 1

    def is_done(self):
        return self.point_index > 3

    def set_position(self, position):
        self.points[self.point_index] = position
        self.draw()

    def draw(self):
        self.canvas.clear()
        with self.canvas:
            Color(self.hue, 0.2, 1.0, mode='hsv')
            for edge in self.edges:
                if edge[0] < len(self.points) and edge[1] < len(self.points):
                    start, end = self.points[edge[0]], self.points[edge[1]]
                    Line(points=[start, end])
            for tag, point in zip(self.tags, self.points):
                value = TAG_COLOR_VALUE_MAP[tag]
                Color(self.hue, 1.0, value, mode='hsv')
                Ellipse(pos=(point[0] - POINT_RADIUS, point[1] - POINT_RADIUS), size=(2 * POINT_RADIUS, 2 * POINT_RADIUS))

    def get_data(self):
        return {'nodes': self.points, 'edges': self.edges, 'tags': self.tags}

class SkeletonAnnotator(Widget):

    def __init__(self):
        super().__init__()
        self.skeletons = []
        Window.bind(mouse_pos=self.mouse_pos)

    def on_touch_down(self, touch):

        position = (touch.x, touch.y)

        if touch.button in MOUSE_BUTTON_MAP:
            tag = MOUSE_BUTTON_MAP[touch.button]

            if self.can_stop():
                self.skeletons.append(Skeleton(position))
                self.add_widget(self.skeletons[-1])

            self.skeletons[-1].add_point(tag)

    def can_stop(self):
        return len(self.skeletons) == 0 or self.skeletons[-1].is_done()

    def mouse_pos(self, window, pos):
        position = (pos[0], pos[1])
        if len(self.skeletons) > 0:
            self.skeletons[-1].set_position(position)

    def get_data(self):
        return [skel.get_data() for skel in self.skeletons]

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

    AnnotationApp(images, start_index, save_function).run()
    