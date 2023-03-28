import os
os.environ['KIVY_NO_ARGS'] = '1'
# os.environ['KIVY_NO_CONSOLELOG'] = '1'

from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
Config.set('graphics', 'fullscreen', 'auto')

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.image import AsyncImage
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Ellipse, Line
from kivy.core.window import Window
from kivy import clock

from random import random
from glob import glob
import json
import argparse
import numpy as np
import math

ESCAPE_KEYCODE = 41
BACKSPACE_KEYCODE = 42
RIGHT_KEYCODE = 79
LEFT_KEYCODE = 80

MOUSE_BUTTON_MAP = {
    "left": "visible",
    "right": "occluded",
}

TAG_COLOR_VALUE_MAP = {
    "visible": 1.0,
    "occluded": 0.6,
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

    def __init__(self, position, tag, node_radius, hue):
        super().__init__()
        self.node_radius = node_radius
        self.color_map = {k: (hue, 0.5, TAG_COLOR_VALUE_MAP[k]) for k in TAG_COLOR_VALUE_MAP}
        self.nodes = [position, position]
        self.tags = [tag, tag]
        self.edges = [(0, 1), (1, 2), (1, 3)]
        self.transitions = [None, None, None]
        
    @property
    def current_node(self):
        return len(self.nodes)-1
    
    @property
    def base_node(self):
        index = [e[1] for e in self.edges].index(self.current_node)
        return self.edges[index][0]
    
    @property
    def is_interpolating(self):
        return self.tags[self.base_node] != self.tags[self.current_node]
        
    @property
    def must_stop(self):
        return len(self.nodes) == 5
    
    @property
    def can_stop(self):
        return self.current_node > 1 and not self.is_interpolating
    
    def set_point(self, tag):
        if not self.is_interpolating:
            self.tags[self.current_node] = tag
            if not self.is_interpolating:
                self.nodes.append(self.nodes[self.current_node])
                if len(self.nodes) < 5:
                    self.tags.append(self.tags[self.base_node])
        else:
            self.nodes.append(self.nodes[self.current_node])
            if len(self.nodes) < 5:
                self.tags.append(self.tags[self.base_node])
        self.draw()
    
    def finish(self):
        self.nodes = self.nodes[:-1]
        while len(self.nodes) < 4:
            self.nodes.append((0.0, 0.0))
            self.tags.append("missing")
        self.draw()

    def set_position(self, position):
        if self.is_interpolating:
            a = self.nodes[self.base_node]
            b = self.nodes[self.current_node]
            edge_index = self.edges.index((self.base_node, self.current_node))
            self.transitions[edge_index] = position_on_line(position, a, b)
        else:
            self.nodes[self.current_node] = position
        self.draw()
        
    def get_data(self):
        return {'nodes': self.nodes, 'tags': self.tags, 'edges': self.edges, 'transitions': self.transitions}
    
    def set_data(self, data):
        self.nodes = data['nodes']
        self.tags = data['tags']
        self.edges = data['edges']
        self.transitions = data['transitions']
        self.draw()
        
    def draw(self):
        self.canvas.clear()
        with self.canvas:
            for (start, end), transition in zip(self.edges, self.transitions):
                if start < len(self.nodes) and end < len(self.nodes):
                    start_node, end_node = self.nodes[start], self.nodes[end]
                    start_tag, end_tag = self.tags[start], self.tags[end]
                    if start_tag != "missing" and end_tag != "missing":
                        if transition != None:
                            Color(*self.color_map[start_tag], mode='hsv')
                            Line(points=[start_node, transition], width=self.node_radius/2.5)
                            Color(*self.color_map[end_tag], mode='hsv')
                            Line(points=[transition, end_node], width=self.node_radius/2.5)
                        else:
                            Color(*self.color_map[start_tag], mode='hsv')
                            Line(points=[start_node, end_node], width=self.node_radius/2.5)
            for node, tag in zip(self.nodes, self.tags):
                if tag != "missing":
                    Color(*self.color_map[tag], mode='hsv')
                    Ellipse(pos=(node[0] - self.node_radius, node[1] - self.node_radius), size=(2 * self.node_radius, 2 * self.node_radius))

   

class SkeletonAnnotator(Widget):

    def __init__(self, node_size):
        super().__init__()
        Window.bind(mouse_pos=self.mouse_pos)
        self.node_size = node_size
        self.skeletons = []
        self.current_skeleton = None
        self.waiting = False

    @property
    def is_busy(self):
        return self.current_skeleton != None
    
    def get_hue(self):
        i = len(self.skeletons)
        return i * 2 / 7.0

    def on_touch_down(self, touch):
        
        if self.waiting:
            return
        
        position = (touch.x, touch.y)
        
        if touch.button in MOUSE_BUTTON_MAP:
            tag = MOUSE_BUTTON_MAP[touch.button]
            if self.current_skeleton == None:
                self.current_skeleton = Skeleton(position, tag, self.node_size, self.get_hue())
                self.add_widget(self.current_skeleton)
            else:
                self.current_skeleton.set_point(tag)
            
        if self.current_skeleton.must_stop or touch.button == "middle" and self.current_skeleton.can_stop:
            self.current_skeleton.finish()
            self.skeletons.append(self.current_skeleton)
            self.current_skeleton = None

    def mouse_pos(self, window, pos):
        if self.current_skeleton != None:
            self.current_skeleton.set_position((pos[0], pos[1]))

    def set_data(self, data):
        for skel in data:
            skeleton = Skeleton((0, 0), "missing", self.node_size, self.get_hue())
            skeleton.set_data(skel)
            self.add_widget(skeleton)
            self.skeletons.append(skeleton)

    def get_data(self):
        return [skel.get_data() for skel in self.skeletons]

    def delete_last(self):
        if len(self.skeletons) > 0:
            self.remove_widget(self.skeletons[-1])
            self.skeletons = self.skeletons[:-1]
        
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
        root = BoxLayout(padding=4*[100,])
        self.image_display = AsyncImage(allow_stretch=True)
        root.add_widget(self.image_display)
        self.annotator = SkeletonAnnotator(3.0)
        self.image_display.add_widget(self.annotator)
        Window.bind(on_key_down=self.key_down)
        self.image_display.source = self.image_files[self.index]
        return root
    
    def on_start(self):
        self.load()

    def key_down(self, instance, keyboard, keycode, text, modifiers):
        if keycode == BACKSPACE_KEYCODE:
            self.annotator.delete_last()
        elif not self.annotator.is_busy and keycode == LEFT_KEYCODE and self.index > 0:
            self.save()
            self.index -= 1
            self.load()
        elif not self.annotator.is_busy and keycode == RIGHT_KEYCODE and self.index < len(self.image_files) - 1:
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
            skel['nodes'] = [pos if pos == None else self.image_to_gui(pos) for pos in skel['nodes']]
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
        y = self.image_display.texture.size[1] - (point[1] - y_shift) * y_scale
        return [x, y]
        
    def image_to_gui(self, point):
        x_shift = self.image_display.pos[0] + int((self.image_display.size[0] - self.image_display.norm_image_size[0]) / 2)
        y_shift = self.image_display.pos[1] + int((self.image_display.size[1] - self.image_display.norm_image_size[1]) / 2)
        x_scale = self.image_display.texture.size[0] / self.image_display.norm_image_size[0]
        y_scale = self.image_display.texture.size[1] / self.image_display.norm_image_size[1]
        x = (point[0] / x_scale) + x_shift
        y = ((self.image_display.texture.size[1] - point[1]) / y_scale) + y_shift
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
    