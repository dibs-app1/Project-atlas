"""Scenery kits for engine 3: ground, roads, rails, water, trees, houses, city blocks, farms, mountains,
snow, harbours, airfields and sky. Long features are cut into chunks so the renderer can skip what the
camera cannot see.
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import r3d as R
from .r3d import Mesh, Obj, box, cone, cylinder, extrude, sphere

CHUNK = 120.0


# ------------------------------------------------------------------ paths

class Path:
    """A smooth path through control points (x, y, z), sampled every metre; pose(s) by arc length."""

    def __init__(self, pts, step=1.0):
        P = np.asarray(pts, float)
        if P.shape[1] == 2:
            P = np.hstack([P, np.zeros((len(P), 1))])
        out = []
        for i in range(len(P) - 1):           # Catmull-Rom
            p0 = P[max(0, i - 1)]
            p1, p2 = P[i], P[i + 1]
            p3 = P[min(len(P) - 1, i + 2)]
            n = max(2, int(np.linalg.norm(p2 - p1) / step))
            for k in range(n):
                t = k / n
                t2, t3 = t * t, t * t * t
                out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
        out.append(P[-1])
        self.P = np.array(out)
        d = np.sqrt(((self.P[1:] - self.P[:-1]) ** 2).sum(axis=1))
        self.S = np.concatenate([[0], np.cumsum(d)])
        self.length = float(self.S[-1])

    def pose(self, s):
        s = min(max(s, 0.0), self.length - 1e-6) if s >= 0 else s
        if s < 0 or s > self.length:   # extend straight beyond the ends
            i = 0 if s < 0 else len(self.P) - 2
            a, b = self.P[i], self.P[i + 1]
            d = (b - a) / (np.linalg.norm(b - a) + 1e-9)
            base = self.P[0] if s < 0 else self.P[-1]
            p = base + d * (s if s < 0 else s - self.length)
            return float(p[0]), float(p[1]), float(p[2]), math.atan2(d[1], d[0])
        i = int(np.searchsorted(self.S, s) - 1)
        i = max(0, min(i, len(self.P) - 2))
        u = (s - self.S[i]) / max(1e-9, self.S[i + 1] - self.S[i])
        p = self.P[i] + (self.P[i + 1] - self.P[i]) * u
        # heading: blended smoothly between neighbouring samples (a heading that steps at every sample makes
        # animals snap-turn and swings any camera that keeps beside them)
        h0, h1 = self._heading(i), self._heading(i + 1)
        dh = (h1 - h0 + math.pi) % (2 * math.pi) - math.pi
        return float(p[0]), float(p[1]), float(p[2]), h0 + dh * u

    def _heading(self, i):
        i = max(0, min(i, len(self.P) - 2))
        j0, j1 = max(0, i - 2), min(len(self.P) - 1, i + 3)
        d = self.P[j1] - self.P[j0]
        return math.atan2(d[1], d[0])

    def side(self, s, off, dz=0.0):
        x, y, z, h = self.pose(s)
        return x - math.sin(h) * off, y + math.cos(h) * off, z + dz, h


def straight(x0, x1, y=0.0, z=0.0):
    return Path([(x0, y, z), (x1, y, z)], step=4.0)


# ------------------------------------------------------------------ helpers

def _rng(seed, *k):
    return random.Random(hash((seed,) + k) & 0xFFFFFFFF)


def jitter(c, r, amt=8):
    return tuple(max(0, min(255, v + r.randint(-amt, amt))) for v in c)


def strip(m, path, s0, s1, off0, off1, z, color, step=6.0, jit=None):
    """A flat ribbon along the path between lateral offsets off0..off1."""
    s = s0
    while s < s1:
        e = min(s1, s + step)
        a0, a1 = path.side(s, off0), path.side(s, off1)
        b0, b1 = path.side(e, off0), path.side(e, off1)
        c = jit() if jit else color
        m.poly([(a0[0], a0[1], a0[2] + z), (b0[0], b0[1], b0[2] + z), (b1[0], b1[1], b1[2] + z), (a1[0], a1[1], a1[2] + z)], c)
        s = e
    return m


def chunks(builder, s0, s1, layer=0, order=1, shadow=False, size=CHUNK):
    """Call builder(mesh, a, b) for each chunk [a, b) and return one Obj per non-empty chunk."""
    out = []
    a = s0
    while a < s1:
        b = min(s1, a + size)
        m = Mesh()
        builder(m, a, b)
        if m.f:
            out.append(Obj(m, layer=layer, order=order, shadow=shadow))
        a = b
    return out


# ------------------------------------------------------------------ ground and terrain

def ground(seed, color, x0=-1500, x1=1500, y0=-700, y1=700, tile=40.0, var=7, far=6000):
    """Flat ground with gentle colour variation (tiles), plus a huge skirt out to the horizon."""
    objs = []
    r = random.Random(seed)
    xs = np.arange(x0, x1, tile)
    for cx in np.arange(x0, x1, CHUNK * 2):
        m = Mesh()
        for x in xs[(xs >= cx) & (xs < cx + CHUNK * 2)]:
            for y in np.arange(y0, y1, tile):
                m.poly([(x, y, 0), (x + tile, y, 0), (x + tile, y + tile, 0), (x, y + tile, 0)], jitter(color, r, var))
        objs.append(Obj(m, layer=0, order=0, shadow=False))
    sk = Mesh()
    for (a, b, c_, d) in [((-far, -far), (far, -far), (far, y0), (-far, y0)), ((-far, y1), (far, y1), (far, far), (-far, far)),
                          ((-far, y0), (x0, y0), (x0, y1), (-far, y1)), ((x1, y0), (far, y0), (far, y1), (x1, y1))]:
        sk.poly([(a[0], a[1], -0.02), (b[0], b[1], -0.02), (c_[0], c_[1], -0.02), (d[0], d[1], -0.02)], color)
    objs.insert(0, Obj(sk, layer=0, order=-1, shadow=False))
    return objs


def hills(seed, color, y_from, y_to, x0=-2500, x1=2500, height=60.0, step=60.0, snow_above=None):
    """Rolling hills (a height field) in a band away from the action."""
    r = random.Random(seed)
    ph = [r.uniform(0, 6.28) for _ in range(6)]
    def h(x, y):
        d = min(abs(y - y_from), abs(y - y_to)) / max(1.0, abs(y_to - y_from)) * 2
        e = min(1.0, d * 2.2)
        return height * e * (0.55 + 0.25 * math.sin(x / 210 + ph[0]) + 0.2 * math.sin(x / 97 + y / 130 + ph[1])
                             + 0.15 * math.sin(y / 70 + ph[2]))
    objs = []
    ys = np.arange(min(y_from, y_to), max(y_from, y_to), step)
    for cx in np.arange(x0, x1, step * 6):
        m = Mesh()
        for x in np.arange(cx, cx + step * 6, step):
            for y in ys:
                q = [(x, y), (x + step, y), (x + step, y + step), (x, y + step)]
                pts = [(a, b, h(a, b)) for a, b in q]
                zc = sum(p[2] for p in pts) / 4
                c = color
                if snow_above is not None and zc > snow_above:
                    c = (240, 244, 250)
                c = jitter(c, r, 6)
                m.poly(pts[:3], c)
                m.poly([pts[0], pts[2], pts[3]], c)
        objs.append(Obj(m, layer=1, shadow=False))
    return objs


def mountains(seed, n, y_from, y_to, x0=-4000, x1=4000, hmin=250, hmax=700, color=(110, 120, 140), snow=0.62):
    r = random.Random(seed)
    m = Mesh()
    for _ in range(n):
        x, y = r.uniform(x0, x1), r.uniform(y_from, y_to)
        h = r.uniform(hmin, hmax)
        rad = min(h * r.uniform(1.4, 2.2), abs(y) - 400)      # keep the foot of the mountain well away from the action
        if rad < 150:
            continue
        h = min(h, rad * 0.9)
        k = r.randint(6, 9)
        apex = (x + r.uniform(-50, 50), y + r.uniform(-50, 50), h)
        ring = [(x + rad * math.cos(2 * math.pi * i / k + r.uniform(-.2, .2)), y + rad * math.sin(2 * math.pi * i / k), 0) for i in range(k)]
        for i in range(k):
            a, b = ring[i], ring[(i + 1) % k]
            mid_a = tuple(a[j] + (apex[j] - a[j]) * snow for j in range(3))
            mid_b = tuple(b[j] + (apex[j] - b[j]) * snow for j in range(3))
            cc = jitter(color, r, 10)
            m.poly([a, b, mid_b, mid_a], cc)
            m.poly([mid_a, mid_b, apex], (240, 244, 250) if snow < 1 else cc)
        R._fix_outwards(m, (x, y, h * 0.2), 2 * k)
    return [Obj(m, layer=1, shadow=False)]


# ------------------------------------------------------------------ roads and rails

def road(path, width=7.0, kind="asphalt", s0=None, s1=None, markings=True, kerb=True, seed=0, center=True):
    s0 = -400 if s0 is None else s0
    s1 = path.length + 400 if s1 is None else s1
    base = {"asphalt": (78, 80, 88), "dirt": (150, 122, 88), "snow": (196, 200, 210), "city": (70, 72, 80)}[kind]
    r = random.Random(seed)
    jit = (lambda: jitter(base, r, 4))
    objs = chunks(lambda m, a, b: strip(m, path, a, b, -width / 2, width / 2, 0.02, base, jit=jit), s0, s1, order=1)
    if kerb and kind in ("asphalt", "city"):
        kc = (170, 168, 162)
        objs += chunks(lambda m, a, b: (strip(m, path, a, b, width / 2, width / 2 + (3.0 if kind == "city" else 0.6), 0.06, kc),
                                       strip(m, path, a, b, -width / 2 - (3.0 if kind == "city" else 0.6), -width / 2, 0.06, kc)),
                       s0, s1, order=1)
    if markings and kind in ("asphalt", "city"):
        def marks(m, a, b):
            s = math.ceil(a / 12) * 12
            while center and s < b:
                strip(m, path, s, s + 5, -0.08, 0.08, 0.05, (240, 222, 120), step=5)
                s += 12
            strip(m, path, a, b, width / 2 - 0.25, width / 2 - 0.12, 0.05, (236, 236, 236), step=20)
            strip(m, path, a, b, -width / 2 + 0.12, -width / 2 + 0.25, 0.05, (236, 236, 236), step=20)
        objs += chunks(marks, s0, s1, order=2)
    if kind == "snow":
        objs += snowbanks(path, width, s0, s1, seed)
    return objs


def snowbanks(path, width, s0, s1, seed):
    def b(m, a, e):
        s = a
        while s < e:
            for off in (width / 2 + 0.8, -width / 2 - 0.8):
                x, y, z, h = path.side(s, off)
                box(m, (x, y, 0.3), (8.2, 1.4, 0.6), (246, 248, 252), R=R.rot_z(h))
            s += 8
    return chunks(b, s0, s1, layer=1)


def crosswalk(path, s, width=7.0):
    m = Mesh()
    for k in range(int(width / 0.9)):
        off = -width / 2 + 0.3 + k * 0.9
        strip(m, path, s, s + 3.0, off, off + 0.5, 0.06, (238, 238, 236), step=3)
    return [Obj(m, layer=0, order=3, shadow=False)]


def rails(path, s0=None, s1=None, bed=(150, 140, 128), seed=0, viaduct=None):
    s0 = -400 if s0 is None else s0
    s1 = path.length + 400 if s1 is None else s1
    objs = chunks(lambda m, a, b: strip(m, path, a, b, -2.0, 2.0, 0.04, bed), s0, s1, order=1)

    def sleepers(m, a, b):
        s = math.ceil(a / 1.2) * 1.2
        while s < b:
            strip(m, path, s, s + 0.28, -1.3, 1.3, 0.08, (100, 78, 60), step=1)
            s += 1.2
    objs += chunks(sleepers, s0, s1, order=2)

    def rl(m, a, b):
        for off in (-0.72, 0.72):
            strip(m, path, a, b, off - 0.05, off + 0.05, 0.16, (170, 174, 184), step=10)
    objs += chunks(rl, s0, s1, order=3)
    return objs


def overhead_wires(path, s0, s1, side=3.2, every=50.0):
    def b(m, a, e):
        s = math.ceil(a / every) * every
        while s < e:
            x, y, z, h = path.side(s, side)
            box(m, (x, y, 3.5), (0.3, 0.3, 7.0), (120, 124, 132))
            x2, y2, _, _ = path.side(s, side / 2)
            box(m, (x2, y2, 6.6), (0.15, side, 0.15), (120, 124, 132), R=R.rot_z(h))
            s += every
        p0, p1 = path.side(a, 0), path.side(e, 0)
        box(m, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, 6.3), (math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 0.04, 0.04),
            (50, 50, 56), R=R.rot_z(p0[3]))
    return chunks(b, s0, s1, layer=1)


# ------------------------------------------------------------------ water

def water(y_from, y_to, x0=-6000, x1=6000, color=(46, 110, 160), shore=None):
    lo, hi = sorted((y_from, y_to))
    objs = []
    # tiles near the action (so the haze is right for each), then big panels out to the horizon
    near_lo, near_hi = max(lo, -1500), min(hi, 1500)
    tile = 60.0
    r = random.Random(int(lo * 7 + hi))
    for cx in np.arange(-1800, 1800, tile * 4):
        m = Mesh()
        for x in np.arange(cx, cx + tile * 4, tile):
            for y in np.arange(near_lo, near_hi, tile):
                y2 = min(near_hi, y + tile)
                m.poly([(x, y, 0.01), (x + tile, y, 0.01), (x + tile, y2, 0.01), (x, y2, 0.01)], jitter(color, r, 3))
        objs.append(Obj(m, layer=0, order=1, shadow=False))
    far = Mesh()
    for (a0, a1, b0, b1) in [(x0, -1800, lo, hi), (1800, x1, lo, hi), (-1800, 1800, lo, near_lo), (-1800, 1800, near_hi, hi)]:
        if a1 > a0 and b1 > b0:
            far.poly([(a0, b0, 0.008), (a1, b0, 0.008), (a1, b1, 0.008), (a0, b1, 0.008)], color)
    if far.f:
        objs.insert(0, Obj(far, layer=0, order=1, shadow=False))
    if shore:   # a sandy beach along the water's edge nearest the action (y = 0)
        s = Mesh()
        edge = hi if abs(hi) < abs(lo) else lo
        a, b = sorted((edge, edge + (18 if edge == hi else -18)))
        s.poly([(x0, a, 0.012), (x1, a, 0.012), (x1, b, 0.012), (x0, b, 0.012)], shore)
        objs.append(Obj(s, layer=0, order=1, shadow=False))
    return objs


class Ripples:
    """Moving light streaks on the water near the camera (gentle waves), rebuilt each frame."""

    def __init__(self, seed, y_from, y_to, color=(150, 196, 226), n=260, spread=260):
        r = random.Random(seed)
        self.items = [(r.uniform(-spread, spread), r.uniform(min(y_from, y_to), max(y_from, y_to)), r.uniform(1.5, 5), r.uniform(0, 6.28))
                      for _ in range(n)]
        self.color = color
        self.spread = spread

    def obj(self, t, cam_x):
        m = Mesh()
        for x, y, ln, ph in self.items:
            xx = cam_x + ((x + t * 1.5 - cam_x) % (2 * self.spread)) - self.spread
            yy = y + 0.6 * math.sin(t * 0.8 + ph)
            a = 0.5 + 0.5 * math.sin(t * 1.3 + ph)
            if a < 0.25:
                continue
            w = 0.18
            m.poly([(xx - ln / 2, yy - w, 0.03), (xx + ln / 2, yy - w, 0.03), (xx + ln / 2, yy + w, 0.03), (xx - ln / 2, yy + w, 0.03)],
                   self.color)
        return Obj(m, layer=0, order=2, shadow=False)


def wake(pos, heading, speed, length=40.0):
    """V-shaped foam trail behind a moving boat (a ground decal)."""
    m = Mesh()
    if speed < 0.5:
        return None
    x, y = pos[0], pos[1]
    c, s = math.cos(heading), math.sin(heading)
    L = min(length, speed * 4)
    for side in (1, -1):
        for k in range(6):
            u0, u1 = k / 6, (k + 0.8) / 6
            p0 = (x - c * L * u0 - s * side * L * u0 * 0.35, y - s * L * u0 + c * side * L * u0 * 0.35)
            p1 = (x - c * L * u1 - s * side * L * u1 * 0.35, y - s * L * u1 + c * side * L * u1 * 0.35)
            w = 0.4 + 1.2 * u0
            nx, ny = -s * w, c * w
            shadec = int(250 - 40 * u0)
            m.poly([(p0[0] - nx * .3, p0[1] - ny * .3, 0.04), (p1[0] - nx * .3, p1[1] - ny * .3, 0.04),
                    (p1[0] + nx * .3, p1[1] + ny * .3, 0.04), (p0[0] + nx * .3, p0[1] + ny * .3, 0.04)], (shadec, shadec, 250))
    # centre trail
    for k in range(8):
        u0, u1 = k / 8, (k + 0.7) / 8
        a = (x - c * L * u0, y - s * L * u0)
        b = (x - c * L * u1, y - s * L * u1)
        w = 0.8 + 1.5 * u0
        m.poly([(a[0] + s * w, a[1] - c * w, 0.035), (b[0] + s * w, b[1] - c * w, 0.035), (b[0] - s * w, b[1] + c * w, 0.035),
                (a[0] - s * w, a[1] + c * w, 0.035)], (200, 222, 236))
    return Obj(m, layer=0, order=3, shadow=False)


# ------------------------------------------------------------------ vegetation and buildings

def tree(m, x, y, r, kind="pine", scale=1.0, snow=False):
    s = scale * r.uniform(0.8, 1.25)
    if kind == "pine":
        cylinder(m, (x, y, 1.0 * s), 0.22 * s, 2.0 * s, (100, 72, 50), axis="z", n=5)
        g = (54, 110, 66) if not snow else (70, 110, 90)
        for k, (rad, hh, z0) in enumerate([(2.6, 4.0, 1.4), (2.0, 3.4, 3.4), (1.3, 2.8, 5.2)]):
            cone(m, (x, y, z0 * s), rad * s, hh * s, jitter(g, r, 8) if not snow else (238, 242, 248) if k == 2 else jitter(g, r, 8), n=7)
    elif kind == "round":
        cylinder(m, (x, y, 1.3 * s), 0.25 * s, 2.6 * s, (110, 80, 56), axis="z", n=5)
        sphere(m, (x, y, 4.0 * s), 2.4 * s, jitter((70, 132, 64), r, 12), n=7, scale=(1, 1, 0.9))
    elif kind == "palm":
        for k in range(5):
            box(m, (x + 0.08 * k, y, 0.8 + k * 1.4), (0.35, 0.35, 1.4), (150, 120, 80))
        for a in range(6):
            ang = a * math.pi / 3
            box(m, (x + 0.4 + math.cos(ang) * 1.6, y + math.sin(ang) * 1.6, 7.2), (3.2, 0.6, 0.08), (60, 140, 70),
                R=R.rot_z(ang) @ R.rot_y(0.35))
    elif kind == "bush":
        sphere(m, (x, y, 0.6 * s), 1.0 * s, jitter((76, 130, 66), r, 12), n=6, scale=(1.2, 1, 0.7))


def forest(seed, area, density=0.004, kinds=("pine",), snow=False, avoid=None):
    """Trees scattered over a rectangle (x0, x1, y0, y1), chunked along x."""
    x0, x1, y0, y1 = area
    r = random.Random(seed)
    n = int((x1 - x0) * (y1 - y0) * density)
    pts = []
    for _ in range(n):
        x, y = r.uniform(x0, x1), r.uniform(y0, y1)
        if avoid and avoid(x, y):
            continue
        pts.append((x, y, r.choice(kinds)))
    pts.sort()

    def b(m, a, e):
        rr = random.Random(int(a) + seed)
        for x, y, k in pts:
            if a <= x < e:
                tree(m, x, y, rr, k, snow=snow)
    return chunks(b, x0, x1, layer=1, size=160)


def house(m, x, y, r, w=8, d=7, h=3.2, yaw=0.0, wall=None, roof=None, snow=False):
    Rz = R.rot_z(yaw)
    wall = wall or r.choice([(236, 226, 200), (226, 200, 180), (240, 236, 226), (200, 214, 226), (236, 214, 170)])
    roof = (244, 246, 250) if snow else (roof or r.choice([(170, 70, 60), (90, 70, 66), (120, 60, 50), (70, 90, 120)]))
    box(m, (x, y, h / 2), (w, d, h), wall, R=Rz)
    P = np.array([(-w / 2 - 0.4, -d / 2 - 0.4, h), (w / 2 + 0.4, -d / 2 - 0.4, h), (w / 2 + 0.4, 0, h + d * 0.45),
                  (-w / 2 - 0.4, 0, h + d * 0.45), (-w / 2 - 0.4, d / 2 + 0.4, h), (w / 2 + 0.4, d / 2 + 0.4, h)]) @ Rz.T + (x, y, 0)
    m.poly([P[0], P[1], P[2], P[3]], roof)
    m.poly([P[4], P[3], P[2], P[5]], R_shade(roof, 0.9))
    m.poly([P[0], P[3], P[4]], wall)
    m.poly([P[1], P[5], P[2]], wall)
    for side in (-1, 1):   # windows and a door on the long sides
        for k in (-0.3, 0.3):
            c = np.array([w * k, side * (d / 2 + 0.01), h * 0.55]) @ Rz.T + (x, y, 0)
            box(m, tuple(c), (1.1, 0.02, 0.9), (90, 120, 150), R=Rz)
    c = np.array([0, -(d / 2 + 0.01), 1.0]) @ Rz.T + (x, y, 0)
    box(m, tuple(c), (0.9, 0.02, 2.0), (110, 80, 60), R=Rz)


def R_shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def street_houses(seed, path, s0, s1, off, gap=(14, 24), snow=False, facing=1):
    r = random.Random(seed)
    spots = []
    s = s0
    while s < s1:
        spots.append(s)
        s += r.uniform(*gap)

    def b(m, a, e):
        rr = random.Random(int(a) + seed)
        for s in spots:
            if a <= s < e:
                x, y, z, h = path.side(s, off + rr.uniform(-1, 2))
                house(m, x, y, rr, w=rr.uniform(7, 10), d=rr.uniform(6, 8), h=rr.uniform(3, 6.5), yaw=h, snow=snow)
                tx, ty, _, _ = path.side(s + 6, off - 6)
                tree(m, tx, ty, rr, rr.choice(["round", "bush"]))
    return chunks(b, s0, s1, layer=1, size=160)


def city_blocks(seed, path, s0, s1, off, depth=18.0, night=False, hmin=12, hmax=42):
    """Rows of buildings with window grids facing the street."""
    r = random.Random(seed)
    lots = []
    s = s0
    while s < s1:
        w = r.uniform(14, 26)
        lots.append((s + w / 2, w, r.uniform(hmin, hmax), r.choice([(196, 186, 170), (170, 176, 186), (210, 200, 186),
                                                                   (150, 120, 110), (200, 170, 140), (186, 196, 200)])))
        s += w + r.uniform(0.5, 3)

    def b(m, a, e):
        rr = random.Random(int(a) + seed)
        for s, w, h, c in lots:
            if not (a <= s < e):
                continue
            sign = 1 if off > 0 else -1
            x, y, z, hd = path.side(s, off + sign * depth / 2)
            Rz = R.rot_z(hd)
            box(m, (x, y, h / 2), (w, depth, h), c, R=Rz)
            box(m, (x, y, h + 0.3), (w + 0.4, depth + 0.4, 0.6), R_shade(c, 0.8), R=Rz)
            face_off = -sign * (depth / 2 + 0.02)
            for fz in np.arange(4.0, h - 1.5, 3.4):
                for fx in np.arange(-w / 2 + 1.6, w / 2 - 1.0, 2.6):
                    lit = night and rr.random() < 0.55
                    cc = (255, 214, 140) if lit else (90, 110, 130)
                    p = np.array([fx, face_off, fz]) @ Rz.T + (x, y, 0)
                    box(m, tuple(p), (1.4, 0.02, 1.7), cc, R=Rz, flags=1 if lit else 0)
            p = np.array([0, face_off, 1.6]) @ Rz.T + (x, y, 0)
            box(m, tuple(p), (min(w - 2, 8), 0.02, 2.6), (210, 196, 150) if not night else (255, 220, 160), R=Rz,
                flags=1 if night else 0)
    return chunks(b, s0, s1, layer=1, size=140)


def lamps(path, s0, s1, off, every=30, night=False):
    def b(m, a, e):
        s = math.ceil(a / every) * every
        while s < e:
            x, y, z, h = path.side(s, off)
            cylinder(m, (x, y, 3.2), 0.08, 6.4, (90, 94, 100), axis="z", n=6)
            hx, hy, _, _ = path.side(s, off - (0.8 if off > 0 else -0.8))
            box(m, (hx, hy, 6.4), (0.5, 0.3, 0.15), (250, 236, 190) if night else (200, 200, 196), flags=1 if night else 0)
            s += every
    return chunks(b, s0, s1, layer=1)


def fence(path, s0, s1, off, color=(236, 232, 220)):
    def b(m, a, e):
        s = math.ceil(a / 2.5) * 2.5
        while s < e:
            x, y, z, h = path.side(s, off)
            box(m, (x, y, 0.55), (0.12, 0.12, 1.1), color)
            s += 2.5
        for zz in (0.45, 0.9):
            p0, p1 = path.side(a, off), path.side(e, off)
            box(m, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, zz), (math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 0.06, 0.1), color,
                R=R.rot_z(p0[3]))
    return chunks(b, s0, s1, layer=1, size=60)


def poles(path, s0, s1, off, every=45):
    def b(m, a, e):
        s = math.ceil(a / every) * every
        prev = None
        while s < e:
            x, y, z, h = path.side(s, off)
            cylinder(m, (x, y, 4.5), 0.13, 9.0, (110, 86, 64), axis="z", n=6)
            box(m, (x, y, 8.6), (0.12, 1.6, 0.12), (110, 86, 64), R=R.rot_z(h))
            s += every
    return chunks(b, s0, s1, layer=1)


def fields(seed, area, colors, row=3.0, along="x"):
    """Crop fields with stripes (plough rows) as ground decals."""
    x0, x1, y0, y1 = area
    r = random.Random(seed)
    objs = []
    x = x0
    while x < x1:
        w = r.uniform(80, 160)
        base = r.choice(colors)
        m = Mesh()
        m.poly([(x, y0, 0.015), (x + w, y0, 0.015), (x + w, y1, 0.015), (x, y1, 0.015)], base)
        dark = R_shade(base, 0.86)
        y = y0
        while y < y1:
            m.poly([(x, y, 0.02), (x + w, y, 0.02), (x + w, y + row * 0.45, 0.02), (x, y + row * 0.45, 0.02)], dark)
            y += row
        objs.append(Obj(m, layer=0, order=1, shadow=False))
        x += w + 4
    return objs


def barn(m, x, y, yaw=0.0, color=(170, 50, 40), r=None):
    Rz = R.rot_z(yaw)
    box(m, (x, y, 4), (16, 11, 8), color, R=Rz)
    P = np.array([(-8.3, -5.8, 8), (8.3, -5.8, 8), (8.3, 0, 12.5), (-8.3, 0, 12.5), (-8.3, 5.8, 8), (8.3, 5.8, 8)]) @ Rz.T + (x, y, 0)
    m.poly([P[0], P[1], P[2], P[3]], (90, 84, 84))
    m.poly([P[4], P[3], P[2], P[5]], (80, 74, 74))
    m.poly([P[0], P[3], P[4]], color)
    m.poly([P[1], P[5], P[2]], color)
    c = np.array([8.02, 0, 3]) @ Rz.T + (x, y, 0)
    box(m, tuple(c), (0.02, 5, 6), (236, 230, 220), R=Rz)
    cylinder(m, tuple(np.array([-12, 0, 8]) @ Rz.T + (x, y, 0)), 3.0, 16, (196, 200, 206), axis="z", n=12)
    cone(m, tuple(np.array([-12, 0, 16]) @ Rz.T + (x, y, 0)), 3.1, 2.2, (150, 156, 164), n=12)


def haybales(m, x, y, r, n=6):
    for k in range(n):
        cylinder(m, (x + k * 3.2, y + r.uniform(-2, 2), 0.75), 0.75, 1.3, (220, 190, 110), axis="y", n=10, cap=(200, 170, 90))


def lighthouse(m, x, y):
    for k in range(6):
        z = k * 3.0
        cylinder(m, (x, y, z + 1.5), 2.2 - k * 0.15, 3.0, (240, 240, 236) if k % 2 == 0 else (200, 50, 46), axis="z", n=12,
                 r2=2.2 - (k + 1) * 0.15)
    cylinder(m, (x, y, 19.0), 1.2, 2.0, (255, 236, 170), axis="z", n=10, flags=0)
    cone(m, (x, y, 20.0), 1.6, 1.8, (60, 60, 66), n=10)
    box(m, (x, y, 18.0), (3.6, 3.6, 0.3), (60, 60, 66))


def pier(m, x0, x1, y, width=4.0, z=1.2):
    box(m, ((x0 + x1) / 2, y, z), (x1 - x0, width, 0.4), (150, 120, 90))
    for x in np.arange(x0, x1, 4.0):
        for yy in (y - width / 2 + 0.2, y + width / 2 - 0.2):
            box(m, (x, yy, z / 2), (0.3, 0.3, z + 0.6), (110, 90, 70))


def runway(x0, x1, y=0.0, width=40.0):
    m = Mesh()
    m.poly([(x0, y - width / 2, 0.02), (x1, y - width / 2, 0.02), (x1, y + width / 2, 0.02), (x0, y + width / 2, 0.02)], (84, 86, 92))
    mk = Mesh()
    for x in np.arange(x0 + 60, x1 - 60, 50):
        mk.poly([(x, y - 0.5, 0.05), (x + 25, y - 0.5, 0.05), (x + 25, y + 0.5, 0.05), (x, y + 0.5, 0.05)], (236, 236, 236))
    for k in range(8):
        for xe in (x0 + 10, x1 - 40):
            yy = y - width / 2 + 3 + k * (width - 6) / 8
            mk.poly([(xe, yy, 0.05), (xe + 30, yy, 0.05), (xe + 30, yy + 1.8, 0.05), (xe, yy + 1.8, 0.05)], (236, 236, 236))
    for yy in (y - width / 2 + 1, y + width / 2 - 1.6):
        mk.poly([(x0, yy, 0.05), (x1, yy, 0.05), (x1, yy + 0.6, 0.05), (x0, yy + 0.6, 0.05)], (236, 236, 236))
    return [Obj(m, layer=0, order=1, shadow=False), Obj(mk, layer=0, order=2, shadow=False)]


def terminal(m, x, y, length=180):
    box(m, (x, y, 7), (length, 30, 14), (210, 214, 220))
    for xx in np.arange(x - length / 2 + 3, x + length / 2 - 2, 4):
        box(m, (xx, y - 15.02, 8), (3.2, 0.02, 7), (90, 130, 160))
    cylinder(m, (x + length / 2 + 30, y, 18), 2.5, 36, (220, 222, 226), axis="z", n=10)
    cylinder(m, (x + length / 2 + 30, y, 38), 6, 5, (90, 130, 160), axis="z", n=10, r2=7)
    box(m, (x + length / 2 + 30, y, 41), (15, 15, 1), (200, 204, 210))


def station(m, path, s, length=90, off=4.2, night=False):
    for k in np.arange(0, length, 6):
        x, y, z, h = path.side(s + k, off)
        box(m, (x, y, 0.5), (6.2, 4.0, 1.0), (196, 190, 180), R=R.rot_z(h))
        xe, ye, _, _ = path.side(s + k, off - 1.7)
        box(m, (xe, ye, 1.02), (6.2, 0.4, 0.02), (240, 210, 60), R=R.rot_z(h))
        if k % 12 == 0:
            xr, yr, _, _ = path.side(s + k, off + 1.2)
            box(m, (xr, yr, 2.6), (0.2, 0.2, 3.2), (120, 124, 132))
    x, y, z, h = path.side(s + length / 2, off + 1.2)
    box(m, (x, y, 4.3), (length, 4.6, 0.3), (180, 70, 60), R=R.rot_z(h))
    x, y, z, h = path.side(s + length / 2, off + 6)
    box(m, (x, y, 3.0), (24, 7, 6), (200, 186, 160), R=R.rot_z(h))


def bridge_deck(m, path, s0, s1, width, z, color=(150, 150, 156), rail_color=(200, 60, 50)):
    s = s0
    while s < s1:
        e = min(s1, s + 6)
        a0, a1 = path.side(s, -width / 2), path.side(s, width / 2)
        b0, b1 = path.side(e, -width / 2), path.side(e, width / 2)
        m.poly([(a0[0], a0[1], z), (b0[0], b0[1], z), (b1[0], b1[1], z), (a1[0], a1[1], z)], color)
        s = e
    for k in np.arange(s0, s1, 12):
        for off in (-width / 2, width / 2):
            x, y, _, h = path.side(k, off)
            box(m, (x, y, z / 2), (1.0, 1.0, z), (160, 160, 166))
            box(m, (x, y, z + 1.2), (0.25, 0.25, 2.4), rail_color)
    for off in (-width / 2, width / 2):
        p0, p1 = path.side(s0, off), path.side(s1, off)
        box(m, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, z + 2.3), (math.hypot(p1[0] - p0[0], p1[1] - p0[1]), 0.25, 0.25),
            rail_color, R=R.rot_z(p0[3]))


def traffic_light(m, x, y, yaw, state):
    box(m, (x, y, 2.4), (0.18, 0.18, 4.8), (60, 62, 68))
    Rz = R.rot_z(yaw)
    box(m, (x, y, 4.8), (0.4, 0.4, 1.2), (40, 40, 44), R=Rz)
    cols = {"red": (255, 60, 50), "amber": (255, 190, 40), "green": (60, 230, 100)}
    for k, name in enumerate(("red", "amber", "green")):
        p = np.array([0.21, 0, 5.2 - k * 0.38]) @ Rz.T + (x, y, 0)
        on = name == state
        box(m, tuple(p), (0.02, 0.26, 0.26), cols[name] if on else (60, 60, 60), R=Rz, flags=1 if on else 0)


def helipad(m, x, y):
    cylinder(m, (x, y, 0.1), 12, 0.2, (100, 104, 110), axis="z", n=16)
    box(m, (x, y, 0.22), (1.0, 7, 0.02), (240, 240, 240))
    box(m, (x - 2.5, y, 0.22), (1.0, 7, 0.02), (240, 240, 240))
    box(m, (x + 2.5, y, 0.22), (1.0, 7, 0.02), (240, 240, 240))
    box(m, (x, y, 0.22), (5.0, 1.0, 0.02), (240, 240, 240))


def tunnel_portal(m, x, y, h, yaw=0.0, depth=60.0, color=(120, 116, 110)):
    """A rocky hill with a tunnel mouth facing -x (for a track along +x)."""
    Rz = R.rot_z(yaw)
    for k, (w, hh, dx) in enumerate([(90, 30, 30), (70, 46, 50), (40, 60, 70)]):
        p = np.array([dx, 0, hh / 2]) @ Rz.T + (x, y, 0)
        box(m, tuple(p), (depth + 40 - k * 10, w, hh), jitter(color, random.Random(k), 10), R=Rz)
    p = np.array([0.0, 0, 3.2]) @ Rz.T + (x, y, 0)
    box(m, tuple(p), (0.05, 6.0, 6.4), (24, 22, 22), R=Rz)


def cable_towers(path, s_list, h=24.0):
    m = Mesh()
    for s in s_list:
        x, y, z, hd = path.pose(s)
        box(m, (x, y, (z - h) / 2 + 2), (1.4, 1.4, z), (110, 116, 126))
        box(m, (x, y, z + 0.6), (1.0, 6.0, 0.5), (110, 116, 126), R=R.rot_z(hd))
    return [Obj(m, layer=1, shadow=True)]


def cable_line(path, s0, s1, off=0.0):
    def b(m, a, e):
        p0, p1 = path.side(a, off, 0.6), path.side(e, off, 0.6)
        d = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2)
        pitch = math.atan2(p1[2] - p0[2], d)
        box(m, mid, (math.sqrt(d * d + (p1[2] - p0[2]) ** 2), 0.06, 0.06), (40, 40, 44), R=R.ypr(p0[3], pitch))
    return chunks(b, s0, s1, layer=1, size=20)


# ------------------------------------------------------------------ sky

def cloud_sprite(seed, w=900, h=320, color=(255, 255, 255), shadow=(214, 222, 236)):
    r = random.Random(seed)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for _ in range(14):
        cx, cy = r.uniform(w * 0.15, w * 0.85), r.uniform(h * 0.4, h * 0.75)
        rr = r.uniform(h * 0.18, h * 0.36)
        d.ellipse([cx - rr * 1.3, cy - rr, cx + rr * 1.3, cy + rr], fill=shadow + (255,))
    for _ in range(14):
        cx, cy = r.uniform(w * 0.15, w * 0.85), r.uniform(h * 0.3, h * 0.62)
        rr = r.uniform(h * 0.16, h * 0.32)
        d.ellipse([cx - rr * 1.3, cy - rr, cx + rr * 1.3, cy + rr], fill=color + (255,))
    return img.filter(ImageFilter.GaussianBlur(6))


def sun_sprite(color=(255, 246, 214), size=400):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    a = np.zeros((size, size), float)
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.hypot(xx - size / 2, yy - size / 2) / (size / 2)
    a = np.clip(1.15 - d, 0, 1) ** 2.2 * 255
    a[d < 0.12] = 255
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def sky_sprites(seed, n=14, spread=5000, alt=(350, 900), dist=(900, 2800), tint=(255, 255, 255), shadow=(214, 222, 236)):
    r = random.Random(seed)
    out = []
    for i in range(n):
        ang = r.uniform(0, 2 * math.pi)
        dd = r.uniform(*dist)
        pos = (dd * math.cos(ang), dd * math.sin(ang), r.uniform(*alt))
        out.append((np.array(pos), cloud_sprite(seed + i, color=tint, shadow=shadow), r.uniform(120, 260)))
    return out


TIMES = {
    # sky top, horizon, sun dir (travelling), sun colour, sky light colour, ambient, diffuse, fog distance
    "morning": ((92, 150, 220), (232, 214, 196), (-0.6, 0.45, -0.45), (1.0, 0.9, 0.78), (0.64, 0.7, 0.8), 0.54, 0.7, 1300),
    "day": ((66, 132, 214), (196, 220, 238), (-0.35, 0.45, -0.82), (1.0, 0.97, 0.9), (0.62, 0.68, 0.78), 0.54, 0.72, 1600),
    "golden": ((88, 128, 200), (252, 200, 146), (-0.75, -0.2, -0.4), (1.0, 0.84, 0.66), (0.7, 0.66, 0.72), 0.56, 0.8, 1300),
    "dusk": ((50, 64, 128), (236, 156, 130), (-0.8, 0.1, -0.2), (0.95, 0.7, 0.6), (0.52, 0.5, 0.66), 0.5, 0.55, 1100),
    "night": ((18, 26, 56), (52, 64, 104), (0.3, 0.4, -0.6), (0.6, 0.66, 0.84), (0.42, 0.46, 0.64), 0.52, 0.45, 900),
    "snow": ((150, 166, 190), (220, 226, 234), (-0.4, 0.3, -0.7), (0.95, 0.95, 0.98), (0.72, 0.76, 0.84), 0.64, 0.5, 700),
    "overcast": ((130, 146, 170), (206, 212, 222), (-0.3, 0.4, -0.8), (0.9, 0.92, 0.96), (0.64, 0.68, 0.76), 0.56, 0.48, 900),
}


def renderer(time="day", seed=0, clouds=34):
    top, hz, sd, sc, sk, amb, dif, fog = TIMES[time]
    rd = R.Renderer(top, hz, fog_color=hz, fog_dist=fog, light=R.Light(sd, sc, sk, amb, dif), night=time == "night")
    if time != "night":
        tint = (255, 255, 255) if time not in ("golden", "dusk") else (255, 226, 206)
        shadow = (214, 222, 236) if time not in ("golden", "dusk") else (220, 170, 170)
        if time in ("snow", "overcast"):
            tint, shadow = (236, 238, 244), (196, 202, 214)
        rd.sprites = sky_sprites(seed, n=clouds, tint=tint, shadow=shadow)
        d = -np.asarray(sd, float)
        d /= np.linalg.norm(d)
        if time not in ("snow", "overcast"):
            rd.sprites.insert(0, (d * 4000, sun_sprite((255, 240, 200) if time in ("day", "morning") else (255, 200, 150)), 420))
    else:
        moon = sun_sprite((230, 236, 250), 300)
        rd.sprites = [(np.array([2500, 1500, 1400]), moon, 160)] + \
                     [(np.array([math.cos(a) * 3000, math.sin(a) * 3000, 900 + 700 * random.Random(i).random()]),
                       sun_sprite((255, 255, 255), 40), 14) for i, a in enumerate(np.linspace(0, 6.28, 70))]
    return rd
