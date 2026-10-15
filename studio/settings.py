"""Landscape builders. Each returns a Setting: static sky + scrolling parallax layers + props.

Layers tile seamlessly every TW pixels, so the camera can travel forever without repeating
a cut: scenery scrolls continuously instead of being re-used clip by clip.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from art import COLORS, GLOWING, TIMES, WARM_LIGHT, H, W, Pen, cloud, light, mix, shade, soft_glow

TW = 3840


class Layer:
    def __init__(self, img, y, depth, drift=0.0):
        self.img, self.y, self.depth, self.drift = img, y, depth, drift

    def crop(self, cam, t=0.0):
        off = int(cam * self.depth + self.drift * t) % TW
        return self.img.crop((off, 0, off + W, self.img.height))


class Setting:
    def __init__(self, name, time):
        self.name, self.time = name, time
        self.bg = None
        self.layers = []       # drawn behind the vehicle, back to front
        self.front = []        # drawn in front of the vehicle
        self.props = []        # static (img, (x, y)) drawn behind the vehicle (camera-locked)
        self.front_props = []
        self.clouds = []       # (img, x0, y, speed)
        self.snow = False
        self.baseline = 900    # y of the vehicle's bottom edge
        self.water = False


def periodic(rng, k_max=7):
    terms = [(k, rng.uniform(0, 2 * math.pi), rng.uniform(0.3, 1.0) / k) for k in range(1, k_max + 1)]
    norm = sum(a for _, _, a in terms)
    return lambda x: sum(a * math.sin(2 * math.pi * k * x / TW + ph) for k, ph, a in terms) / norm


def make_layer(height, time, draw, atmos=0.0):
    """draw(pen, glow, rep) where rep(x) yields wrap-around copies of x."""
    p, g = Pen(TW, height), Pen(TW, height)

    def rep(x):
        return (x - TW, x, x + TW)

    draw(p, g, rep)
    base = light(p.done(), time)
    if atmos:
        horizon = TIMES[time][1]
        haze = Image.new("RGBA", base.size, horizon + (0,))
        haze.putalpha(base.getchannel("A").point(lambda a: int(a * atmos)))
        base.alpha_composite(haze)
    if time in GLOWING:
        base.alpha_composite(g.done())
    ext = Image.new("RGBA", (TW + W, height), (0, 0, 0, 0))
    ext.paste(base, (0, 0))
    ext.paste(base.crop((0, 0, W, height)), (TW, 0))
    return ext


def sky(time, rng, stars=None):
    top, bot, _, sun = TIMES[time]
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        grad.putpixel((0, y), mix(top, bot, min(1.0, (y / H) ** 0.8 * 1.15)))
    img = grad.resize((W, H)).convert("RGBA")
    if stars or (stars is None and time == "night"):
        d = ImageDraw.Draw(img)
        for _ in range(140):
            x, y = rng.uniform(0, W), rng.uniform(0, H * 0.5)
            r = rng.choice((1, 1, 1.5))
            d.ellipse([x - r, y - r, x + r, y + r], fill=(240, 240, 220, 200))
    sx, sy, sr, sc = sun
    x, y = int(W * sx), int(H * sy)
    glow = soft_glow(int(sr * 12), sc, sr * 2)
    img.alpha_composite(glow, (x - glow.width // 2, y - glow.height // 2))
    disc = Pen(int(sr * 2 + 4), int(sr * 2 + 4))
    disc.circle(sr + 2, sr + 2, sr, sc + (255,))
    if time == "night":
        disc.circle(sr + 2 + sr * 0.45, sr + 2 - sr * 0.2, sr * 0.85, (0, 0, 0, 0))
    d = disc.done()
    if time == "night":  # crescent: knock out the shadow disc
        d2 = Pen(int(sr * 2 + 4), int(sr * 2 + 4))
        d2.circle(sr + 2, sr + 2, sr, (255, 255, 255, 255))
        d2.circle(sr + 2 + sr * 0.45, sr + 2 - sr * 0.2, sr * 0.85, (0, 0, 0, 255))
        mask = d2.done().convert("L").point(lambda v: 255 if v > 128 else 0)
        d = Image.new("RGBA", d.size, sc + (255,))
        d.putalpha(mask)
    img.alpha_composite(d, (x - d.width // 2, y - d.height // 2))
    return img


def add_clouds(s, rng, n, y0, y1, scale=1.0, color=(255, 255, 255)):
    cc = mix(color, TIMES[s.time][1], 0.25) if s.time != "day" else color
    if s.time == "night":
        cc = (110, 118, 156)
    for _ in range(n):
        w = int(rng.uniform(220, 420) * scale)
        img = cloud(rng, w, int(w * 0.42), cc, 225)
        s.clouds.append((img, rng.uniform(-w, W), rng.uniform(y0, y1), rng.uniform(4, 10)))


def ridge(p, f, base, amp, height, color):
    pts = [(x, base - amp * f(x)) for x in range(0, TW + 9, 8)]
    p.poly([(0, height)] + pts + [(TW, height)], color)


# ------------------------------------------------------------------ features

def pine(p, x, base, h, color, snow=False):
    p.rect(x - h * 0.04, base - h * 0.15, x + h * 0.04, base, (110, 84, 60))
    for i in range(3):
        y0 = base - h * (0.15 + 0.28 * i)
        wd = h * (0.34 - 0.08 * i)
        p.poly([(x - wd, y0), (x + wd, y0), (x, y0 - h * 0.42)], color)
        if snow:
            p.poly([(x - wd * 0.45, y0 - h * 0.24), (x + wd * 0.45, y0 - h * 0.24), (x, y0 - h * 0.42)],
                   (246, 248, 252))


def round_tree(p, x, base, h, color):
    p.rect(x - h * 0.06, base - h * 0.45, x + h * 0.06, base, (120, 90, 64))
    p.circle(x, base - h * 0.62, h * 0.34, color)
    p.circle(x - h * 0.2, base - h * 0.5, h * 0.24, shade(color, 0.93))
    p.circle(x + h * 0.2, base - h * 0.52, h * 0.24, shade(color, 1.05))


def cypress(p, x, base, h, color):
    p.ellipse(x - h * 0.12, base - h, x + h * 0.12, base, color)


def house(p, g, x, base, w, h, wall, roof, rng, snow=False):
    p.rect(x, base - h, x + w, base, wall)
    p.poly([(x - 10, base - h), (x + w + 10, base - h), (x + w / 2, base - h - h * 0.6)], roof)
    if snow:
        p.poly([(x - 6, base - h - 2), (x + w + 6, base - h - 2), (x + w / 2, base - h - h * 0.55)],
               (246, 248, 252))
    for i in range(max(1, int(w // 46))):
        wx = x + 14 + i * 46
        if wx + 22 > x + w - 8:
            break
        p.rect(wx, base - h * 0.7, wx + 22, base - h * 0.7 + 24, (176, 204, 226), r=3)
        g.rect(wx, base - h * 0.7, wx + 22, base - h * 0.7 + 24, WARM_LIGHT + (235,), r=3)
    p.rect(x + w - 30, base - 40, x + w - 12, base, shade(roof, 0.8), r=3)


def spaced(rng, gap0, gap1, start=0):
    x, out = start, []
    while x < TW:
        out.append(x)
        x += rng.uniform(gap0, gap1)
    return out


# ------------------------------------------------------------------ settings

def lake(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("lake", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 4, 60, 300)
    f = periodic(rng)
    mtn = (120, 136, 168)
    s.layers.append(Layer(make_layer(600, time, lambda p, g, rep: (
        ridge(p, f, 470, 150, 600, mtn),
        [p.poly([(x - 60, 470 - 150 * f(x) + 60), (x + 60, 470 - 150 * f(x) + 60), (x, 470 - 150 * f(x))],
                (240, 244, 250)) for x in range(0, TW, 480) if f(x) > 0.25]), atmos=0.35), 0, 0.06))
    trees = spaced(rng, 26, 60)

    def shore(p, g, rep):
        p.rect(0, 556, TW, 600, (92, 132, 92))
        for x in trees:
            h = rng.uniform(60, 110)
            for xx in rep(x):
                pine(p, xx, 580, h, (66, 110, 80))
    s.layers.append(Layer(make_layer(600, time, shore, atmos=0.15), 0, 0.25))
    water_top, water_bot = mix((110, 168, 200), TIMES[time][1], 0.3), (70, 130, 170)
    _water(s, rng, 590, water_top, water_bot, extras)
    s.baseline = 800
    return s


def _water(s, rng, top, c_top, c_bot, extras, ducks_y=930):
    s.water = True
    t = s.time

    def band(p, g, rep):
        for i in range(24):
            y0 = (H - top) * i / 24
            p.rect(0, y0, TW, y0 + (H - top) / 24 + 1, mix(c_top, c_bot, i / 23))
    s.layers.append(Layer(make_layer(H - top, t, band), top, 0.0))
    marks = [(rng.uniform(0, TW), rng.uniform(top + 20, H - 10), rng.uniform(20, 70)) for _ in range(260)]

    def ripples(p, g, rep):
        for x, y, ln in marks:
            a = int(70 + 80 * (y - top) / (H - top))
            for xx in rep(x):
                p.rect(xx, y - top, xx + ln * (0.5 + (y - top) / (H - top)), y - top + 3,
                       (255, 255, 255, a), r=1.5)
    s.layers.append(Layer(make_layer(H - top, t, ripples), top, 0.8, drift=6))
    if "ducks" in extras:
        from art import duck
        for i in range(3):
            s.front_props.append(("duck", duck(i), rng.uniform(100, W - 200), ducks_y + i * 18, rng.uniform(3, 7)))
    if "far_sails" in extras:
        from art import boat
        for i in range(3):
            b, _ = boat(rng.choice(["white", "yellow", "pink"]), "sailboat", seed=rng.randint(0, 999))
            b = light(b.resize((b.width // 5, b.height // 5)), t)
            s.props.append((b, (int(rng.uniform(100, W - 100)), top - b.height + 12)))


def harbor(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("harbor", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 4, 60, 280)
    blocks = []
    x = 0
    while x < TW:
        w = rng.uniform(60, 140)
        blocks.append((x, w, rng.uniform(60, 200), rng.choice([(170, 160, 150), (150, 160, 176), (190, 172, 150), (160, 150, 170)])))
        x += w + rng.uniform(0, 30)

    def city(p, g, rep):
        for bx, bw, bh, c in blocks:
            for xx in rep(bx):
                p.rect(xx, 620 - bh, xx + bw, 620, c)
                for wy in range(int(620 - bh + 14), 600, 26):
                    for wx in range(int(xx + 10), int(xx + bw - 14), 22):
                        if (wx * 7 + wy) % 3:
                            p.rect(wx, wy, wx + 10, wy + 12, shade(c, 1.12))
                            g.rect(wx, wy, wx + 10, wy + 12, WARM_LIGHT + (220,))
    s.layers.append(Layer(make_layer(640, time, city, atmos=0.35), 0, 0.08))
    cranes = spaced(rng, 500, 900)

    def pier(p, g, rep):
        p.rect(0, 618, TW, 640, (130, 110, 92))
        for x in range(0, TW, 60):
            p.rect(x, 618, x + 8, 660, (100, 84, 70))
        for c in cranes:
            col = rng.choice([COLORS["orange"], COLORS["red"], COLORS["yellow"]])
            for xx in rep(c):
                p.rect(xx, 400, xx + 14, 620, col)
                p.rect(xx - 80, 400, xx + 160, 414, col)
                p.line([(xx + 7, 400), (xx + 7, 370), (xx + 150, 404)], col, 4)
    s.layers.append(Layer(make_layer(660, time, pier, atmos=0.1), 0, 0.3))
    if "lighthouse" in extras:
        p, g = Pen(120, 330), Pen(120, 330)
        p.poly([(36, 320), (84, 320), (74, 60), (46, 60)], COLORS["white"])
        for yy in (110, 200, 280):
            p.poly([(44 + (320 - yy) * 0.02, yy), (76 - (320 - yy) * 0.02, yy), (76 - (320 - yy) * 0.02, yy + 30), (44 + (320 - yy) * 0.02, yy + 30)], COLORS["red"])
        p.rect(40, 30, 80, 62, (240, 220, 160), r=6)
        p.poly([(34, 32), (86, 32), (60, 8)], COLORS["red"])
        g.rect(40, 30, 80, 62, (255, 236, 170, 255), r=6)  # steady light, no sweeping beam
        img = light(p.done(), time)
        if time in GLOWING:
            img.alpha_composite(g.done())
        s.props.append((img, (110, 330)))
    _water(s, rng, 650, mix((100, 150, 186), TIMES[time][1], 0.25), (60, 108, 150), extras)
    s.baseline = 850
    return s


def airfield(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("airfield", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 5, 60, 360)
    f = periodic(rng, 5)
    s.layers.append(Layer(make_layer(700, time, lambda p, g, rep: ridge(p, f, 630, 70, 700, (120, 160, 120)), atmos=0.35), 0, 0.06))
    trees = spaced(rng, 40, 140)
    hangars = spaced(rng, 900, 1400, 300)

    def edge(p, g, rep):
        p.rect(0, 650, TW, 720, (132, 180, 104))
        for x in trees:
            h = rng.uniform(60, 100)
            for xx in rep(x):
                round_tree(p, xx, 668, h, (88, 140, 92))
        for hx in hangars:
            for xx in rep(hx):
                p.rect(xx, 560, xx + 260, 668, (196, 200, 206))
                p.ellipse(xx - 4, 520, xx + 264, 600, (176, 182, 190))
                p.rect(xx + 70, 600, xx + 190, 668, (120, 126, 136))
    s.layers.append(Layer(make_layer(720, time, edge, atmos=0.12), 0, 0.3))

    def ground(p, g, rep):
        p.rect(0, 0, TW, 380, (140, 190, 108))
        p.rect(0, 120, TW, 220, (120, 124, 130))
        for x in range(0, TW, 240):
            p.rect(x, 166, x + 120, 174, (245, 245, 240))
        for x in range(0, TW, 30):
            p.rect(x, 240 + (x * 13) % 90, x + 4, 250 + (x * 13) % 90, (124, 172, 96))
    s.layers.append(Layer(make_layer(380, time, ground), 700, 1.0))
    if "windsock" in extras:
        p = Pen(160, 220)
        p.rect(20, 20, 28, 220, (200, 200, 206))
        for i, c in enumerate([(240, 130, 60), (250, 250, 250), (240, 130, 60)]):
            p.poly([(28 + i * 38, 22 + i * 3), (66 + i * 38, 24 + i * 4), (66 + i * 38, 56 - i * 4), (28 + i * 38, 58 - i * 3)], c)
        s.props.append((light(p.done(), time), (1500, 470)))
    s.baseline = 880
    return s


def ocean_islands(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("ocean_islands", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 6, 80, 620, 1.2)
    isl = spaced(rng, 600, 1100)

    def islands(p, g, rep):
        for x in isl:
            w = rng.uniform(160, 380)
            for xx in rep(x):
                p.ellipse(xx, 690, xx + w, 760, (96, 140, 118))
                round_tree(p, xx + w * 0.4, 706, 50, (80, 128, 96))
    s.layers.append(Layer(make_layer(760, time, islands, atmos=0.45), 0, 0.03))
    _water(s, rng, 730, mix((90, 156, 196), TIMES[time][1], 0.35), (48, 106, 160), [])
    s.layers[-1].depth = 0.12  # ripples far below the plane move slowly
    s.baseline = 560
    return s


def above_clouds(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("above_clouds", time)
    s.bg = sky(time, rng, stars=False)
    add_clouds(s, rng, 3, 80, 260, 0.8)
    top_col = mix((255, 255, 255), TIMES[time][1], 0.35)
    for depth, y0, n, sc in ((0.05, 640, 60, 0.7), (0.12, 760, 50, 1.0)):
        blobs = [(rng.uniform(0, TW), rng.uniform(0, 60), rng.uniform(60, 130) * sc) for _ in range(n)]

        def sea(p, g, rep, blobs=blobs, sc=sc):
            p.rect(0, 80, TW, H, shade(top_col, 0.97))
            for x, y, r in blobs:
                for xx in rep(x):
                    p.circle(xx, 80 + y, r, top_col)
        s.layers.append(Layer(make_layer(H - y0 + 80, time, sea), y0 - 80, depth))
    s.baseline = 560
    return s


def snowy_village(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("snowy_village", time)
    s.bg = sky(time, rng)
    f = periodic(rng, 5)
    s.layers.append(Layer(make_layer(700, time, lambda p, g, rep: ridge(p, f, 600, 80, 700, (226, 234, 246)), atmos=0.2), 0, 0.06))
    homes = spaced(rng, 220, 420, 50)
    trees = spaced(rng, 120, 260, 140)
    walls = [(232, 210, 186), (200, 120, 110), (176, 196, 214), (236, 222, 170)]
    roofs = [(150, 82, 74), (90, 96, 116), (120, 90, 80)]

    def village(p, g, rep):
        p.rect(0, 700, TW, 760, (236, 242, 250))
        for x in homes:
            w, h = rng.uniform(120, 180), rng.uniform(90, 130)
            wall, roof = rng.choice(walls), rng.choice(roofs)
            for xx in rep(x):
                house(p, g, xx, 712, w, h, wall, roof, rng, snow=True)
        for x in trees:
            h = rng.uniform(90, 140)
            for xx in rep(x):
                pine(p, xx, 716, h, (64, 104, 86), snow=True)
    s.layers.append(Layer(make_layer(760, time, village, atmos=0.08), 0, 0.35))

    lamps = spaced(rng, 520, 520, 200)

    def road(p, g, rep):
        p.rect(0, 0, TW, 380, (238, 244, 252))
        p.rect(0, 70, TW, 190, (206, 214, 226))
        for y in (100, 160):
            p.rect(0, y, TW, y + 5, (190, 198, 212))
        for x in lamps:
            for xx in rep(x):
                p.rect(xx, -0, xx + 8, 60, (60, 64, 76))
                g.circle(xx + 4, 0, 22, (255, 220, 150, 90))
    s.layers.append(Layer(make_layer(380, time, road), 700, 1.0))
    s.snow = True
    s.baseline = 880
    return s


def town_crossroads(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("town_crossroads", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 4, 60, 260)
    shops = spaced(rng, 240, 320, 0)
    leaf = [(220, 140, 70), (230, 180, 80), (200, 100, 70)]

    def street(p, g, rep):
        for i, x in enumerate(shops):
            w, h = 220, rng.uniform(260, 380)
            wall = rng.choice([(236, 214, 190), (190, 210, 220), (226, 190, 190), (210, 220, 190), (240, 226, 170)])
            aw = rng.choice([COLORS["red"], COLORS["teal"], COLORS["yellow"], COLORS["blue"]])
            tree_col = rng.choice(leaf)
            for xx in rep(x):
                p.rect(xx, 760 - h, xx + w, 760, wall)
                p.rect(xx - 4, 760 - h - 14, xx + w + 4, 760 - h, shade(wall, 0.8))
                for wy in (760 - h + 30, 760 - h + 110):
                    if wy < 600:
                        for wx in (xx + 30, xx + 130):
                            p.rect(wx, wy, wx + 56, wy + 56, (180, 206, 226), r=4)
                            g.rect(wx, wy, wx + 56, wy + 56, WARM_LIGHT + (220,), r=4)
                for k in range(5):
                    p.rect(xx + 20 + k * 36, 640, xx + 38 + k * 36, 664, aw if k % 2 == 0 else (250, 250, 246))
                p.rect(xx + 30, 670, xx + 150, 760, (170, 196, 214), r=4)
                p.rect(xx + 166, 680, xx + 200, 760, shade(wall, 0.7), r=3)
                round_tree(p, xx + w + 10, 790, 150, tree_col)
    s.layers.append(Layer(make_layer(800, time, street), 0, 0.5))

    def road(p, g, rep):
        p.rect(0, 0, TW, 40, (196, 190, 184))
        p.rect(0, 40, TW, 240, (92, 96, 104))
        for x in range(0, TW, 160):
            p.rect(x, 136, x + 80, 144, (240, 228, 170))
        p.rect(0, 240, TW, 320, (196, 190, 184))
    s.layers.append(Layer(make_layer(320, time, road), 760, 1.0))
    s.baseline = 990
    return s


def desert_canyon(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("desert_canyon", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 3, 60, 240)
    mesas = spaced(rng, 400, 800)

    def far(p, g, rep):
        for x in mesas:
            w, h = rng.uniform(200, 420), rng.uniform(90, 200)
            c = rng.choice([(206, 130, 96), (190, 116, 90), (214, 150, 110)])
            for xx in rep(x):
                p.poly([(xx, 640), (xx + 40, 640 - h), (xx + w - 40, 640 - h), (xx + w, 640)], c)
                p.rect(xx + 40, 640 - h, xx + w - 40, 640 - h + 14, shade(c, 1.1))
    s.layers.append(Layer(make_layer(660, time, far, atmos=0.3), 0, 0.06))
    cacti = spaced(rng, 120, 300)

    def mid(p, g, rep):
        p.rect(0, 640, TW, 760, (234, 196, 146))
        for x in cacti:
            h = rng.uniform(50, 100)
            for xx in rep(x):
                c = (106, 150, 100)
                p.rect(xx - 9, 700 - h, xx + 9, 700, c, r=9)
                p.rect(xx - 30, 700 - h * 0.7, xx - 20, 700 - h * 0.35, c, r=5)
                p.rect(xx - 30, 700 - h * 0.42, xx, 700 - h * 0.34, c, r=4)
    s.layers.append(Layer(make_layer(760, time, mid, atmos=0.1), 0, 0.3))
    trestle = "bridge" in extras

    def rail(p, g, rep):
        if trestle:
            p.rect(0, 0, TW, 400, (226, 186, 140))
            p.rect(0, 300, TW, 400, (110, 170, 196))
            for x in range(0, TW, 120):
                p.line([(x, 70), (x + 60, 300)], (150, 110, 80), 8)
                p.line([(x + 60, 70), (x, 300)], (150, 110, 80), 8)
                p.rect(x, 70, x + 10, 300, (130, 96, 70))
            p.rect(0, 50, TW, 72, (130, 96, 70))
        else:
            p.rect(0, 0, TW, 400, (238, 204, 156))
            p.poly([(0, 80), (TW, 80), (TW, 40), (0, 40)], (200, 168, 126))
        for x in range(0, TW, 40):
            p.rect(x, 38, x + 22, 52, (120, 90, 66))
        p.rect(0, 34, TW, 40, (150, 150, 158))
    s.layers.append(Layer(make_layer(400, time, rail), 790, 1.0))
    s.baseline = 832
    return s


def spring_fields(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("spring_fields", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 5, 60, 300)
    f = periodic(rng, 4)
    s.layers.append(Layer(make_layer(640, time, lambda p, g, rep: ridge(p, f, 580, 60, 640, (130, 184, 120)), atmos=0.3), 0, 0.06))
    mills = spaced(rng, 700, 1100, 200)
    stripes = [(232, 96, 96), (246, 210, 96), (236, 150, 186), (250, 250, 240)]

    def fields(p, g, rep):
        p.rect(0, 600, TW, 800, (120, 176, 100))
        for i in range(6):
            y0 = 640 + i * 24
            p.rect(0, y0, TW, y0 + 14, stripes[i % 4])
        for x in mills:
            for xx in rep(x):
                p.poly([(xx - 40, 640), (xx + 40, 640), (xx + 22, 460), (xx - 22, 460)], (236, 230, 220))
                p.poly([(xx - 30, 464), (xx + 30, 464), (xx, 420)], (150, 90, 80))
                p.rect(xx - 12, 590, xx + 12, 640, (130, 90, 70))
                for a in (0.4, 2.0, 3.6, 5.2):
                    p.line([(xx, 448), (xx + 120 * math.cos(a), 448 + 120 * math.sin(a))], (246, 242, 232), 10)
    s.layers.append(Layer(make_layer(800, time, fields, atmos=0.1), 0, 0.35))

    def rail(p, g, rep):
        p.rect(0, 0, TW, 360, (126, 180, 104))
        p.rect(0, 30, TW, 70, (170, 160, 150))
        for x in range(0, TW, 40):
            p.rect(x, 38, x + 22, 50, (120, 90, 66))
        p.rect(0, 34, TW, 40, (150, 150, 158))
        for x in range(0, TW, 26):
            p.circle(x, 140 + (x * 7) % 180, 4, stripes[(x // 26) % 4])
    s.layers.append(Layer(make_layer(360, time, rail), 790, 1.0))
    if "crossing" in extras:
        # Level crossing: barrier arm DOWN, steady red lamps (no flashing), a family waiting safely.
        p = Pen(420, 260)
        p.rect(30, 60, 40, 250, (90, 90, 96))
        p.rect(14, 40, 56, 66, (60, 60, 66), r=6)
        p.circle(24, 53, 9, (230, 80, 70))
        p.circle(46, 53, 9, (230, 80, 70))
        for i in range(8):
            p.rect(40 + i * 46, 150, 86 + i * 46, 164, (230, 70, 64) if i % 2 == 0 else (250, 250, 250))
        from art import person
        r = random.Random(seed)
        person(p, 0 + 8, 196, 1.3, r)
        img = light(p.done(), time)
        s.front_props.append(("static", img, 1450, 800, 0))
    s.baseline = 832
    return s


def lavender_valley(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("lavender_valley", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 4, 80, 360)
    f = periodic(rng, 5)
    s.layers.append(Layer(make_layer(720, time, lambda p, g, rep: ridge(p, f, 660, 110, 720, (130, 146, 186)), atmos=0.4), 0, 0.0))
    trees = spaced(rng, 140, 400)
    farm = rng.uniform(600, 1400)

    def mid(p, g, rep):
        p.rect(0, 690, TW, 760, (170, 186, 120))
        for x in trees:
            h = rng.uniform(70, 120)
            for xx in rep(x):
                cypress(p, xx, 712, h, (70, 110, 80))
        for xx in rep(farm):
            house(p, g, xx, 712, 170, 90, (236, 214, 180), (180, 110, 86), rng)
    s.layers.append(Layer(make_layer(760, time, mid, atmos=0.15), 0, 0.0))

    def rows(p, g, rep):
        p.rect(0, 0, TW, 400, (120, 150, 96))
        for i in range(12):
            y = 10 + i * (18 + i * 2.6)
            p.rect(0, y, TW, y + 8 + i * 1.8, (156, 120, 196) if i % 2 == 0 else (172, 136, 210))
    s.layers.append(Layer(make_layer(400, time, rows), 740, 0.0))
    s.baseline = 700
    return s


def coastal_hills(time, seed, extras):
    rng = random.Random(seed)
    s = Setting("coastal_hills", time)
    s.bg = sky(time, rng)
    add_clouds(s, rng, 5, 60, 320)

    def sea(p, g, rep):
        p.rect(0, 0, TW, 200, mix((96, 160, 200), TIMES[time][1], 0.3))
        for x in range(0, TW, 70):
            p.rect(x, 30 + (x * 11) % 150, x + 34, 33 + (x * 11) % 150, (230, 240, 248, 120))
    s.layers.append(Layer(make_layer(200, time, sea), 600, 0.04))
    f = periodic(rng, 5)
    sheep = [(rng.uniform(0, TW), rng.uniform(0, 1)) for _ in range(40)]
    lh = rng.uniform(400, 3000)

    def hills(p, g, rep):
        ridge(p, f, 700, 70, 900, (118, 176, 104))
        for x, k in sheep:
            for xx in rep(x):
                y = 700 - 70 * f(x) + 30 + 120 * k
                p.ellipse(xx - 12, y - 8, xx + 12, y + 8, (248, 248, 244))
                p.circle(xx + 12, y - 4, 5, (70, 70, 74))
        for xx in rep(lh):
            y = 700 - 70 * f(lh)
            p.rect(xx - 14, y - 120, xx + 14, y + 4, COLORS["white"])
            p.rect(xx - 14, y - 80, xx + 14, y - 60, COLORS["red"])
            p.poly([(xx - 18, y - 120), (xx + 18, y - 120), (xx, y - 140)], COLORS["red"])
    s.layers.append(Layer(make_layer(900, time, hills, atmos=0.12), 0, 0.2))

    def front(p, g, rep):
        ridge(p, periodic(random.Random(seed + 1), 3), 120, 40, 300, (104, 162, 94))
        for x in range(0, TW, 34):
            p.rect(x, 170 + (x * 17) % 110, x + 4, 180 + (x * 17) % 110, (90, 148, 82))
    s.layers.append(Layer(make_layer(300, time, front), 780, 0.7))
    if "helipad" in extras:
        p = Pen(520, 80)
        p.ellipse(10, 10, 510, 74, (196, 198, 204))
        p.ellipse(60, 20, 460, 64, (120, 124, 132))
        p.rect(220, 30, 236, 54, (250, 250, 250))
        p.rect(284, 30, 300, 54, (250, 250, 250))
        p.rect(220, 38, 300, 46, (250, 250, 250))
        s.props.append((light(p.done(), time), (W // 2 - 260, 900)))
    s.baseline = 470
    return s


BUILDERS = {f.__name__: f for f in (lake, harbor, airfield, ocean_islands, above_clouds, snowy_village,
                                    town_crossroads, desert_canyon, spring_fields, lavender_valley, coastal_hills)}


def build(name, time, seed, extras=()):
    return BUILDERS[name](time, seed, set(extras))
