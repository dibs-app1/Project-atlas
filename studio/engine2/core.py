"""World, camera, weather, water and motion for engine 2.

Scenery is generated in chunks from a seeded random generator, so the camera can travel
any distance and never sees the same stretch twice (no repeated clips, even inside a scene).
"""
import math
import random
from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFilter

from art import GLOWING, TIMES, H, W, Pen, light, mix, soft_glow

CW = 1600          # chunk width (world px)
M = 360            # overhang drawn on each side of a chunk so props never get cut
FPS = 24


def _stable(*parts):
    """Deterministic seed (Python's hash() of strings changes between runs)."""
    import zlib
    return zlib.crc32(repr(parts).encode())


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def env(t, t0, t1, ramp=1.5):
    """1 between t0 and t1 with soft ramps, 0 outside."""
    return smooth((t - t0) / ramp) * (1 - smooth((t - t1) / ramp))


# --------------------------------------------------------------------------- layers

class Layer:
    """A parallax layer drawn chunk by chunk.

    draw(p, g, X0, X1, rng) draws world x in [X0, X1) at local x = world - X0 + M.
    """

    def __init__(self, world, name, y, height, depth, draw, atmos=0.0, cache=6, zoom=1.0):
        self.world, self.name, self.y, self.h = world, name, int(round(y)), height
        self.depth, self.draw, self.atmos, self.zoom = depth, draw, atmos, zoom
        self.cache = OrderedDict()
        self.cache_size = cache

    def chunk(self, k):
        if k in self.cache:
            self.cache.move_to_end(k)
            return self.cache[k]
        X0 = k * CW
        from .vehicles import Pen as KPen
        p, g = KPen(CW + 2 * M, self.h, self.zoom), KPen(CW + 2 * M, self.h, self.zoom)
        rng = random.Random(_stable(self.world.seed, self.name, k))
        self.draw(p, g, X0, X0 + CW, rng)
        img = light(p.done(), self.world.time)
        from . import look
        img = look.texture(img, _stable(self.world.seed, self.name, k, 1), amount=0.035)
        if self.depth <= 0.1:   # distant hills are a touch soft, like real depth of field
            img = img.filter(ImageFilter.GaussianBlur(1.4))
        if self.atmos:
            haze = Image.new("RGBA", img.size, TIMES[self.world.time][1] + (0,))
            haze.putalpha(img.getchannel("A").point(lambda a: int(a * self.atmos)))
            img.alpha_composite(haze)
        if self.world.time in GLOWING:
            img.alpha_composite(g.done())
        self.cache[k] = img
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return img

    def render(self, frame, cam):
        start = cam * self.depth
        z = self.zoom
        k0 = math.floor((start / z - M) / CW)
        k1 = math.floor(((start + W) / z + M) / CW)
        for k in range(k0, k1 + 1):
            x = int(round((k * CW - M) * z - start))
            img = self.chunk(k)
            sx0, sx1 = max(0, -x), min(img.width, W - x)
            if sx1 > sx0:
                frame.alpha_composite(img, (x + sx0, self.y), (sx0, 0, sx1, img.height))


# --------------------------------------------------------------------------- weather

class Weather:
    """Clouds, rain, snow, fog, rainbow, sun rays. Intensities can change over time (gradually)."""

    def __init__(self, world, spec):
        self.w = world
        self.kind = spec.get("weather", "clear")
        rng = random.Random(world.seed + 77)
        self.rng = rng
        self.wind = spec.get("wind", 30.0)
        clouds = spec.get("clouds", {"clear": 5, "cloudy": 9, "rain": 12, "snow": 10, "fog": 6,
                                     "rain_then_sun": 11}.get(self.kind, 5))
        grey = self.kind in ("rain", "snow", "rain_then_sun")
        self.clouds = []
        from .look import cloud
        for i in range(clouds):
            layer = i % 3
            scale = (0.7, 1.0, 1.4)[layer]
            w = int(rng.uniform(220, 460) * scale)
            col = (226, 230, 238) if grey else (255, 255, 255)
            if world.time in ("dusk", "night"):
                col = (120, 126, 160) if world.time == "night" else (232, 196, 200)
            img = light(cloud(rng, w, int(w * 0.5), col, 240), world.time)
            self.clouds.append((img, rng.uniform(-w, W + 400), rng.uniform(30, 330 - 60 * layer),
                                (0.04, 0.08, 0.14)[layer], rng.uniform(0.6, 1.4)))
        self.drops = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.75, 1.25)) for _ in range(360)]
        self.flakes = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(26, 60), rng.uniform(4, 22),
                        rng.uniform(0, 6.28), rng.choice((2, 2.5, 3, 3.5, 4))) for _ in range(240)]
        self.fog = None
        if self.kind == "fog" or spec.get("fog"):
            f = Image.new("RGBA", (W * 2, 420), (0, 0, 0, 0))
            d = ImageDraw.Draw(f)
            for _ in range(40):
                x, y, r = rng.uniform(0, W * 2), rng.uniform(80, 340), rng.uniform(80, 200)
                d.ellipse([x - r * 2, y - r * 0.5, x + r * 2, y + r * 0.5], fill=(236, 240, 246, 70))
            self.fog = f.filter(ImageFilter.GaussianBlur(30))
        self.rainbow = None
        if self.kind == "rain_then_sun" or spec.get("rainbow"):
            rb = Image.new("RGBA", (1400, 700), (0, 0, 0, 0))
            d = ImageDraw.Draw(rb)
            cols = [(230, 80, 80), (240, 150, 70), (240, 220, 90), (110, 190, 110), (90, 140, 220), (140, 100, 200)]
            for i, c in enumerate(cols):
                r = 640 - i * 18
                d.arc([700 - r, 700 - r, 700 + r, 700 + r], 180, 360, fill=c + (110,), width=18)
            self.rainbow = rb.filter(ImageFilter.GaussianBlur(3))
        self.dark = Image.new("RGBA", (W, H), (70, 80, 100, 0))

    def rain_level(self, t, D):
        if self.kind == "rain":
            return 1.0
        if self.kind == "rain_then_sun":
            return 1 - smooth((t - D * 0.5) / 8.0)
        return 0.0

    def sky(self, frame, t, cam):
        """Clouds and rainbow: drawn right after the sky, behind the scenery."""
        D = self.w.D
        if self.rainbow is not None:
            a = smooth((t - D * 0.55) / 6.0) if self.kind == "rain_then_sun" else 1.0
            if a > 0.01:
                rb = self.rainbow.copy()
                rb.putalpha(rb.getchannel("A").point(lambda v: int(v * a)))
                frame.alpha_composite(rb, (int(W * 0.55 - 700), 210))
        for img, x0, y, depth, sp in self.clouds:
            span = W + img.width + 400
            x = (x0 + self.wind * sp * t - cam * depth) % span - img.width
            frame.alpha_composite(img, (int(x), int(y)))

    def front(self, frame, t, cam, ground_y):
        D = self.w.D
        rl = self.rain_level(t, D)
        if rl > 0.01:
            dk = self.dark.copy()
            dk.putalpha(int(70 * rl))
            frame.alpha_composite(dk)
            d = ImageDraw.Draw(frame)
            n = int(len(self.drops) * rl)
            slant = 0.18 + self.wind / 400
            for x0, y0, s in self.drops[:n]:
                y = (y0 + 1100 * s * t) % (H + 60) - 30
                x = (x0 - cam * 0.9 - slant * 1100 * s * t) % W
                d.line([(x, y), (x - 26 * slant * s, y + 26 * s)], fill=(210, 222, 240, int(150 * rl)), width=2)
            for i in range(int(40 * rl)):  # splashes on the ground, each lasting a few frames
                k = int(t * 12) + i * 7919
                r = random.Random(k)
                x, y = r.uniform(0, W), ground_y + r.uniform(-10, 120)
                if y < H:
                    d.arc([x - 9, y - 3, x + 9, y + 3], 180, 360, fill=(230, 236, 246, int(140 * rl)), width=2)
        if self.kind == "snow":
            d = ImageDraw.Draw(frame)
            for x0, y0, vy, amp, ph, r in self.flakes:
                y = (y0 + vy * 1.6 * t) % (H + 20) - 10
                x = (x0 + amp * math.sin(t / 1.8 + ph) - cam * 0.7 - self.wind * 0.6 * t) % W
                d.ellipse([x - r, y - r, x + r, y + r], fill=(250, 252, 255, 235))
        if self.fog is not None:
            x = -((cam * 0.5 + t * 14) % W)
            frame.alpha_composite(self.fog, (int(x), int(ground_y - 360)))


# --------------------------------------------------------------------------- water

class Water:
    """Animated waves: a moving surface that boats ride on, with crests, foam and ripples."""

    def __init__(self, world, top, c_top, c_bot, amp=10.0, choppy=1.0, rain=None):
        self.w, self.top, self.amp, self.choppy = world, top, amp, choppy
        lit = TIMES[world.time][2]
        f = lambda c: tuple(int(c[i] * lit[i] / 255) for i in range(3))  # noqa: E731
        grad = Image.new("RGB", (1, H - top + 40))
        for y in range(grad.height):
            grad.putpixel((0, y), mix(f(c_top), f(c_bot), min(1, y / (H - top))))
        self.body = grad.resize((W, grad.height))
        self.crest = mix(f(c_top), (255, 255, 255), 0.55)
        rng = random.Random(world.seed + 5)
        self.waves = [(rng.uniform(0.004, 0.009), rng.uniform(0.8, 1.6), rng.uniform(0, 6.28), 1.0),
                      (rng.uniform(0.010, 0.018), rng.uniform(1.3, 2.2), rng.uniform(0, 6.28), 0.45),
                      (rng.uniform(0.020, 0.035), rng.uniform(2.0, 3.0), rng.uniform(0, 6.28), 0.2)]
        self.lines = [(rng.uniform(0, 1), rng.uniform(0.05, 1.0), rng.uniform(40, 140), rng.uniform(0, 6.28))
                      for _ in range(140)]
        self.rain = rain
        self.lane = 0.0   # boats ride this far below the horizon line (closer to the camera)

    def height(self, x_world, t):
        """Surface y at a world x (screen coordinates)."""
        y = self.top
        for k, w, ph, a in self.waves:
            y += self.amp * self.choppy * a * math.sin(k * x_world - w * t + ph)
        return y

    def surface(self, x_world, t):
        return self.height(x_world, t) + self.lane

    def slope(self, x_world, t):
        return (self.height(x_world + 6, t) - self.height(x_world - 6, t)) / 12

    def render_back(self, frame, t, cam):
        pts = [(x, self.height(x + cam, t)) for x in range(-10, W + 20, 16)]
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(pts + [(W + 20, H), (-10, H)], fill=255)
        body = Image.new("RGB", (W, H))
        body.paste(self.body, (0, self.top - 40 if self.top > 40 else 0))
        frame.paste(body.convert("RGBA"), (0, 0), mask)
        d = ImageDraw.Draw(frame)
        depth = H - self.top
        for u, v, ln, ph in self.lines:  # moving swell lines, faster and longer near the camera
            y = self.top + 20 + v * v * (depth - 20)
            par = 0.15 + 0.85 * v
            x = (u * (W + 400) - cam * par - t * 30 * par) % (W + 400) - 200
            yy = y + 5 * math.sin(t * 1.3 + ph)
            d.line([(x, yy), (x + ln * par * 1.5, yy)], fill=self.crest + (int(60 + 90 * v),), width=max(2, int(4 * v)))
        d.line(pts, fill=self.crest + (230,), width=4)
        r = random.Random(int(t * 6))
        for _ in range(60):   # sparkles where the light catches the waves
            sx = r.uniform(0, W)
            sy = self.height(sx + cam, t) + r.uniform(4, (H - self.top) * 0.8) * r.random() ** 2
            ln = r.uniform(4, 14)
            d.line([(sx - ln, sy), (sx + ln, sy)], fill=(255, 255, 255, r.randint(90, 200)), width=2)
        if self.rain is not None and self.rain(t) > 0.01:
            rl = self.rain(t)
            for i in range(int(45 * rl)):
                k = int(t * 8) - i
                r = random.Random(k * 31 + i)
                x, y = r.uniform(0, W), self.top + 15 + r.uniform(0, depth - 20)
                age = (t * 8 - int(t * 8)) + (i % 3)
                rad = 6 + 10 * age
                d.ellipse([x - rad, y - rad * 0.3, x + rad, y + rad * 0.3], outline=self.crest + (int(140 / (1 + age)),), width=2)

    def render_front(self, frame, t, cam, xs):
        """Translucent water in front of hulls (only around boats, so it is cheap)."""
        for x0, x1 in xs:
            x0, x1 = max(0, int(x0)), min(W, int(x1))
            if x1 <= x0:
                continue
            pts = [(x, self.surface(x + cam, t) + 9) for x in range(x0, x1 + 8, 8)]
            mask = Image.new("L", (x1 - x0 + 8, 120), 0)
            ymin = int(min(p[1] for p in pts)) - 4
            ImageDraw.Draw(mask).polygon([(x - x0, y - ymin) for x, y in pts] + [(x1 - x0 + 8, 120), (0, 120)], fill=205)
            yb = max(0, ymin - self.top + 40)
            patch = self.body.crop((x0, yb, x1 + 8, yb + 120)).convert("RGBA")
            frame.paste(patch, (x0, ymin), mask)
            ImageDraw.Draw(frame).line(pts, fill=self.crest + (210,), width=3)


# --------------------------------------------------------------------------- motion

class Mover:
    """Integrates a vehicle's position with gentle acceleration limits.

    target(x, t, v) -> desired speed. Positions are precomputed for the whole scene.
    """

    def __init__(self, x0, v0, D, target, accel=70.0, decel=110.0):
        n = int(D * FPS) + 3
        self.x, self.v = [], []
        x, v = x0, v0
        for i in range(n):
            t = i / FPS
            self.x.append(x)
            self.v.append(v)
            want = max(0.0, target(x, t, v))
            if want > v:
                v = min(want, v + accel / FPS)
            else:
                v = max(want, v - decel / FPS)
            x += v / FPS

    def at(self, t):
        i = min(int(t * FPS), len(self.x) - 1)
        return self.x[i], self.v[i]


def stop_target(cruise, stops, front, a=110.0):
    """Cruise, but brake smoothly to each (x_line, t_release) stop line until its release time."""
    def target(x, t, v):
        want = cruise(x, t) if callable(cruise) else cruise
        for line, release in stops:
            gap = line - (x + front)
            if t < release and gap > -5:
                want = min(want, math.sqrt(max(0.0, 2 * a * 0.8 * max(0.0, gap - 4))))
        return want
    return target


class World:
    def __init__(self, spec, D):
        self.spec, self.D = spec, D
        self.seed = spec["seed"]
        self.time = spec.get("time", "day")
        self.layers = []
        self.water = None
        from . import look
        self.sky_img = look.sky(self.time, spec.get("weather", "clear"), TIMES[self.time][3])
        self.weather = Weather(self, spec)
        self.ground_y = 900

    def add(self, name, y, h, depth, draw, atmos=0.0):
        self.layers.append(Layer(self, name, y, h, depth, draw, atmos))
        return self.layers[-1]


def sky_image(time, rng, weather):
    from settings import sky
    img = sky(time, rng)
    if weather in ("rain", "snow", "rain_then_sun"):
        grey = Image.new("RGBA", img.size, (150, 158, 172, 120 if weather != "rain_then_sun" else 70))
        img.alpha_composite(grey)
    return img


def label(text, size=44, bg=(30, 40, 66, 150), fg=(255, 252, 244, 255)):
    from PIL import ImageFont
    from scenes import FONT
    font = ImageFont.truetype(FONT, size)
    l, t, r, b = font.getbbox(text)
    w, h = r - l + 56, b - t + 30
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=bg)
    d.text((28 - l, 15 - t), text, font=font, fill=fg)
    return img


def fade(img, a):
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return out


__all__ = ["World", "Layer", "Weather", "Water", "Mover", "stop_target", "smooth", "env", "label", "fade",
           "CW", "M", "FPS", "W", "H", "soft_glow"]
