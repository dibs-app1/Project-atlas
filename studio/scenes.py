"""Scene engine: turns a scene spec into frames.

Vehicle motion is computed from a velocity profile so that speed and acceleration are
always smooth and gentle (and can be checked by the safety reviewer before rendering).
"""
import math
import random

from PIL import Image, ImageDraw, ImageFont

import art
import settings
from art import GLOWING, H, W, light

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FPS = 24

# Safety limits (screen px/s at 1080p; a car is ~300 px long, so 90 px/s is a gentle crawl).
SPEED_LIMIT = {"car": 95, "boat": 70, "train": 110, "airplane": 120, "helicopter": 90, "balloon": 16}
ACCEL_LIMIT = 30  # px/s^2: no sudden starts or stops


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def caption_image(text, size=56):
    font = ImageFont.truetype(FONT, size)
    l, t, r, b = font.getbbox(text)
    w, h = r - l + 80, b - t + 44
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=(30, 40, 60, 110))
    d.text((40 - l, 22 - t), text, font=font, fill=(255, 252, 244, 255))
    return img


def make_sprite(v, seed):
    t = v["type"]
    if t == "car":
        return art.car(v["color"], v.get("kind", "sedan"), seed, snow=v.get("snow", False))
    if t == "boat":
        return art.boat(v["color"], v.get("kind", "sailboat"), seed)
    if t == "airplane":
        return art.airplane(v["color"], v.get("kind", "airliner"), seed, gear=v.get("gear", False))
    if t == "train":
        return art.train(v["color"], v.get("kind", "steam"), v.get("cars", 3), seed, v.get("cargo"))
    if t == "helicopter":
        return art.helicopter(v["color"], seed)
    if t == "balloon":
        return art.balloon(v["scheme"], seed)
    raise ValueError(t)


class Scene:
    def __init__(self, spec, duration):
        self.spec, self.D = spec, duration
        self.seed = spec["seed"]
        self.rng = random.Random(self.seed)
        self.set = settings.build(spec["setting"], spec["time"], self.seed, spec.get("extras", []))
        self.time = spec["time"]
        self.v = spec["vehicle"]
        self.motion = spec["motion"]
        self.left = spec.get("direction", "right") == "left"
        self.speed = spec.get("speed", 60)
        sprite, glow = make_sprite(self.v, self.seed)
        self.sprite = light(sprite, self.time)
        self.glow = glow if (glow is not None and self.time in GLOWING) else None
        if self.left:
            self.sprite = self.sprite.transpose(Image.FLIP_LEFT_RIGHT)
            if self.glow is not None:
                self.glow = self.glow.transpose(Image.FLIP_LEFT_RIGHT)
        self.caption = caption_image(spec["caption"]) if spec.get("caption") else None
        self._plan_path()
        if self.motion == "float":
            self._plan_balloons()
        if self.v["type"] == "train" and self.v.get("kind", "steam") == "steam":
            self.puffs = art.puff(14, 110)
        else:
            self.puffs = None
        if self.set.snow:
            r = self.rng
            self.flakes = [(r.uniform(0, W), r.uniform(0, H), r.uniform(22, 40), r.uniform(6, 20),
                            r.uniform(0, 6.28), r.choice((2, 2.5, 3, 3.5))) for _ in range(170)]
        if self.motion == "stop_and_go":
            self.walker = art.Pen(40, 70)
            art.person(self.walker, 20, 12, 1.6, random.Random(self.seed + 7))
            self.walker = light(self.walker.done(), self.time)

    # ---------------------------------------------------------------- motion
    def _profile(self, segments):
        """segments: list of (duration, v_start, v_end). Returns per-frame velocities."""
        out = []
        for dur, a, b in segments:
            n = max(1, int(round(dur * FPS)))
            out += [a + (b - a) * smooth((i + 0.5) / n) for i in range(n)]
        return out

    def _plan_path(self):
        """Fill self.xs/self.ys/self.ang (per frame, right-facing) and self.cam (per frame)."""
        n = int(math.ceil(self.D * FPS)) + 2
        w, h = self.sprite.size
        base = self.set.baseline
        v = self.speed
        xs, ys, ang, cam, vel = [], [], [], [], []
        m = self.motion
        if m in ("track", "float"):
            for i in range(n):
                t = i / FPS
                ramp = smooth(t / 4.0)  # camera eases in, never jumps
                vel.append(v * ramp if m == "track" else 0.0)
            c = 0.0
            for i in range(n):
                t = i / FPS
                cam.append(c)
                c += vel[i] / FPS
                drift = 60 * math.sin(2 * math.pi * t / 41)
                cx = (W * 0.62 - w + 330) if self.v["type"] == "train" else (W / 2 - w / 2)
                xs.append(cx + drift)
                ys.append(base - h + self._bob(t))
                ang.append(self._tilt(t))
        else:
            if m == "pass":
                # cross the whole scene unhurried: never faster than the spec's limit
                travel = W + w + 40
                v = min(v, travel / max(10.0, self.D - 14))
                self.speed_eff = v
                segs = [(self.D + 10, v, v)]
                x0 = -w - 20 - 2 * v
            elif m == "stop_and_go":
                stop_x = self.spec.get("stop_x", 1300) - w
                x0 = -w - 20
                decel_d = v * 6 / 2
                cruise = (stop_x - x0 - decel_d) / v
                segs = [(1, v, v), (cruise - 1, v, v), (6, v, 0.0), (self.spec.get("wait", 20), 0.0, 0.0),
                        (6, 0.0, v), (40, v, v)]
                x0 = x0 - v * 0  # starts already moving, just off-screen
            elif m in ("takeoff",):
                x0 = 120
                segs = [(8, 0.0, 0.0), (16, 0.0, v * 0.5), (40, v * 0.5, v), (60, v, v)]
            elif m == "landing":
                x0 = -w - 20
                touch = W - w - 80 - 8.75 * v
                self.touch = touch
                segs = [((touch - x0) / v, v, v), (12, v, v * 0.25), (10, v * 0.25, 0.0), (200, 0.0, 0.0)]
            elif m == "heli_land":
                x0 = -w - 20
                target = W / 2 - 260  # skids centred over the H
                cruise = (target - x0 - v * 8 / 2) / v
                segs = [(cruise, v, v), (8, v, 0.0), (200, 0.0, 0.0)]
            else:
                raise ValueError(m)
            vel = self._profile(segs)
            vel += [vel[-1]] * max(0, n - len(vel))
            x = x0
            for i in range(n):
                t = i / FPS
                xs.append(x)
                x += vel[i] / FPS
                cam.append(0.0)
                ang.append(self._tilt(t))
                ys.append(base - h + self._bob(t))
            if m == "takeoff":
                rot_x = 760  # rotate/lift off only after a long, slow roll
                for i in range(n):
                    climb = max(0.0, xs[i] - rot_x)
                    ys[i] -= climb * math.tan(math.radians(6)) * smooth(climb / 300)
                    ang[i] = 6 * smooth(climb / 260)
            elif m == "landing":
                for i in range(n):
                    d = max(0.0, self.touch - xs[i])
                    ys[i] -= d * math.tan(math.radians(7)) * smooth(d / 160)
                    ang[i] = -2.0 * smooth((d - 160) / 200)  # gentle descent attitude, level at touchdown
            elif m == "heli_land":
                hover_t = None
                for i in range(n):
                    if vel[i] == 0.0 and hover_t is None:
                        hover_t = i
                pad_y = 948 - 180  # skids touch the helipad
                start_y = ys[0] if hover_t is None else ys[hover_t]
                T = (pad_y - start_y) / 22 * 1.5  # average ~15 px/s, soft start and soft touchdown
                for i in range(n):
                    if hover_t is not None and i > hover_t + 4 * FPS:
                        k = (i - hover_t - 4 * FPS) / FPS
                        ys[i] = start_y + (pad_y - start_y) * smooth(k / T)
                self.hover_t = hover_t
        self.vel = vel
        self.xs, self.ys, self.ang, self.cam = xs, ys, ang, cam

    def _bob(self, t):
        typ = self.v["type"]
        if typ == "boat":
            return 5 * math.sin(2 * math.pi * t / 5.3) + 12
        if typ in ("helicopter", "airplane") and self.motion in ("track",):
            return 8 * math.sin(2 * math.pi * t / 9.0)
        if typ == "car":
            return 1.2 * math.sin(2 * math.pi * t / 1.9) if self.speed else 0
        if typ == "train":
            return 20
        return 0

    def _tilt(self, t):
        if self.v["type"] == "boat":
            return 1.4 * math.sin(2 * math.pi * t / 6.7)
        return 0.0

    def _plan_balloons(self):
        r = self.rng
        schemes = self.spec["vehicle"].get("schemes") or [self.v["scheme"]]
        self.balloons = []
        n = self.spec.get("count", 4)
        for i in range(n):
            scale = [0.35, 0.5, 0.7, 1.0, 0.45, 0.6][i % 6]
            img, _ = art.balloon(schemes[i % len(schemes)], self.seed + i)
            img = light(img.resize((int(img.width * scale), int(img.height * scale)), art.Image.LANCZOS), self.time)
            x0 = (i + 0.5) / n * W + r.uniform(-120, 120) - img.width / 2
            y0 = 80 + (1 - scale) * 320 + r.uniform(0, 160)
            self.balloons.append((scale, img, x0, y0, r.uniform(4, 9) * scale + 2, r.uniform(0, 6.28)))
        self.balloons.sort(key=lambda b: b[0])

    # ---------------------------------------------------------------- render
    def frame(self, t):
        i = min(int(t * FPS), len(self.xs) - 1)
        s = self.set
        cam = self.cam[i] * (-1 if self.left else 1)
        img = s.bg.copy()
        for c_img, x0, y, sp in s.clouds:
            span = W + c_img.width
            x = (x0 + sp * t - cam * 0.03) % span - c_img.width
            img.alpha_composite(c_img, (int(x), int(y)))
        for layer in s.layers:
            img.alpha_composite(layer.crop(cam, t), (0, layer.y))
        for p_img, (px, py) in s.props:
            img.alpha_composite(p_img, (px, py))
        if self.motion == "float":
            self._draw_balloons(img, t)
        else:
            if self.motion == "stop_and_go":
                self._draw_signal(img, t)
            self._draw_vehicle(img, i, t, cam)
            if self.motion == "stop_and_go":
                self._draw_walker(img, t)
        for kind, p_img, px, py, sp in s.front_props:
            x = px if not sp else (px + sp * t - cam) % (W + 100) - 100
            img.alpha_composite(p_img, (int(x), int(py)))
        if s.snow:
            d = ImageDraw.Draw(img)
            for x0, y0, vy, amp, ph, r in self.flakes:
                y = (y0 + vy * t) % (H + 20) - 10
                x = (x0 + amp * math.sin(t / 2.2 + ph) - cam * 0.4) % W
                d.ellipse([x - r, y - r, x + r, y + r], fill=(250, 252, 255, 230))
        if self.caption is not None:
            a = smooth((t - 1.5) / 1.5) * (1 - smooth((t - 8.0) / 1.5))
            if a > 0.01:
                cap = self.caption
                if a < 0.999:
                    cap = cap.copy()
                    cap.putalpha(cap.getchannel("A").point(lambda v: int(v * a)))
                img.alpha_composite(cap, ((W - cap.width) // 2, H - cap.height - 46))
        return img

    def _vehicle_xy(self, i):
        w = self.sprite.width
        x, y = self.xs[i], self.ys[i]
        if self.left:
            x = W - x - w
        return x, y

    def _draw_vehicle(self, img, i, t, cam):
        x, y = self._vehicle_xy(i)
        spr, glow = self.sprite, self.glow
        if self.v["type"] == "helicopter":
            spr = self._heli_sprite(i, t)
        a = self.ang[i] * (-1 if self.left else 1)
        if abs(a) > 0.05:
            w0, h0 = spr.size
            spr = spr.rotate(a, resample=Image.BICUBIC, expand=True)
            x -= (spr.width - w0) / 2
            y -= (spr.height - h0) / 2
            if glow is not None:
                glow = glow.rotate(a, resample=Image.BICUBIC, expand=True)
        if self.puffs is not None:
            self._draw_puffs(img, i, t)
        if x < W and x + spr.width > 0:
            img.alpha_composite(spr, (int(x), int(y)))
            if glow is not None:
                img.alpha_composite(glow, (int(x), int(y)))

    def _heli_sprite(self, i, t):
        # Rotor blur breathes very slowly; after landing it winds down smoothly. No strobing.
        phase = 2 * math.pi * t / 3.0
        spr, _ = art.helicopter(self.v["color"], self.seed, phase)
        spr = light(spr, self.time)
        return spr.transpose(Image.FLIP_LEFT_RIGHT) if self.left else spr

    def _draw_puffs(self, img, i, t):
        w = self.sprite.width
        chim_dx = w - 330 + 249  # chimney position inside the locomotive sprite
        for k in range(int(t / 1.4) - 5, int(t / 1.4) + 1):
            te = k * 1.4
            a = t - te
            if te < 0 or not (0 <= a <= 7):
                continue
            j = min(int(te * FPS), len(self.xs) - 1)
            ex = self.xs[j] + chim_dx
            sx = ex + self.cam[j] - self.cam[i] - 10 * a
            sy = self.ys[j] + 24 - 16 * a
            if self.left:
                sx = W - sx
            r = 14 + 5 * a
            pf = self.puffs.resize((int(r * 2 + 4), int(r * 2 + 4)))
            alpha = max(0.0, 1 - a / 7) * 0.9
            pf.putalpha(pf.getchannel("A").point(lambda v: int(v * alpha)))
            img.alpha_composite(pf, (int(sx - r), int(sy - r)))

    def _draw_signal(self, img, t):
        """Traffic light for cars + pedestrian walking on the crosswalk while cars wait."""
        stop_x = self.spec.get("stop_x", 1300)
        d = ImageDraw.Draw(img)
        # crosswalk stripes
        for k in range(6):
            yy = 806 + k * 32
            d.polygon([(stop_x + 30, yy), (stop_x + 150, yy), (stop_x + 156, yy + 18), (stop_x + 36, yy + 18)],
                      fill=(236, 236, 232))
        d.rectangle([stop_x + 4, 800, stop_x + 10, 1000], fill=(246, 246, 240))  # stop line
        # light timing: red while the car approaches and the walker crosses, then green
        arrive = self._arrival_time()
        wait = self.spec.get("wait", 20)
        green_at = arrive + wait - 2
        g = smooth((t - green_at) / 1.2)
        px = stop_x + 190  # far-side sidewalk, behind the road
        d.rectangle([px + 20, 560, px + 32, 800], fill=(70, 74, 84))
        d.rounded_rectangle([px, 480, px + 52, 620], radius=12, fill=(50, 54, 62))
        dim = (70, 70, 74)
        red = art.mix((236, 84, 72), dim, g)
        grn = art.mix(dim, (96, 210, 120), g)
        d.ellipse([px + 8, 490, px + 44, 526], fill=red)
        d.ellipse([px + 8, 532, px + 44, 568], fill=dim)
        d.ellipse([px + 8, 574, px + 44, 610], fill=grn)

    def _draw_walker(self, img, t):
        stop_x = self.spec.get("stop_x", 1300)
        arrive = self._arrival_time()
        wait = self.spec.get("wait", 20)
        # walker crosses only while the car is fully stopped
        w0 = arrive + 2
        u = (t - w0) / (wait - 6)
        if 0 <= u <= 1:
            y = 770 + 230 * smooth(u)
            img.alpha_composite(self.walker, (int(stop_x + 70), int(y - 60)))

    def _arrival_time(self):
        for i, v in enumerate(self.vel):
            if i > FPS and v == 0.0:
                return i / FPS
        return 20.0

    def _draw_balloons(self, img, t):
        for scale, b, x0, y0, sp, ph in self.balloons:
            x = (x0 + sp * t + b.width) % (W + 2 * b.width) - b.width
            y = y0 + 14 * scale * math.sin(2 * math.pi * t / 14 + ph) - 1.2 * t * scale
            img.alpha_composite(b, (int(x), int(y)))


def safety_review(spec):
    """Return a list of problems with a scene spec. Empty list == approved."""
    issues = []
    typ = spec["vehicle"]["type"]
    v = spec.get("speed", 60)
    if v > SPEED_LIMIT[typ]:
        issues.append(f"speed {v}px/s over the gentle limit {SPEED_LIMIT[typ]} for {typ}")
    m = spec["motion"]
    # every speed change in the engine takes >= 6 s, so acceleration = v/6
    if m in ("pass", "stop_and_go", "heli_land", "landing", "takeoff") and v / 6 > ACCEL_LIMIT:
        issues.append(f"acceleration {v / 6:.0f}px/s^2 too abrupt")
    if typ == "car" and m not in ("track", "stop_and_go", "pass"):
        issues.append("cars may only cruise, pass, or stop at the light")
    if m == "stop_and_go" and spec.get("wait", 20) < 14:
        issues.append("car must wait long enough for the pedestrian to finish crossing")
    if typ == "train" and "crossing" in spec.get("extras", []) and m not in ("pass", "track"):
        issues.append("train at crossing must pass steadily")
    if typ == "airplane" and m == "takeoff" and v > 110:
        issues.append("take-off roll too fast")
    if spec["time"] == "night" and typ in ("balloon",):
        issues.append("balloons do not fly at night")
    if typ == "helicopter" and m not in ("track", "heli_land"):
        issues.append("helicopters only cruise or land on a marked helipad")
    if m == "heli_land" and "helipad" not in spec.get("extras", []):
        issues.append("helicopter landing needs a marked helipad")
    return issues
