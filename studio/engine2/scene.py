"""Scene framework for engine 2: depth-sorted layers and actors, camera, captions, sound cues."""
import math
import random

from PIL import Image, ImageDraw

from .core import FPS, H, W, Layer, World, fade, label, smooth

SCRIPTS = {}


def script(name):
    def deco(fn):
        SCRIPTS[name] = fn
        return fn
    return deco


def bump_profile(dx, half=34.0):
    """Height factor (0..1) of a speed bump at horizontal distance dx from its centre."""
    if abs(dx) >= half:
        return 0.0
    return math.cos(dx / half * math.pi / 2) ** 2


class Scene2:
    def __init__(self, spec, D):
        self.spec, self.D = spec, D
        self.seed = spec["seed"]
        self.rng = random.Random(self.seed)
        self.world = World(spec, D)
        self.time = self.world.time
        self.items = []          # (z, fn(frame, t, cam))
        self.captions = []       # (t0, t1, image)
        self.pops = []           # (t0, fn(t) -> (x, y), image)
        self.sounds = []         # dicts consumed by sfx.py
        self.ground_y = 900
        self._cam = None
        self.cam_static = 0.0
        title = spec.get("caption")
        if title:
            self.say(0.6, 7.0, title, size=54)
        SCRIPTS[spec["script"]](self)
        if spec.get("birds", self.time not in ("night",)) and spec.get("weather") not in ("rain",):
            self.add(2.5, _birds(self.seed, D))

    # -------------------------------------------------------------- building blocks
    def layer(self, name, y, h, depth, draw, z, atmos=0.0, zoom=1.0):
        lay = Layer(self.world, name, y, h, depth, draw, atmos, zoom=zoom)
        self.items.append((z, lambda f, t, cam, lay=lay: lay.render(f, cam)))
        return lay

    def add(self, z, fn):
        self.items.append((z, fn))

    def say(self, t0, t1, text, size=46):
        self.captions.append((t0, t1, label(text, size)))

    def pop(self, t0, where, text):
        self.pops.append((t0, where, label(text, 60, bg=(250, 250, 246, 235), fg=(40, 50, 80, 255))))

    def sound(self, kind, **kw):
        self.sounds.append(dict(kind=kind, **kw))

    def follow(self, mover, anchor=0.36, offset=0.0, ease=0.0):
        """Camera rides along with a mover so the hero stays at `anchor` of the screen width."""
        n = int(self.D * FPS) + 3
        cams = []
        for i in range(n):
            x, _ = mover.at(i / FPS)
            cams.append(x - W * anchor + offset)
        self._cam = cams
        self.focus_x = W * anchor - offset  # where the hero sits on screen (used to frame vertical Shorts)

    def cam(self, t):
        if self._cam is None:
            return self.cam_static
        return self._cam[min(int(t * FPS), len(self._cam) - 1)]

    # -------------------------------------------------------------- actors
    def road_vehicle(self, veh, mover, ground, z, depth=1.0, direction=1, x0=0.0, bumps=(), state=None,
                     wheelbase=None, bump_h=16.0):
        """A wheeled vehicle on a road. direction -1 drives right-to-left (sprite mirrored)."""
        L = getattr(veh, "length", veh.w)
        xs = sorted(w[0] for w in veh.wheels)
        wb = wheelbase or (xs[-1] - xs[0] if len(xs) > 1 else L * 0.6)
        rear_off = xs[0] if xs else 0

        def draw(frame, t, cam):
            d, v = mover.at(t)
            if direction > 0:
                xw = x0 + d
                sx = xw - cam * depth
                rear_w, front_w = xw + rear_off, xw + rear_off + wb
            else:
                xw = x0 - d
                sx = xw - cam * depth - veh.w
                front_w, rear_w = xw - rear_off - wb, xw - rear_off
            if sx > W + 40 or sx + veh.w < -40:
                return
            lr = lf = 0.0
            for b in bumps:
                lr = max(lr, bump_profile(rear_w - b))
                lf = max(lf, bump_profile(front_w - b))
            lift = bump_h * (lr + lf) / 2 + 1.2 * math.sin(t * 17 + x0) * min(1.0, v / 120)
            tilt = math.degrees(math.atan2(bump_h * (lf - lr), wb)) * direction
            gy = ground(xw) if callable(ground) else ground
            st = state(t, d, v) if state else {}
            veh.draw(frame, sx, gy, d * direction, t, tilt=tilt, lift=lift, state=st, flip=direction < 0)
        self.add(z, draw)

    def boat_actor(self, veh, mover, water, z, x0=0.0, direction=1, heel=0.0, wake=True, spray=0.0, state=None,
                   sink=0.0):
        def draw(frame, t, cam):
            d, v = mover.at(t)
            xw = x0 + d * direction
            sx = xw - cam - (veh.w if direction < 0 else 0)
            if sx > W + 60 or sx + veh.w < -60:
                return
            mid = xw + (veh.w / 2) * direction
            wy = water.surface(mid, t)
            tilt = -math.degrees(math.atan(water.slope(mid, t))) * 0.8 + heel * direction
            st = state(t, d, v) if state else {}
            st["dist"] = d
            if wake and v > 5:
                _wake(frame, sx, wy, veh.w, v, t, direction)
            veh.draw(frame, sx, wy + sink, d, t, tilt=tilt, state=st, flip=direction < 0, shadow=False)
            water.render_front(frame, t, cam, [(sx, sx + veh.w)])
            if spray > 0 and v > 60:
                _spray(frame, sx + (veh.w if direction > 0 else 0), wy, v * spray, t, direction)
        self.add(z, draw)

    def train_actor(self, train, mover, ground, z, x0=0.0, depth=1.0, state=None):
        def draw(frame, t, cam):
            d, v = mover.at(t)
            sx = x0 + d - cam * depth
            if sx > W + 40 or sx + train.length < -40:
                return
            st = state(t, d, v) if state else {}
            train.draw(frame, sx, ground, d, t, state=st)
        self.add(z, draw)

    def smoke(self, mover, src, z, every=0.45, life=4.0, col=(244, 244, 244), drift=(-20, -46), size=16, x0=0.0,
              depth=1.0):
        """Puffs from a moving source. src(d) -> (world x, y) at travel distance d."""
        def draw(frame, t, cam):
            dr = ImageDraw.Draw(frame)
            k1 = int(t / every)
            for k in range(max(0, k1 - int(life / every) - 1), k1 + 1):
                te = k * every
                a = t - te
                if a < 0 or a > life:
                    continue
                de, _ = mover.at(te)
                wx, wy = src(de)
                x = x0 + wx - cam * depth + drift[0] * a
                y = wy + drift[1] * a
                r = size + 9 * a
                al = int(170 * (1 - a / life))
                dr.ellipse([x - r, y - r, x + r, y + r], fill=col + (al,))
        self.add(z, draw)

    # -------------------------------------------------------------- frame
    def frame(self, t):
        cam = self.cam(t)
        f = self.world.sky_img.copy()
        self.world.weather.sky(f, t, cam)
        for z, fn in sorted(self.items, key=lambda it: it[0]):
            fn(f, t, cam)
        self.world.weather.front(f, t, cam, self.ground_y)
        for t0, where, img in self.pops:
            a = t - t0
            if 0 <= a <= 2.2:
                x, y = where(t)
                al = smooth(a / 0.3) * (1 - smooth((a - 1.6) / 0.6))
                f.alpha_composite(fade(img, al), (int(x - img.width / 2), int(y - img.height - 30 * a)))
        if self.spec.get("no_captions"):    # Shorts draw their own big text instead
            return self._grade(f)
        for t0, t1, img in self.captions:   # captions sit at the top, clear of the vehicles
            a = smooth((t - t0) / 0.8) * (1 - smooth((t - t1) / 0.8))
            if a > 0.01:
                f.alpha_composite(fade(img, a), ((W - img.width) // 2, 34))
        return self._grade(f)

    def _grade(self, f):
        if self.spec.get("look", "rich") != "rich":
            return f
        from .look import grade
        return grade(f, time=self.time).convert("RGBA")


def _wake(frame, sx, wy, w, v, t, direction):
    d = ImageDraw.Draw(frame)
    stern = sx if direction > 0 else sx + w
    n = 9
    for k in range(n):
        a = (k + (t * 3) % 1) / n
        x = stern - direction * a * min(420, v * 3)
        spread = 6 + a * 40
        al = int(170 * (1 - a))
        d.ellipse([x - 20, wy - 3 + spread * 0.15, x + 20, wy + 5 + spread * 0.3], fill=(250, 252, 255, al))
        d.line([(x, wy + 6 + spread * 0.3), (x - direction * 40, wy + 10 + spread * 0.5)], fill=(250, 252, 255, al // 2), width=3)


def _spray(frame, bow, wy, power, t, direction):
    d = ImageDraw.Draw(frame)
    r = random.Random(int(t * 24))
    for _ in range(int(min(40, power / 4))):
        u = r.uniform(0, 1)
        x = bow - direction * r.uniform(0, 60) + direction * u * 30
        y = wy - u * 46 + r.uniform(-6, 6)
        rad = r.uniform(2, 5)
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(250, 252, 255, int(200 * (1 - u))))


def make(spec, D):
    from . import scripts_boats, scripts_cars, scripts_planes, scripts_trains  # noqa: F401  (register)
    from . import vehicles
    vehicles.SCALE = spec.get("scale", 1.6)
    return Scene2(spec, D)


def _birds(seed, D):
    """Small flocks crossing the sky now and then, wings flapping."""
    r = random.Random(seed + 404)
    flocks = []
    t = r.uniform(2, 8)
    while t < D:
        n = r.randint(3, 6)
        flocks.append((t, r.uniform(80, 360), r.choice((-1, 1)), r.uniform(110, 170),
                       [(r.uniform(-90, 90), r.uniform(-40, 40), r.uniform(0, 6)) for _ in range(n)]))
        t += r.uniform(14, 24)

    def draw(frame, t, cam):
        d = ImageDraw.Draw(frame)
        for t0, y0, dirn, sp, birds in flocks:
            a = t - t0
            span = (W + 400) / sp
            if not (0 <= a <= span):
                continue
            x0 = -200 + a * sp if dirn > 0 else W + 200 - a * sp
            for dx, dy, ph in birds:
                x, y = x0 + dx, y0 + dy + 6 * math.sin(a * 1.3 + ph)
                wing = 9 * math.sin(a * 9 + ph)
                d.line([(x - 13, y - wing), (x, y), (x + 13, y - wing)], fill=(70, 76, 92, 220), width=3)
    return draw
