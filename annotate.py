import os
os.environ['KIVY_NO_ARGS'] = '1'

from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
Config.set('graphics', 'fullscreen', 'auto')

from kivy.core.window import Window
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, Ellipse, Line

from src import ImageAnnotator

from glob import glob
import json
import argparse
import numpy as np

ESCAPE_KEYCODE = 41
BACKSPACE_KEYCODE = 42
RIGHT_KEYCODE = 79
LEFT_KEYCODE = 80
UP_KEYCODE = 81
DOWN_KEYCODE = 82

MOUSE_BUTTON_MAP = {
    "left": "visible",
    "right": "occluded",
}

TAG_COLOR_VALUE_MAP = {
    "visible": 1.0,
    "occluded": 0.3,
}

def position_on_line(p, a, b):
    p, a, b = tuple(map(np.array, (p, a, b)))
    ap, ab = p - a, b - a
    abl = np.linalg.norm(ab)
    abu = ab / abl
    return tuple(a + abu * np.clip(np.dot(ap, abu), 0, abl))

class Skeleton():
    def __init__(self, position, tag, hue, node_radius) -> None:
        self.color_map = {k: (hue, 0.5, TAG_COLOR_VALUE_MAP[k]) for k in TAG_COLOR_VALUE_MAP}
        self.node_radius = 0.5 * node_radius
        self.node_size = (node_radius,  node_radius)
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
    
    def add_point(self, position, tag):
        if not self.is_interpolating:
            self.tags[self.current_node] = tag
            if not self.is_interpolating:
                self.nodes[self.current_node] = position
                self.nodes.append(self.nodes[self.current_node])
                if len(self.nodes) < 5:
                    self.tags.append(self.tags[self.base_node])
        else:
            self.nodes.append(position)
            if len(self.nodes) < 5:
                self.tags.append(self.tags[self.base_node])
        
    def finish(self):
        self.nodes = self.nodes[:-1]
        self.tags = self.tags[:len(self.nodes)]
        while len(self.nodes) < 4:
            self.nodes.append(None)
            self.tags.append("missing")
        
    def update_cursor_position(self, position):
        if self.is_interpolating:
            a = self.nodes[self.base_node]
            b = self.nodes[self.current_node]
            edge_index = self.edges.index((self.base_node, self.current_node))
            self.transitions[edge_index] = position_on_line(position, a, b)
        else:
            self.nodes[self.current_node] = position
        
    def draw(self):
        for (start, end), transition in zip(self.edges, self.transitions):
            if end >= len(self.nodes):
                break
            start_tag, end_tag = self.tags[start], self.tags[end]
            if start_tag != "missing" and end_tag != "missing":
                start_node, end_node = self.nodes[start], self.nodes[end]
                if transition != None:
                    Color(*self.color_map[start_tag], mode='hsv')
                    Line(points=[start_node, transition], width=0.5 * self.node_radius)
                    Color(*self.color_map[end_tag], mode='hsv')
                    Line(points=[transition, end_node], width=0.5 * self.node_radius)
                else:
                    Color(*self.color_map[start_tag], mode='hsv')
                    Line(points=[start_node, end_node], width=0.5 * self.node_radius)
        for node, tag in zip(self.nodes, self.tags):
            if tag != "missing":
                Color(*self.color_map[tag], mode='hsv')
                Ellipse(pos=(node[0] - self.node_radius, node[1] - self.node_radius), size=self.node_size)

    def set_data(self, data):
        self.nodes = data['nodes']
        self.tags = data['tags']
        self.edges = data['edges']
        self.transitions = data['transitions']
    
    def get_data(self):
        return {'nodes': self.nodes, 'tags': self.tags, 'edges': self.edges, 'transitions': self.transitions}
    
class SkeletonAnnotator(ImageAnnotator):
    def __init__(self, allow_editing):
        super().__init__()
        self.allow_editing = allow_editing
        self.skeletons = []
        self.current_skeleton = None
    
    @property
    def is_busy(self):
        return self.current_skeleton != None
    
    def on_cursor_moved(self, position):
        if self.current_skeleton != None:
            self.current_skeleton.update_cursor_position(position)
            self.draw()
    
    def on_click(self, position, button):
        if not self.allow_editing:
            return
        if self.current_skeleton == None:
            if button in MOUSE_BUTTON_MAP:
                hue = (1 + len(self.skeletons)) * 2 / 7.0
                self.current_skeleton = Skeleton(position, MOUSE_BUTTON_MAP[button], hue, 4.0)
        else:
            if button in MOUSE_BUTTON_MAP:
                self.current_skeleton.add_point(position, MOUSE_BUTTON_MAP[button])
            if (button == "middle" and self.current_skeleton.can_stop) or self.current_skeleton.must_stop:
                self.current_skeleton.finish()
                self.skeletons.append(self.current_skeleton)
                self.current_skeleton = None
        self.draw()
    
    def on_draw(self):
        for skeleton in self.skeletons:
            skeleton.draw()
        if self.current_skeleton != None:
            self.current_skeleton.draw()
    
    def delete_last(self):
        if not self.allow_editing:
            return
        elif self.current_skeleton != None:
            self.current_skeleton = None
        elif len(self.skeletons) > 0:
            self.skeletons = self.skeletons[:-1]
        self.draw()
    
    def set_data(self, data):
        for skeleton_data in data:
            hue = (1 + len(self.skeletons)) * 2 / 7.0
            skeleton = Skeleton((0, 0), "missing", hue, 4.0)
            skeleton.set_data(skeleton_data)
            self.skeletons.append(skeleton)
        self.draw()
    
    def get_data(self):
        return [skeleton.get_data() for skeleton in self.skeletons]
    
    def reset(self):
        self.skeletons = []
        self.current_skeleton = None


class AnnotationApp(App):

    def __init__(self, image_files, annotation_files, allow_editing):
        super().__init__()
        self.image_files = image_files
        self.annotation_files = annotation_files
        self.allow_editing = allow_editing
        self.index = 0
        
    def build(self):
        self.root = BoxLayout()
        self.annotator = SkeletonAnnotator(self.allow_editing)
        self.root.add_widget(self.annotator)
        Window.bind(on_key_down=self.key_down)
        Window.bind(on_request_close=self.on_request_close)
        return self.root
    
    def on_start(self):
        self.load()

    def key_down(self, instance, keyboard, keycode, text, modifiers):
        if self.allow_editing and keycode == BACKSPACE_KEYCODE:
            self.annotator.delete_last()
        elif not self.annotator.is_busy and keycode == LEFT_KEYCODE and self.index > 0:
            self.save()
            self.index -= 1
            self.load()
        elif not self.annotator.is_busy and keycode == RIGHT_KEYCODE and self.index < len(self.image_files) - 1:
            self.save()
            self.index += 1
            self.load()
            
    def on_request_close(self, *args, **kwargs):
        if self.annotator.is_busy:
            return True
        else:
            self.save()
            return False

    def load(self):
        self.annotator.set_image(self.image_files[self.index])
        self.annotator.reset()
        if os.path.exists(self.annotation_files[self.index]):
            with open(self.annotation_files[self.index], 'r') as file:
                data = json.load(file)
            self.annotator.set_data(data)
            
    def save(self):
        if self.allow_editing:
            data = self.annotator.get_data()
            with open(self.annotation_files[self.index], 'w') as file:
                json.dump(data, file)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--image-glob', required=True, type=str,
        help='glob pattern for finding images'
    )
    parser.add_argument(
        '--visualise-only', action="store_true",
        help='blocks annotation editing'
    )
    args = parser.parse_args()

    images = sorted(glob(args.image_glob, recursive=True))
        
    assert len(images) > 0, 'No images found!'

    annotations = [i.split(".")[0] + ".json" for i in images]

    AnnotationApp(images, annotations, not args.visualise_only).run()
    