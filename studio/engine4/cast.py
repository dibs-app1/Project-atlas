"""The cast and the scenery kit of engine 4: free CC0 models made by artists (mostly Quaternius, plus other
OpenGameArt CC0 authors, see studio/assets/CREDITS.md), each with its real-world size, its walking speed
(so the walk cycle matches the ground), colours where the file carries none, and its call.

AnimalModel is an engine-3 compatible model: actors, camera angles and sound treat it like any vehicle,
and the Blender bridge replaces it with the real animated model.
"""
import glob
import os
from pathlib import Path

import numpy as np

ASSETS = Path(__file__).resolve().parent.parent / "assets"
_FOUND = {}


def find(name):
    """Path of an asset file by its file name (searched once under studio/assets). Colour-only (untextured)
    versions from the Ultimate Nature Pack are preferred for scenery."""
    if name not in _FOUND:
        hits = sorted(glob.glob(str(ASSETS / "**" / name), recursive=True), key=lambda h: ("ultimate_nature" not in h, len(h)))
        if not hits:
            raise FileNotFoundError(name)
        _FOUND[name] = hits[0]
    return _FOUND[name]


# kind: file, length (m), height (m), walking speed for the walk clip (m/s), call, palette (colours by body share)
ANIMALS = {
    # farm
    "cow": dict(file="Cow.fbx", length=2.3, height=1.4, walk=1.0, call="moo"),
    "horse": dict(file="Horse.fbx", length=2.3, height=1.7, walk=1.4, run=5.0, call="neigh"),
    "pony": dict(file="Horse.fbx", length=1.6, height=1.2, walk=1.1, call="neigh", palette=[(236, 226, 206), (60, 50, 46)]),
    "pig": dict(file="Pig.fbx", length=1.3, height=0.75, walk=0.8, call="oink"),
    "piglet": dict(file="Pig.fbx", length=0.6, height=0.35, walk=0.6, call="oink"),
    "sheep": dict(file="Sheep.fbx", length=1.3, height=1.0, walk=0.8, call="baa"),
    "lamb": dict(file="Sheep.fbx", length=0.75, height=0.6, walk=0.6, call="baa"),
    "llama": dict(file="Llama.fbx", length=1.8, height=1.8, walk=1.0, call="none"),
    "goat": dict(file="goat_0.blend", length=1.2, height=0.9, walk=0.9, call="maa"),
    "chicken": dict(file="chickenV2.blend", length=0.45, height=0.45, walk=0.45, call="cluck",
                    eyes={"recolor": "Eyes", "add": True, "top": 0.24, "back": 0.45, "down": 0.42}),
    "rooster": dict(file="rooster.blend", length=0.55, height=0.6, walk=0.5, call="rooster", eyes={"recolor": "Eyes", "add": True},
                    palette=[(196, 84, 40), (40, 70, 60), (220, 40, 40), (250, 190, 60), (30, 30, 30)]),
    "chick": dict(file="Chick.fbx", length=0.16, height=0.16, walk=0.25, call="peep"),
    "duck": dict(file="duck6.blend", length=0.55, height=0.45, walk=0.4, call="quack", eyes={"top": 0.3, "back": 0.5, "down": 0.4}),
    "goose": dict(file="duck6.blend", length=0.85, height=0.75, walk=0.5, call="honk",
                  palette=[(246, 244, 238), (250, 150, 40), (20, 20, 20), (20, 20, 20), (250, 150, 40)],
                  eyes={"top": 0.3, "back": 0.5, "down": 0.4}),
    "duckling": dict(file="duckling1.blend", length=0.22, height=0.18, walk=0.3, call="peep", eyes={"top": 0.35, "back": 0.5, "down": 0.4}),
    "rabbit": dict(file="rabbit.blend", length=0.45, height=0.35, walk=1.0, call="none"),
    "penguin": dict(file="Pingouin-NEW.blend", length=0.45, height=0.7, walk=0.45, call="penguin", texture="Pingouin_Plane.010.png"),
    # pets
    "cat": dict(file="Cat.fbx", length=0.6, height=0.4, walk=0.6, call="meow"),
    "ginger_cat": dict(file="Cat.fbx", length=0.6, height=0.4, walk=0.6, call="meow",
                       palette=[(236, 140, 60), (250, 240, 226), (240, 160, 170)]),
    "black_cat": dict(file="Cat.fbx", length=0.6, height=0.4, walk=0.6, call="meow",
                      palette=[(44, 42, 48), (250, 246, 240), (240, 160, 170)]),
    "kitten": dict(file="Cat.fbx", length=0.32, height=0.22, walk=0.4, call="mew",
                   palette=[(250, 250, 246), (236, 150, 80), (240, 160, 170)]),
    "dog": dict(file="Dog.fbx", length=0.95, height=0.65, walk=1.1, call="woof"),
    "puppy": dict(file="Dog.fbx", length=0.5, height=0.35, walk=0.7, call="yip", palette=[(236, 214, 170)]),
    "black_dog": dict(file="Dog.fbx", length=0.95, height=0.65, walk=1.1, call="woof", palette=[(52, 48, 50)]),
    "pug": dict(file="Pug.fbx", length=0.55, height=0.4, walk=0.6, call="woof"),
    "butterfly": dict(file="butterfly.blend", length=0.12, height=0.05, walk=1.0, call="none", fly=True,
                      palette=[(250, 150, 40), (40, 36, 40), (250, 240, 220)]),
    # birds
    "eagle": dict(file="Eagle.fbx", length=0.9, height=0.3, walk=8.0, call="screech", fly=True),
    "songbird": dict(file="bird.fbx", length=0.22, height=0.2, walk=4.0, call="tweet", fly=True),
    "robin": dict(file="bird.fbx", length=0.22, height=0.2, walk=4.0, call="tweet", fly=True,
                  palette=[(150, 100, 70), (240, 120, 60)]),
    "seagull": dict(file="bird.fbx", length=0.5, height=0.4, walk=6.0, call="gull", fly=True,
                    palette=[(240, 242, 244), (250, 200, 60)]),
    "parrot": dict(file="bird.fbx", length=0.45, height=0.35, walk=5.0, call="squawk", fly=True,
                   palette=[(220, 40, 40), (250, 210, 60)]),
    "bluejay": dict(file="bird.fbx", length=0.28, height=0.24, walk=4.5, call="tweet", fly=True),
    "pigeon": dict(file="genuinely-my-pigeon-extended-furthur.blend", length=0.33, height=0.3, walk=0.4, call="coo",
                   palette=[(150, 156, 170), (120, 130, 140)]),
    # water
    "dolphin": dict(file="Dolphin.fbx", length=2.5, height=0.8, walk=3.0, call="dolphin", swim=True),
    "whale": dict(file="Whale.fbx", length=12.0, height=3.0, walk=3.0, call="whale", swim=True),
    "humpback": dict(file="whale_0.blend", length=13.0, height=3.0, walk=3.0, call="whale", swim=True),
    "manta": dict(file="Manta ray.fbx", length=3.0, height=0.6, walk=2.0, call="blub", swim=True),
    "tuna": dict(file="Fish1.fbx", length=0.5, height=0.15, walk=1.2, call="blub", swim=True),
    "bluetang": dict(file="Fish2.fbx", length=0.3, height=0.2, walk=0.9, call="blub", swim=True),
    "clownfish": dict(file="Fish3.fbx", length=0.22, height=0.12, walk=0.7, call="blub", swim=True),
    "goldfish": dict(file="scardinius.blend", length=0.25, height=0.1, walk=0.6, call="blub", swim=True,
                     palette=[(250, 150, 40), (250, 200, 80)]),
    "turtle": dict(file="Turtle.blend", length=1.1, height=0.35, walk=0.8, call="blub", swim=True,
                   palette=[(120, 150, 80), (150, 116, 70), (60, 50, 40)]),
    "crab": dict(file="crab.blend", length=0.35, height=0.15, walk=0.25, call="click_clack"),
}


# the coat each animal wears in the soft look: short fur, a mane and tail, curly wool or overlapping feathers
# (len in metres, density per square metre, tilt from the skin's normal in degrees, droop 0 = backwards, 1 = down)
FUR = dict(shape="fur", len=0.035, density=2600, tilt=70, droop=0.45)
COATS = {
    "cow": [dict(FUR, slots=[0, 1], len=0.02, density=4200, tilt=80, droop=0.4)],
    "horse": [dict(FUR, slots=[0], len=0.022, density=3000, tilt=78),
              dict(shape="hair", slots=[1], len=0.16, density=1600, tilt=82, droop=0.85, zmin=0.45, front_cut=0.16)],
    "goat": [dict(FUR, slots=[0], len=0.026, density=3600, tilt=80, droop=0.45)],
    "sheep": [dict(shape="wool", slots=[1], len=0.065, density=950, tilt=0, droop=0)],
    "lamb": [dict(shape="wool", slots=[1], len=0.036, density=2400, tilt=0, droop=0)],
    "chicken": [dict(shape="feather", slots=[0], len=0.055, density=2200, tilt=86, droop=0.2)],
    "rooster": [dict(shape="feather", slots=[0], len=0.06, density=2000, tilt=86, droop=0.2)],
    "chick": [dict(shape="wool", slots=[0], len=0.007, density=60000, tilt=0, droop=0)],
    "duck": [dict(shape="feather", slots=[0], len=0.04, density=2800, tilt=87, droop=0.1)],
    "duckling": [dict(shape="wool", slots=[0], len=0.007, density=60000, tilt=0, droop=0)],
}
COATS["pony"] = COATS["horse"]
COATS["goose"] = [dict(shape="feather", slots=[0], len=0.05, density=2400, tilt=87, droop=0.1)]


class Pose:
    """What an animal actor hands the renderer each frame (instead of meshes)."""
    def __init__(self, model, pos, yaw, pitch, roll, v, t, dist):
        self.model, self.pos, self.yaw, self.pitch, self.roll = model, np.asarray(pos, float), yaw, pitch, roll
        self.v, self.t, self.dist = v, t, dist
        self.mesh = None
        self.layer = 1


class AnimalModel:
    """An animal for engine-4 scenes. state: 'auto' (idle/walk/run from speed), or a clip-name hint via mood_fn(t)."""
    _n = 0

    def __init__(self, kind, mood_fn=None, scale=1.0):
        info = ANIMALS[kind]
        self.kind = kind
        self.name = kind
        self.info = info
        self.length = info["length"] * scale
        self.height = info["height"] * scale
        self.width = self.length * 0.4
        self.eye = np.array([self.length * 0.45, 0, self.height * 0.9])
        self.horn = np.array([self.length * 0.5, 0, self.height * 0.8])
        self.mood_fn = mood_fn
        self.parts = []
        self.uid = AnimalModel._n
        AnimalModel._n += 1

    def objs(self, pos, yaw=0.0, pitch=0.0, roll=0.0, dist=0.0, t=0.0, shadow=True, state=None):
        return [Pose(self, pos, yaw, pitch, roll, (state or {}).get("v", 0.0), t, dist)]


# scenery kit (file names); variants are picked by seed
KIT = {
    "tree": ["CommonTree_%d.fbx" % i for i in range(1, 6)],
    "tree_autumn": ["CommonTree_Autumn_%d.fbx" % i for i in range(1, 6)],
    "pine": ["PineTree_%d.fbx" % i for i in range(1, 6)],
    "pine_snow": ["PineTree_Snow_%d.fbx" % i for i in range(1, 6)],
    "birch": ["BirchTree_%d.fbx" % i for i in range(1, 6)],
    "willow": ["Willow_%d.fbx" % i for i in range(1, 6)],
    "palm": ["PalmTree_%d.fbx" % i for i in range(1, 5)],
    "bush": ["Bush_1.fbx", "Bush_2.fbx", "BushBerries_1.fbx", "BushBerries_2.fbx"],
    "bush_snow": ["Bush_Snow_1.fbx", "Bush_Snow_2.fbx"],
    "rock": ["Rock_%d.fbx" % i for i in range(1, 8)],
    "rock_moss": ["Rock_Moss_%d.fbx" % i for i in range(1, 8)],
    "rock_snow": ["Rock_Snow_%d.fbx" % i for i in range(1, 8)],
    "plant": ["Plant_%d.fbx" % i for i in range(1, 6)],
    "flowers": ["Flowers.fbx"],
    "grass": ["Grass.fbx", "Grass_Short.fbx"],
    "lilypad": ["Lilypad.fbx"],
    "corn": ["Corn_1.fbx", "Corn_2.fbx"],
    "wheat": ["Wheat_3.fbx"],
    "stump": ["TreeStump.fbx", "TreeStump_Moss.fbx"],
    "log": ["WoodLog.fbx", "WoodLog_Moss.fbx"],
    "cactus": ["Cactus_%d.fbx" % i for i in range(1, 6)],
}


# real-world size of each scenery kind: ("h", metres tall) or ("w", metres wide)
KIT_SIZE = {"tree": ("h", 8.0), "tree_autumn": ("h", 8.0), "pine": ("h", 11.0), "pine_snow": ("h", 10.0), "birch": ("h", 9.0),
            "willow": ("h", 8.0), "palm": ("h", 9.0), "bush": ("h", 1.3), "bush_snow": ("h", 1.2), "rock": ("h", 1.0),
            "rock_moss": ("h", 1.0), "rock_snow": ("h", 1.0), "plant": ("h", 0.9), "flowers": ("h", 0.45), "grass": ("h", 0.4),
            "lilypad": ("w", 0.9), "corn": ("h", 2.2), "wheat": ("h", 1.0), "stump": ("h", 0.6), "log": ("w", 2.2),
            "cactus": ("h", 2.0)}


def kit_file(kind, r):
    return find(r.choice(KIT[kind]))


def exists():
    return os.path.isdir(ASSETS)
