"""Batch 5: four animal videos (Birds, Dogs and Cats, Fish, Farm Animals), ten scenes each, rendered by engine 4.

Every scene: a real-photo sky (or the blue sea), a world dressed with artist-made trees, bushes, flowers,
grass and rocks, a hero animal (often with friends) that walks, stops, grazes, pecks, flies or swims with
its own animation, three camera angles at the animal's own scale that dissolve into each other, the
animal's footsteps / wing beats / splashes in 3D, and its call for the song's noise game.
"""
import math
import random

import numpy as np

from engine3 import world as Wd
from engine3.r3d import Mesh, Obj, box, cone, cylinder, sphere
from engine3.stage import Actor, scene, smoke
from engine4.cast import ANIMALS, AnimalModel

SKIES = {"day": "kloofendal_48d_partly_cloudy_puresky", "noon": "qwantani_noon_puresky", "morning": "qwantani_morning_puresky",
         "golden": "qwantani_late_afternoon_puresky", "dusk": "qwantani_dusk_2_puresky", "overcast": "kloofendal_overcast_puresky",
         "snow": "kloofendal_overcast_puresky", "sunrise": "qwantani_sunrise_puresky"}


# ------------------------------------------------------------------ helpers

def sky(st, fog=None):
    from engine4.cast import ASSETS
    name = SKIES.get(st.time, SKIES["day"])
    st.look = dict(hdri=str(ASSETS / "sky" / (name + ".hdr")), hdri_strength=1.0 if st.time != "dusk" else 1.3,
                   fog=fog or ((206, 220, 236), 900.0))
    st.props = getattr(st, "props", [])


def prop(st, kind, x, y, z=0.0, yaw=None, scale=1.0):
    st.props = getattr(st, "props", [])
    st.props.append((kind, (x, y, z), st.r.uniform(0, 6.283) if yaw is None else yaw, scale))


def scatter(st, kind, area, n, scale=(0.8, 1.2), avoid=None, seed=0):
    r = random.Random(st.seed * 7 + seed + len(kind))
    x0, x1, y0, y1 = area
    k = 0
    tries = 0
    while k < n and tries < n * 20:
        tries += 1
        x, y = r.uniform(x0, x1), r.uniform(y0, y1)
        if avoid and avoid(x, y):
            continue
        prop(st, kind, x, y, 0.0, r.uniform(0, 6.283), r.uniform(*scale))
        k += 1


def water_obj(objs):
    for o in objs:
        o.name = "water"
    return objs


def pond(cx, cy, rx, ry, color=(70, 130, 150), rim=(150, 140, 120), n=40):
    m = Mesh()
    ring = [(cx + rx * 1.08 * math.cos(2 * math.pi * i / n), cy + ry * 1.12 * math.sin(2 * math.pi * i / n), 0) for i in range(n)]
    m.poly(ring, rim)
    rim_o = Obj(m, layer=0, order=1, shadow=False)
    w = Mesh()
    w.poly([(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n), 0) for i in range(n)], color)
    wo = Obj(w, layer=0, order=2, shadow=False, name="water")
    return [rim_o, wo]


def path_strip(path, width, color, s0=None, s1=None, order=2):
    m = Mesh()
    Wd.strip(m, path, s0 or 0, s1 or path.length, -width / 2, width / 2, 0.0, color, step=2.0)
    return [Obj(m, layer=0, order=order, shadow=False)]


def near_path(path, d):
    P = path.P[::4]

    def fn(x, y):
        return bool(np.min((P[:, 0] - x) ** 2 + (P[:, 1] - y) ** 2) < d * d)
    return fn


def schedule(r, D, walk=(5, 9), stop=(3, 6), v=1.0, start_walking=True):
    """A speed profile: walk, stop (to eat / sniff / look), walk again, with gentle starts and stops."""
    segs, t, moving = [], 0.0, start_walking
    while t < D + 5:
        d = r.uniform(*(walk if moving else stop))
        segs.append((t, t + d, moving))
        t += d
        moving = not moving

    def sp(tt):
        for a, b, mv in segs:
            if a <= tt < b:
                if not mv:
                    return 0.0
                ramp = min(1.0, (tt - a) / 0.8, (b - tt) / 0.8)
                return v * max(0.0, ramp)
        return v
    return sp


def animal(st, kind, path, speed, s0=0.0, offset=0.0, z=0.0, mood=None, scale=1.0, sound=True, level=0.8, hero=False,
           alt_fn=None, pitch_fn=None, bob=0.0, bank=0.0, reverse=False, roll_fn=None):
    m = AnimalModel(kind, mood_fn=mood, scale=scale)
    v = speed if callable(speed) else (lambda t, sp=speed: sp)
    a = Actor(m, path, v, s0=s0, D=st.D, offset=offset, z=z, alt_fn=alt_fn, pitch_fn=pitch_fn, bob=bob, bank=bank, reverse=reverse)
    if roll_fn:
        base = a.state

        def state(t, base=base):
            pos, h, p, r, d, vv = base(t)
            return pos, h, p, r + roll_fn(t, vv), d, vv
        a.state = state
    st.actors.append(a)
    if sound:
        info = ANIMALS[kind]
        step = "wings" if info.get("fly") else ("swim" if info.get("swim") else
                                                ("hooves" if kind in ("cow", "horse", "pony", "goat", "sheep", "lamb", "llama")
                                                 else "paws"))
        st.sounds.append(dict(kind=step, src=a, level=level, call=info.get("call"), hero=hero, size=m.length))
    return a


def mid_s(path, D, speed_fn, frac=0.5):
    """Start distance so that the animal is near the middle of the path at the middle of the scene."""
    d = sum(speed_fn(i / 24) / 24 for i in range(int(D / 2 * 24)))
    return path.length * frac - d


def cams(a, names):
    """Camera angles at the animal's own scale."""
    L, Hh = a.model.length, a.model.height
    flying = a.state(1.0)[0][2] > 2.0
    out = []
    for nm in names:
        kw = {}
        if isinstance(nm, tuple):
            nm, kw = nm[0], dict(nm[1])
        base = {
            "side": dict(dist=L * 3.0 + 1.6, h=Hh * 0.7 + 0.25, look_h=Hh * 0.55, sway=0.05 * (L + 1)),
            "front": dict(off=L * 2.2 + 1.2, h=Hh * 0.6 + 0.1, look_h=Hh * 0.5),
            "low": dict(off=L * 1.8 + 0.8),
            "orbit": dict(radius=L * 2.8 + 1.4, h=Hh * 1.1 + 0.4, speed=0.1),
            "chase": dict(back=L * 3.2 + 1.2, h=Hh * 1.4 + 0.4, look_ahead=L * 2 + 1),
            "drone": dict(back=L * 5 + 4, h=L * 3 + 3),
            "top": dict(alt=L * 5 + 3),
        }[nm]
        base.update(kw)
        out.append((nm, base))
    return out


def hero(st, a, shots, noise=None):
    st.hero = a
    for snd in st.sounds:
        if snd["src"] is a:
            snd["hero"] = True
    st.shot_plan(cams(a, shots), overlays={})


def bench(m, x, y, yaw=0.0):
    from engine3.r3d import rot_z
    Rz = rot_z(yaw)
    for dz, sy, sz, dy in ((0.45, 0.45, 0.06, 0.0), (0.8, 0.06, 0.4, 0.22)):
        box(m, tuple(np.array([0, dy, dz]) @ Rz.T + (x, y, 0)), (1.6, sy, sz), (150, 104, 66), R=Rz)
    for dx in (-0.7, 0.7):
        box(m, tuple(np.array([dx, 0, 0.22]) @ Rz.T + (x, y, 0)), (0.08, 0.4, 0.44), (60, 60, 64), R=Rz)


# ------------------------------------------------------------------ worlds

def park(st, pond_at=(0, -32), plaza=False):
    sky(st)
    s = st.seed
    st.add(Wd.ground(s, (104, 156, 76), x0=-500, x1=500, y0=-400, y1=400, tile=25, var=6))
    path = Wd.Path([(x, 7 * math.sin(x / 38) + 2, 0) for x in np.arange(-260, 261, 20)], step=0.5)
    st.add(path_strip(path, 2.6, (206, 192, 160)))
    cx, cy = pond_at
    st.add(pond(cx, cy, 70, 20))
    m = Mesh()
    for k, x in enumerate(np.arange(-200, 201, 32)):
        xx, yy, _, hh = path.side(path.length / 2 + x, 3.0)
        bench(m, xx, yy, hh)
    if plaza:
        cylinder(m, (40, 22, 0.02), 14, 0.04, (168, 158, 146), axis="z", n=32)
        cylinder(m, (40, 22, 0.35), 3.2, 0.7, (200, 196, 190), axis="z", n=24)
        cylinder(m, (40, 22, 0.72), 2.9, 0.06, (110, 170, 200), axis="z", n=24)
        cylinder(m, (40, 22, 1.2), 0.35, 1.6, (200, 196, 190), axis="z", n=12)
    st.add([Obj(m, layer=1)])
    st.add(Wd.lamps(path, 20, path.length - 20, -3.2, every=36))
    avoid = lambda x, y: near_path(path, 6)(x, y) or ((x - cx) / 80) ** 2 + ((y - cy) / 26) ** 2 < 1 or (plaza and math.hypot(x - 40, y - 22) < 17)
    scatter(st, "tree", (-260, 260, 26, 120), 60, (0.9, 1.4), avoid, 1)
    scatter(st, "birch", (-260, 260, -140, -60), 30, (0.9, 1.3), avoid, 2)
    scatter(st, "willow", (cx - 90, cx + 90, cy - 34, cy + 34), 7, (1.0, 1.3), avoid, 3)
    scatter(st, "bush", (-200, 200, -50, 40), 70, (0.7, 1.2), avoid, 4)
    scatter(st, "flowers", (-150, 150, -12, 16), 120, (0.8, 1.3), avoid, 5)
    scatter(st, "grass", (-150, 150, -20, 20), 260, (0.25, 0.45), avoid, 6)
    scatter(st, "rock_moss", (cx - 80, cx + 80, cy - 26, cy + 26), 14, (0.4, 0.8),
            lambda x, y: ((x - cx) / 72) ** 2 + ((y - cy) / 21) ** 2 < 1, 7)
    scatter(st, "lilypad", (cx - 60, cx + 60, cy - 15, cy + 15), 26, (0.8, 1.4),
            lambda x, y: ((x - cx) / 66) ** 2 + ((y - cy) / 18) ** 2 > 1, 8)
    st.add(Wd.hills(s + 3, (98, 146, 80), 160, 700, height=50))
    st.add(Wd.street_houses(s + 4, Wd.straight(-600, 600, y=150), 40, 1160, off=0, gap=(18, 30)))
    return dict(path=path, pond=Wd.Path([(cx - 50, cy + 2, 0), (cx - 20, cy - 4, 0), (cx + 20, cy + 3, 0), (cx + 55, cy - 2, 0)], step=0.5),
                lawn=Wd.Path([(x, -10 + 3 * math.sin(x / 9), 0) for x in np.arange(-90, 91, 10)], step=0.5),
                air=Wd.Path([(x, 4 + 10 * math.sin(x / 50), 9 + 3 * math.sin(x / 23)) for x in np.arange(-300, 301, 25)], step=0.5),
                plaza=Wd.Path([(40 + 9 * math.cos(a), 22 + 9 * math.sin(a), 0) for a in np.linspace(0, 4 * math.pi, 40)], step=0.3))


def garden(st, snowy=False):
    sky(st)
    s = st.seed
    grass = (236, 240, 246) if snowy else (98, 158, 72)
    st.add(Wd.ground(s, grass, x0=-300, x1=300, y0=-300, y1=300, tile=20, var=4 if snowy else 7))
    if not snowy:   # mowing stripes
        m = Mesh()
        for k, y in enumerate(np.arange(-12, 14, 2.0)):
            c = (110, 172, 80) if k % 2 else (96, 152, 70)
            m.poly([(-40, y, 0), (40, y, 0), (40, y + 2, 0), (-40, y + 2, 0)], c)
        st.add([Obj(m, layer=0, order=1, shadow=False)])
    r = random.Random(s)
    m = Mesh()
    Wd.house(m, 0, 24, r, w=22, d=10, h=6.0, wall=(236, 226, 206), roof=(150, 70, 60), snow=snowy)
    for x in np.arange(-40, 40.1, 0.5):      # a low brick garden wall along the front (a cat can walk on it)
        pass
    box(m, (0, -13.2, 0.5), (80, 0.35, 1.0), (176, 100, 80))
    box(m, (0, -13.2, 1.03), (80.2, 0.42, 0.06), (200, 190, 180))
    box(m, (-28, 10, 1.2), (5, 4, 2.4), (130, 96, 70))           # shed
    for x in (-40, 40):
        box(m, (x, 6, 0.6), (0.3, 38, 1.2), (236, 232, 222))
    st.add([Obj(m, layer=1)])
    path = Wd.Path([(0, 18, 0), (1, 10, 0), (-1, 2, 0), (0, -6, 0)], step=0.4)
    st.add(path_strip(path, 1.4, (190, 180, 168) if not snowy else (226, 230, 236)))
    kind_tree = "pine_snow" if snowy else "tree"
    prop(st, kind_tree, 18, 6, scale=1.4)
    prop(st, kind_tree, -60, -40, scale=1.2)
    scatter(st, kind_tree, (-200, 200, -200, -30), 40, (1.0, 1.4), seed=1)
    scatter(st, kind_tree, (-200, 200, 40, 200), 40, (1.0, 1.4), seed=2)
    if not snowy:
        scatter(st, "flowers", (-38, 38, -12.6, -10.5), 70, (0.9, 1.4), seed=3)
        scatter(st, "flowers", (-38, -12, 12, 17), 30, (0.9, 1.3), seed=4)
        scatter(st, "bush", (-39, 39, 15, 18), 18, (0.8, 1.2), seed=5)
        scatter(st, "grass", (-38, 38, -10, 12), 60, (0.2, 0.35), lambda x, y: abs(x) < 3, 6)
    else:
        scatter(st, "bush_snow", (-39, 39, 14, 18), 16, (0.8, 1.2), seed=5)
    st.add(Wd.street_houses(s + 4, Wd.straight(-500, 500, y=-70), 40, 960, off=0, gap=(16, 26), snow=snowy))
    loop = Wd.Path([(9 * math.cos(a) - 6, 9 * math.sin(a) * 0.6, 0) for a in np.linspace(0, 6 * math.pi, 70)], step=0.3)
    return dict(lawn=Wd.Path([(x, -4 + 2.5 * math.sin(x / 6), 0) for x in np.arange(-38, 39, 4)], step=0.3), loop=loop,
                wall=Wd.straight(-38, 38, y=-13.2, z=1.06), path=path,
                air=Wd.Path([(x, -2 + 6 * math.sin(x / 14), 4 + 1.5 * math.sin(x / 7)) for x in np.arange(-60, 61, 6)], step=0.3))


def beach(st):
    sky(st, fog=((214, 226, 238), 1200.0))
    s = st.seed
    st.add(Wd.ground(s, (232, 214, 172), x0=-500, x1=500, y0=-14, y1=400, tile=25, var=5))
    st.add(water_obj(Wd.water(-14, -4000, color=(50, 140, 176))))
    m = Mesh()
    m.poly([(-6000, -14, 0.0), (6000, -14, 0.0), (6000, -9, 0.0), (-6000, -9, 0.0)], (206, 188, 150))
    st.add([Obj(m, layer=0, order=1, shadow=False)])
    st.dynamic.append(lambda t, cam: _foam(t))
    scatter(st, "palm", (-260, 260, 14, 60), 40, (1.0, 1.5), seed=1)
    scatter(st, "rock", (-260, 260, -12, 4), 26, (0.4, 1.0), seed=2)
    scatter(st, "bush", (-260, 260, 40, 90), 40, (0.8, 1.2), seed=3)
    st.add(Wd.hills(s + 3, (200, 190, 150), 120, 600, height=40))
    return dict(shore=Wd.Path([(x, -7 + 1.5 * math.sin(x / 20), 0) for x in np.arange(-260, 261, 20)], step=0.5),
                sand=Wd.Path([(x, 2 + 3 * math.sin(x / 30), 0) for x in np.arange(-260, 261, 20)], step=0.5),
                air=Wd.Path([(x, -12 + 6 * math.sin(x / 40), 10 + 3 * math.sin(x / 19)) for x in np.arange(-300, 301, 20)], step=0.5),
                sea=Wd.straight(-300, 300, y=-40))


_FOAM = {}


def _foam(t):
    m = Mesh()
    k = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 6.0)
    y0 = -14.5 + 3.0 * k
    for x in np.arange(-300, 300, 25):
        m.poly([(x, y0, 0.0), (x + 25, y0 + 0.3 * math.sin(x), 0.0), (x + 25, y0 + 0.9, 0.0), (x, y0 + 0.9, 0.0)], (246, 248, 250))
    o = Obj(m, layer=0, order=3, shadow=False)
    return [o]


def farmyard(st, mud=False):
    sky(st)
    s = st.seed
    st.add(Wd.ground(s, (110, 160, 74), x0=-500, x1=500, y0=-400, y1=400, tile=25, var=7))
    st.add(Wd.fields(s + 1, (-500, 500, 70, 260), [(196, 170, 90), (120, 160, 70), (210, 190, 110)]))
    track = Wd.Path([(x, 18 + 4 * math.sin(x / 60), 0) for x in np.arange(-300, 301, 20)], step=0.5)
    st.add(path_strip(track, 3.4, (170, 140, 104)))
    st.add(Wd.fence(Wd.straight(-200, 200, y=-24), 0, 400, 0, color=(150, 116, 84)))
    st.add(Wd.fence(Wd.straight(-200, 200, y=14), 0, 400, 0, color=(150, 116, 84)))
    m = Mesh()
    r = random.Random(s)
    Wd.barn(m, 40, 34, yaw=0.0)
    Wd.house(m, -30, 36, r, w=12, d=9, h=5, wall=(240, 232, 214), roof=(120, 60, 50))
    Wd.haybales(m, 10, 28, r, n=5)
    box(m, (-8, 8, 0.35), (2.4, 0.8, 0.7), (110, 90, 70))       # water trough
    box(m, (-8, 8, 0.66), (2.2, 0.6, 0.04), (90, 140, 170))
    st.add([Obj(m, layer=1)])
    if mud:
        mm = Mesh()
        mm.poly([(18 + 9 * math.cos(a), -8 + 5 * math.sin(a), 0) for a in np.linspace(0, 2 * math.pi, 30, endpoint=False)], (120, 92, 66))
        st.add([Obj(mm, layer=0, order=2, shadow=False)])
    st.add(pond(-60, -10, 16, 9))
    scatter(st, "tree", (-300, 300, -200, -40), 40, (1.0, 1.4), seed=1)
    scatter(st, "tree", (-300, 300, 50, 70), 14, (1.0, 1.4), seed=2)
    scatter(st, "bush", (-200, 200, -23, -20), 30, (0.7, 1.1), seed=3)
    scatter(st, "grass", (-120, 120, -22, 12), 220, (0.25, 0.45), lambda x, y: math.hypot(x + 60, (y + 10) * 1.7) < 19, 4)
    scatter(st, "flowers", (-120, 120, -22, 12), 60, (0.8, 1.2), lambda x, y: math.hypot(x + 60, (y + 10) * 1.7) < 19, 5)
    scatter(st, "lilypad", (-72, -48, -15, -5), 8, (0.8, 1.2), lambda x, y: ((x + 60) / 15) ** 2 + ((y + 10) / 8) ** 2 > 1, 6)
    scatter(st, "corn", (-200, -80, 72, 100), 60, (1.0, 1.3), seed=7)
    st.add(Wd.hills(s + 3, (100, 150, 84), 260, 900, height=90))
    st.add(Wd.hills(s + 4, (100, 150, 84), -220, -900, height=70))
    return dict(meadow=Wd.Path([(x, -6 + 5 * math.sin(x / 25), 0) for x in np.arange(-180, 181, 15)], step=0.5), track=track,
                yard=Wd.Path([(x, 6 + 2 * math.sin(x / 7), 0) for x in np.arange(-40, 61, 5)], step=0.3),
                mud=Wd.Path([(18 + 6 * math.cos(a), -8 + 3 * math.sin(a), 0) for a in np.linspace(0, 6 * math.pi, 50)], step=0.3),
                pond=Wd.Path([(-72 + 4 * k, -10 + 2 * math.sin(k), 0) for k in range(7)], step=0.3),
                air=Wd.Path([(x, -4 + 8 * math.sin(x / 40), 8) for x in np.arange(-300, 301, 25)], step=0.5))


def forest_lake(st):
    sky(st, fog=((200, 214, 228), 700.0))
    s = st.seed
    st.add(Wd.ground(s, (96, 140, 76), x0=-500, x1=500, y0=-10, y1=500, tile=25, var=7))
    st.add(water_obj(Wd.water(-10, -600, color=(60, 116, 140))))
    m = Mesh()
    m.poly([(-6000, -10, 0.0), (6000, -10, 0.0), (6000, -5, 0.0), (-6000, -5, 0.0)], (150, 146, 130))
    st.add([Obj(m, layer=0, order=1, shadow=False)])
    scatter(st, "pine", (-300, 300, 8, 160), 140, (1.0, 1.6), seed=1)
    scatter(st, "birch", (-300, 300, 0, 40), 30, (1.0, 1.4), seed=2)
    scatter(st, "rock_moss", (-200, 200, -9, 4), 30, (0.5, 1.2), seed=3)
    scatter(st, "log", (-150, 150, -3, 10), 10, (0.8, 1.2), seed=4)
    scatter(st, "grass", (-120, 120, -5, 8), 120, (0.25, 0.45), seed=5)
    st.add(Wd.mountains(s + 4, 14, 1200, 3600, hmin=500, hmax=1100, color=(110, 124, 120), snow=0.75))
    st.add(Wd.mountains(s + 5, 14, -1300, -3600, hmin=400, hmax=900, color=(110, 124, 120), snow=0.75))
    return dict(lake=Wd.straight(-300, 300, y=-40), shore=Wd.Path([(x, -2 + 2 * math.sin(x / 15), 0) for x in np.arange(-200, 201, 15)],
                                                                    step=0.5),
                air=Wd.Path([(x, -30 + 25 * math.sin(x / 90), 22 + 6 * math.sin(x / 40)) for x in np.arange(-400, 401, 25)], step=0.5))


def lagoon(st):
    sky(st, fog=((216, 230, 236), 900.0))
    s = st.seed
    st.add(Wd.ground(s, (84, 150, 70), x0=-500, x1=500, y0=-8, y1=500, tile=25, var=8))
    st.add(water_obj(Wd.water(-8, -500, color=(60, 170, 170))))
    m = Mesh()
    m.poly([(-6000, -8, 0.0), (6000, -8, 0.0), (6000, -3, 0.0), (-6000, -3, 0.0)], (228, 210, 160))
    st.add([Obj(m, layer=0, order=1, shadow=False)])
    scatter(st, "palm", (-300, 300, 0, 80), 90, (1.0, 1.6), seed=1)
    scatter(st, "plant", (-200, 200, -2, 30), 120, (1.0, 1.8), seed=2)
    scatter(st, "bush", (-200, 200, 0, 40), 60, (1.0, 1.5), seed=3)
    scatter(st, "flowers", (-150, 150, -2, 20), 90, (1.0, 1.4), seed=4)
    st.add(Wd.mountains(s + 4, 16, 900, 3000, hmin=300, hmax=800, color=(70, 120, 70), snow=2.0))
    return dict(air=Wd.Path([(x, 2 + 10 * math.sin(x / 35), 7 + 2.5 * math.sin(x / 17)) for x in np.arange(-300, 301, 20)], step=0.5),
                shore=Wd.Path([(x, -1 + 1.5 * math.sin(x / 15), 0) for x in np.arange(-200, 201, 15)], step=0.5))


def snowfield(st):
    sky(st, fog=((226, 232, 240), 500.0))
    s = st.seed
    st.add(Wd.ground(s, (238, 242, 248), x0=-500, x1=500, y0=-12, y1=500, tile=25, var=4))
    st.add(water_obj(Wd.water(-12, -600, color=(46, 90, 126))))
    m = Mesh()
    r = random.Random(s)
    for k in range(40):     # ice floes and icebergs
        x, y = r.uniform(-300, 300), r.uniform(-30, -300)
        w = r.uniform(4, 14)
        m.poly([(x + w * math.cos(a), y + w * 0.6 * math.sin(a), 0.05) for a in np.linspace(0, 2 * math.pi, 9, endpoint=False)],
               (240, 246, 252))
    for k in range(10):
        x, y = r.uniform(-500, 500), r.uniform(-200, -700)
        cone(m, (x, y, 0), r.uniform(12, 30), r.uniform(12, 40), (226, 238, 248), n=6)
    st.add([Obj(m, layer=1, shadow=False)])
    scatter(st, "rock_snow", (-200, 200, -10, 20), 30, (0.6, 1.4), seed=1)
    scatter(st, "pine_snow", (-300, 300, 60, 200), 40, (1.0, 1.4), seed=2)
    st.add(Wd.hills(s + 3, (236, 240, 248), 30, 500, height=60))
    return dict(ice=Wd.Path([(x, -4 + 2 * math.sin(x / 12), 0) for x in np.arange(-150, 151, 10)], step=0.4),
                sea=Wd.straight(-300, 300, y=-30))


def reef(st, kelp=False, deep=False, pond_style=False):
    """Under the water: sandy floor, coral, rocks, sea grass, light from above, and soft blue haze."""
    s = st.seed
    blue = (40, 120, 150) if not deep else (24, 70, 120)
    if pond_style:
        blue = (70, 120, 90)
    st.look = dict(underwater=((90, 180, 210), blue) if not pond_style else ((150, 190, 140), blue),
                   fog=(blue, 22.0 if not deep else 40.0))
    st.props = []
    sand = (214, 196, 150) if not pond_style else (120, 110, 80)
    st.add(Wd.ground(s, sand, x0=-200, x1=200, y0=-200, y1=200, tile=10, var=8, far=600))
    r = random.Random(s)
    m = Mesh()
    cols = [(240, 110, 120), (250, 160, 60), (170, 90, 200), (250, 220, 90), (90, 200, 180), (240, 90, 160)]
    for k in range(260 if not deep else 60):
        x, y = r.uniform(-120, 120), r.uniform(-25, 25)
        if abs(y) < 3.5 and not pond_style:
            continue
        c = r.choice(cols) if not pond_style else (70 + r.randint(0, 40), 110 + r.randint(0, 40), 60)
        kind = r.random()
        if pond_style:
            for j in range(4):
                h = r.uniform(0.8, 2.2)
                cylinder(m, (x + r.uniform(-.3, .3), y + r.uniform(-.3, .3), h / 2), 0.03, h, c, axis="z", n=4)
        elif kind < 0.4:     # bubble / branching coral: a cluster of round knobs
            for j in range(7):
                a = r.uniform(0, 6.28)
                d = r.uniform(0.0, 0.45)
                h = r.uniform(0.2, 0.9)
                sphere(m, (x + d * math.cos(a), y + d * math.sin(a), h), r.uniform(0.14, 0.28), c, n=8)
                cylinder(m, (x + d * math.cos(a), y + d * math.sin(a), h / 2), 0.08, h, c, axis="z", n=6)
        elif kind < 0.6:     # brain coral
            sphere(m, (x, y, 0.1), r.uniform(0.5, 1.0), c, n=12, scale=(1, 1, 0.6))
        elif kind < 0.7:     # sea anemone: soft tentacles in a ring
            for j in range(12):
                a = 2 * math.pi * j / 12
                cone(m, (x + 0.18 * math.cos(a), y + 0.18 * math.sin(a), 0.15), 0.06, r.uniform(0.35, 0.55), (250, 170, 200), n=5)
            cylinder(m, (x, y, 0.08), 0.3, 0.16, (200, 90, 140), axis="z", n=12)
        elif kind < 0.85:    # fan coral
            w = r.uniform(0.6, 1.2)
            a = r.uniform(0, 3.14)
            ca, sa = math.cos(a), math.sin(a)
            m.poly([(x - w * ca, y - w * sa, 0.1), (x + w * ca, y + w * sa, 0.1), (x + w * 0.7 * ca, y + w * 0.7 * sa, w * 1.3),
                    (x - w * 0.7 * ca, y - w * 0.7 * sa, w * 1.3)], c, flags=2)
        else:                # sea grass
            for j in range(6):
                h = r.uniform(0.6, 1.6)
                cylinder(m, (x + r.uniform(-.4, .4), y + r.uniform(-.4, .4), h / 2), 0.03, h, (70, 160, 90), axis="z", n=4)
    if kelp:
        for k in range(70):
            x, y = r.uniform(-100, 100), r.uniform(-30, 30)
            if abs(y) < 5:
                continue
            h = r.uniform(6, 12)
            cylinder(m, (x, y, h / 2), 0.08, h, (90, 140, 60), axis="z", n=5)
            for j in range(int(h / 0.8)):
                z = 0.6 + j * 0.8
                a = r.uniform(0, 6.28)
                m.poly([(x, y, z), (x + 0.6 * math.cos(a), y + 0.6 * math.sin(a), z + 0.3), (x + 0.5 * math.cos(a), y + 0.5 * math.sin(a), z + 0.6)],
                       (100, 156, 70), flags=2)
    st.add([Obj(m, layer=1, shadow=True)])
    if not pond_style:
        scatter(st, "rock_moss", (-120, 120, -30, 30), 60, (0.6, 1.8), lambda x, y: abs(y) < 5, 1)
    else:
        scatter(st, "rock", (-60, 60, -20, 20), 30, (0.5, 1.2), lambda x, y: abs(y) < 4, 1)
    sm = Mesh()      # the water's surface seen from below
    zs = 14.0 if not pond_style else 3.2
    for x in np.arange(-200, 200, 20):
        for y in np.arange(-200, 200, 20):
            sm.poly([(x, y, zs), (x, y + 20, zs), (x + 20, y + 20, zs), (x + 20, y, zs)], (170, 220, 236), flags=1 | 2)
    st.add([Obj(sm, layer=1, shadow=False)])
    st.overlays.append(_bubbles(s))
    st.overlays.append(_rays(s))
    return dict(swim=Wd.Path([(x, 1.5 * math.sin(x / 9), 0) for x in np.arange(-120, 121, 10)], step=0.4),
                high=Wd.Path([(x, 3 * math.sin(x / 15), 0) for x in np.arange(-200, 201, 20)], step=0.5),
                floor=Wd.Path([(x, 2 + 0.8 * math.sin(x / 4), 0) for x in np.arange(-60, 61, 4)], step=0.3), surface=zs)


def _bubbles(seed):
    r = random.Random(seed)
    B = [(r.uniform(0, 1920), r.uniform(0, 1080), r.uniform(30, 70), r.uniform(3, 9), r.uniform(0, 6)) for _ in range(70)]

    def draw(img, d, cam, t):
        from engine3.r3d import SS
        for x, y, sp, rr, ph in B:
            yy = (y - t * sp) % 1180 - 50
            xx = x + 8 * math.sin(t * 1.3 + ph)
            d.ellipse([(xx - rr) * SS, (yy - rr) * SS, (xx + rr) * SS, (yy + rr) * SS], outline=(230, 246, 255, 150), width=2 * SS)
            d.ellipse([(xx - rr * 0.4) * SS, (yy - rr * 0.6) * SS, (xx - rr * 0.1) * SS, (yy - rr * 0.3) * SS], fill=(255, 255, 255, 120))
    return draw


def _rays(seed):
    r = random.Random(seed)
    R_ = [(r.uniform(0, 1920), r.uniform(60, 180), r.uniform(0, 6)) for _ in range(6)]

    def draw(img, d, cam, t):
        from engine3.r3d import SS
        from PIL import Image as _I, ImageDraw as _D
        lay = _I.new("RGBA", (480, 270), (0, 0, 0, 0))
        dd = _D.Draw(lay)
        for x, w, ph in R_:
            xx = (x + 40 * math.sin(t * 0.2 + ph) - cam.yaw * 300) % 2200 - 140
            a = int(26 + 12 * math.sin(t * 0.5 + ph))
            dd.polygon([(xx / 4, 0), ((xx + w) / 4, 0), ((xx + w + 260) / 4, 270), ((xx + 260 - w) / 4, 270)], fill=(220, 246, 255, a))
        lay = lay.resize(img.size)
        img.paste(lay, (0, 0), lay)
    return draw


# ------------------------------------------------------------------ BIRDS

BIRD_SIZE = {"songbird": 2.4, "robin": 2.4, "bluejay": 2.2, "seagull": 1.6, "parrot": 1.7, "eagle": 1.8}


def _flyer(st, kind, path, v, s0, z=0.0, flap=True, scale=1.0, hero_=False, level=0.7, wobble=1.0):
    scale *= BIRD_SIZE.get(kind, 1.0)          # storybook-sized birds, so little viewers can see them well
    return animal(st, kind, path, v, s0=s0, z=z, scale=scale, hero=hero_, level=level, bank=0.6,
                  alt_fn=lambda t, w=wobble, p=random.random() * 6: 0.4 * w * math.sin(t * 0.9 + p))


@scene("ducks_pond")
def ducks_pond(st):
    ln = park(st)
    p = ln["pond"]
    sp = schedule(st.r, st.D, walk=(6, 10), stop=(3, 5), v=0.45)
    a = animal(st, "duck", p, sp, s0=mid_s(p, st.D, sp), z=-0.12, mood=lambda t: "Peck", hero=True)
    for k in range(4):
        animal(st, "duckling", p, sp, s0=mid_s(p, st.D, sp) - 0.7 - 0.45 * k, z=-0.05, offset=0.25 * (-1) ** k, level=0.3)
    animal(st, "duck", p, schedule(st.r, st.D, v=0.4), s0=mid_s(p, st.D, sp) + 5, offset=3.0, z=-0.12, level=0.4)
    hero(st, a, ["side", "front", "orbit"])


@scene("ducklings_parade")
def ducklings_parade(st):
    ln = park(st)
    lawn = ln["lawn"]
    sp = schedule(st.r, st.D, walk=(7, 12), stop=(2, 4), v=0.42)
    s0 = mid_s(lawn, st.D, sp)
    a = animal(st, "duck", lawn, sp, s0=s0, mood=lambda t: "Peck", hero=True)
    for k in range(5):
        animal(st, "duckling", lawn, sp, s0=s0 - 0.6 - 0.38 * k, offset=0.12 * (-1) ** k, level=0.3)
    hero(st, a, ["low", "side", "chase"])


@scene("songbirds_park")
def songbirds_park(st):
    ln = park(st)
    air = ln["air"]
    s0 = air.length / 2 - 4.0 * st.D / 2
    a = _flyer(st, "bluejay", air, 4.0, s0, hero_=True)
    _flyer(st, "robin", air, 4.0, s0 - 2.5, z=0.6, scale=0.9)
    _flyer(st, "songbird", air, 4.0, s0 - 5.0, z=-0.4)
    hero(st, a, [("side", {"dist": 2.6}), ("chase", {"back": 2.4, "h": 0.5}), ("orbit", {"radius": 2.8, "h": 0.4, "speed": 0.12})])


@scene("seagulls_beach")
def seagulls_beach(st):
    ln = beach(st)
    air = ln["air"]
    s0 = air.length / 2 - 6.0 * st.D / 2
    a = _flyer(st, "seagull", air, 6.0, s0, hero_=True)
    for k in range(3):
        _flyer(st, "seagull", air, 6.0, s0 - 4 - 3 * k, z=1 + k * 0.7, scale=0.9)
    hero(st, a, [("side", {"dist": 3.2}), ("orbit", {"radius": 3.4, "h": 0.6, "speed": 0.12}), ("side", {"side": 1, "dist": 3.6})])


@scene("parrots_jungle")
def parrots_jungle(st):
    ln = lagoon(st)
    air = ln["air"]
    s0 = air.length / 2 - 5.0 * st.D / 2
    a = _flyer(st, "parrot", air, 5.0, s0, hero_=True)
    _flyer(st, "parrot", air, 5.0, s0 - 3.0, z=0.8)
    hero(st, a, [("side", {"dist": 2.8}), ("orbit", {"radius": 3.0, "h": 0.6, "speed": 0.15}), ("chase", {"back": 2.6, "h": 0.5})])


@scene("eagle_lake")
def eagle_lake(st):
    ln = forest_lake(st)
    air = ln["air"]
    s0 = air.length / 2 - 8.0 * st.D / 2
    a = _flyer(st, "eagle", air, 8.0, s0, hero_=True)
    hero(st, a, [("side", {"dist": 4.5}), ("orbit", {"radius": 5, "h": 1.5, "speed": 0.1}), ("chase", {"back": 4, "h": 1.0})])


@scene("pigeons_plaza")
def pigeons_plaza(st):
    ln = park(st, plaza=True)
    pl = ln["plaza"]
    a = None
    for k in range(6):
        sp = schedule(random.Random(st.seed + k), st.D, walk=(2, 4), stop=(2, 4), v=0.35)
        b = animal(st, "pigeon", pl, sp, s0=10 + k * 4.5, offset=st.r.uniform(-2, 2), level=0.4, hero=k == 0)
        a = a or b
    hero(st, a, ["low", "side", "orbit"])


@scene("robin_snow")
def robin_snow(st):
    ln = garden(st, snowy=True)
    air = ln["air"]
    s0 = air.length / 2 - 3.5 * st.D / 2
    a = _flyer(st, "robin", air, 3.5, s0, hero_=True, wobble=0.6)
    _flyer(st, "robin", air, 3.5, s0 - 2.0, z=0.5, scale=0.9)
    hero(st, a, [("side", {"dist": 2.4}), ("chase", {"back": 2.2, "h": 0.4}), ("orbit", {"radius": 2.6, "h": 0.4})])


@scene("penguins_ice")
def penguins_ice(st):
    ln = snowfield(st)
    ice = ln["ice"]
    a = None
    for k in range(4):
        sp = schedule(random.Random(st.seed + k), st.D, walk=(6, 10), stop=(2, 3), v=0.45)
        b = animal(st, "penguin", ice, sp, s0=mid_s(ice, st.D, sp) - 1.6 * k, offset=0.6 * ((k % 3) - 1), scale=1.0 - 0.15 * (k > 1),
                   roll_fn=lambda t, v, p=k: 0.14 * math.sin(t * 5.5 + p) * min(1.0, v / 0.2),
                   level=0.5, hero=k == 0)
        a = a or b
    hero(st, a, ["side", "front", "orbit"])


@scene("birds_sunset")
def birds_sunset(st):
    ln = farmyard(st)
    air = ln["air"]
    s0 = air.length / 2 - 5.0 * st.D / 2
    a = None
    for k in range(7):
        b = _flyer(st, "songbird", air, 5.0, s0 - 1.6 * k, z=0.3 * (k % 3), scale=0.9 + 0.1 * (k % 2), hero_=k == 0,
                   level=0.4 if k else 0.7)
        a = a or b
    hero(st, a, [("side", {"dist": 4.5}), ("chase", {"back": 4, "h": 0.8}), ("orbit", {"radius": 5, "h": 1.0})])


# ------------------------------------------------------------------ DOGS AND CATS

@scene("dog_park_walk")
def dog_park_walk(st):
    ln = park(st)
    p = ln["path"]
    sp = schedule(st.r, st.D, walk=(8, 12), stop=(3, 5), v=1.2)
    a = animal(st, "dog", p, sp, s0=mid_s(p, st.D, sp), offset=0.3, mood=lambda t: "Idle", hero=True)
    hero(st, a, ["side", "front", "chase"])


@scene("puppy_butterfly")
def puppy_butterfly(st):
    ln = garden(st)
    lawn = ln["lawn"]
    sp = schedule(st.r, st.D, walk=(5, 8), stop=(2, 4), v=0.8)
    s0 = mid_s(lawn, st.D, sp)
    a = animal(st, "puppy", lawn, sp, s0=s0, hero=True)
    animal(st, "butterfly", lawn, sp, s0=s0 + 1.0, z=0.6, sound=False, alt_fn=lambda t: 0.25 * math.sin(t * 2.3))
    hero(st, a, ["low", "side", "orbit"])


@scene("ginger_cat_garden")
def ginger_cat_garden(st):
    ln = garden(st)
    p = ln["lawn"]
    sp = schedule(st.r, st.D, walk=(6, 9), stop=(3, 5), v=0.6)
    a = animal(st, "ginger_cat", p, sp, s0=mid_s(p, st.D, sp), offset=-6.0, hero=True)
    hero(st, a, ["side", "front", "orbit"])


@scene("kittens_play")
def kittens_play(st):
    ln = garden(st)
    loop = ln["loop"]
    sp = schedule(st.r, st.D, walk=(4, 7), stop=(2, 3), v=0.55)
    s0 = loop.length * 0.4
    a = animal(st, "kitten", loop, sp, s0=s0, hero=True)
    animal(st, "kitten", loop, sp, s0=s0 - 0.8, scale=0.95, level=0.4)
    hero(st, a, ["low", "orbit", "side"])


@scene("black_dog_beach")
def black_dog_beach(st):
    ln = beach(st)
    p = ln["shore"]
    sp = schedule(st.r, st.D, walk=(9, 14), stop=(2, 4), v=1.6)
    a = animal(st, "black_dog", p, sp, s0=mid_s(p, st.D, sp), hero=True)
    hero(st, a, ["side", "front", "drone"])


@scene("pug_and_puppy")
def pug_and_puppy(st):
    ln = park(st)
    p = ln["path"]
    sp = schedule(st.r, st.D, walk=(7, 11), stop=(3, 4), v=0.65)
    s0 = mid_s(p, st.D, sp)
    a = animal(st, "pug", p, sp, s0=s0, offset=0.4, hero=True)
    animal(st, "puppy", p, sp, s0=s0 - 0.9, offset=-0.4, level=0.5)
    hero(st, a, ["front", "side", "chase"])


@scene("cat_on_wall")
def cat_on_wall(st):
    ln = garden(st)
    w = ln["wall"]
    sp = schedule(st.r, st.D, walk=(8, 12), stop=(3, 5), v=0.5)
    a = animal(st, "black_cat", w, sp, s0=mid_s(w, st.D, sp), hero=True)
    hero(st, a, ["side", ("front", {"h": 1.4}), ("side", {"side": 1})])


@scene("dog_snow")
def dog_snow(st):
    ln = garden(st, snowy=True)
    p = ln["lawn"]
    sp = schedule(st.r, st.D, walk=(8, 12), stop=(2, 4), v=1.1)
    a = animal(st, "dog", p, sp, s0=mid_s(p, st.D, sp), hero=True)
    hero(st, a, ["side", "orbit", "front"])


@scene("cat_meadow_butterfly")
def cat_meadow_butterfly(st):
    ln = farmyard(st)
    p = ln["meadow"]
    sp = schedule(st.r, st.D, walk=(6, 9), stop=(4, 6), v=0.55)
    s0 = mid_s(p, st.D, sp)
    a = animal(st, "cat", p, sp, s0=s0, hero=True)
    animal(st, "butterfly", p, lambda t: 0.6, s0=s0 + 0.5, z=0.7, sound=False, offset=0.6,
           alt_fn=lambda t: 0.3 * math.sin(t * 2.1))
    hero(st, a, ["side", "low", "orbit"])


@scene("friends_sunset")
def friends_sunset(st):
    ln = park(st)
    p = ln["path"]
    sp = schedule(st.r, st.D, walk=(10, 16), stop=(2, 3), v=0.75)
    s0 = mid_s(p, st.D, sp)
    a = animal(st, "dog", p, sp, s0=s0, offset=0.5, hero=True)
    animal(st, "ginger_cat", p, sp, s0=s0 - 0.3, offset=-0.5, level=0.5)
    hero(st, a, ["side", "chase", ("side", {"side": 1})])


# ------------------------------------------------------------------ FISH

def _school(st, kind, path, v, s0, n, spread, z, r, scale=1.0):
    out = []
    for k in range(n):
        dz = r.uniform(-spread, spread) * 0.6
        out.append(animal(st, kind, path, v * r.uniform(0.95, 1.05), s0=s0 - r.uniform(0, spread * 2),
                          offset=r.uniform(-spread, spread), z=z + dz, scale=scale * r.uniform(0.85, 1.1), sound=False,
                          alt_fn=lambda t, p=r.uniform(0, 6): 0.15 * math.sin(t * 1.3 + p)))
    return out


@scene("reef_clownfish")
def reef_clownfish(st):
    ln = reef(st)
    p = ln["swim"]
    sp = schedule(st.r, st.D, walk=(6, 10), stop=(2, 3), v=0.5)
    a = animal(st, "clownfish", p, lambda t: max(0.15, sp(t)), s0=mid_s(p, st.D, sp), z=1.2, scale=1.6, hero=True,
               alt_fn=lambda t: 0.2 * math.sin(t * 0.8))
    animal(st, "clownfish", p, lambda t: max(0.15, sp(t)), s0=mid_s(p, st.D, sp) - 0.6, z=1.4, offset=0.3, scale=1.3, sound=False)
    hero(st, a, [("side", {"dist": 1.6}), ("orbit", {"radius": 1.8, "h": 0.3}), ("front", {"off": 1.4})])


@scene("reef_tangs")
def reef_tangs(st):
    ln = reef(st)
    p = ln["swim"]
    a = animal(st, "bluetang", p, 0.8, s0=p.length / 2 - 0.8 * st.D / 2, z=1.6, scale=1.5, hero=True,
               alt_fn=lambda t: 0.3 * math.sin(t * 0.7))
    _school(st, "bluetang", p, 0.8, p.length / 2 - 0.8 * st.D / 2 - 1, 4, 1.2, 1.8, random.Random(st.seed), 1.3)
    hero(st, a, [("side", {"dist": 2.4}), ("chase", {"back": 2.2, "h": 0.4}), ("orbit", {"radius": 2.6, "h": 0.5})])


@scene("fish_school")
def fish_school(st):
    ln = reef(st, deep=True)
    p = ln["high"]
    s0 = p.length / 2 - 1.4 * st.D / 2
    fish = _school(st, "tuna", p, 1.4, s0, 30, 2.5, 5.0, random.Random(st.seed))
    st.sounds.append(dict(kind="swim", src=fish[0], level=0.8, call="blub", hero=True, size=0.5))
    hero(st, fish[0], [("side", {"dist": 6}), ("chase", {"back": 5, "h": 1.0}), ("orbit", {"radius": 7, "h": 1.5})])


@scene("dolphins_play")
def dolphins_play(st):
    ln = reef(st, deep=True)
    p = ln["high"]
    s0 = p.length / 2 - 3.0 * st.D / 2
    a = animal(st, "dolphin", p, 3.0, s0=s0, z=6.0, hero=True, alt_fn=lambda t: 1.2 * math.sin(t * 0.5),
               pitch_fn=lambda t: 0.25 * math.cos(t * 0.5))
    animal(st, "dolphin", p, 3.0, s0=s0 - 3.5, z=7.0, offset=2.5, level=0.5, alt_fn=lambda t: 1.2 * math.sin(t * 0.5 + 1),
           pitch_fn=lambda t: 0.25 * math.cos(t * 0.5 + 1))
    hero(st, a, [("side", {"dist": 6}), ("chase", {"back": 6, "h": 1.0}), ("side", {"side": 1, "dist": 7})])


@scene("whale_song")
def whale_song(st):
    ln = reef(st, deep=True)
    p = ln["high"]
    a = animal(st, "humpback", p, 2.0, s0=p.length / 2 - 2.0 * st.D / 2, z=7.0, hero=True, alt_fn=lambda t: 0.6 * math.sin(t * 0.3))
    hero(st, a, [("side", {"dist": 26, "h": 1.0}), ("front", {"off": 22, "h": -1.0}), ("orbit", {"radius": 28, "h": 3})])


@scene("manta_glide")
def manta_glide(st):
    ln = reef(st)
    p = ln["high"]
    a = animal(st, "manta", p, 1.5, s0=p.length / 2 - 1.5 * st.D / 2, z=4.0, hero=True, alt_fn=lambda t: 0.5 * math.sin(t * 0.4))
    hero(st, a, [("side", {"dist": 5}), ("low", {"off": 4}), ("orbit", {"radius": 6, "h": 2})])


@scene("turtle_swim")
def turtle_swim(st):
    ln = reef(st)
    p = ln["swim"]
    a = animal(st, "turtle", p, 0.7, s0=p.length / 2 - 0.7 * st.D / 2, z=2.0, hero=True, alt_fn=lambda t: 0.4 * math.sin(t * 0.35))
    hero(st, a, [("side", {"dist": 3.2}), ("front", {"off": 3}), ("orbit", {"radius": 3.6, "h": 0.8})])


@scene("crab_sand")
def crab_sand(st):
    ln = reef(st)
    p = ln["floor"]
    sp = schedule(st.r, st.D, walk=(4, 6), stop=(2, 4), v=0.25)
    a = animal(st, "crab", p, sp, s0=mid_s(p, st.D, sp), hero=True)
    animal(st, "crab", p, sp, s0=mid_s(p, st.D, sp) - 0.8, offset=0.5, scale=0.8, level=0.4)
    hero(st, a, [("low", {"off": 1.2}), ("side", {"dist": 1.4, "h": 0.4}), ("orbit", {"radius": 1.6, "h": 0.6})])


@scene("goldfish_pond")
def goldfish_pond(st):
    ln = reef(st, pond_style=True)
    p = ln["swim"]
    a = animal(st, "goldfish", p, 0.6, s0=p.length / 2 - 0.6 * st.D / 2, z=1.2, scale=1.6, hero=True,
               alt_fn=lambda t: 0.2 * math.sin(t * 0.9))
    _school(st, "goldfish", p, 0.6, p.length / 2 - 0.6 * st.D / 2 - 0.8, 4, 0.8, 1.3, random.Random(st.seed), 1.3)
    hero(st, a, [("side", {"dist": 1.8}), ("orbit", {"radius": 2.0, "h": 0.4}), ("chase", {"back": 1.8, "h": 0.3})])


@scene("reef_parade")
def reef_parade(st):
    ln = reef(st, kelp=True)
    p = ln["swim"]
    r = random.Random(st.seed)
    s0 = p.length / 2 - 0.8 * st.D / 2
    a = animal(st, "bluetang", p, 0.8, s0=s0, z=1.6, scale=1.5, hero=True)
    _school(st, "clownfish", p, 0.8, s0 - 1, 4, 1.0, 1.4, r, 1.4)
    _school(st, "goldfish", p, 0.8, s0 + 2, 3, 1.0, 2.0, r, 1.2)
    hero(st, a, [("side", {"dist": 2.6}), ("orbit", {"radius": 3, "h": 0.6}), ("chase", {"back": 2.6, "h": 0.5})])


# ------------------------------------------------------------------ FARM ANIMALS

def _graze(t):
    return "Eat|Eating|eat|Idle"


@scene("cows_meadow")
def cows_meadow(st):
    ln = farmyard(st)
    p = ln["meadow"]
    sp = schedule(st.r, st.D, walk=(6, 9), stop=(5, 8), v=0.9)
    a = animal(st, "cow", p, sp, s0=mid_s(p, st.D, sp), mood=_graze, hero=True)
    animal(st, "cow", p, schedule(random.Random(st.seed + 1), st.D, v=0.8), s0=mid_s(p, st.D, sp) - 5, offset=3.5, mood=_graze, level=0.5)
    hero(st, a, ["side", "front", "orbit"])


@scene("horse_pony")
def horse_pony(st):
    ln = farmyard(st)
    p = ln["meadow"]
    sp = schedule(st.r, st.D, walk=(8, 12), stop=(3, 5), v=1.3)
    s0 = mid_s(p, st.D, sp)
    a = animal(st, "horse", p, sp, s0=s0, hero=True)
    animal(st, "pony", p, sp, s0=s0 - 1.8, offset=1.4, level=0.5)
    hero(st, a, ["side", "front", "drone"])


@scene("pigs_mud")
def pigs_mud(st):
    ln = farmyard(st, mud=True)
    p = ln["mud"]
    sp = schedule(st.r, st.D, walk=(4, 7), stop=(3, 5), v=0.6)
    a = animal(st, "pig", p, sp, s0=6, hero=True)
    for k in range(3):
        animal(st, "piglet", p, sp, s0=6 - 0.9 - 0.6 * k, offset=0.3 * (-1) ** k, level=0.35)
    hero(st, a, ["low", "side", "orbit"])


@scene("sheep_lambs")
def sheep_lambs(st):
    ln = farmyard(st)
    p = ln["meadow"]
    sp = schedule(st.r, st.D, walk=(5, 8), stop=(4, 6), v=0.7)
    s0 = mid_s(p, st.D, sp)
    a = animal(st, "sheep", p, sp, s0=s0, mood=_graze, hero=True)
    for k in range(4):
        animal(st, "lamb" if k % 2 else "sheep", p, sp, s0=s0 - 1.5 - 1.3 * k, offset=1.2 * ((k % 3) - 1), mood=_graze, level=0.4)
    hero(st, a, ["side", "orbit", "front"])


@scene("goats_hill")
def goats_hill(st):
    ln = farmyard(st)
    p = ln["meadow"]
    sp = schedule(st.r, st.D, walk=(5, 8), stop=(3, 5), v=0.8)
    s0 = mid_s(p, st.D, sp)
    a = animal(st, "goat", p, sp, s0=s0, mood=lambda t: "eat|idle", hero=True)
    animal(st, "goat", p, sp, s0=s0 - 1.6, offset=1.0, scale=0.75, mood=lambda t: "eat|idle", level=0.4)
    for k in range(6):
        prop(st, "rock", p.pose(s0 + 4 + 5 * k)[0], p.pose(s0 + 4 + 5 * k)[1] + 5, scale=1.2)
    hero(st, a, ["side", "front", "orbit"])


@scene("hens_yard")
def hens_yard(st):
    ln = farmyard(st)
    p = ln["yard"]
    a = None
    for k in range(4):
        sp = schedule(random.Random(st.seed + k), st.D, walk=(3, 5), stop=(3, 5), v=0.4)
        b = animal(st, "chicken", p, sp, s0=p.length / 2 - 3 + 1.4 * k, offset=0.8 * ((k % 3) - 1), mood=lambda t: "Pecking|Eating",
                   hero=k == 0, level=0.6 if k == 0 else 0.35)
        a = a or b
    hero(st, a, ["low", "side", "orbit"])


@scene("rooster_morning")
def rooster_morning(st):
    ln = farmyard(st)
    p = ln["track"]
    sp = schedule(st.r, st.D, walk=(5, 7), stop=(4, 6), v=0.5)
    a = animal(st, "rooster", p, sp, s0=mid_s(p, st.D, sp), mood=lambda t: "Pecking", hero=True)
    hero(st, a, ["low", "side", "front"])


@scene("chicks_follow")
def chicks_follow(st):
    ln = farmyard(st)
    p = ln["yard"]
    sp = schedule(st.r, st.D, walk=(5, 8), stop=(3, 4), v=0.35)
    s0 = p.length / 2 - 4
    a = animal(st, "chicken", p, sp, s0=s0, mood=lambda t: "Pecking|Eating", hero=True)
    for k in range(5):
        animal(st, "chick", p, sp, s0=s0 - 0.5 - 0.25 * k, offset=0.15 * (-1) ** k, level=0.3)
    hero(st, a, ["low", "chase", "side"])


@scene("ducks_farm_pond")
def ducks_farm_pond(st):
    ln = farmyard(st)
    p = ln["pond"]
    sp = schedule(st.r, st.D, walk=(6, 9), stop=(3, 4), v=0.35)
    s0 = 4
    a = animal(st, "duck", p, sp, s0=s0, z=-0.12, mood=lambda t: "Peck", hero=True)
    animal(st, "duck", p, sp, s0=s0 - 1.2, z=-0.12, offset=0.8, level=0.4)
    hero(st, a, ["side", "front", "orbit"])


@scene("barn_sunset")
def barn_sunset(st):
    ln = farmyard(st)
    p = ln["track"]
    sp = schedule(st.r, st.D, walk=(12, 18), stop=(2, 3), v=0.9)
    s0 = mid_s(p, st.D, sp)
    a = animal(st, "cow", p, sp, s0=s0, hero=True)
    animal(st, "sheep", p, sp, s0=s0 - 3.0, offset=0.6, level=0.4)
    animal(st, "pig", p, sp, s0=s0 - 5.0, offset=-0.5, level=0.4)
    animal(st, "goat", p, sp, s0=s0 - 7.0, offset=0.4, level=0.4)
    hero(st, a, ["side", "drone", "chase"])
