"""Drawing toolkit: supersampled pen, palettes, time-of-day lighting, vehicle sprites.

Everything is drawn from scratch with Pillow; no external images are used.
"""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1920, 1080
SS = 2  # supersampling factor for smooth edges

COLORS = {
    "red": (214, 92, 86), "blue": (84, 132, 201), "yellow": (240, 199, 92),
    "green": (104, 168, 112), "orange": (236, 150, 84), "purple": (150, 116, 192),
    "teal": (72, 168, 166), "pink": (233, 144, 172), "white": (244, 242, 236),
    "navy": (60, 78, 128), "cream": (246, 232, 200), "grey": (150, 156, 164),
}
JACKET = (245, 128, 40)  # life-jacket orange
SKIN = [(241, 205, 175), (204, 152, 112), (150, 104, 74), (233, 186, 150)]
GLASS = (190, 222, 240)
WARM_LIGHT = (255, 214, 140)

# sky top, sky horizon, light multiplier, sun/moon (x, y, radius, color) or None
TIMES = {
    "dawn":    ((124, 140, 196), (250, 202, 176), (246, 222, 214), (0.78, 0.40, 70, (255, 226, 180))),
    "morning": ((138, 188, 230), (222, 236, 246), (252, 252, 255), (0.18, 0.22, 60, (255, 246, 214))),
    "day":     ((108, 172, 226), (204, 230, 246), (255, 255, 255), (0.82, 0.16, 58, (255, 248, 220))),
    "golden":  ((148, 158, 212), (255, 206, 152), (255, 230, 204), (0.70, 0.40, 76, (255, 214, 150))),
    "dusk":    ((72, 82, 142), (232, 152, 142), (206, 186, 206), (0.25, 0.42, 64, (250, 176, 140))),
    "night":   ((26, 36, 72), (62, 72, 118), (122, 134, 176), (0.80, 0.18, 44, (238, 236, 214))),
}
GLOWING = {"dusk", "night"}


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


class Pen:
    """Draws in 1x coordinates onto a supersampled RGBA canvas."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def rect(self, x0, y0, x1, y1, fill, r=0):
        box = [x0 * SS, y0 * SS, x1 * SS, y1 * SS]
        if r:
            self.d.rounded_rectangle(box, radius=r * SS, fill=fill)
        else:
            self.d.rectangle(box, fill=fill)

    def ellipse(self, x0, y0, x1, y1, fill):
        self.d.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=fill)

    def circle(self, x, y, r, fill):
        self.ellipse(x - r, y - r, x + r, y + r, fill)

    def poly(self, pts, fill):
        self.d.polygon(self._p(pts), fill=fill)

    def line(self, pts, fill, width):
        self.d.line(self._p(pts), fill=fill, width=max(1, int(width * SS)), joint="curve")

    def done(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def light(img, time):
    """Apply time-of-day lighting to an RGBA image (alpha preserved)."""
    mult = TIMES[time][2]
    if mult == (255, 255, 255):
        return img
    r, g, b, a = img.split()
    rgb = ImageChops.multiply(Image.merge("RGB", (r, g, b)), Image.new("RGB", img.size, mult))
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def soft_glow(size, color, radius):
    """A soft round glow sprite (used for sun, moon, lamps)."""
    s = size
    g = Image.new("RGBA", (s, s), color + (0,))
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).ellipse([s / 2 - radius, s / 2 - radius, s / 2 + radius, s / 2 + radius], fill=150)
    g.putalpha(m.filter(ImageFilter.GaussianBlur(radius * 0.6)))
    return g


def cloud(rng, w, h, color=(255, 255, 255), alpha=235):
    p = Pen(w, h)
    c = color + (alpha,)
    n = rng.randint(4, 6)
    for i in range(n):
        cx = w * (0.18 + 0.64 * i / (n - 1))
        r = h * rng.uniform(0.28, 0.42) * (1.15 if 0 < i < n - 1 else 0.85)
        p.circle(cx, h * 0.62 - r * 0.3, r, c)
    p.rect(w * 0.12, h * 0.55, w * 0.88, h * 0.9, c, r=h * 0.17)
    return p.done()


# --------------------------------------------------------------------- people

def person(p, x, y, s, rng, jacket=False):
    """Tiny friendly figure: head at (x, y) with scale s; optional life jacket."""
    skin = rng.choice(SKIN)
    body = JACKET if jacket else rng.choice([COLORS["blue"], COLORS["green"], COLORS["purple"], COLORS["teal"]])
    p.rect(x - 7 * s, y + 7 * s, x + 7 * s, y + 24 * s, body, r=5 * s)
    if jacket:
        p.rect(x - 1.2 * s, y + 8 * s, x + 1.2 * s, y + 23 * s, (250, 220, 120))
    p.circle(x, y, 7 * s, skin)
    p.ellipse(x - 7 * s, y - 8 * s, x + 7 * s, y - 1 * s, rng.choice([(80, 56, 40), (40, 32, 30), (196, 150, 90)]))


# ------------------------------------------------------------------- vehicles
# Each returns (sprite, glow) at 1x. glow may be None. Sprites face right.

def car(color, kind="sedan", seed=0, snow=False):
    rng = random.Random(seed)
    w, h = 300, 150
    p, g = Pen(w, h), Pen(w, h)
    body = COLORS[color]
    dark = shade(body, 0.8)
    if kind == "van":
        p.rect(24, 30, 270, 112, body, r=22)
        for wx in (60, 120, 180):
            p.rect(wx, 42, wx + 48, 74, GLASS, r=8)
    elif kind == "hatch":
        p.rect(30, 68, 272, 114, body, r=22)
        p.poly([(64, 70), (98, 32), (214, 32), (246, 70)], body)
        p.poly([(80, 68), (104, 40), (152, 40), (152, 68)], GLASS)
        p.poly([(160, 68), (160, 40), (208, 40), (230, 68)], GLASS)
    elif kind == "plow":
        p.rect(60, 34, 262, 112, (240, 170, 60), r=16)
        p.rect(170, 44, 240, 78, GLASS, r=8)
        p.poly([(262, 74), (296, 64), (296, 118), (262, 112)], (120, 124, 132))
        p.rect(78, 18, 120, 34, (240, 170, 60), r=4)
        p.rect(84, 22, 114, 30, (250, 196, 110), r=3)  # steady beacon, never flashing
        p.rect(66, 46, 158, 98, shade((240, 170, 60), 0.85), r=10)
    else:  # sedan
        p.rect(18, 70, 282, 114, body, r=22)
        p.poly([(70, 72), (108, 30), (196, 30), (238, 72)], body)
        p.poly([(86, 70), (114, 38), (148, 38), (148, 70)], GLASS)
        p.poly([(156, 70), (156, 38), (192, 38), (222, 70)], GLASS)
    if kind != "plow":
        # driver and passenger, sitting upright
        person(p, 186 if kind != "van" else 220, 46, 1.0, rng)
        if kind != "van":
            person(p, 128, 48, 0.9, rng)
        p.rect(36, 92, 266, 98, dark, r=3)
    if snow:
        p.rect(100, 26, 210, 34, (250, 252, 255), r=4)
    p.rect(268, 80, 284, 92, (255, 240, 190), r=4)  # headlight
    p.rect(14, 82, 26, 94, (230, 90, 80), r=3)  # tail light
    for wx in (78, 226):
        p.circle(wx, 116, 26, (52, 54, 62))
        p.circle(wx, 116, 12, (196, 200, 208))
    g.poly([(284, 78), (300, 70), (300, 104), (284, 96)], (255, 236, 170, 120))
    return p.done(), g.done()


def boat(color, kind="sailboat", seed=0):
    rng = random.Random(seed)
    body = COLORS[color]
    if kind == "sailboat":
        w, h = 300, 330
        p = Pen(w, h)
        p.poly([(30, 248), (270, 248), (240, 300), (64, 300)], body)
        p.rect(30, 240, 270, 252, (250, 250, 250), r=4)
        p.rect(146, 30, 154, 248, (110, 90, 70))
        p.poly([(158, 40), (158, 232), (262, 232)], (250, 248, 240))
        p.poly([(142, 70), (142, 232), (60, 232)], mix(body, (255, 255, 255), 0.55))
        person(p, 100, 214, 1.0, rng, jacket=True)
        person(p, 200, 214, 1.0, rng, jacket=True)
        return p.done(), None
    if kind == "rowboat":
        w, h = 260, 150
        p = Pen(w, h)
        person(p, 128, 64, 1.1, rng, jacket=True)
        p.poly([(18, 92), (242, 92), (214, 132), (48, 132)], body)
        p.rect(18, 86, 242, 96, shade(body, 0.75), r=4)
        p.line([(80, 100), (36, 136)], (150, 110, 70), 5)
        p.line([(176, 100), (222, 136)], (150, 110, 70), 5)
        return p.done(), None
    if kind == "tugboat":
        w, h = 360, 230
        p, g = Pen(w, h), Pen(w, h)
        p.poly([(20, 150), (340, 150), (310, 204), (50, 204)], body)
        p.rect(14, 144, 346, 156, (60, 60, 66), r=6)
        for tx in (40, 300):
            p.circle(tx, 168, 12, (40, 40, 44))  # bumper tyres
        p.rect(130, 80, 270, 146, COLORS["white"], r=10)
        p.rect(180, 40, 262, 84, COLORS["white"], r=8)
        for wx in (150, 196, 228):
            p.rect(wx, 98, wx + 26, 122, GLASS, r=5)
            g.rect(wx, 98, wx + 26, 122, WARM_LIGHT + (200,), r=5)
        p.rect(192, 52, 248, 72, GLASS, r=5)
        person(p, 220, 60, 0.8, rng)
        p.rect(92, 52, 118, 146, (60, 60, 66))
        p.rect(88, 52, 122, 64, body)
        return p.done(), g.done()
    # ferry
    w, h = 620, 270
    p, g = Pen(w, h), Pen(w, h)
    p.poly([(20, 170), (600, 170), (566, 240), (60, 240)], COLORS["navy"])
    p.rect(14, 162, 606, 176, COLORS["white"], r=6)
    p.rect(70, 92, 540, 166, COLORS["white"], r=12)
    p.rect(150, 46, 470, 96, COLORS["white"], r=12)
    p.rect(70, 140, 540, 150, body)
    for wx in range(96, 520, 44):
        p.rect(wx, 104, wx + 28, 128, GLASS, r=6)
        g.rect(wx, 104, wx + 28, 128, WARM_LIGHT + (210,), r=6)
    for wx in range(176, 450, 52):
        p.rect(wx, 58, wx + 32, 80, GLASS, r=6)
    p.rect(300, 14, 340, 50, body, r=6)
    for px in (110, 190, 410, 470):
        person(p, px, 104, 0.8, rng, jacket=True)
    return p.done(), g.done()


def airplane(color, kind="airliner", seed=0, gear=False):
    body = COLORS["white"]
    accent = COLORS[color]
    if kind == "prop":
        w, h = 340, 150
        p = Pen(w, h)
        p.rect(40, 62, 300, 104, accent, r=20)
        p.poly([(40, 66), (8, 22), (40, 22), (80, 66)], accent)
        p.rect(130, 74, 230, 88, shade(accent, 0.7), r=6)  # wing seen edge-on
        p.poly([(220, 64), (262, 64), (276, 82), (220, 82)], GLASS)
        p.rect(298, 66, 312, 100, (90, 90, 96), r=4)
        p.ellipse(306, 34, 318, 132, (200, 200, 210, 120))  # soft prop disc
        p.line([(160, 104), (150, 128)], (70, 70, 76), 4)
        p.line([(250, 104), (256, 128)], (70, 70, 76), 4)
        p.circle(150, 132, 10, (52, 54, 62))
        p.circle(256, 132, 10, (52, 54, 62))
        return p.done(), None
    w, h = 620, 210
    p, g = Pen(w, h), Pen(w, h)
    p.rect(40, 84, 580, 140, body, r=28)
    p.ellipse(540, 84, 610, 140, body)
    p.poly([(40, 90), (8, 18), (60, 18), (130, 90)], accent)
    p.poly([(60, 112), (20, 92), (60, 92), (110, 112)], shade(body, 0.92))
    p.poly([(250, 120), (380, 120), (300, 176), (240, 176)], shade(body, 0.9))
    p.rect(300, 150, 360, 172, (190, 194, 204), r=10)  # engine
    p.rect(40, 122, 580, 130, accent)
    for wx in range(150, 520, 30):
        p.rect(wx, 98, wx + 14, 112, GLASS, r=5)
        g.rect(wx, 98, wx + 14, 112, WARM_LIGHT + (200,), r=5)
    p.poly([(560, 92), (594, 98), (600, 112), (560, 112)], GLASS)
    g.circle(14, 40, 6, (255, 255, 230, 200))  # steady tail light
    if gear:
        for gx in (200, 520):
            p.rect(gx - 3, 136, gx + 3, 192, (90, 90, 96))
            p.circle(gx, 196, 12, (52, 54, 62))
    return p.done(), g.done()


def helicopter(color, seed=0, rotor_phase=0.0):
    rng = random.Random(seed)
    w, h = 420, 200
    p = Pen(w, h)
    body = COLORS[color]
    p.rect(30, 82, 210, 98, body, r=8)  # tail boom
    p.poly([(16, 50), (34, 50), (48, 96), (30, 96)], body)
    p.circle(26, 70, 18, (200, 200, 210, 110))  # tail rotor disc
    p.ellipse(170, 50, 356, 150, body)
    p.poly([(290, 60), (346, 86), (350, 116), (290, 116)], GLASS)
    person(p, 300, 84, 0.95, rng)
    p.rect(254, 36, 268, 54, (80, 80, 88))
    half = 190 * (0.92 + 0.08 * math.cos(rotor_phase))
    p.ellipse(261 - half, 28, 261 + half, 40, (90, 90, 100, 120))  # rotor blur, steady
    p.line([(200, 150), (190, 176)], (80, 80, 88), 5)
    p.line([(320, 150), (330, 176)], (80, 80, 88), 5)
    p.rect(160, 172, 360, 180, (80, 80, 88), r=4)
    return p.done(), None


BALLOON_SCHEMES = {
    "stripes": [COLORS["red"], COLORS["yellow"]],
    "rainbow": [COLORS[c] for c in ("red", "orange", "yellow", "green", "blue", "purple")],
    "ocean": [COLORS["teal"], COLORS["white"], COLORS["blue"]],
    "sunset": [COLORS["pink"], COLORS["orange"], COLORS["purple"]],
    "meadow": [COLORS["green"], COLORS["yellow"], COLORS["white"]],
}


def balloon(scheme, seed=0):
    rng = random.Random(seed)
    w, h = 240, 340
    p = Pen(w, h)
    cols = BALLOON_SCHEMES[scheme]
    n = 8
    cx, cy, rx, ry = 120, 118, 108, 114
    for i in range(n):
        a0 = -1 + 2 * i / n
        a1 = -1 + 2 * (i + 1) / n
        pts = []
        for k in range(15):
            yy = -1 + 2 * k / 14
            pts.append((cx + rx * a0 * math.sqrt(max(0.0, 1 - yy * yy)) * (1 if yy < 0.4 else 1 - (yy - 0.4)), cy + ry * yy))
        for k in range(14, -1, -1):
            yy = -1 + 2 * k / 14
            pts.append((cx + rx * a1 * math.sqrt(max(0.0, 1 - yy * yy)) * (1 if yy < 0.4 else 1 - (yy - 0.4)), cy + ry * yy))
        p.poly(pts, cols[i % len(cols)])
    p.poly([(84, 222), (156, 222), (140, 248), (100, 248)], shade(cols[0], 0.8))
    for x0, x1 in ((96, 102), (144, 138)):
        p.line([(x0, 246), (x1 + (0 if x0 < 120 else 0), 286)], (110, 90, 70), 2)
    person(p, 108, 270, 0.9, rng)
    person(p, 132, 270, 0.9, rng)
    p.rect(92, 284, 148, 322, (168, 120, 74), r=6)
    p.rect(92, 296, 148, 300, (140, 98, 60))
    return p.done(), None


def locomotive(color, kind="steam", seed=0):
    rng = random.Random(seed)
    body = COLORS[color]
    w, h = 330, 200
    p, g = Pen(w, h), Pen(w, h)
    if kind == "steam":
        p.rect(110, 72, 300, 146, body, r=16)
        p.rect(18, 40, 124, 146, shade(body, 0.85), r=10)
        p.rect(36, 56, 78, 92, GLASS, r=6)
        g.rect(36, 56, 78, 92, WARM_LIGHT + (210,), r=6)
        person(p, 58, 70, 0.95, rng)
        p.rect(10, 30, 132, 44, (60, 60, 66), r=6)
        p.rect(236, 32, 262, 74, (60, 60, 66), r=4)
        p.rect(230, 28, 268, 38, (60, 60, 66), r=4)
        p.circle(300, 104, 14, (255, 240, 190))
        p.poly([(300, 146), (326, 168), (300, 168)], (90, 90, 96))
        for wx, r in ((60, 22), (150, 28), (226, 28)):
            p.circle(wx, 164, r, (52, 54, 62))
            p.circle(wx, 164, r * 0.45, (200, 70, 60))
        p.rect(140, 160, 240, 168, (170, 170, 176), r=3)
    else:  # modern passenger train cab
        p.rect(10, 50, 290, 156, body, r=14)
        p.poly([(260, 50), (300, 70), (326, 140), (290, 156), (260, 156)], body)
        p.poly([(270, 62), (300, 76), (314, 110), (270, 110)], GLASS)
        person(p, 284, 86, 0.9, rng)
        for wx in range(30, 240, 52):
            p.rect(wx, 74, wx + 36, 104, GLASS, r=6)
            g.rect(wx, 74, wx + 36, 104, WARM_LIGHT + (210,), r=6)
        p.rect(10, 124, 300, 132, COLORS["white"])
        for wx in (60, 110, 220, 270):
            p.circle(wx, 164, 16, (52, 54, 62))
    g.circle(316, 120, 8, (255, 240, 190, 220))
    return p.done(), g.done()


def carriage(color, kind="steam", seed=0, cargo=None):
    rng = random.Random(seed)
    body = COLORS[color]
    w, h = 300, 200
    p, g = Pen(w, h), Pen(w, h)
    if cargo:
        p.rect(10, 120, 290, 150, (90, 90, 96), r=6)
        if cargo == "logs":
            for i, yy in enumerate((100, 80, 100)):
                p.rect(24 + i * 6, yy, 276 - i * 6, yy + 20, (150, 104, 66), r=10)
        else:
            p.rect(24, 64, 276, 120, body, r=8)
            for xx in range(40, 270, 30):
                p.rect(xx, 70, xx + 4, 114, shade(body, 0.85))
    else:
        top = 56 if kind == "steam" else 50
        p.rect(10, top, 290, 156, body, r=12)
        if kind == "steam":
            p.rect(4, top - 10, 296, top + 4, (70, 70, 76), r=6)
        for wx in range(28, 270, 50):
            p.rect(wx, top + 18, wx + 36, top + 50, GLASS, r=6)
            g.rect(wx, top + 18, wx + 36, top + 50, WARM_LIGHT + (200,), r=6)
            if rng.random() < 0.55:
                person(p, wx + 18, top + 32, 0.8, rng)
        p.rect(10, 128, 290, 134, COLORS["white"] if kind != "steam" else shade(body, 0.75))
    for wx in (50, 92, 208, 250):
        p.circle(wx, 164, 15, (52, 54, 62))
    p.rect(0, 140, 12, 148, (70, 70, 76))
    return p.done(), (None if cargo else g.done())


def train(color, kind, n_cars, seed, cargo=None):
    """Compose a whole train into one wide sprite."""
    loco, lglow = locomotive(color, kind, seed)
    cars = [carriage(COLORS_CYCLE[(i + seed) % len(COLORS_CYCLE)] if cargo else color, kind, seed + i, cargo)
            for i in range(n_cars)]
    total = loco.width + sum(c.width for c, _ in cars)
    img = Image.new("RGBA", (total, loco.height), (0, 0, 0, 0))
    glow = Image.new("RGBA", (total, loco.height), (0, 0, 0, 0))
    x = 0
    for c, cg in reversed(cars):
        img.alpha_composite(c, (x, 0))
        if cg:
            glow.alpha_composite(cg, (x, 0))
        x += c.width
    img.alpha_composite(loco, (x, 0))
    glow.alpha_composite(lglow, (x, 0))
    return img, glow


COLORS_CYCLE = ["red", "blue", "yellow", "green", "orange", "teal"]


def puff(r, alpha=120):
    p = Pen(int(r * 2 + 4), int(r * 2 + 4))
    p.circle(r + 2, r + 2, r, (245, 245, 245, alpha))
    return p.done()


def duck(seed=0):
    p = Pen(60, 44)
    c = (250, 214, 90) if seed % 2 else (244, 240, 230)
    p.ellipse(4, 18, 46, 40, c)
    p.circle(42, 14, 9, c)
    p.poly([(49, 12), (58, 15), (49, 18)], (240, 150, 60))
    p.circle(44, 12, 1.6, (30, 30, 30))
    return p.done()


def bird_soft(seed=0):
    p = Pen(40, 20)
    p.line([(2, 12), (12, 4), (20, 11), (28, 4), (38, 12)], (90, 96, 110), 2.5)
    return p.done()
