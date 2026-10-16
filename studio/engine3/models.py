"""Low-poly 3D vehicles for engine 3, built to scale (metres) with correct anatomy.

Every model faces +x (its front), with y to its left and z up; the origin is on the ground under
the middle. Moving parts (wheels, propellers, rotors, paddles) are separate small meshes that spin.
Trains are assembled engine-first: the locomotive leads (+x) and the cars trail behind it.
"""
import math
import random

import numpy as np

from . import r3d as R
from .r3d import Mesh, cone, cylinder, extrude, sphere, wedge_wing


def box(*a, **k):
    k.setdefault("outward", True)
    return R.box(*a, **k)

GLASS = (120, 160, 190)
GLASS_DARK = (70, 96, 120)
TYRE = (34, 34, 38)
RIM = (180, 184, 192)
CHROME = (200, 204, 212)
DARK = (52, 54, 60)
HEAD = (255, 248, 220)
TAIL = (210, 40, 36)
WHITE = (238, 238, 234)
PAL = {
    "red": (196, 46, 40), "blue": (40, 90, 180), "yellow": (240, 190, 40), "green": (52, 140, 70),
    "orange": (232, 120, 40), "white": (236, 236, 232), "silver": (176, 182, 190), "black": (40, 42, 48),
    "teal": (30, 140, 140), "purple": (110, 70, 160), "navy": (36, 50, 96), "cream": (236, 226, 196),
    "brown": (120, 80, 50), "pink": (230, 130, 160), "grey": (120, 124, 132),
}


def col(c):
    return PAL.get(c, c) if isinstance(c, str) else tuple(c)


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def loft(m, sections, color, n=10, cap0=True, cap1=True, colors=None):
    """A smooth tube along x through sections [(x, half_width, half_height, z_centre), ...]."""
    rings = []
    for x, ry, rz, zc in sections:
        rings.append([(x, ry * math.cos(2 * math.pi * i / n), zc + rz * math.sin(2 * math.pi * i / n)) for i in range(n)])
    k0 = len(m.f)
    for s in range(len(rings) - 1):
        a, b = rings[s], rings[s + 1]
        for i in range(n):
            j = (i + 1) % n
            c = colors(s, i) if colors else color
            m.poly([a[i], b[i], b[j], a[j]], c)
    if cap0 and sections[0][1] > 1e-3:
        m.poly(rings[0], color)
    if cap1 and sections[-1][1] > 1e-3:
        m.poly(rings[-1][::-1], color)
    # orient outward from the local axis
    V = m.v
    for k in range(k0, len(m.f)):
        f = m.f[k]
        P = np.array([V[i] for i in f])
        cen = P.mean(axis=0)
        xs = [s[0] for s in sections]
        zc = np.interp(cen[0], xs, [s[3] for s in sections]) if xs[0] < xs[-1] else sections[0][3]
        axis_pt = np.array([cen[0], 0.0, zc])
        nrm = np.cross(P[1] - P[0], P[2] - P[0])
        out = cen - axis_pt
        if np.linalg.norm(out) < 1e-6:     # end caps: point along x away from the middle
            out = np.array([cen[0] - np.mean(xs), 0, 0])
        if np.dot(nrm, out) < 0:
            m.f[k] = tuple(reversed(f))
    m._done = False
    return m


def fin(m, root_x, root_len, tip_x, tip_len, height, z0, thick, color, y=0.0):
    """A vertical fin/stabiliser in the x-z plane (leading edge at root_x / tip_x)."""
    prof = [(root_x, z0), (root_x - root_len, z0), (tip_x - tip_len, z0 + height), (tip_x, z0 + height)]
    return extrude(m, prof, y - thick / 2, y + thick / 2, color)


class Part:
    """A moving part: mesh at a local position, turning about a local axis.
    kind: wheel (turns with distance), prop (spins with time), fixed, or fn (angle = fn(t, dist, speed))."""

    def __init__(self, mesh, at, axis="y", kind="wheel", radius=0.35, speed=0.0, fn=None, parent=None):
        self.mesh = mesh.finalize()
        self.at = np.asarray(at, float)
        self.axis, self.kind, self.radius, self.speed = axis, kind, radius, speed
        self.fn = fn
        self.parent = parent      # index of another part this one is attached to (e.g. a lower leg)


class Model:
    def __init__(self, name, length, width, height):
        self.name = name
        self.body = Mesh()
        self.parts = []
        self.length, self.width, self.height = length, width, height
        self.lights = []        # local points of headlights (for night glow)
        self.horn = np.array([length / 2, 0, height * 0.6])   # where its sound comes from
        self.eye = np.array([0.2, 0.35, 1.2])                  # driver's / pilot's eye (cockpit view)
        self.trailers = []      # (Model, gap) for trains and trucks with trailers

    def objs(self, pos, yaw=0.0, pitch=0.0, roll=0.0, dist=0.0, t=0.0, shadow=True, state=None):
        Rm = R.ypr(yaw, pitch, roll)
        pos = np.asarray(pos, float)
        v = (state or {}).get("v", 0.0)
        out = [R.Obj(self.body, pos, Rm, shadow=shadow, name=self.name)]
        frames = []
        for p in self.parts:
            if p.kind == "wheel":
                ang = dist / max(0.05, p.radius)
            elif p.kind == "fixed":
                ang = 0.0
            elif p.kind == "fn":
                ang = p.fn(t, dist, v)
            else:
                ang = t * p.speed
            if p.axis == "y":
                Rl = R.rot_y(ang)
            elif p.axis == "x":
                Rl = R.rot_x(ang)
            else:
                Rl = R.rot_z(ang)
            if p.parent is not None:          # attached to another moving part
                ppos, pR = frames[p.parent]
                wpos, wR = ppos + pR @ p.at, pR @ Rl
            else:
                wpos, wR = pos + Rm @ p.at, Rm @ Rl
            frames.append((wpos, wR))
            out.append(R.Obj(p.mesh, wpos, wR, shadow=p.kind == "fn" and self.body_shadow_parts))
        return out

    body_shadow_parts = False


def wheel_mesh(r, w, spokes=5, rim=RIM, tyre=TYRE):
    m = Mesh()
    cylinder(m, (0, 0, 0), r, w, tyre, axis="y", n=16, cap=tyre)
    for side in (-1, 1):
        cylinder(m, (0, side * (w / 2 + 0.005), 0), r * 0.62, 0.012, rim, axis="y", n=12)
        for k in range(spokes):   # spokes/bolts make the turning visible
            a = 2 * math.pi * k / spokes
            box(m, (r * 0.36 * math.cos(a), side * (w / 2 + 0.014), r * 0.36 * math.sin(a)), (r * 0.16, 0.01, r * 0.16),
                shade(rim, 0.6))
    return m


def add_wheels(model, xs, track, r, w=0.25, spokes=5, rim=RIM):
    wm = wheel_mesh(r, w, spokes, rim)
    for x in xs:
        for side in (-1, 1):
            model.parts.append(Part(wm, (x, side * track / 2, r), "y", "wheel", r))


# ================================================================== road vehicles

def car(kind="sedan", color="red", seed=0):
    c = col(color)
    rng = random.Random(seed)
    L = {"sedan": 4.5, "hatch": 3.9, "suv": 4.7, "taxi": 4.6, "pickup": 5.2, "van": 4.9}[kind]
    Wd = 1.8 if kind not in ("suv", "van", "pickup") else 1.9
    m = Model(kind, L, Wd, 1.5)
    b = m.body
    h0, belt = 0.32, (0.95 if kind in ("sedan", "taxi", "hatch") else 1.05)
    hl = L / 2
    lower = [(-hl, h0 + 0.12), (-hl + 0.05, h0), (hl - 0.05, h0), (hl, h0 + 0.14), (hl - 0.05, belt - 0.15),
             (hl - 0.9, belt), (-hl + 0.2, belt), (-hl, belt - 0.12)]
    extrude(b, lower, -Wd / 2, Wd / 2, c)
    roof_c = shade(c, 1.05)
    if kind in ("sedan", "taxi"):
        cab = [(hl - 1.0, belt), (hl - 1.75, belt + 0.5), (-hl + 1.25, belt + 0.52), (-hl + 0.55, belt)]
    elif kind == "hatch":
        cab = [(hl - 0.95, belt), (hl - 1.65, belt + 0.52), (-hl + 0.45, belt + 0.52), (-hl + 0.15, belt)]
    elif kind == "pickup":
        cab = [(hl - 1.15, belt), (hl - 1.75, belt + 0.62), (hl - 2.6, belt + 0.62), (hl - 2.65, belt)]
    else:  # suv, van: tall box cabin
        cab = [(hl - 0.95, belt), (hl - 1.5, belt + 0.72), (-hl + 0.2, belt + 0.74), (-hl + 0.1, belt)]
    # glasshouse: glass sides, coloured roof and pillars
    extrude(b, cab, -Wd / 2 + 0.08, Wd / 2 - 0.08, GLASS, cap=GLASS,
            side=lambda i: roof_c if i in (1,) else (GLASS if i != len(cab) - 1 else c))
    top = max(z for _, z in cab)
    xs = [x for x, z in cab if z == top] or [cab[1][0]]
    for x, z in cab[1:3]:    # A and C pillars
        box(b, (x, Wd / 2 - 0.07, (belt + top) / 2), (0.1, 0.03, top - belt), shade(c, 0.85))
        box(b, (x, -Wd / 2 + 0.07, (belt + top) / 2), (0.1, 0.03, top - belt), shade(c, 0.85))
    bx = (cab[0][0] + cab[-1][0]) / 2
    for y in (Wd / 2 - 0.07, -Wd / 2 + 0.07):    # B pillar
        box(b, (bx, y, (belt + top) / 2), (0.1, 0.03, top - belt), shade(c, 0.8))
    if kind == "pickup":   # open bed behind the cab
        for y in (Wd / 2 - 0.05, -Wd / 2 + 0.05):
            box(b, (-0.6, y, belt + 0.18), (2.6, 0.08, 0.36), c)
        box(b, (-hl + 0.05, 0, belt + 0.18), (0.08, Wd, 0.36), c)
        box(b, (-0.6, 0, belt - 0.02), (2.6, Wd - 0.1, 0.04), DARK)
    # lights, grille, bumpers, mirrors, door seams
    for y in (Wd / 2 - 0.3, -Wd / 2 + 0.3):
        box(b, (hl + 0.005, y, h0 + 0.42), (0.04, 0.34, 0.14), HEAD, flags=1)
        box(b, (-hl - 0.005, y, h0 + 0.45), (0.04, 0.3, 0.12), TAIL, flags=1)
        box(b, (hl - 1.05, y + (0.16 if y > 0 else -0.16), belt + 0.08), (0.14, 0.12, 0.09), c)
    box(b, (hl + 0.01, 0, h0 + 0.3), (0.04, 0.6, 0.12), DARK)
    box(b, (hl, 0, h0 + 0.08), (0.12, Wd - 0.05, 0.12), shade(c, 0.6))
    box(b, (-hl, 0, h0 + 0.08), (0.12, Wd - 0.05, 0.12), shade(c, 0.6))
    for y in (Wd / 2 + 0.002, -Wd / 2 - 0.002):
        box(b, (bx, y, (h0 + belt) / 2 + 0.05), (0.02, 0.004, belt - h0 - 0.15), shade(c, 0.75))
    if kind == "taxi":
        box(b, (0, 0, top + 0.08), (0.5, 0.25, 0.16), (250, 240, 200), flags=1)
    wb = L * 0.6
    add_wheels(m, (wb / 2, -wb / 2), Wd - 0.2, 0.33, 0.22)
    for x in (wb / 2, -wb / 2):    # dark wheel arches
        for y in (Wd / 2 + 0.003, -Wd / 2 - 0.003):
            box(b, (x, y, 0.42), (0.86, 0.004, 0.4), (30, 30, 34))
    m.lights = [(hl, Wd / 2 - 0.3, h0 + 0.42), (hl, -Wd / 2 + 0.3, h0 + 0.42)]
    m.eye = np.array([hl - 2.0, 0.35, belt + 0.38])
    m.horn = np.array([hl, 0, 0.6])
    return m


def bus(color="red", seed=0, school=False):
    c = (246, 190, 30) if school else col(color)
    L, Wd, Hh = 11.5, 2.5, 3.1
    m = Model("bus", L, Wd, Hh)
    b = m.body
    hl = L / 2
    prof = [(-hl, 0.35), (hl, 0.35), (hl + 0.05, 1.2), (hl - 0.1, Hh - 0.15), (hl - 0.4, Hh), (-hl + 0.2, Hh), (-hl, Hh - 0.2)]
    extrude(b, prof, -Wd / 2, Wd / 2, c, side=lambda i: shade(c, 1.08) if i == 4 else c)
    box(b, (hl + 0.04, 0, 2.05), (0.04, Wd - 0.2, 1.4), GLASS_DARK)              # windscreen
    for y in (Wd / 2 + 0.005, -Wd / 2 - 0.005):
        for x in np.arange(-hl + 1.2, hl - 2.2, 1.45):
            box(b, (x + 0.6, y, 2.15), (1.3, 0.01, 1.0), GLASS_DARK)            # side windows
        box(b, (0, y, 1.0), (L - 0.4, 0.01, 0.06), shade(c, 0.75) if not school else (30, 30, 30))
    box(b, (hl - 1.3, -Wd / 2 - 0.01, 1.4), (1.1, 0.01, 2.0), shade(GLASS_DARK, 0.9))   # door (kerb side)
    for y in (Wd / 2 - 0.35, -Wd / 2 + 0.35):
        box(b, (hl + 0.06, y, 0.75), (0.03, 0.3, 0.16), HEAD, flags=1)
        box(b, (-hl - 0.02, y, 0.85), (0.03, 0.25, 0.3), TAIL, flags=1)
    box(b, (hl + 0.03, 0, Hh - 0.25), (0.03, 1.4, 0.22), (250, 190, 60) if not school else DARK, flags=1 if not school else 0)
    add_wheels(m, (hl - 2.4, -hl + 2.8), Wd - 0.3, 0.5, 0.3, spokes=8)
    m.lights = [(hl, Wd / 2 - 0.35, 0.75), (hl, -Wd / 2 + 0.35, 0.75)]
    m.eye = np.array([hl - 0.8, 0.6, 2.2])
    m.horn = np.array([hl, 0, 1.0])
    return m


def _cab(b, x_front, c, Wd=2.5, h=3.0, depth=2.3, z0=0.9):
    """Truck cab whose front face is at x_front."""
    prof = [(x_front - depth, z0), (x_front, z0), (x_front + 0.05, z0 + 1.0), (x_front - 0.25, h), (x_front - depth, h)]
    extrude(b, prof, -Wd / 2, Wd / 2, c)
    box(b, (x_front - 0.08, 0, z0 + 1.55), (0.04, Wd - 0.25, 0.9), GLASS_DARK, R=R.rot_y(-0.2))
    for y in (Wd / 2 + 0.004, -Wd / 2 - 0.004):
        box(b, (x_front - 0.7, y, z0 + 1.5), (0.8, 0.008, 0.7), GLASS_DARK)
        box(b, (x_front - 0.2, y + (0.2 if y > 0 else -0.2), z0 + 1.3), (0.06, 0.06, 0.6), DARK)   # mirror arm
    box(b, (x_front + 0.07, 0, z0 + 0.45), (0.06, Wd - 0.5, 0.6), DARK)              # grille
    for y in (Wd / 2 - 0.3, -Wd / 2 + 0.3):
        box(b, (x_front + 0.08, y, z0 + 0.2), (0.04, 0.3, 0.16), HEAD, flags=1)
    box(b, (x_front + 0.05, 0, z0 - 0.15), (0.2, Wd, 0.25), DARK)                   # bumper


def truck(kind="box", color="blue", seed=0, load_color="white"):
    """kind: box, tanker, mixer, logs, plow, dump, garbage, fire (no flashing lights), milk."""
    c = col(color)
    L = {"box": 8.5, "tanker": 9.5, "mixer": 8.0, "logs": 10.0, "plow": 8.0, "dump": 8.0, "garbage": 8.5,
         "fire": 9.0, "milk": 9.0}[kind]
    Wd = 2.5
    m = Model("truck", L, Wd, 3.6)
    b = m.body
    hl = L / 2
    _cab(b, hl, c, Wd)
    box(b, (-0.6, 0, 0.95), (L - 0.6, 1.0, 0.25), DARK)                          # chassis
    back_len = L - 2.6
    bx = hl - 2.5 - back_len / 2
    lc = col(load_color)
    if kind == "box":
        box(b, (bx, 0, 2.3), (back_len, Wd, 2.6), lc)
        box(b, (bx, Wd / 2 + 0.005, 2.0), (back_len - 0.4, 0.01, 0.35), c)
    elif kind in ("tanker", "milk"):
        loft(b, [(bx - back_len / 2, 0.01, 0.01, 2.1), (bx - back_len / 2 + 0.05, 1.15, 1.0, 2.1),
                 (bx + back_len / 2 - 0.05, 1.15, 1.0, 2.1), (bx + back_len / 2, 0.01, 0.01, 2.1)],
             CHROME if kind == "tanker" else WHITE, n=14)
        box(b, (bx, 0, 3.15), (back_len - 1, 0.5, 0.08), DARK)
        if kind == "milk":
            box(b, (bx, Wd / 2 - 0.05, 2.1), (back_len - 1.2, 0.02, 0.4), (60, 120, 200))
    elif kind == "mixer":
        drum = Mesh()
        loft(drum, [(-2.3, 0.3, 0.3, 0), (-1.6, 1.0, 1.0, 0), (0.8, 1.1, 1.1, 0), (2.1, 0.5, 0.5, 0)], lc, n=12,
             colors=lambda s, i: c if (i + s) % 4 == 0 else lc)
        m.parts.append(Part(drum, (bx - 0.2, 0, 2.3), "x", "spin", 1.0, speed=1.2))
        box(b, (bx - 2.6, 0, 1.6), (0.8, 0.8, 1.2), DARK)
    elif kind == "logs":
        for i, (y, z) in enumerate([(-0.65, 1.5), (0, 1.5), (0.65, 1.5), (-0.33, 2.05), (0.33, 2.05), (0, 2.6)]):
            cylinder(b, (bx - 0.3, y, z), 0.3, back_len + 0.4, (150, 104, 66), axis="x", n=8, cap=(214, 176, 120))
        for x in (bx - back_len / 2 + 0.3, bx + back_len / 2 - 0.3):
            for y in (-1.15, 1.15):
                box(b, (x, y, 2.0), (0.12, 0.12, 2.0), DARK)
    elif kind in ("dump",):
        extrude(b, [(bx - back_len / 2, 1.2), (bx + back_len / 2, 1.2), (bx + back_len / 2, 2.8), (bx - back_len / 2 - 0.4, 2.9)],
                -Wd / 2, Wd / 2, lc)
    elif kind == "garbage":
        extrude(b, [(bx - back_len / 2, 1.1), (bx + back_len / 2, 1.1), (bx + back_len / 2, 3.4), (bx - back_len / 2 + 0.6, 3.4),
                    (bx - back_len / 2 - 0.3, 2.4)], -Wd / 2, Wd / 2, lc)
    elif kind == "fire":
        box(b, (bx, 0, 2.0), (back_len, Wd, 2.1), c)
        for x in np.arange(bx - back_len / 2 + 0.6, bx + back_len / 2 - 0.4, 1.2):
            for y in (Wd / 2 + 0.005, -Wd / 2 - 0.005):
                box(b, (x, y, 2.0), (1.0, 0.01, 1.7), shade(c, 0.8))
        box(b, (bx - 0.4, 0, 3.25), (back_len + 1.0, 0.5, 0.18), CHROME)                # ladder
        for x in np.arange(bx - back_len / 2, bx + back_len / 2 + 0.5, 0.5):
            box(b, (x, 0, 3.3), (0.05, 0.6, 0.06), CHROME)
        box(b, (hl - 1.2, 0, 3.05), (0.3, 1.4, 0.14), (220, 60, 50))                  # lights bar (steady, off)
    elif kind == "plow":
        box(b, (bx, 0, 2.0), (back_len, Wd - 0.2, 1.8), (130, 134, 142))
        extrude(b, [(hl + 0.3, 0.05), (hl + 1.1, 0.25), (hl + 1.2, 1.3), (hl + 0.5, 1.2)], -1.6, 1.6, (240, 160, 30))
        box(b, (hl - 1.2, 0, 3.1), (0.3, 0.9, 0.14), (250, 170, 40), flags=1)
    wheels_x = [hl - 1.4, -hl + 2.6, -hl + 1.4] if L > 8.6 else [hl - 1.4, -hl + 1.8]
    add_wheels(m, wheels_x, Wd - 0.3, 0.5, 0.35, spokes=8)
    for y in (Wd / 2 - 0.3, -Wd / 2 + 0.3):
        box(b, (-hl - 0.02, y, 1.0), (0.04, 0.25, 0.2), TAIL, flags=1)
    m.lights = [(hl, Wd / 2 - 0.3, 1.1), (hl, -Wd / 2 + 0.3, 1.1)]
    m.eye = np.array([hl - 0.9, 0.6, 2.4])
    m.horn = np.array([hl, 0, 2.6])
    return m


def tractor(color="green", seed=0, trailer=False):
    c = col(color)
    m = Model("tractor", 4.2, 2.3, 2.9)
    b = m.body
    extrude(b, [(-0.6, 0.9), (2.0, 0.9), (2.1, 1.7), (-0.2, 1.75)], -0.55, 0.55, c)        # hood / engine
    box(b, (2.12, 0, 1.3), (0.06, 0.8, 0.6), DARK)                                         # grille
    box(b, (-1.0, 0, 2.0), (1.5, 1.3, 2.1), GLASS, top=c)                                 # cab glass
    box(b, (-1.0, 0, 3.07), (1.7, 1.5, 0.12), c)                                           # roof
    for x in (-1.72, -0.28):
        for y in (-0.62, 0.62):
            box(b, (x, y, 2.0), (0.08, 0.08, 2.1), DARK)
    cylinder(b, (1.4, 0.35, 2.2), 0.06, 1.0, DARK, axis="z", n=6)                         # exhaust pipe
    box(b, (-1.0, 0, 0.95), (1.8, 1.0, 0.5), DARK)
    rear = wheel_mesh(0.85, 0.45, spokes=6, rim=(240, 200, 40))
    front = wheel_mesh(0.5, 0.3, spokes=5, rim=(240, 200, 40))
    for y in (-0.95, 0.95):
        m.parts.append(Part(rear, (-1.0, y, 0.85), "y", "wheel", 0.85))
        m.parts.append(Part(front, (1.5, y * 0.85, 0.5), "y", "wheel", 0.5))
    for y in (-0.95, 0.95):   # fenders
        box(b, (-1.0, y, 1.75), (1.9, 0.5, 0.08), c)
    for y in (-0.5, 0.5):
        box(b, (2.12, y, 1.55), (0.04, 0.16, 0.1), HEAD, flags=1)
    m.lights = [(2.1, 0.5, 1.55), (2.1, -0.5, 1.55)]
    m.eye = np.array([-0.8, 0.0, 2.45])
    m.horn = np.array([2.0, 0, 1.6])
    return m


# ================================================================== trains

def steam_loco(color="green", seed=0):
    """A tender steam locomotive: smokebox and chimney in front, boiler, cab, then the coal tender."""
    c = col(color)
    m = Model("steam", 17.5, 2.8, 4.1)
    b = m.body
    blk = (40, 40, 44)
    # engine part: x from -1.0 to 9.0 (front at 9.0); tender from -8.5 to -1.5
    loft(b, [(1.5, 0.95, 0.95, 2.45), (8.2, 0.95, 0.95, 2.45)], c, n=14, cap0=False)
    loft(b, [(8.2, 1.0, 1.0, 2.45), (9.0, 1.0, 1.0, 2.45)], blk, n=14)                  # smokebox
    cylinder(b, (9.02, 0, 2.45), 0.6, 0.04, (60, 60, 64), axis="x", n=12)               # smokebox door
    cylinder(b, (7.7, 0, 3.75), 0.32, 0.9, blk, axis="z", n=10, r2=0.4)                 # chimney
    cylinder(b, (4.8, 0, 3.55), 0.38, 0.4, (200, 160, 60), axis="z", n=10, r2=0.3)      # brass dome
    cylinder(b, (3.2, 0, 3.5), 0.22, 0.35, (200, 160, 60), axis="z", n=8)              # safety valve
    box(b, (0.3, 0, 2.6), (2.4, 2.8, 2.6), c)                                          # cab
    box(b, (0.3, 0, 3.98), (2.8, 3.0, 0.14), blk)                                      # cab roof
    for y in (1.405, -1.405):
        box(b, (0.6, y, 3.2), (0.9, 0.01, 0.8), GLASS_DARK)                            # cab windows
    box(b, (5.0, 0, 1.25), (9.0, 2.7, 0.3), blk)                                       # running board / frame
    for y in (1.3, -1.3):
        cylinder(b, (8.0, y, 1.35), 0.38, 1.1, (70, 72, 80), axis="x", n=10)            # cylinders
    extrude(b, [(9.0, 0.15), (10.0, 0.15), (9.0, 1.05)], -1.2, 1.2, (150, 40, 36))      # cow catcher (front!)
    box(b, (9.0, 0, 3.15), (0.3, 0.4, 0.35), blk)
    box(b, (9.16, 0, 3.15), (0.03, 0.28, 0.24), HEAD, flags=1)                         # headlamp
    # tender (behind the cab)
    box(b, (-4.6, 0, 2.15), (6.0, 2.7, 2.1), c)
    box(b, (-4.6, 0, 3.25), (5.6, 2.3, 0.2), (30, 30, 32))                             # coal
    box(b, (-4.6, 0, 1.0), (6.2, 2.5, 0.3), blk)
    driver = wheel_mesh(0.9, 0.18, spokes=10, rim=(150, 40, 36), tyre=(50, 50, 54))
    small = wheel_mesh(0.48, 0.16, spokes=8, rim=(150, 40, 36), tyre=(50, 50, 54))
    for x in (2.2, 4.2, 6.2):
        for y in (-1.05, 1.05):
            m.parts.append(Part(driver, (x, y, 0.9), "y", "wheel", 0.9))
    for x in (8.4, -2.4, -3.9, -5.3, -6.8):
        for y in (-1.05, 1.05):
            m.parts.append(Part(small, (x, y, 0.48), "y", "wheel", 0.48))
    m.chimney = np.array([7.7, 0, 4.2])
    m.front_x = 10.0
    m.rear_x = -7.6
    m.eye = np.array([0.6, 0.9, 3.3])
    m.horn = np.array([3.2, 0, 3.7])
    m.lights = [(9.2, 0, 3.15)]
    m.rods = [(2.2, 4.2, 6.2), 0.9, 8.0]
    return m


def diesel_loco(color="red", seed=0, kind="diesel"):
    """Diesel or electric locomotive: driver's cab with big windscreen at the front (+x)."""
    c = col(color)
    m = Model(kind, 18.0, 3.0, 4.2)
    b = m.body
    hl = 9.0
    prof = [(-hl, 1.2), (hl - 0.4, 1.2), (hl, 1.6), (hl, 2.8), (hl - 1.2, 4.0), (-hl + 0.2, 4.0), (-hl, 3.8)]
    extrude(b, prof, -1.45, 1.45, c)
    box(b, (hl - 0.55, 0, 3.35), (0.04, 2.6, 0.9), GLASS_DARK, R=R.rot_y(-0.78))           # windscreen
    for y in (1.455, -1.455):
        box(b, (hl - 2.0, y, 3.2), (1.0, 0.01, 0.7), GLASS_DARK)
        box(b, (0, y, 1.9), (2 * hl - 0.6, 0.01, 0.35), (240, 220, 80) if kind == "diesel" else WHITE)
        for x in np.arange(-hl + 1.0, hl - 3.5, 0.6):
            box(b, (x, y, 3.0), (0.3, 0.012, 0.9), shade(c, 0.8))                          # grilles
    box(b, (hl + 0.02, 0, 2.2), (0.03, 0.4, 0.25), HEAD, flags=1)
    for y in (0.9, -0.9):
        box(b, (hl + 0.02, y, 1.55), (0.03, 0.25, 0.16), HEAD, flags=1)
        box(b, (-hl - 0.02, y, 1.55), (0.03, 0.25, 0.16), TAIL, flags=1)
    if kind == "electric":
        box(b, (2.0, 0, 4.4), (0.1, 1.6, 0.06), DARK)
        box(b, (1.4, 0, 4.25), (1.4, 0.1, 0.06), DARK, R=R.rot_y(0.5))
    box(b, (0, 0, 1.05), (2 * hl - 1, 2.4, 0.4), DARK)
    wm = wheel_mesh(0.55, 0.16, spokes=8, rim=(90, 90, 96), tyre=(50, 50, 54))
    for x in (hl - 2.0, hl - 3.8, -hl + 3.8, -hl + 2.0):
        for y in (-1.0, 1.0):
            m.parts.append(Part(wm, (x, y, 0.55), "y", "wheel", 0.55))
    m.front_x, m.rear_x = hl + 0.1, -hl - 0.1
    m.eye = np.array([hl - 1.3, 0.7, 3.2])
    m.horn = np.array([hl - 1.0, 0, 4.0])
    m.lights = [(hl, 0, 2.2)]
    return m


def railcar(kind="coach", color="red", seed=0):
    """Passenger coach or freight wagon, 16 m (freight 13 m)."""
    c = col(color)
    L = 16.0 if kind in ("coach", "tram") else 13.0
    m = Model(kind, L, 2.9, 4.0)
    b = m.body
    hl = L / 2
    if kind in ("coach", "tram"):
        extrude(b, [(-hl, 1.2), (hl, 1.2), (hl, 3.6), (hl - 0.3, 4.0), (-hl + 0.3, 4.0), (-hl, 3.6)], -1.4, 1.4, c,
                side=lambda i: (150, 154, 160) if i in (3,) else c)
        for y in (1.405, -1.405):
            for x in np.arange(-hl + 1.6, hl - 1.2, 1.5):
                box(b, (x, y, 2.75), (1.1, 0.01, 0.75), GLASS_DARK)
            box(b, (hl - 0.8, y, 2.4), (0.8, 0.012, 2.0), shade(c, 0.75))
            box(b, (-hl + 0.8, y, 2.4), (0.8, 0.012, 2.0), shade(c, 0.75))
            box(b, (0, y, 1.9), (L - 0.4, 0.012, 0.12), WHITE)
    elif kind == "container":
        box(b, (0, 0, 1.2), (L, 2.5, 0.25), DARK)
        box(b, (0, 0, 2.6), (L - 0.4, 2.5, 2.6), c)
        for x in np.arange(-hl + 0.6, hl - 0.4, 0.5):
            for y in (1.255, -1.255):
                box(b, (x, y, 2.6), (0.06, 0.01, 2.5), shade(c, 0.85))
    elif kind == "tanker":
        box(b, (0, 0, 1.2), (L, 2.4, 0.25), DARK)
        loft(b, [(-hl + 0.3, 0.01, 0.01, 2.5), (-hl + 0.4, 1.3, 1.25, 2.5), (hl - 0.4, 1.3, 1.25, 2.5), (hl - 0.3, 0.01, 0.01, 2.5)],
             c, n=14)
        box(b, (0, 0, 3.8), (0.8, 0.8, 0.2), DARK)
    elif kind == "hopper":
        extrude(b, [(-hl + 0.3, 3.6), (hl - 0.3, 3.6), (hl - 1.5, 1.4), (-hl + 1.5, 1.4)], -1.4, 1.4, c)
        box(b, (0, 0, 3.55), (L - 0.8, 2.6, 0.1), (60, 52, 46))
        box(b, (0, 0, 1.2), (L, 2.2, 0.2), DARK)
    else:  # boxcar
        box(b, (0, 0, 1.2), (L, 2.4, 0.25), DARK)
        box(b, (0, 0, 2.6), (L - 0.2, 2.8, 2.6), c)
        for y in (1.405, -1.405):
            box(b, (0, y, 2.5), (2.6, 0.01, 2.3), shade(c, 0.8))
    if kind == "tram":
        box(b, (0, 0, 4.25), (0.1, 1.4, 0.06), DARK)
        box(b, (-0.5, 0, 4.15), (1.2, 0.1, 0.06), DARK, R=R.rot_y(0.45))
    wm = wheel_mesh(0.45, 0.14, spokes=6, rim=(90, 90, 96), tyre=(50, 50, 54))
    for x in (hl - 1.8, hl - 3.2, -hl + 3.2, -hl + 1.8):
        for y in (-1.0, 1.0):
            m.parts.append(Part(wm, (x, y, 0.45), "y", "wheel", 0.45))
    for x in (hl, -hl):
        box(b, (x + (0.15 if x > 0 else -0.15), 0, 1.15), (0.3, 0.3, 0.2), DARK)    # couplers
    m.front_x, m.rear_x = hl + 0.3, -hl - 0.3
    return m


class Train:
    """Engine first (+x), cars trailing behind. Positions along a track are given for the engine's front."""

    def __init__(self, engine, cars, gap=0.6):
        self.units = [engine] + list(cars)
        self.offsets = []          # distance from the train's front back to each unit's origin
        d = 0.0
        for u in self.units:
            d += u.front_x
            self.offsets.append(d)
            d += -u.rear_x + gap
        self.length = d
        self.engine = engine

    def objs(self, track_pose, front_s, dist, t):
        """track_pose(s) -> (x, y, z, yaw) at arc length s along the track."""
        out = []
        for u, off in zip(self.units, self.offsets):
            # place each unit by its two bogies so it follows curves
            s_mid = front_s - off
            x1, y1, z1, _ = track_pose(s_mid + u.length * 0.3)
            x2, y2, z2, _ = track_pose(s_mid - u.length * 0.3)
            yaw = math.atan2(y1 - y2, x1 - x2)
            pitch = math.atan2(z1 - z2, math.hypot(x1 - x2, y1 - y2))
            x, y, z, _ = track_pose(s_mid)
            out += u.objs((x, y, z), yaw, pitch, dist=dist, t=t)
        return out


# ================================================================== boats (above the waterline)

def _hull(b, L, Wd, deck, color, bow=0.3, stern_w=0.85, top_color=None, chine=0.45):
    """Hull from the waterline (z=0) to the deck: pointed bow at +x."""
    hl = L / 2
    n = 9
    xs = np.linspace(-hl, hl, n)

    def half(x, z):
        u = (x + hl) / L
        w = Wd / 2 * (stern_w + (1 - stern_w) * math.sin(min(1, u / (1 - bow)) * math.pi / 2))
        if u > 1 - bow:
            w *= max(0.0, 1 - ((u - (1 - bow)) / bow) ** 1.6)
        return w * (chine + (1 - chine) * (z / deck))
    deckz = lambda x: deck + 0.25 * max(0, (x - hl * 0.3) / (hl * 0.7)) ** 2   # sheer: bow rises a little
    for i in range(n - 1):
        x0, x1 = xs[i], xs[i + 1]
        for s in (1, -1):
            pts = [(x0, s * half(x0, 0.01), 0.0), (x1, s * half(x1, 0.01), 0.0), (x1, s * half(x1, deck), deckz(x1)),
                   (x0, s * half(x0, deck), deckz(x0))]
            if s < 0:
                pts = pts[::-1]
            b.poly(pts, color)
    deck_pts = [(x, half(x, deck), deckz(x)) for x in xs] + [(x, -half(x, deck), deckz(x)) for x in xs[::-1]]
    b.poly(deck_pts, top_color or (196, 170, 130))
    b.poly([(-hl, half(-hl, 0.01), 0), (-hl, half(-hl, deck), deckz(-hl)), (-hl, -half(-hl, deck), deckz(-hl)),
            (-hl, -half(-hl, 0.01), 0)], color)     # transom
    b._done = False
    # stripe at the waterline
    return half


def _fix_hull(b, k0):
    V = b.v
    for k in range(k0, len(b.f)):
        f = b.f[k]
        P = np.array([V[i] for i in f])
        cen = P.mean(axis=0)
        nrm = np.cross(P[1] - P[0], P[2] - P[0])
        out = np.array([0.0, cen[1], 0.0]) if abs(cen[1]) > 0.05 else np.array([cen[0], 0, 0.5])
        if abs(nrm[2]) > 0.8 and abs(cen[1]) < 0.01:
            out = np.array([0, 0, 1.0])
        if np.dot(nrm, out) < 0:
            b.f[k] = tuple(reversed(f))


def boat(kind="sailboat", color="red", seed=0, sail="white"):
    c = col(color)
    spec = {"sailboat": (9.0, 3.0, 1.0), "speedboat": (7.0, 2.5, 0.9), "fishing": (12.0, 4.0, 1.6),
            "ferry": (40.0, 11.0, 3.0), "rowboat": (4.0, 1.5, 0.5), "tug": (14.0, 5.0, 1.6),
            "ship": (90.0, 16.0, 6.0), "canal": (18.0, 2.1, 0.8), "lake": (24.0, 7.0, 2.0)}[kind]
    L, Wd, deck = spec
    m = Model(kind, L, Wd, deck)
    b = m.body
    k0 = len(b.f)
    _hull(b, L, Wd, deck, c, bow=0.35 if kind != "ship" else 0.18, stern_w=0.85 if kind != "rowboat" else 0.5,
          top_color=(200, 176, 136) if kind in ("sailboat", "rowboat", "canal") else (190, 192, 196))
    _fix_hull(b, k0)
    hl = L / 2
    if kind == "sailboat":
        cylinder(b, (0.6, 0, deck + 5.5), 0.08, 11.0, (220, 220, 220), axis="z", n=6)        # mast
        box(b, (-1.0, 0, deck + 1.3), (3.4, 0.1, 0.1), (200, 200, 200))                      # boom
        sc = col(sail)
        b.poly([(0.55, 0, deck + 1.35), (0.55, 0, deck + 10.6), (-2.6, 0, deck + 1.35)], shade(sc, 0.93), flags=3)  # mainsail
        b.poly([(0.75, 0, deck + 9.5), (hl - 0.3, 0, deck + 0.4), (0.75, 0, deck + 1.2)], shade(sc, 0.86), flags=3)  # jib
        box(b, (-1.8, 0, deck + 0.4), (2.0, 1.6, 0.6), WHITE)
        m.sail = True
    elif kind == "speedboat":
        box(b, (0.6, 0, deck + 0.35), (0.05, Wd - 0.6, 0.5), GLASS, R=R.rot_y(0.5))
        box(b, (-0.8, 0, deck + 0.3), (2.0, Wd - 0.8, 0.5), (230, 230, 226))
        box(b, (-hl - 0.25, 0, deck - 0.1), (0.5, 0.5, 0.9), DARK)                        # outboard motor
    elif kind in ("fishing", "tug"):
        box(b, (hl * 0.15, 0, deck + 1.3), (L * 0.28, Wd * 0.6, 2.6), WHITE)
        for y in (Wd * 0.3 + 0.005, -Wd * 0.3 - 0.005):
            box(b, (hl * 0.15, y, deck + 1.8), (L * 0.22, 0.01, 0.7), GLASS_DARK)
        box(b, (hl * 0.15 + L * 0.14 + 0.01, 0, deck + 1.8), (0.01, Wd * 0.5, 0.7), GLASS_DARK)
        if kind == "fishing":
            cylinder(b, (-hl * 0.4, 0, deck + 3.5), 0.1, 7.0, (230, 230, 230), axis="z", n=6)
            box(b, (-hl * 0.6, 0, deck + 2.5), (0.08, 0.08, 4.4), (200, 200, 200), R=R.rot_y(0.7))
        else:
            cylinder(b, (-hl * 0.15, 0, deck + 3.6), 0.45, 2.2, DARK, axis="z", n=10)        # funnel
            for x in np.linspace(-hl + 1, hl - 2, 6):
                for y in (1, -1):
                    cylinder(b, (x, y * (Wd / 2 * 0.9), deck * 0.6), 0.32, 0.4, (40, 40, 40), axis="x", n=8)  # fenders
    elif kind in ("ferry", "lake"):
        for lvl, (ln, h) in enumerate([(L * 0.75, 2.6), (L * 0.5, 2.4)]):
            z = deck + 1.3 + lvl * 2.6
            box(b, (-hl * 0.05, 0, z), (ln, Wd * (0.92 - 0.1 * lvl), h), WHITE)
            for y in (1, -1):
                for x in np.arange(-ln / 2 + 1.2, ln / 2 - 1, 1.6):
                    box(b, (x - hl * 0.05, y * Wd * (0.92 - 0.1 * lvl) / 2 * 1.002, z + 0.2), (1.0, 0.01, 0.9), GLASS_DARK)
        cylinder(b, (-hl * 0.25, 0, deck + 7.5), 1.1, 3.0, c, axis="z", n=12)
        box(b, (hl * 0.32, 0, deck + 6.4), (2.2, Wd * 0.5, 1.6), WHITE)
        box(b, (hl * 0.32 + 1.11, 0, deck + 6.6), (0.01, Wd * 0.45, 0.8), GLASS_DARK)
    elif kind == "ship":
        palette = [PAL[k] for k in ("red", "blue", "yellow", "green", "orange", "teal", "white")]
        rng = random.Random(seed)
        for x in np.arange(-hl + 14, hl - 14, 6.2):
            for row in range(3):
                for y in np.arange(-Wd / 2 + 2, Wd / 2 - 1.5, 2.5):
                    box(b, (x, y + 1.2, deck + 1.3 + row * 2.6), (6.0, 2.4, 2.55), rng.choice(palette))
        box(b, (-hl + 7, 0, deck + 6), (8, Wd * 0.9, 12), WHITE)
        for z in (deck + 5, deck + 8, deck + 11):
            box(b, (-hl + 11.02, 0, z), (0.02, Wd * 0.8, 1.0), GLASS_DARK)
    elif kind == "canal":
        box(b, (-1.0, 0, deck + 0.75), (L - 4.5, Wd - 0.3, 1.5), (40, 100, 70))
        for x in np.arange(-L / 2 + 3, L / 2 - 4, 1.6):
            for y in (1, -1):
                box(b, (x, y * (Wd - 0.3) / 2 * 1.002, deck + 0.9), (0.6, 0.01, 0.45), (230, 200, 90))
    if kind == "rowboat":
        for y in (1, -1):
            box(b, (0, y * 0.95, deck + 0.05), (2.3, 0.05, 0.05), (160, 120, 80), R=R.rot_z(y * 0.25))   # oars
    m.horn = np.array([hl * 0.2, 0, deck + 3])
    m.eye = np.array([0, 0.3, deck + 2.5]) if kind not in ("rowboat", "sailboat") else np.array([-1.5, 0, deck + 1.4])
    return m


# ================================================================== aircraft

def airliner(color="blue", seed=0, cargo=False, gear=True):
    """Twin-engine airliner (about 38 m): round fuselage, swept low wings with engines under them,
    tall fin with a horizontal tailplane, tricycle landing gear."""
    c = col(color)
    m = Model("airliner", 38.0, 35.0, 12.0)
    b = m.body
    r = 2.0
    zc = 3.6
    loft(b, [(19.0, 0.05, 0.05, zc - 0.3), (18.4, 0.9, 0.85, zc - 0.15), (17.0, 1.7, 1.75, zc), (14.5, r, r, zc),
             (-9.0, r, r, zc), (-14.0, 1.4, 1.5, zc + 0.5), (-18.5, 0.35, 0.45, zc + 1.4)], WHITE, n=16,
         colors=lambda s, i: (c if (s in (3, 4) and i in (12, 13)) else WHITE))
    # windows (both sides) and cockpit
    for y in (r * 1.003, -r * 1.003):
        box(b, (2.0, y, zc + 0.45), (26.0, 0.01, 0.22), (60, 70, 90))
        box(b, (2.0, y, zc - 0.55), (31.0, 0.012, 0.18), c)                  # cheat line in the airline colour
    for y in (0.55, -0.55):
        box(b, (17.6, y, zc + 0.75), (0.7, 0.3, 0.32), (40, 50, 70), R=R.rot_z(0.35 if y > 0 else -0.35))
    # swept wings (low, slight dihedral) with engines slung underneath
    for side in (1, -1):
        wedge_wing(b, root_x=4.5, root_len=7.0, tip_x=-6.0, tip_len=2.0, span=15.5, z=zc - 1.2, thick=0.5,
                   color=(214, 216, 222), y0=side * 1.2, dihedral=math.radians(5), side=side)
    _place_engines(b, zc, c)
    # tail: vertical fin and horizontal tailplane
    fin(b, root_x=-11.5, root_len=6.0, tip_x=-16.2, tip_len=3.0, height=6.8, z0=zc + 1.0, thick=0.35, color=c)
    for side in (1, -1):
        wedge_wing(b, root_x=-13.6, root_len=3.6, tip_x=-17.0, tip_len=1.6, span=6.0, z=zc + 0.9, thick=0.25,
                   color=(214, 216, 222), y0=side * 0.8, dihedral=math.radians(6), side=side)
    m.gear = gear
    if gear:
        gm = Mesh()
        cylinder(gm, (0, 0, 0.55), 0.55, 0.4, TYRE, axis="y", n=12, cap=RIM)
        for x, y in ((-0.5, 2.6), (-0.5, -2.6), (15.0, 0.0)):
            box(b, (x, y, (0.55 + zc - r) / 2 + 0.4), (0.18, 0.18, zc - r + 0.3), (150, 154, 160))
            m.parts.append(Part(gm, (x, y, 0.0), "y", "fixed", 0.55))
    m.eye = np.array([17.2, 0.5, zc + 0.9])
    m.horn = np.array([4.5, 0, zc - 1.9])
    m.lights = [(19.0, 0, zc - 0.3)]
    return m


def _place_engines(b, zc, c):
    """Two turbofan engines hanging under the wings on pylons."""
    for side in (1, -1):
        e = Mesh()
        loft(e, [(6.8, 0.6, 0.6, 0), (6.5, 0.9, 0.9, 0), (3.4, 0.95, 0.95, 0), (2.2, 0.55, 0.55, 0)], (205, 208, 216), n=12)
        cylinder(e, (6.82, 0, 0), 0.62, 0.02, (60, 62, 70), axis="x", n=12)
        box(e, (4.2, 0, 0.9), (2.4, 0.18, 0.6), (190, 192, 200))     # pylon up to the wing
        b.extend(e, t=(0, side * 5.6, zc - 2.05))


def small_plane(color="red", seed=0, floats=False, skis=False):
    """High-wing four-seater (about 8 m): wing on top of the cabin with struts, propeller at the nose,
    tail with fin and tailplane, tricycle gear (or floats / skis)."""
    c = col(color)
    m = Model("small_plane", 8.3, 11.0, 2.7)
    b = m.body
    zc = 1.45
    loft(b, [(3.9, 0.35, 0.35, zc), (3.4, 0.6, 0.55, zc), (1.8, 0.62, 0.7, zc + 0.1), (-0.5, 0.58, 0.68, zc + 0.12),
             (-3.6, 0.18, 0.25, zc + 0.35)], WHITE, n=12,
         colors=lambda s, i: c if i in (8, 9, 10) or s == 0 else WHITE)
    for y in (0.6, -0.6):
        box(b, (1.4, y * 1.01, zc + 0.45), (1.6, 0.01, 0.42), GLASS_DARK)
    box(b, (2.35, 0, zc + 0.6), (0.02, 1.0, 0.42), GLASS_DARK, R=R.rot_y(-0.6))
    # high wing across the top of the cabin
    for side in (1, -1):
        wedge_wing(b, root_x=2.0, root_len=1.6, tip_x=1.85, tip_len=1.3, span=5.3, z=zc + 0.82, thick=0.16,
                   color=shade(WHITE, 0.98), y0=side * 0.1, dihedral=math.radians(2), side=side)
        box(b, (1.2, side * 1.6, zc + 0.2), (0.07, 0.07, 1.4), (150, 154, 160), R=R.rot_x(side * 0.75))   # strut
        box(b, (1.2, side * 5.2, zc + 0.92), (1.3, 0.25, 0.02), c)                                         # wing-tip colour
    fin(b, root_x=-2.6, root_len=1.4, tip_x=-3.3, tip_len=0.8, height=1.35, z0=zc + 0.4, thick=0.08, color=c)
    for side in (1, -1):
        wedge_wing(b, root_x=-2.9, root_len=1.0, tip_x=-3.2, tip_len=0.7, span=1.6, z=zc + 0.38, thick=0.08,
                   color=shade(WHITE, 0.98), y0=side * 0.15, side=side)
    sp = Mesh()
    cylinder(sp, (0.12, 0, 0), 0.16, 0.25, (200, 60, 50), axis="x", n=10, r2=0.04)
    box(sp, (0, 0, 0), (0.05, 0.12, 1.85), (60, 60, 66))                # two-blade propeller
    m.parts.append(Part(sp, (4.0, 0, zc), "x", "prop", 1.0, speed=38.0))
    if floats:
        for y in (1.1, -1.1):
            fm = Mesh()
            loft(fm, [(3.4, 0.05, 0.05, 0.3), (2.6, 0.3, 0.25, 0.3), (-2.6, 0.3, 0.25, 0.3), (-3.2, 0.1, 0.1, 0.35)],
                 WHITE, n=8)
            b.extend(fm, t=(0, y, 0))
        for x in (1.5, -0.8):
            for y in (1.1, -1.1):
                box(b, (x, y * 0.7, 0.9), (0.06, 0.06, 1.0), (150, 154, 160), R=R.rot_x(-y * 0.45))
    elif skis:
        for x, y in ((0.7, 1.1), (0.7, -1.1), (3.0, 0.0)):
            box(b, (x, y, 0.08), (1.5, 0.22, 0.06), (220, 60, 50))
            box(b, (x, y, 0.5), (0.08, 0.08, 0.85), (150, 154, 160))
    else:
        gm = wheel_mesh(0.27, 0.16, spokes=4)
        for x, y in ((0.7, 1.15), (0.7, -1.15), (3.0, 0.0)):
            box(b, (x, y * 0.85, 0.7), (0.08, 0.08, 0.8), (150, 154, 160), R=R.rot_x(-y * 0.35))
            m.parts.append(Part(gm, (x, y, 0.27), "y", "wheel", 0.27))
    m.eye = np.array([1.1, 0.3, zc + 0.55])
    m.horn = np.array([4.0, 0, zc])
    m.lights = [(1.9, 5.3, zc + 0.8)]
    return m


def helicopter(color="red", seed=0):
    c = col(color)
    m = Model("helicopter", 12.0, 2.4, 3.6)
    b = m.body
    loft(b, [(2.6, 0.2, 0.3, 1.6), (2.3, 0.85, 0.85, 1.65), (0.6, 1.1, 1.15, 1.75), (-1.2, 0.9, 1.0, 1.85),
             (-2.0, 0.3, 0.4, 2.2), (-6.4, 0.16, 0.2, 2.35)], c, n=12)
    box(b, (1.6, 0, 1.9), (0.02, 1.6, 1.1), GLASS_DARK, R=R.rot_y(-0.7))
    for y in (1.05, -1.05):
        box(b, (0.9, y, 2.0), (1.4, 0.01, 0.7), GLASS_DARK)
    fin(b, root_x=-5.6, root_len=0.9, tip_x=-6.3, tip_len=0.6, height=1.3, z0=2.3, thick=0.08, color=c)
    box(b, (-0.2, 0, 2.95), (1.4, 0.8, 0.5), shade(c, 0.85))                     # engine housing
    for y in (0.9, -0.9):                                                        # skids
        box(b, (0.2, y, 0.1), (3.6, 0.12, 0.1), DARK)
        for x in (1.0, -0.6):
            box(b, (x, y * 0.85, 0.55), (0.08, 0.08, 0.9), DARK, R=R.rot_x(-y * 0.25))
    rot = Mesh()
    cylinder(rot, (0, 0, 0), 0.2, 0.3, DARK, axis="z", n=8)
    for a in (0, math.pi / 2):
        box(rot, (0, 0, 0.12), (10.6, 0.32, 0.05), (60, 62, 68), R=R.rot_z(a))
    m.parts.append(Part(rot, (-0.1, 0, 3.4), "z", "prop", 5.3, speed=22.0))
    tr = Mesh()
    box(tr, (0, 0, 0), (0.12, 0.05, 1.5), (60, 62, 68))
    box(tr, (0, 0, 0), (0.12, 0.05, 1.5), (60, 62, 68), R=R.rot_y(math.pi / 2))
    m.parts.append(Part(tr, (-6.3, 0.2, 2.6), "y", "prop", 0.8, speed=40.0))
    m.eye = np.array([1.4, 0.4, 2.15])
    m.horn = np.array([0, 0, 3.4])
    m.lights = [(2.6, 0, 1.6)]
    return m


def cable_car(color="red", seed=0):
    c = col(color)
    m = Model("cable_car", 3.0, 2.2, 5.0)
    b = m.body
    box(b, (0, 0, 1.2), (3.0, 2.2, 2.2), c, top=shade(c, 1.1))
    for y in (1.105, -1.105):
        box(b, (0, y, 1.5), (2.6, 0.01, 1.0), GLASS_DARK)
    for x in (1.505, -1.505):
        box(b, (x, 0, 1.5), (0.01, 1.8, 1.0), GLASS_DARK)
    box(b, (0, 0, 3.0), (0.12, 0.12, 1.5), DARK)
    box(b, (0, 0, 3.8), (1.2, 0.4, 0.3), DARK)
    return m


REGISTRY = {
    "car": car, "bus": bus, "truck": truck, "tractor": tractor, "steam_loco": steam_loco, "diesel_loco": diesel_loco,
    "railcar": railcar, "boat": boat, "airliner": airliner, "small_plane": small_plane, "helicopter": helicopter,
    "cable_car": cable_car,
}
