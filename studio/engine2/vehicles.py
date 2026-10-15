"""Detailed vehicles with moving parts (engine 2). All drawn from scratch.

Every vehicle is a Vehicle: a cached, lit body plus parts that animate each frame
(rotating wheels, suspension bounce, dump beds, mixer drums, paddles, rods, gear...).
"""
import math
import random

from PIL import Image

from art import COLORS, GLASS, GLOWING, JACKET, SKIN, SS, WARM_LIGHT, light, mix, shade
from art import Pen as BasePen
from PIL import ImageDraw

SCALE = 1.0  # set per scene before building vehicles (bigger vehicles for road scenes)


class Pen(BasePen):
    """A Pen whose 1x coordinates are scaled by k (default: the current SCALE) at full sharpness."""

    def __init__(self, w, h, k=None):
        self.k = SCALE if k is None else k
        self.w, self.h = max(1, int(round(w * self.k))), max(1, int(round(h * self.k)))
        self.img = Image.new("RGBA", (self.w * SS, self.h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.f = SS * self.k

    def _p(self, pts):
        return [(x * self.f, y * self.f) for x, y in pts]

    def rect(self, x0, y0, x1, y1, fill, r=0):
        box = [x0 * self.f, y0 * self.f, x1 * self.f, y1 * self.f]
        if r:
            self.d.rounded_rectangle(box, radius=r * self.f, fill=fill)
        else:
            self.d.rectangle(box, fill=fill)

    def ellipse(self, x0, y0, x1, y1, fill):
        self.d.ellipse([x0 * self.f, y0 * self.f, x1 * self.f, y1 * self.f], fill=fill)

    def line(self, pts, fill, width):
        self.d.line(self._p(pts), fill=fill, width=max(1, int(width * self.f)), joint="curve")

    def done(self):
        return self.img.reduce(SS)  # exact 2x box downsample: same anti-aliasing, much faster


def FastPen(w, h):
    """Unscaled pen with the fast downsample (for props drawn every frame)."""
    return Pen(w, h, 1.0)

_WHEELS = {}


def wheel(r, style, angle, time):
    """Wheel image, rotated to angle (radians). Cached in 15-degree steps per spoke period."""
    spokes = {"car": 5, "truck": 6, "train": 8, "big": 10, "bike": 12}.get(style, 5)
    period = 2 * math.pi / spokes
    step = int(((angle % period) / period) * 12) % 12
    key = (r, style, step, time)
    if key in _WHEELS:
        return _WHEELS[key]
    s = int(r * 2 + 4)
    p = BasePen(s, s)
    c = r + 2
    a0 = step / 12 * period
    if style == "train":
        p.circle(c, c, r, (64, 66, 74))
        p.circle(c, c, r * 0.86, (150, 40, 36))
        for i in range(spokes):
            a = a0 + i * period
            p.line([(c, c), (c + r * 0.84 * math.cos(a), c + r * 0.84 * math.sin(a))], (96, 30, 28), max(2, r * 0.1))
        p.circle(c, c, r * 0.22, (60, 60, 66))
    else:
        p.circle(c, c, r, (44, 46, 54))
        p.circle(c, c, r * 0.9, (58, 60, 68))
        p.circle(c, c, r * 0.6, (196, 200, 208))
        p.circle(c, c, r * 0.5, (168, 172, 182))
        for i in range(spokes):
            a = a0 + i * period
            x, y = c + r * 0.36 * math.cos(a), c + r * 0.36 * math.sin(a)
            p.circle(x, y, r * 0.07 + 0.6, (110, 114, 124))
        p.circle(c, c, r * 0.16, (226, 228, 234))
    img = light(p.done(), time)
    _WHEELS[key] = img
    return img


class Vehicle:
    """body: RGBA sprite; wheels: [(cx, cy, r, style)]; ground: sprite y where tyres touch the road."""

    def __init__(self, body, wheels, ground, time, glow=None, parts=None, kind=""):
        self.k = k = SCALE
        wheels = [(cx * k, cy * k, r * k, st) for cx, cy, r, st in wheels]
        ground = ground * k
        self.body, self.wheels, self.ground, self.time = body, wheels, ground, time
        self.glow = glow if time in GLOWING else None
        self.parts = parts
        self.kind = kind
        self.w, self.h = body.size

    def sprite(self, dist, t, state=None):
        img = self.body.copy()
        if self.parts:
            self.parts(img, t, state or {}, behind=True)
        for cx, cy, r, style in self.wheels:
            wi = wheel(r, style, dist / max(1, r), self.time)
            img.alpha_composite(wi, (int(cx - wi.width / 2), int(cy - wi.height / 2)))
        if self.parts:
            self.parts(img, t, state or {}, behind=False)
        if self.glow is not None:
            img.alpha_composite(self.glow)
        return img

    def draw(self, frame, x, ground_y, dist, t, tilt=0.0, lift=0.0, state=None, flip=False, shadow=True):
        img = self.sprite(dist, t, state)
        if flip:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        ox, oy = x, ground_y - self.ground - lift
        if shadow:
            sh = _shadow(self.w)
            frame.alpha_composite(sh, (int(x), int(ground_y - sh.height // 2)))
        if abs(tilt) > 0.05:
            w0, h0 = img.size
            img = img.rotate(tilt, resample=Image.BICUBIC, expand=True)
            ox -= (img.width - w0) / 2
            oy -= (img.height - h0) / 2
        frame.alpha_composite(img, (int(ox), int(oy)))
        return ox, oy


_SH = {}


def _shadow(w):
    if w not in _SH:
        p = BasePen(w, 24)
        p.ellipse(4, 4, w - 4, 20, (20, 24, 30, 70))
        _SH[w] = p.done()
    return _SH[w]


# --------------------------------------------------------------------------- people

def person(p, x, y, s=1.0, rng=None, phase=None, jacket=False, vest=False, umbrella=None, body=None, kid=False,
           bust=False):
    """Standing or walking figure; head centre at (x, y). phase (radians) animates the legs."""
    rng = rng or random.Random(0)
    skin = rng.choice(SKIN)
    hair = rng.choice([(80, 56, 40), (40, 32, 30), (196, 150, 90), (120, 70, 40)])
    shirt = body or rng.choice([COLORS["blue"], COLORS["green"], COLORS["purple"], COLORS["teal"],
                                COLORS["red"], COLORS["yellow"], COLORS["orange"]])
    if jacket:
        shirt = JACKET
    if vest:
        shirt = (250, 170, 40)
    pants = rng.choice([(60, 70, 100), (80, 70, 60), (50, 54, 66)])
    k = 0.8 if kid else 1.0
    s = s * k
    leg = 26 * s
    hip = y + 34 * s
    if bust:  # seated in a vehicle: head and shoulders only
        p.rect(x - 9 * s, y + 9 * s, x + 9 * s, y + 24 * s, shirt, r=6 * s)
        if jacket:
            p.rect(x - 1.5 * s, y + 10 * s, x + 1.5 * s, y + 24 * s, (250, 220, 120))
        p.circle(x, y, 8 * s, skin)
        p.ellipse(x - 8 * s, y - 9 * s, x + 8 * s, y - 1 * s, hair)
        return
    if phase is None:
        p.rect(x - 6 * s, hip, x - 1 * s, hip + leg, pants, r=2 * s)
        p.rect(x + 1 * s, hip, x + 6 * s, hip + leg, pants, r=2 * s)
    else:
        for sgn in (1, -1):
            a = 0.45 * math.sin(phase) * sgn
            fx, fy = x + math.sin(a) * leg, hip + math.cos(a) * leg
            p.line([(x, hip), (fx, fy)], pants, 5 * s)
            p.rect(fx - 4 * s, fy - 2 * s, fx + 5 * s, fy + 2 * s, (50, 44, 40), r=2)
    p.rect(x - 9 * s, y + 9 * s, x + 9 * s, hip + 4 * s, shirt, r=6 * s)
    if vest:
        p.rect(x - 9 * s, y + 20 * s, x + 9 * s, y + 24 * s, (240, 240, 230))
    if jacket:
        p.rect(x - 1.5 * s, y + 10 * s, x + 1.5 * s, hip, (250, 220, 120))
    p.circle(x, y, 8 * s, skin)
    p.ellipse(x - 8 * s, y - 9 * s, x + 8 * s, y - 1 * s, hair)
    if umbrella:
        p.line([(x + 8 * s, y + 18 * s), (x + 8 * s, y - 22 * s)], (60, 60, 66), 2 * s)
        p.poly([(x - 22 * s, y - 18 * s), (x + 38 * s, y - 18 * s), (x + 8 * s, y - 40 * s)], umbrella)


# --------------------------------------------------------------------------- cars

def _lights(p, g, x, y, w, h, front=True):
    if front:
        p.rect(x, y, x + w, y + h, (255, 244, 200), r=4)
        p.rect(x + 2, y + 2, x + w * 0.5, y + h * 0.5, (255, 255, 255), r=2)
        g.poly([(x + w, y - 6), (x + w + 220, y - 30), (x + w + 220, y + h + 60), (x + w, y + h + 6)],
               (255, 232, 160, 70))
    else:
        p.rect(x, y, x + w, y + h, (226, 72, 64), r=3)
        g.rect(x - 2, y - 2, x + w + 2, y + h + 2, (255, 90, 80, 110), r=4)


def car(kind="sedan", color="red", seed=0, time="day", snow=False):
    k = SCALE
    rng = random.Random(seed)
    body = COLORS.get(color, color) if isinstance(color, str) else color
    hi, lo = mix(body, (255, 255, 255), 0.28), shade(body, 0.72)
    L = {"sedan": 330, "hatch": 300, "suv": 340, "pickup": 360, "taxi": 330, "van": 340}[kind]
    Hs, gy, r = 190, 182, 28
    p, g = Pen(L + 260, Hs), Pen(L + 260, Hs)   # extra room on the right for the headlight beam
    fw, rw = L - 70, 70
    if kind in ("suv", "van"):
        p.rect(10, 62, L - 6, 156, body, r=24)
        roof = 24 if kind == "suv" else 18
        p.rect(30 if kind == "suv" else 14, roof, L - 70 if kind == "suv" else L - 40, 80, body, r=18)
        p.poly([(L - 72, roof + 2), (L - 40, 76), (L - 72, 76)] if kind == "suv" else
               [(L - 42, roof + 2), (L - 10, 76), (L - 42, 76)], body)
        wins = [(42, roof + 10, 110, 70), (118, roof + 10, 186, 70), (194, roof + 10, L - 82, 70)] if kind == "suv" else \
               [(26, roof + 12, 100, 70), (108, roof + 12, 182, 70), (190, roof + 12, L - 56, 70)]
        for x0, y0, x1, y1 in wins:
            p.rect(x0, y0, x1, y1, GLASS, r=8)
        p.poly([(L - 70 if kind == "suv" else L - 42, roof + 10), (L - 46 if kind == "suv" else L - 16, 70),
                (L - 72 if kind == "suv" else L - 44, 70)], GLASS)
    elif kind == "pickup":
        p.rect(10, 84, L - 6, 156, body, r=20)
        p.poly([(150, 86), (176, 30), (L - 92, 30), (L - 56, 86)], body)
        p.poly([(184, 82), (200, 40), (L - 100, 40), (L - 72, 82)], GLASS)
        p.rect(14, 80, 146, 92, lo, r=4)  # truck bed rail
        p.rect(30, 66, 60, 84, (176, 120, 70), r=4)  # cargo: a couple of boxes
        p.rect(64, 72, 100, 84, (200, 150, 90), r=4)
    else:
        top = 34 if kind != "hatch" else 32
        p.rect(10, 80, L - 6, 156, body, r=26)
        back = 70 if kind != "hatch" else 34
        p.poly([(back, 84), (back + (40 if kind != "hatch" else 12), top), (L - 120, top), (L - 66, 82)], body)
        p.poly([(back + 14, 80), (back + (46 if kind != "hatch" else 22), top + 8), (L / 2 - 4, top + 8), (L / 2 - 4, 80)], GLASS)
        p.poly([(L / 2 + 4, 80), (L / 2 + 4, top + 8), (L - 126, top + 8), (L - 80, 80)], GLASS)
        if kind == "taxi":
            p.rect(L / 2 - 40, top - 22, L / 2 + 40, top, (250, 250, 240), r=6)
            p.rect(L / 2 - 30, top - 16, L / 2 + 30, top - 6, (40, 40, 40), r=3)
            for i in range(9):
                p.rect(30 + i * 30, 112, 44 + i * 30, 120, (40, 40, 40) if i % 2 else (250, 250, 240))
    # shading: shoulder highlight, rocker shadow, door seams
    p.rect(20, 86, L - 16, 94, hi, r=4)
    p.rect(16, 138, L - 10, 152, lo, r=6)
    for dx in (L * 0.48, L * 0.72):
        p.line([(dx, 90), (dx, 140)], shade(body, 0.85), 2)
        p.rect(dx - 30, 104, dx - 12, 109, shade(body, 0.6), r=2)
    # people inside, sitting up straight
    if kind in ("sedan", "taxi", "hatch", "suv", "van"):
        person(p, L * 0.62, 56 if kind not in ("suv", "van") else 50, 1.0, rng, bust=True)
        if rng.random() < 0.7:
            person(p, L * 0.38, 58 if kind not in ("suv", "van") else 50, 0.95, rng, bust=True)
    else:
        person(p, L * 0.66, 58, 1.0, rng, bust=True)
    # window shine
    p.poly([(L * 0.55, 44), (L * 0.6, 44), (L * 0.52, 78), (L * 0.47, 78)], (255, 255, 255, 70))
    # mirror, lights, bumpers, arches
    p.rect(L - 96, 70, L - 78, 84, body, r=4)
    _lights(p, g, L - 18, 98, 16, 14, True)
    _lights(p, g, 8, 98, 10, 16, False)
    p.rect(L - 22, 132, L + 2, 148, (90, 92, 100), r=6)
    p.rect(4, 132, 26, 148, (90, 92, 100), r=6)
    for cx in (rw, fw):
        p.circle(cx, gy - r, r + 6, shade(body, 0.45))
    if snow:
        p.rect(L * 0.32, 26, L * 0.66, 36, (250, 252, 255), r=5)
    wheels = [(rw, gy - r, r, "car"), (fw, gy - r, r, "car")]
    return Vehicle(light(p.done(), time), wheels, gy, time, glow=g.done(), kind="car")


def bus(color="red", seed=0, time="day", school=False):
    k = SCALE
    rng = random.Random(seed)
    body = (246, 196, 46) if school else COLORS.get(color, color)
    L, Hs, gy, r = 620, 250, 242, 32
    p, g = Pen(L + 260, Hs), Pen(L + 260, Hs)
    p.rect(10, 30, L - 8, 214, body, r=22)
    if school:
        p.rect(L - 70, 90, L - 4, 214, body, r=16)  # school bus nose
        p.rect(14, 126, L - 76, 132, (40, 40, 40))
        p.rect(14, 172, L - 10, 178, (40, 40, 40))
    for i in range(8):
        x0 = 40 + i * 66
        if x0 + 50 > L - 90:
            break
        p.rect(x0, 54, x0 + 52, 116, GLASS, r=8)
        g.rect(x0, 54, x0 + 52, 116, WARM_LIGHT + (200,), r=8)
        if rng.random() < 0.75:
            person(p, x0 + 26, 82, 0.95, rng, kid=school, bust=True)
    p.rect(L - 84, 50, L - 22 if not school else L - 76, 124, GLASS, r=10)
    person(p, L - 52 if not school else L - 104, 82, 1.0, rng, bust=True)
    p.rect(L - 140, 60, L - 96, 196, shade(body, 0.85), r=6)   # door
    p.rect(L - 136, 66, L - 100, 120, GLASS, r=4)
    if not school:
        p.rect(14, 140, L - 12, 152, mix(body, (255, 255, 255), 0.6))
        p.rect(60, 22, L - 140, 32, shade(body, 0.8), r=6)
        p.rect(L - 100, 34, L - 30, 48, (30, 30, 34), r=4)       # destination display
        p.rect(L - 96, 37, L - 34, 45, (250, 190, 70), r=2)
    _lights(p, g, L - 14, 170, 12, 16, True)
    _lights(p, g, 10, 170, 8, 18, False)
    for cx in (100, L - 150):
        p.circle(cx, gy - r, r + 7, shade(body, 0.45))
    wheels = [(100, gy - r, r, "truck"), (L - 150, gy - r, r, "truck")]

    def parts(img, t, st, behind):
        if behind or not school:
            return
        a = st.get("stop_arm", 0.0)  # school bus stop sign swings out (steady red, never flashing)
        if a > 0.01:
            q = Pen(img.width / k, img.height / k, k)
            x0, y0 = L - 170, 96
            q.line([(x0, y0), (x0 - 14 * a, y0)], (60, 60, 60), 4)
            q.circle(x0 - 34 * a, y0, 20 * a, (210, 50, 44))
            q.circle(x0 - 34 * a, y0, 14 * a, (230, 70, 60))
            img.alpha_composite(q.done())
    return Vehicle(light(p.done(), time), wheels, gy, time, glow=g.done(), parts=parts, kind="bus")


def _cab(p, g, x, gy, body, rng, h=150, w=150):
    """Truck cab facing right with its front at x + w."""
    top = gy - 40 - h
    p.rect(x, top + 30, x + w, gy - 40, body, r=14)
    p.poly([(x + 20, top + 32), (x + 34, top), (x + w - 34, top), (x + w - 6, top + 40)], body)
    p.poly([(x + 60, top + 36), (x + 66, top + 10), (x + w - 40, top + 10), (x + w - 16, top + 44), (x + 60, top + 44)], GLASS)
    person(p, x + w - 66, top + 28, 1.0, rng, bust=True)
    p.rect(x + w - 10, gy - 92, x + w + 4, gy - 50, (90, 92, 100), r=4)  # grille/bumper
    p.rect(x + 10, top + 52, x + 52, gy - 52, shade(body, 0.85), r=6)    # door
    _lights(p, g, x + w - 8, gy - 112, 12, 16, True)
    p.rect(x + w - 4, top + 40, x + w + 10, top + 44, (60, 60, 66))         # mirror arm
    p.rect(x + w + 6, top + 30, x + w + 16, top + 62, (70, 70, 76), r=3)


def truck(kind="dump", color="orange", seed=0, time="day", cargo=None):
    """kind: dump, mixer, garbage, box, tanker, carrier, plow, tow."""
    k = SCALE
    rng = random.Random(seed)
    body = COLORS.get(color, color) if isinstance(color, str) else color
    big = kind in ("box", "tanker", "carrier")
    L = {"dump": 520, "mixer": 520, "garbage": 540, "box": 860, "tanker": 860, "carrier": 900,
         "plow": 520, "tow": 820}[kind]
    Hs, gy, r = 300, 290, 34
    p, g = Pen(L + 260, Hs), Pen(L + 260, Hs)
    cab_x = L - 170
    _cab(p, g, cab_x, gy, body, rng)
    p.rect(20, gy - 76, L - 30, gy - 56, (70, 72, 80), r=6)  # chassis
    wheels = [(cab_x + 90, gy - r, r, "truck")]
    if kind in ("dump", "mixer", "garbage", "plow", "tow"):
        wheels += [(90, gy - r, r, "truck"), (170, gy - r, r, "truck")]
    else:
        wheels += [(cab_x - 40, gy - r, r, "truck"), (90, gy - r, r, "truck"), (160, gy - r, r, "truck")]
    bed_col = shade(body, 0.9)
    if kind == "garbage":
        p.rect(20, gy - 200, cab_x - 6, gy - 66, (110, 160, 110), r=12)
        for x in range(40, cab_x - 20, 48):
            p.rect(x, gy - 190, x + 8, gy - 76, (96, 140, 96))
        p.rect(28, gy - 170, cab_x - 20, gy - 150, (240, 240, 230), r=4)
    elif kind == "box":
        p.rect(14, gy - 236, cab_x - 14, gy - 70, (246, 244, 236), r=10)
        stripe = rng.choice([COLORS["blue"], COLORS["red"], COLORS["green"], COLORS["purple"]])
        p.rect(14, gy - 140, cab_x - 14, gy - 112, stripe)
        p.circle(cab_x / 2, gy - 186, 30, stripe)
    elif kind == "tanker":
        p.rect(20, gy - 200, cab_x - 20, gy - 72, (214, 218, 226), r=60)
        p.rect(20, gy - 150, cab_x - 20, gy - 132, body)
        for x in range(120, cab_x - 60, 160):
            p.rect(x, gy - 214, x + 50, gy - 198, (150, 156, 166), r=4)
    elif kind == "carrier":
        p.rect(14, gy - 150, cab_x - 10, gy - 140, (90, 94, 104))
        p.rect(14, gy - 70, cab_x - 10, gy - 62, (90, 94, 104))
        for x in range(30, cab_x - 30, 140):
            p.rect(x, gy - 240, x + 8, gy - 62, (90, 94, 104))
    elif kind == "plow":
        p.rect(30, gy - 180, cab_x - 10, gy - 70, (120, 124, 132), r=10)   # salt hopper
        p.poly([(30, gy - 180), (cab_x - 10, gy - 180), (cab_x - 30, gy - 210), (50, gy - 210)], (100, 104, 112))
        p.poly([(L + 4, gy - 110), (L + 70, gy - 140), (L + 70, gy - 10), (L + 4, gy - 30)], (240, 170, 50))
        p.rect(cab_x + 40, gy - 206, cab_x + 90, gy - 194, (250, 180, 80), r=4)  # steady amber beacon
    elif kind == "tow":
        p.rect(40, gy - 120, cab_x - 6, gy - 66, body, r=8)
        p.line([(cab_x - 20, gy - 120), (60, gy - 210), (30, gy - 150)], (70, 72, 80), 8)
    p.rect(cab_x + 100, gy - 240, cab_x + 112, gy - 170, (120, 124, 132), r=4) if kind != "plow" else None  # exhaust stack
    for cx, cy, rr, _ in wheels:
        p.circle(cx, cy, rr + 7, shade(body if not big else (90, 94, 104), 0.5))
    _lights(p, g, 12, gy - 110, 8, 18, False)
    mini = []
    if kind == "carrier":  # the cars it carries: count them!
        cols = ["red", "blue", "yellow", "green", "white", "purple", "orange", "teal"]
        for i in range(6):
            deck = gy - 152 if i < 3 else gy - 72
            c = car(rng.choice(["sedan", "hatch"]), cols[(i + seed) % len(cols)], seed + i, "day").body
            c = c.resize((c.width * 37 // 100, c.height * 37 // 100), Image.LANCZOS)
            mini.append((c, int((40 + (i % 3) * 205) * k), int(deck * k) - c.height + 4))
    body_img = p.done()
    for c, x, y in mini:
        body_img.alpha_composite(c, (x, y))

    def parts(img, t, st, behind):
        if behind or kind not in ("dump", "mixer", "garbage", "plow"):
            return
        if kind == "plow" and not st.get("salt", 0):
            return
        q = Pen(img.width / k, img.height / k, k)
        if kind == "dump" and not behind:
            a = st.get("bed", 0.0)  # 0..1 tipping
            ang = -math.radians(48) * a
            px, py = 40, gy - 70
            pts = [(0, 0), (cab_x - 50, 0), (cab_x - 50, -110), (0, -130)]
            rp = [(px + x * math.cos(ang) - y * math.sin(ang), py + x * math.sin(ang) + y * math.cos(ang)) for x, y in pts]
            q.poly(rp, bed_col)
            q.line(rp[:2] + [rp[2]], shade(bed_col, 0.8), 6)
            dirt = st.get("dirt", 1.0)
            if dirt > 0.02:
                dp = [(10, -100 - 30 * dirt), (cab_x - 70, -110 - 20 * dirt), (cab_x - 60, -104), (10, -104)]
                rd = [(px + x * math.cos(ang) - y * math.sin(ang), py + x * math.sin(ang) + y * math.cos(ang)) for x, y in dp]
                q.poly(rd, (140, 100, 66))
        if kind == "mixer" and not behind:
            cx, cy = (cab_x) / 2 + 10, gy - 150
            q.ellipse(cx - 160, cy - 80, cx + 160, cy + 80, (232, 232, 226))
            ph = (t * 1.6) % 1.0
            for i in range(5):  # spiral stripes travel along the turning drum
                x = cx - 150 + ((i + ph) / 5) * 300
                half = 80 * math.sqrt(max(0.0, 1 - ((x - cx) / 160) ** 2))
                q.line([(x - 14, cy - half), (x + 14, cy + half)], body, 12)
            q.poly([(cx + 140, cy - 40), (cx + 190, cy - 70), (cx + 196, cy - 50), (cx + 150, cy - 20)], (200, 200, 196))
        if kind == "garbage" and not behind:
            a = st.get("arm", 0.0)  # lifts a bin up and over the top
            ang = math.radians(-160 * a)
            bx, by = cab_x - 4, gy - 80
            ex, ey = bx + 70 * math.cos(ang), by + 70 * math.sin(ang)
            q.line([(bx, by), (ex, ey)], (70, 72, 80), 10)
            if st.get("bin", 0) and a > 0:
                q.rect(ex - 22, ey - 50, ex + 22, ey, st.get("bin_color", (60, 120, 200)), r=4)
        if kind == "plow" and not behind and st.get("salt", 0):
            r2 = random.Random(int(t * 24))
            for _ in range(26):
                sx, sy = 30 - r2.uniform(0, 90), gy - 60 + r2.uniform(-20, 60)
                q.circle(sx, sy, 3, (246, 246, 250))
        img.alpha_composite(q.done())

    v = Vehicle(light(body_img, time), wheels, gy, time, glow=g.done(), parts=parts, kind="truck")
    v.cab_x = cab_x * k
    return v


def excavator(color="yellow", seed=0, time="day"):
    k = SCALE
    body = COLORS.get(color, color)
    L, Hs, gy = 520, 420, 410
    p = Pen(L + 200, Hs)
    p.rect(60, gy - 60, 360, gy, (60, 62, 70), r=30)       # tracks
    p.rect(140, gy - 190, 360, gy - 64, body, r=14)         # house
    p.rect(260, gy - 260, 350, gy - 150, body, r=10)        # cab
    p.rect(272, gy - 248, 340, gy - 170, GLASS, r=6)
    person(p, 304, gy - 222, 1.0, random.Random(seed), bust=True)
    p.rect(120, gy - 170, 160, gy - 80, shade(body, 0.8), r=6)  # counterweight

    def parts(img, t, st, behind):
        if behind:
            return
        q = Pen(img.width / k, img.height / k, k)
        for i in range(10):  # tread links
            ph = (st.get("track", 0.0) / 30 + i / 10) % 1.0
            x = 80 + ph * 260
            q.rect(x, gy - 8, x + 10, gy - 2, (100, 102, 110))
        dig = st.get("dig", 0.0)  # 0..1 cycle: reach, scoop, lift, dump
        a1 = math.radians(-50 + 30 * math.sin(2 * math.pi * dig))
        a2 = math.radians(60 + 40 * math.sin(2 * math.pi * dig + 1.2))
        x0, y0 = 340, gy - 140
        x1, y1 = x0 + 200 * math.cos(a1), y0 + 200 * math.sin(a1)
        x2, y2 = x1 + 170 * math.cos(a1 + a2), y1 + 170 * math.sin(a1 + a2)
        q.line([(x0, y0), (x1, y1)], body, 26)
        q.line([(x1, y1), (x2, y2)], shade(body, 0.9), 20)
        q.poly([(x2 - 30, y2 - 10), (x2 + 30, y2 - 10), (x2 + 20, y2 + 40), (x2 - 20, y2 + 36)], (80, 82, 90))
        if math.sin(2 * math.pi * dig + 1.2) > 0.2:
            q.ellipse(x2 - 24, y2 - 16, x2 + 24, y2 + 4, (140, 100, 66))
        img.alpha_composite(q.done())
    return Vehicle(light(p.done(), time), [], gy, time, parts=parts, kind="excavator")


# --------------------------------------------------------------------------- boats
# Boats use `ground` as the waterline inside the sprite. Everyone aboard wears a life jacket.

def boat(kind="sailboat", color="red", seed=0, time="day"):
    k = SCALE
    rng = random.Random(seed)
    body = COLORS.get(color, color) if isinstance(color, str) else color
    g = None
    if kind == "sailboat":
        L, Hs, wl = 340, 420, 380
        p = Pen(L, Hs)
        p.poly([(20, wl - 44), (L - 10, wl - 44), (L - 50, wl + 18), (60, wl + 18)], body)
        p.rect(18, wl - 52, L - 8, wl - 40, (250, 250, 248), r=4)
        p.rect(L / 2 - 4, 30, L / 2 + 4, wl - 50, (120, 96, 72))
        p.poly([(L / 2 + 8, 44), (L / 2 + 8, wl - 66), (L - 26, wl - 66)], (252, 250, 244))       # jib
        p.poly([(L / 2 - 8, 60), (L / 2 - 8, wl - 66), (44, wl - 66)], mix(body, (255, 255, 255), 0.5))  # main
        p.line([(L / 2 - 8, wl - 64), (40, wl - 64)], (120, 96, 72), 5)                          # boom
        for i, px in enumerate((96, 150, 250)):
            person(p, px, wl - 84, 1.0, rng, jacket=True, bust=True)
        parts_flag = (L / 2, 30)
    elif kind == "speedboat":
        L, Hs, wl = 380, 200, 168
        p = Pen(L, Hs)
        p.poly([(10, wl - 60), (L - 40, wl - 60), (L - 4, wl - 76), (L - 60, wl + 14), (30, wl + 14)], body)
        p.rect(10, wl - 64, L - 30, wl - 54, (250, 250, 248), r=4)
        p.poly([(200, wl - 64), (238, wl - 104), (250, wl - 104), (226, wl - 64)], GLASS)
        for px in (120, 180):
            person(p, px, wl - 92, 1.0, rng, jacket=True, bust=True)
        p.rect(4, wl - 66, 22, wl - 20, (70, 72, 80), r=4)  # outboard motor
        parts_flag = None
    elif kind == "trawler":
        L, Hs, wl = 520, 380, 330
        p = Pen(L, Hs)
        p.poly([(20, wl - 80), (L - 10, wl - 100), (L - 60, wl + 20), (50, wl + 20)], body)
        p.rect(20, wl - 88, L - 10, wl - 76, (250, 250, 248), r=4)
        p.rect(300, wl - 190, 440, wl - 86, (246, 244, 236), r=10)
        for wx in (318, 362, 404):
            p.rect(wx, wl - 170, wx + 28, wl - 140, GLASS, r=5)
        p.rect(150, 40, 160, wl - 86, (110, 90, 70))
        p.line([(155, 60), (40, wl - 120)], (110, 90, 70), 5)
        p.line([(155, 60), (290, wl - 150)], (110, 90, 70), 4)
        for j in range(8):  # hanging net
            p.line([(40 + j * 6, wl - 120 + j * 4), (60 + j * 10, wl - 86)], (150, 140, 120, 200), 2)
        person(p, 220, wl - 116, 1.0, rng, jacket=True, bust=True)
        parts_flag = (155, 40)
    elif kind == "container":
        L, Hs, wl = 1300, 420, 370
        p = Pen(L, Hs)
        p.poly([(10, wl - 110), (L - 10, wl - 110), (L - 80, wl + 30), (60, wl + 30)], COLORS["navy"])
        p.rect(10, wl - 30, L - 50, wl - 10, (190, 70, 60))
        p.rect(60, wl - 280, 220, wl - 110, (246, 244, 236), r=6)   # bridge tower
        for wy in (wl - 260, wl - 220, wl - 180):
            p.rect(76, wy, 204, wy + 22, GLASS, r=4)
        p.rect(110, wl - 330, 160, wl - 280, (200, 70, 60), r=4)    # funnel
        cols = [COLORS[c] for c in ("red", "blue", "yellow", "green", "orange", "teal", "purple")]
        for row in range(3):
            for col in range(13):
                c = cols[(row * 5 + col * 3 + seed) % len(cols)]
                x0, y0 = 250 + col * 78, wl - 150 - row * 52
                p.rect(x0, y0, x0 + 74, y0 + 48, c, r=2)
                for j in range(1, 6):
                    p.line([(x0 + j * 12, y0 + 4), (x0 + j * 12, y0 + 44)], shade(c, 0.85), 2)
        parts_flag = None
    elif kind == "tug":
        L, Hs, wl = 380, 300, 260
        p = Pen(L, Hs)
        g = Pen(L, Hs)
        p.poly([(14, wl - 70), (L - 10, wl - 70), (L - 40, wl + 18), (40, wl + 18)], body)
        p.rect(10, wl - 78, L - 6, wl - 64, (60, 60, 66), r=6)
        for tx in (40, 120, 200, 280, 340):
            p.circle(tx, wl - 50, 13, (40, 40, 44))
        p.rect(140, wl - 150, 290, wl - 76, COLORS["white"], r=10)
        p.rect(180, wl - 200, 280, wl - 148, COLORS["white"], r=8)
        for wx in (190, 230):
            p.rect(wx, wl - 190, wx + 34, wl - 162, GLASS, r=5)
            g.rect(wx, wl - 190, wx + 34, wl - 162, WARM_LIGHT + (210,), r=5)
        person(p, 248, wl - 176, 0.9, rng, jacket=True, bust=True)
        p.rect(100, wl - 210, 128, wl - 76, (60, 60, 66))
        p.rect(96, wl - 210, 132, wl - 196, body)
        parts_flag = None
    elif kind == "ferry":
        L, Hs, wl = 760, 360, 300
        p = Pen(L, Hs)
        g = Pen(L, Hs)
        p.poly([(10, wl - 90), (L - 10, wl - 90), (L - 50, wl + 24), (50, wl + 24)], COLORS["navy"])
        p.rect(10, wl - 100, L - 10, wl - 86, COLORS["white"], r=6)
        p.rect(200, wl - 220, 620, wl - 150, COLORS["white"], r=12)    # passenger deck
        for wx in range(220, 600, 40):
            p.rect(wx, wl - 206, wx + 26, wl - 180, GLASS, r=5)
            g.rect(wx, wl - 206, wx + 26, wl - 180, WARM_LIGHT + (210,), r=5)
        for px in range(240, 600, 80):
            person(p, px, wl - 196, 0.85, rng, jacket=True, bust=True)
        p.rect(380, wl - 270, 440, wl - 220, body, r=6)
        p.rect(30, wl - 150, L - 30, wl - 96, (210, 214, 222))           # car deck
        cols = ["red", "blue", "yellow", "green", "white", "orange"]
        img0 = p.done()
        for i in range(6):
            c = car(rng.choice(["sedan", "hatch", "van"]), cols[i], seed + i, "day").body
            c = c.resize((c.width * 30 // 100, c.height * 30 // 100), Image.LANCZOS)
            img0.alpha_composite(c, (int((60 + i * 110) * k), int((wl - 98) * k) - c.height + 2))
        return Vehicle(light(img0, time), [], wl, time, glow=g.done(), kind="boat")
    elif kind == "kayak":
        L, Hs, wl = 260, 200, 150
        p = Pen(L, Hs)
        p.poly([(6, wl - 16), (L - 6, wl - 16), (L - 40, wl + 6), (40, wl + 6)], body)
        p.ellipse(100, wl - 28, 160, wl - 12, (60, 60, 66))
        person(p, 130, wl - 54, 1.0, rng, jacket=True, bust=True)
        parts_flag = None
    elif kind == "steamer":
        L, Hs, wl = 760, 460, 400
        p = Pen(L, Hs)
        g = Pen(L, Hs)
        p.poly([(10, wl - 70), (L - 10, wl - 70), (L - 40, wl + 20), (40, wl + 20)], (246, 244, 236))
        p.rect(10, wl - 78, L - 10, wl - 64, COLORS["red"], r=4)
        for deck in range(2):
            y0 = wl - 150 - deck * 80
            p.rect(80 + deck * 60, y0, L - 80 - deck * 60, y0 + 76, (250, 248, 242), r=6)
            for wx in range(100 + deck * 60, L - 100 - deck * 60, 46):
                p.rect(wx, y0 + 16, wx + 28, y0 + 46, GLASS, r=5)
                g.rect(wx, y0 + 16, wx + 28, y0 + 46, WARM_LIGHT + (210,), r=5)
                if rng.random() < 0.5:
                    person(p, wx + 14, y0 + 30, 0.8, rng, jacket=True, bust=True)
        for fx in (320, 420):
            p.rect(fx, wl - 380, fx + 34, wl - 230, (50, 50, 56))
            p.rect(fx - 6, wl - 390, fx + 40, wl - 374, (200, 160, 60))
        parts_flag = None
    else:  # rowboat with someone fishing
        L, Hs, wl = 280, 240, 190
        p = Pen(L, Hs)
        person(p, 140, wl - 70, 1.1, rng, jacket=True, bust=True)
        p.line([(150, wl - 50), (260, wl - 170)], (120, 90, 60), 3)
        p.line([(260, wl - 170), (262, wl)], (230, 230, 230, 200), 1)
        p.poly([(10, wl - 30), (L - 10, wl - 30), (L - 50, wl + 10), (50, wl + 10)], body)
        p.rect(8, wl - 36, L - 8, wl - 26, shade(body, 0.75), r=4)
        parts_flag = None
    img = p.done()

    def parts(img2, t, st, behind):
        if behind:
            return
        q = Pen(img2.width / k, img2.height / k, k)
        if parts_flag:
            fx, fy = parts_flag
            pts = [(fx, fy), (fx, fy + 24)]
            for j in range(5, -1, -1):
                pts.append((fx - 8 - j * 9, fy + 22 - 1 + 4 * math.sin(t * 6 + j)))
            for j in range(6):
                pts.append((fx - 8 - j * 9, fy + 2 + 4 * math.sin(t * 6 + j)))
            q.poly(pts, (230, 70, 64))
        if kind == "kayak":
            a = math.sin(t * 3.2) * 0.9
            cx, cy = 130, wl - 34
            dx, dy = 90 * math.cos(a), 34 * math.sin(a)
            q.line([(cx - dx, cy - dy), (cx + dx, cy + dy)], (90, 70, 50), 4)
            for sx, sy in ((cx - dx, cy - dy), (cx + dx, cy + dy)):
                q.ellipse(sx - 12, sy - 5, sx + 12, sy + 5, COLORS["yellow"])
        if kind == "steamer":
            cx, cy, r = L / 2, wl - 40, 70
            q.circle(cx, cy, r + 6, (200, 60, 54))
            ang = st.get("dist", 0) / 70
            for j in range(10):
                a = ang + j * math.pi / 5
                q.line([(cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a))], (120, 40, 36), 7)
            q.circle(cx, cy, 14, (80, 30, 26))
            q.ellipse(cx - r - 10, cy - r - 14, cx + r + 10, cy - 10, (246, 244, 236))  # wheel box (top half)
        img2.alpha_composite(q.done())
    return Vehicle(light(img, time), [], wl, time, glow=(g.done() if g else None), parts=parts, kind="boat")


# --------------------------------------------------------------------------- aircraft

def airliner(color="blue", seed=0, time="day", jumbo=False, cargo=False):
    k = SCALE
    accent = COLORS.get(color, color)
    L, Hs, gy = (820 if jumbo else 720), 300, 286
    p, g = Pen(L, Hs), Pen(L, Hs)
    white = (246, 246, 242)
    top, bot = 120, 196
    p.rect(60, top, L - 70, bot, white, r=38)
    p.ellipse(L - 150, top, L - 4, bot + 2, white)            # nose
    p.poly([(60, top + 8), (10, top - 100), (78, top - 100), (170, top + 4)], accent)   # tail fin
    p.circle(60, top - 40, 18, mix(accent, white, 0.4))
    p.poly([(70, top + 46), (8, top + 22), (66, top + 22), (140, top + 46)], shade(white, 0.92))  # stabiliser
    if jumbo:
        p.rect(L - 360, top - 40, L - 110, top + 30, white, r=30)
        p.ellipse(L - 200, top - 40, L - 60, top + 50, white)
        for wx in range(L - 340, L - 160, 26):
            p.rect(wx, top - 24, wx + 12, top - 12, GLASS, r=4)
    p.rect(60, bot - 26, L - 80, bot - 18, accent)            # cheat line
    if not cargo:
        for wx in range(170, L - 160, 26):
            p.rect(wx, top + 22, wx + 12, top + 38, GLASS, r=5)
            g.rect(wx, top + 22, wx + 12, top + 38, WARM_LIGHT + (210,), r=5)
    else:
        p.rect(170, top + 20, L - 170, top + 30, shade(white, 0.9))
    for dx in (160, L - 200):
        p.rect(dx, top + 14, dx + 26, bot - 30, shade(white, 0.9), r=6)   # doors
    p.poly([(L - 92, top + 18), (L - 46, top + 26), (L - 30, top + 44), (L - 92, top + 44)], GLASS)  # cockpit
    p.poly([(L * 0.38, bot - 30), (L * 0.6, bot - 30), (L * 0.46, bot + 24), (L * 0.36, bot + 24)], shade(white, 0.88))  # wing root
    p.rect(L * 0.42, bot + 4, L * 0.54, bot + 40, (190, 194, 204), r=16)           # engine
    p.ellipse(L * 0.52, bot + 4, L * 0.56, bot + 40, (120, 124, 134))
    g.circle(14, top - 98, 7, (255, 255, 240, 220))
    body = light(p.done(), time)
    mx = [(L * 0.5, 22), (L - 150, 18)]  # main and nose gear (x, wheel radius)

    def parts(img, t, st, behind):
        if behind:
            return
        q = Pen(img.width / k, img.height / k, k)
        gear = st.get("gear", 1.0)          # 1 = down, 0 = up (folds into the belly)
        flaps = st.get("flaps", 0.0)
        if flaps > 0.01:
            fx0, fx1 = L * 0.36, L * 0.46
            q.poly([(fx0, bot + 22), (fx1, bot + 22), (fx1 - 8, bot + 22 + 26 * flaps), (fx0 - 8, bot + 22 + 30 * flaps)],
                   shade(white, 0.8))
        if gear > 0.02:
            for gx, wr in mx:
                leg = (gy - bot - wr * 2 + 4) * gear
                q.rect(gx - 4, bot - 6, gx + 4, bot + leg, (100, 100, 108))
                q.circle(gx, bot + leg + wr, wr, (44, 46, 54))
                q.circle(gx, bot + leg + wr, wr * 0.45, (180, 184, 192))
        if cargo and st.get("nose", 0) > 0.01:  # nose door swings up for loading
            a = st.get("nose", 0)
            q.poly([(L - 150, top + 6 - 60 * a), (L - 4, top + 30 - 120 * a), (L - 4, bot - 70 * a), (L - 150, bot - 4)],
                   (230, 230, 226))
        img.alpha_composite(light(q.done(), time))
    return Vehicle(body, [], gy, time, glow=g.done(), parts=parts, kind="plane")


def small_plane(color="red", seed=0, time="day", floats=False):
    k = SCALE
    rng = random.Random(seed)
    body = COLORS.get(color, color)
    L, Hs, gy = 380, 200, 186 if not floats else 196
    p = Pen(L, Hs)
    p.rect(40, 86, 330, 130, body, r=22)
    p.poly([(40, 90), (6, 40), (40, 40), (90, 90)], body)
    p.rect(110, 70, 250, 80, shade(body, 0.75), r=4)    # high wing, edge-on
    p.line([(150, 80), (130, 100)], (90, 90, 96), 4)
    p.poly([(230, 86), (260, 86), (284, 104), (230, 104)], GLASS)
    person(p, 244, 92, 0.8, rng, bust=True)
    p.rect(326, 92, 344, 124, (80, 82, 90), r=6)
    p.rect(60, 114, 320, 118, (250, 250, 250))
    if floats:
        p.line([(150, 130), (140, 170)], (90, 90, 96), 4)
        p.line([(260, 130), (270, 170)], (90, 90, 96), 4)
        p.poly([(90, 170), (330, 170), (350, 180), (330, 190), (100, 190)], (240, 240, 236))
        wheels = []
    else:
        p.line([(170, 130), (160, 160)], (90, 90, 96), 4)
        p.line([(280, 130), (286, 160)], (90, 90, 96), 4)
        wheels = [(160, 166, 18, "car"), (286, 168, 16, "car")]

    def parts(img, t, st, behind):
        if behind:
            return
        q = Pen(img.width / k, img.height / k, k)
        q.ellipse(338, 54, 354, 162, (210, 214, 224, 110))   # propeller blur disc
        a = t * 9.0
        q.line([(346, 108 - 50 * math.cos(a)), (346, 108 + 50 * math.cos(a))], (70, 70, 76, 90), 5)
        q.circle(346, 108, 7, (200, 60, 50))
        img.alpha_composite(q.done())
    return Vehicle(light(p.done(), time), wheels, gy, time, parts=parts, kind="plane")


def ground_vehicle(kind="baggage", color="yellow", seed=0, time="day"):
    """Airport helpers: baggage (tug + carts), fuel, stairs, catering, deicer, pushback."""
    k = SCALE
    rng = random.Random(seed)
    body = COLORS.get(color, color)
    if kind == "baggage":
        L, Hs, gy = 620, 150, 140
        p = Pen(L, Hs)
        p.rect(L - 110, 64, L - 10, 120, body, r=10)
        p.rect(L - 70, 30, L - 20, 66, GLASS, r=6)
        person(p, L - 46, 46, 0.9, rng, vest=True, bust=True)
        wheels = [(L - 90, 124, 16, "car"), (L - 30, 124, 16, "car")]
        cols = [COLORS[c] for c in ("red", "blue", "green", "purple", "orange", "teal", "pink")]
        for c in range(3):
            x0 = 20 + c * 160
            p.rect(x0, 82, x0 + 140, 120, (150, 156, 166), r=6)
            p.line([(x0 + 140, 110), (x0 + 160, 110)], (90, 90, 96), 4)
            for b in range(4):  # suitcases: count the colours
                bc = cols[(c * 4 + b + seed) % len(cols)]
                p.rect(x0 + 6 + b * 33, 52 + (b % 2) * 8, x0 + 34 + b * 33, 82, bc, r=4)
                p.rect(x0 + 16 + b * 33, 46 + (b % 2) * 8, x0 + 24 + b * 33, 52 + (b % 2) * 8, shade(bc, 0.7), r=2)
            wheels += [(x0 + 24, 128, 12, "car"), (x0 + 116, 128, 12, "car")]
        return Vehicle(light(p.done(), time), wheels, gy, time, kind="ground")
    if kind == "pushback":
        L, Hs, gy = 260, 120, 112
        p = Pen(L, Hs)
        p.rect(10, 40, L - 10, 90, body, r=10)
        p.rect(L - 80, 14, L - 24, 42, GLASS, r=5)
        person(p, L - 52, 30, 0.8, rng, vest=True, bust=True)
        p.rect(0, 60, 14, 70, (90, 90, 96))
        return Vehicle(light(p.done(), time), [(60, 94, 18, "truck"), (200, 94, 18, "truck")], gy, time, kind="ground")
    L, Hs, gy = 420, 380, 370
    p = Pen(L, Hs)
    p.rect(L - 140, gy - 160, L - 20, gy - 50, body, r=12)
    p.rect(L - 90, gy - 150, L - 30, gy - 100, GLASS, r=6)
    person(p, L - 60, gy - 130, 0.9, rng, vest=True, bust=True)
    p.rect(20, gy - 70, L - 20, gy - 50, (80, 82, 90), r=6)
    wheels = [(80, gy - 26, 26, "truck"), (L - 70, gy - 26, 26, "truck")]
    if kind == "fuel":
        p.rect(20, gy - 170, L - 150, gy - 70, (230, 232, 236), r=40)
        p.rect(20, gy - 128, L - 150, gy - 112, COLORS["red"])
    elif kind == "stairs":
        for j in range(9):
            p.rect(30 + j * 26, gy - 80 - j * 26, 70 + j * 26, gy - 70 - j * 26, (200, 204, 212))
        p.line([(30, gy - 100), (270, gy - 330)], (150, 154, 162), 5)
    elif kind in ("catering", "deicer"):
        p.rect(20, gy - 100, L - 150, gy - 70, (150, 156, 166), r=6)

    def parts(img, t, st, behind):
        if behind:
            return
        q = Pen(img.width / k, img.height / k, k)
        if kind == "catering":
            lift = st.get("lift", 0.0)
            top = gy - 100 - 140 * lift
            for j in range(4):  # scissor lift
                y0 = gy - 100 - (140 * lift) * j / 4
                y1 = gy - 100 - (140 * lift) * (j + 1) / 4
                q.line([(40, y0), (L - 170, y1)], (110, 114, 124), 4)
                q.line([(L - 170, y0), (40, y1)], (110, 114, 124), 4)
            q.rect(24, top - 110, L - 150, top, (246, 246, 240), r=6)
            q.rect(24, top - 70, L - 150, top - 56, COLORS["blue"])
        if kind == "deicer":
            a = st.get("boom", 0.5)
            bx, by = 80, gy - 100
            ex, ey = bx + 200 * math.cos(-0.6 - 0.6 * a), by + 200 * math.sin(-0.6 - 0.6 * a)
            q.line([(bx, by), (ex, ey)], (200, 204, 212), 10)
            q.rect(ex - 24, ey - 30, ex + 24, ey + 4, body, r=6)
            person(q, ex, ey - 22, 0.7, rng, vest=True, bust=True)
            if st.get("spray", 0):
                r2 = random.Random(int(t * 24))
                for _ in range(40):
                    d = r2.uniform(10, 160)
                    q.circle(ex + d, ey + d * 0.4 + r2.uniform(-12, 12), 3 + d / 50, (250, 160, 60, 160))
        img.alpha_composite(light(q.done(), time))
    return Vehicle(light(p.done(), time), wheels, gy, time, parts=parts, kind="ground")


def marshaller(p, x, y, t, rng, s=1.2):
    """Ground crew guiding a plane with orange wands (arms move slowly up and down)."""
    person(p, x, y, s, rng, vest=True)
    a = 0.6 + 0.5 * math.sin(t * 2.4)
    for sgn in (-1, 1):
        ex, ey = x + sgn * 26 * s, y + 14 * s - 30 * s * a
        p.line([(x + sgn * 8 * s, y + 14 * s), (ex, ey)], (250, 170, 40), 5 * s)
        p.line([(ex, ey), (ex + sgn * 6 * s, ey - 26 * s)], (250, 120, 40), 6 * s)


# --------------------------------------------------------------------------- trains

def loco(kind="steam", color="red", seed=0, time="day"):
    k = SCALE
    rng = random.Random(seed)
    body = COLORS.get(color, color)
    if kind == "steam":
        L, Hs, gy = 460, 300, 290
        p, g = Pen(L, Hs), Pen(L, Hs)
        p.rect(140, 120, L - 30, 214, body, r=30)                 # boiler
        p.rect(L - 60, 110, L - 16, 220, (50, 50, 56), r=10)       # smokebox
        p.rect(L - 110, 56, L - 76, 122, (50, 50, 56), r=4)        # chimney
        p.rect(L - 118, 50, L - 68, 62, (50, 50, 56), r=4)
        p.ellipse(260, 96, 310, 130, (200, 160, 60))               # dome
        p.rect(20, 70, 150, 220, shade(body, 0.85), r=10)          # cab
        p.rect(10, 60, 160, 76, (50, 50, 56), r=6)
        p.rect(40, 92, 100, 140, GLASS, r=6)
        g.rect(40, 92, 100, 140, WARM_LIGHT + (210,), r=6)
        person(p, 70, 116, 1.0, rng, bust=True)
        p.rect(L - 140, 210, L - 60, 250, (70, 72, 80), r=8)        # cylinder
        p.poly([(L - 16, 230), (L + 0, 280), (L - 40, 280)], (90, 90, 96))  # cow catcher
        p.circle(L - 30, 150, 14, (255, 240, 190))
        g.circle(L - 30, 150, 22, (255, 240, 190, 140))
        p.rect(20, 214, L - 20, 230, (60, 60, 66))
        drivers = [(170, 240, 46), (276, 240, 46)]
        wheels = [(c, y, r, "train") for c, y, r in drivers] + [(L - 50, 262, 26, "train"), (70, 262, 26, "train")]

        def parts(img, t, st, behind):
            if behind:
                return
            q = Pen(img.width / k, img.height / k, k)
            a = st.get("dist", 0.0) / 46
            pins = [(c + 26 * math.cos(a), 240 + 26 * math.sin(a)) for c, _, _ in drivers]
            q.line(pins, (190, 194, 204), 9)                                   # coupling rod
            cx = L - 120 + 18 * math.cos(a)
            q.line([pins[-1], (cx, 230)], (170, 174, 184), 8)                  # main rod to the piston
            q.rect(cx - 10, 224, cx + 30, 236, (150, 154, 164), r=3)
            img.alpha_composite(light(q.done(), time))
        v = Vehicle(light(p.done(), time), wheels, gy, time, glow=g.done(), parts=parts, kind="train")
        v.chimney = ((L - 93) * k, 50 * k)
        return v
    if kind == "highspeed":
        L, Hs, gy = 640, 240, 230
        p, g = Pen(L, Hs), Pen(L, Hs)
        p.poly([(10, 60), (L - 260, 60), (L - 20, 160), (L - 6, 190), (10, 190)], (248, 248, 246))
        p.rect(10, 150, L - 10, 166, body)
        p.poly([(L - 240, 72), (L - 150, 72), (L - 110, 104), (L - 200, 104)], GLASS)
        person(p, L - 170, 92, 0.85, rng, bust=True)
        for wx in range(40, L - 300, 50):
            p.rect(wx, 84, wx + 34, 116, GLASS, r=6)
            g.rect(wx, 84, wx + 34, 116, WARM_LIGHT + (200,), r=6)
            if rng.random() < 0.6:
                person(p, wx + 17, 104, 0.8, rng, bust=True)
        p.line([(200, 60), (250, 20), (300, 20)], (90, 90, 96), 4)          # pantograph
        p.rect(10, 190, L - 30, 204, (70, 72, 80))
        g.circle(L - 20, 176, 8, (255, 240, 190, 220))
        wheels = [(80, 214, 16, "car"), (140, 214, 16, "car"), (L - 200, 214, 16, "car"), (L - 140, 214, 16, "car")]
        return Vehicle(light(p.done(), time), wheels, gy, time, glow=g.done(), kind="train")
    # diesel / metro
    L, Hs, gy = 440, 240, 230
    p, g = Pen(L, Hs), Pen(L, Hs)
    p.rect(10, 50, L - 10, 196, body, r=18)
    p.rect(L - 110, 70, L - 24, 118, GLASS, r=8)
    person(p, L - 64, 98, 0.95, rng, bust=True)
    p.rect(10, 140, L - 10, 152, (250, 250, 246))
    for gx in range(40, L - 150, 30):
        p.rect(gx, 70, gx + 16, 118, shade(body, 0.8), r=3)                  # grilles
    p.circle(L - 18, 172, 9, (255, 240, 190))
    g.circle(L - 18, 172, 18, (255, 240, 190, 150))
    wheels = [(70, 210, 20, "train"), (130, 210, 20, "train"), (L - 130, 210, 20, "train"), (L - 70, 210, 20, "train")]
    return Vehicle(light(p.done(), time), wheels, gy, time, glow=g.done(), kind="train")


def railcar(kind="coach", color="red", seed=0, time="day", number=None):
    k = SCALE
    rng = random.Random(seed)
    body = COLORS.get(color, color) if isinstance(color, str) else color
    L, Hs, gy = 420, 240, 230
    p, g = Pen(L, Hs), Pen(L, Hs)
    if kind in ("coach", "metro", "sleeper"):
        p.rect(10, 50, L - 10, 196, body, r=14)
        p.rect(10, 140, L - 10, 150, mix(body, (255, 255, 255), 0.5))
        for wx in range(30, L - 50, 56):
            p.rect(wx, 74, wx + 40, 120, GLASS, r=6)
            g.rect(wx, 74, wx + 40, 120, WARM_LIGHT + (220,), r=6)
            if rng.random() < 0.65:
                person(p, wx + 20, 98, 0.85, rng, bust=True)
        if kind == "metro":
            p.rect(L / 2 - 30, 64, L / 2 + 30, 190, shade(body, 0.85), r=4)
    elif kind == "container":
        p.rect(10, 170, L - 10, 190, (80, 82, 90))
        for k, c in enumerate((body, mix(body, (255, 255, 255), 0.3))):
            y0 = 110 - k * 64
            p.rect(20, y0, L - 20, y0 + 60, c, r=2)
            for x in range(34, L - 30, 16):
                p.line([(x, y0 + 4), (x, y0 + 56)], shade(c, 0.85), 2)
        if number is not None:
            from PIL import ImageDraw, ImageFont
            from scenes import FONT
    elif kind == "tanker":
        p.rect(10, 170, L - 10, 190, (80, 82, 90))
        p.rect(20, 70, L - 20, 176, body, r=52)
        p.rect(L / 2 - 20, 56, L / 2 + 20, 72, shade(body, 0.8), r=4)
    elif kind == "hopper":
        p.poly([(20, 60), (L - 20, 60), (L - 60, 180), (60, 180)], body)
        for x in range(60, L - 40, 60):
            p.line([(x, 64), (x, 170)], shade(body, 0.85), 4)
        p.ellipse(30, 40, L - 30, 80, (150, 110, 70))
    elif kind == "logs":
        p.rect(10, 170, L - 10, 190, (80, 82, 90))
        for i, yy in enumerate((140, 112, 140, 84, 112)):
            x0 = 24 + (i % 2) * 8
            p.rect(x0, yy, L - x0, yy + 28, (160, 112, 70), r=14)
            p.circle(L - x0 - 10, yy + 14, 11, (214, 170, 120))
        for x in (20, L - 28):
            p.rect(x, 70, x + 8, 176, (80, 82, 90))
    elif kind == "caboose":
        p.rect(20, 80, L - 20, 196, body, r=10)
        p.rect(L / 2 - 60, 30, L / 2 + 60, 84, body, r=8)
        p.rect(L / 2 - 44, 42, L / 2 + 44, 74, GLASS, r=6)
        g.rect(L / 2 - 44, 42, L / 2 + 44, 74, WARM_LIGHT + (220,), r=6)
        g.circle(14, 150, 12, (255, 90, 80, 160))
    else:  # boxcar
        p.rect(10, 60, L - 10, 190, body, r=6)
        p.rect(L / 2 - 60, 74, L / 2 + 60, 186, shade(body, 0.85), r=4)
        for x in range(30, L - 20, 30):
            p.line([(x, 66), (x, 186)], shade(body, 0.9), 2)
    p.rect(0, 166, 14, 176, (60, 60, 66))
    img = p.done()
    if number is not None:  # big friendly number for counting
        from PIL import ImageDraw, ImageFont
        from scenes import FONT
        d = ImageDraw.Draw(img)
        f = ImageFont.truetype(FONT, 64)
        txt = str(number)
        l, t0, r, b = f.getbbox(txt)
        d.text(((L - (r - l)) / 2 - l, 80 - t0), txt, font=f, fill=(255, 255, 255))
    wheels = [(60, 210, 20, "train"), (110, 210, 20, "train"), (L - 110, 210, 20, "train"), (L - 60, 210, 20, "train")]
    return Vehicle(light(img, time), wheels, gy, time, glow=g.done(), kind="train")


class Train:
    """A whole train: engine at the front (right), cars behind, all wheels turning together."""

    def __init__(self, engine, cars, gap=12):
        self.units = list(cars)[::-1] + [engine]
        self.engine = engine
        self.gap = gap
        self.offsets = []
        x = 0
        for u in self.units:
            self.offsets.append(x)
            x += u.w - (260 if u is not engine and u.w > 500 else 0) * 0 + gap
        self.length = x
        self.ground = max(u.ground for u in self.units)

    def draw(self, frame, x, ground_y, dist, t, tilt=0.0, state=None):
        st = dict(state or {})
        st["dist"] = dist
        for u, ox in zip(self.units, self.offsets):
            if x + ox > 1920 + 20 or x + ox + u.w < -20:
                continue
            u.draw(frame, x + ox, ground_y, dist, t, state=st, shadow=False)

    def front(self):
        return self.offsets[-1] + self.engine.w
