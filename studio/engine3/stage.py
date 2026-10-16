"""Engine 3 stage: a scene = scenery + moving actors + a list of camera shots (angles) + sounds.

Camera angles (rigs) show each vehicle from different points of view:
  side    alongside, riding with it              front   it drives towards us and passes by
  chase   following behind                       top     straight down from above (bird's eye)
  orbit   slowly circling round it               cockpit the driver's / pilot's own view
  low     from near the ground, looking up       drone   high up, alongside and a bit behind
Shots dissolve softly into each other (no hard cuts).
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw

from . import r3d as R
from . import world as Wd
from .r3d import SS, H, W

SCENES = {}


def scene(name):
    def deco(fn):
        SCENES[name] = fn
        return fn
    return deco


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


# ------------------------------------------------------------------ actors

class Actor:
    """A model moving along a path with a speed profile. pose(t) -> pos, yaw, pitch, roll, dist, speed."""

    def __init__(self, model, path, speed_fn, s0=0.0, D=60.0, offset=0.0, z=0.0, bob=0.0, bank=0.0, reverse=False,
                 alt_fn=None, pitch_fn=None):
        self.model, self.path, self.offset, self.z = model, path, offset, z
        self.bob, self.bank, self.reverse = bob, bank, reverse
        self.alt_fn, self.pitch_fn = alt_fn, pitch_fn
        n = int(D * 24) + 48
        self.s = np.zeros(n)
        self.v = np.zeros(n)
        s = s0
        for i in range(n):
            t = i / 24
            v = speed_fn(t)
            self.s[i], self.v[i] = s, v
            s += v / 24 * (-1 if reverse else 1)

    def _i(self, t):
        return min(max(0, int(t * 24)), len(self.s) - 2), (t * 24) % 1

    def state(self, t):
        i, u = self._i(t)
        s = self.s[i] + (self.s[i + 1] - self.s[i]) * u
        v = self.v[i]
        x, y, z, h = self.path.side(s, self.offset)
        if self.reverse:
            h += math.pi
        z += self.z + (self.alt_fn(t) if self.alt_fn else 0.0)
        pitch = self.pitch_fn(t) if self.pitch_fn else 0.0
        roll = 0.0
        if self.bob:
            z += self.bob * math.sin(t * 1.7 + x * 0.05)
            pitch += self.bob * 0.05 * math.sin(t * 1.3 + 1)
            roll = self.bob * 0.06 * math.sin(t * 1.1 + 2)
        if self.bank:
            x2, y2, _, h2 = self.path.side(s + 5, self.offset)
            dh = (h2 - h + math.pi) % (2 * math.pi) - math.pi
            roll += -dh * self.bank
        return np.array([x, y, z]), h, pitch, roll, abs(s), v

    def objs(self, t):
        pos, h, p, r, d, v = self.state(t)
        return self.model.objs(pos, h, p, r, dist=d, t=t, state={"v": v})

    def point(self, t, local):
        pos, h, p, r, d, v = self.state(t)
        return pos + R.ypr(h, p, r) @ np.asarray(local, float)


class TrainActor:
    def __init__(self, train, path, speed_fn, s0=0.0, D=60.0, offset=0.0):
        self.train, self.path, self.offset = train, path, offset
        self.model = train.engine
        n = int(D * 24) + 48
        self.s = np.zeros(n)
        self.v = np.zeros(n)
        s = s0
        for i in range(n):
            v = speed_fn(i / 24)
            self.s[i], self.v[i] = s, v
            s += v / 24

    def front_s(self, t):
        i = min(max(0, int(t * 24)), len(self.s) - 2)
        u = (t * 24) % 1
        return self.s[i] + (self.s[i + 1] - self.s[i]) * u

    def state(self, t):
        s = self.front_s(t) - self.train.offsets[0]
        x, y, z, h = self.path.side(s, self.offset)
        i = min(max(0, int(t * 24)), len(self.v) - 1)
        return np.array([x, y, z]), h, 0.0, 0.0, s, self.v[i]

    def objs(self, t):
        return self.train.objs(lambda s: self.path.side(s, self.offset), self.front_s(t), self.front_s(t), t)

    def point(self, t, local):
        pos, h, p, r, d, v = self.state(t)
        return pos + R.ypr(h) @ np.asarray(local, float)


# ------------------------------------------------------------------ camera rigs

def _look(pos, target, fov, roll=0.0):
    return R.Camera(pos, target=target, fov=fov, roll=roll)


def rig_side(actor, dist=None, h=1.7, side=-1, lead=0.0, fov=42, look_h=None, sway=0.4):
    L = actor.model.length

    def cam(t):
        pos, hd, *_ = actor.state(t)
        d = dist or max(11.0, L * 1.6 + 3.0)
        n = np.array([-math.sin(hd), math.cos(hd), 0.0]) * side
        f = np.array([math.cos(hd), math.sin(hd), 0.0])
        hh = h if pos[2] < 3 else actor.model.height * 0.75 + h * 0.3     # flying: look from wing level
        c = pos + n * d + f * lead + np.array([0, 0, hh + sway * math.sin(t * 0.37)])
        tg = pos + f * lead + np.array([0, 0, look_h if look_h is not None else actor.model.height * 0.45])
        return _look(c, tg, fov)
    return cam


def rig_front(actor, t_pass, off=7.0, h=1.4, fov=40, look_h=None, ahead=0.0):
    """A fixed camera beside the path; the vehicle comes towards it, passes, and we turn to watch it go."""
    pos_p, hd_p, *_ = actor.state(t_pass)
    n = np.array([-math.sin(hd_p), math.cos(hd_p), 0.0])
    f = np.array([math.cos(hd_p), math.sin(hd_p), 0.0])
    c = pos_p + n * off + f * ahead + np.array([0, 0, h])

    def cam(t):
        pos, hd, *_ = actor.state(t)
        tg = pos + np.array([0, 0, look_h if look_h is not None else actor.model.height * 0.5])
        return _look(c, tg, fov)
    return cam


def rig_chase(actor, back=None, h=None, fov=50, look_ahead=20.0, side=0.0):
    L = actor.model.length

    def cam(t):
        pos, hd, p, r, *_ = actor.state(t)
        f = np.array([math.cos(hd), math.sin(hd), 0.0])
        n = np.array([-math.sin(hd), math.cos(hd), 0.0])
        b = back or max(10.0, L * 1.4)
        c = pos - f * b + n * side + np.array([0, 0, h if h is not None else actor.model.height + 2.0])
        return _look(c, pos + f * look_ahead + np.array([0, 0, actor.model.height * 0.5]), fov)
    return cam


def rig_top(actor, alt=None, fov=40, lead=0.0):
    L = actor.model.length

    def cam(t):
        pos, hd, *_ = actor.state(t)
        f = np.array([math.cos(hd), math.sin(hd), 0.0])
        a = alt or max(30.0, L * 2.6)
        return R.Camera(pos + f * lead + np.array([0, 0, a]), yaw=hd + math.pi / 2, pitch=-math.pi / 2 + 1e-3, fov=fov)
    return cam


def rig_orbit(actor, radius=None, h=None, speed=0.12, phase=0.0, fov=40):
    L = actor.model.length

    def cam(t):
        pos, hd, *_ = actor.state(t)
        rr = radius or max(12.0, L * 1.5)
        a = hd + phase + t * speed
        c = pos + np.array([math.cos(a) * rr, math.sin(a) * rr, h if h is not None else actor.model.height + 3])
        return _look(c, pos + np.array([0, 0, actor.model.height * 0.45]), fov)
    return cam


def rig_cockpit(actor, fov=72, pitch=-0.06, eye=None):
    def cam(t):
        pos, hd, p, r, *_ = actor.state(t)
        e = np.asarray(eye if eye is not None else actor.model.eye, float)
        c = pos + R.ypr(hd, p, r) @ e
        return R.Camera(c, yaw=hd, pitch=p + pitch, roll=-r * 0.5, fov=fov)
    return cam


def rig_low(actor, t_pass, off=5.0, fov=55):
    return rig_front(actor, t_pass, off=off, h=0.35, fov=fov, look_h=actor.model.height * 0.6)


def rig_drone(actor, back=None, side=-1, h=None, fov=42):
    L = actor.model.length

    def cam(t):
        pos, hd, *_ = actor.state(t)
        f = np.array([math.cos(hd), math.sin(hd), 0.0])
        n = np.array([-math.sin(hd), math.cos(hd), 0.0])
        b = back or max(25.0, L * 2.0)
        c = pos - f * b * 0.6 + n * side * b + np.array([0, 0, h or max(18.0, L * 1.2)])
        return _look(c, pos + f * L * 0.3, fov)
    return cam


def rig_fixed(pos, target_fn, fov=40):
    def cam(t):
        return _look(np.asarray(pos, float), target_fn(t), fov)
    return cam


RIGS = {"side": rig_side, "front": rig_front, "chase": rig_chase, "top": rig_top, "orbit": rig_orbit, "cockpit": rig_cockpit,
        "low": rig_low, "drone": rig_drone}


# ------------------------------------------------------------------ 2D overlays (drawn at supersampled size)

def dash_car(img, draw, cam, t, color=(36, 38, 46)):
    w, h = W * SS, H * SS
    draw.polygon([(0, h * 0.8), (w * 0.3, h * 0.74), (w * 0.7, h * 0.74), (w, h * 0.8), (w, h), (0, h)], fill=color)
    cx, cy, rr = w * 0.33, h * 1.02, h * 0.26
    draw.arc([cx - rr, cy - rr, cx + rr, cy + rr], 200, 340, fill=(20, 20, 24), width=int(26 * SS))
    for k, gx in enumerate((w * 0.55, w * 0.61)):
        draw.ellipse([gx - 50 * SS, h * 0.82 - 50 * SS, gx + 50 * SS, h * 0.82 + 50 * SS], fill=(20, 22, 28),
                     outline=(120, 124, 132), width=4 * SS)
        a = math.radians(200 + 60 * (0.5 + 0.3 * math.sin(t * 0.3 + k)))
        draw.line([(gx, h * 0.82), (gx + 40 * SS * math.cos(a), h * 0.82 + 40 * SS * math.sin(a))], fill=(240, 120, 60), width=4 * SS)


def frame_train(img, draw, cam, t):
    w, h = W * SS, H * SS
    c = (40, 44, 52)
    draw.rectangle([0, h * 0.84, w, h], fill=c)
    draw.rectangle([0, 0, w, h * 0.06], fill=c)
    draw.rectangle([w * 0.48, 0, w * 0.52, h * 0.84], fill=c)
    draw.rectangle([0, 0, w * 0.04, h], fill=c)
    draw.rectangle([w * 0.96, 0, w, h], fill=c)
    for k, gx in enumerate((w * 0.2, w * 0.27, w * 0.73)):
        draw.ellipse([gx - 44 * SS, h * 0.9 - 44 * SS, gx + 44 * SS, h * 0.9 + 44 * SS], fill=(16, 18, 22), outline=(140, 144, 150),
                     width=4 * SS)


def panel_plane(img, draw, cam, t):
    w, h = W * SS, H * SS
    c = (34, 36, 44)
    draw.polygon([(0, h * 0.74), (w * 0.5, h * 0.7), (w, h * 0.74), (w, h), (0, h)], fill=c)
    draw.rectangle([0, 0, w, h * 0.05], fill=c)
    draw.polygon([(0, 0), (w * 0.06, 0), (w * 0.02, h * 0.74), (0, h * 0.74)], fill=c)
    draw.polygon([(w, 0), (w * 0.94, 0), (w * 0.98, h * 0.74), (w, h * 0.74)], fill=c)
    for k in range(6):
        gx = w * (0.28 + 0.088 * k)
        gy = h * 0.83
        draw.ellipse([gx - 52 * SS, gy - 52 * SS, gx + 52 * SS, gy + 52 * SS], fill=(14, 16, 20), outline=(150, 154, 160), width=4 * SS)
        if k == 2:   # artificial horizon
            draw.chord([gx - 46 * SS, gy - 46 * SS, gx + 46 * SS, gy + 46 * SS], 0, 180, fill=(140, 96, 60))
            draw.chord([gx - 46 * SS, gy - 46 * SS, gx + 46 * SS, gy + 46 * SS], 180, 360, fill=(70, 130, 200))
        else:
            a = math.radians(210 + 120 * (0.5 + 0.4 * math.sin(t * 0.2 + k)))
            draw.line([(gx, gy), (gx + 42 * SS * math.cos(a), gy + 42 * SS * math.sin(a))], fill=(240, 240, 240), width=4 * SS)
    draw.rectangle([w * 0.47, h * 0.9, w * 0.53, h], fill=(20, 20, 24))
    draw.rectangle([w * 0.42, h * 0.88, w * 0.58, h * 0.91], fill=(20, 20, 24))


_PUFF = {}


def _puff(r, col, a):
    """A soft round puff (alpha fades out towards the edge)."""
    rq = max(2, min(360, int(r // 4 * 4)))
    key = (rq, col, int(a * 20))
    if key not in _PUFF:
        size = rq * 2 + 4
        yy, xx = np.mgrid[0:size, 0:size]
        d = np.hypot(xx - size / 2, yy - size / 2) / (rq + 1)
        al = np.clip(1 - d, 0, 1) ** 1.5 * 255 * a
        arr = np.zeros((size, size, 4), np.uint8)
        arr[..., :3] = col
        arr[..., 3] = al.astype(np.uint8)
        im = Image.fromarray(arr, "RGBA")
        if len(_PUFF) > 400:
            _PUFF.clear()
        _PUFF[key] = im
    return _PUFF[key]


def smoke(source_fn, every=0.25, life=4.0, rise=1.6, drift=(-1.0, 0.0), size=0.8, grow=1.4, col=(236, 236, 236), alpha=0.55,
          active=lambda t: True):
    """3D puffs (steam, exhaust, dust): source_fn(t) -> world point where puffs are born."""
    def draw_fn(img, draw, cam, t):
        k1 = int(t / every)
        for k in range(max(0, k1 - int(life / every) - 1), k1 + 1):
            te = k * every
            a = t - te
            if a < 0 or a > life or not active(te):
                continue
            p = np.asarray(source_fn(te), float) + np.array([drift[0] * a, drift[1] * a, rise * a])
            s = cam.screen(p)
            if s is None:
                continue
            x, y, z = s
            rad = (size + grow * a) * cam.f / z
            if rad < 1 or rad > 360:      # too close to the camera: skip rather than fill the screen
                continue
            im = _puff(rad, col, alpha * (1 - a / life) ** 1.3)
            img.paste(im, (int(x * SS - im.width / 2), int(y * SS - im.height / 2)), im)
    return draw_fn


class Snowfall:
    def __init__(self, seed, n=500, heavy=1.0):
        r = random.Random(seed)
        self.f = [(r.uniform(0, W), r.uniform(0, H), r.uniform(30, 90) * heavy, r.uniform(0, 6.28), r.uniform(2, 5)) for _ in range(n)]

    def __call__(self, img, draw, cam, t):
        for x, y, sp, ph, rr in self.f:
            yy = (y + t * sp) % H
            xx = (x + 25 * math.sin(t * 0.6 + ph) - cam.yaw * 300) % W
            draw.ellipse([(xx - rr) * SS, (yy - rr) * SS, (xx + rr) * SS, (yy + rr) * SS], fill=(250, 252, 255))


class Rain:
    def __init__(self, seed, n=380):
        r = random.Random(seed)
        self.d = [(r.uniform(0, W), r.uniform(0, H), r.uniform(0.7, 1.3)) for _ in range(n)]

    def __call__(self, img, draw, cam, t):
        for x, y, s in self.d:
            yy = (y + t * 1400 * s) % H
            xx = (x - t * 120 * s) % W
            draw.line([(xx * SS, yy * SS), ((xx - 5) * SS, (yy + 26 * s) * SS)], fill=(196, 206, 224), width=2 * SS)


# ------------------------------------------------------------------ the stage

class Stage:
    def __init__(self, spec, D):
        self.spec, self.D = spec, D
        self.seed = spec["seed"]
        self.time = spec.get("time", "day")
        self.r = random.Random(self.seed)
        self.rend = Wd.renderer(self.time if spec.get("weather") not in ("snow", "rain") else
                                ("snow" if spec.get("weather") == "snow" else "overcast"), self.seed)
        self.static = []
        self.actors = []          # objects with objs(t)
        self.dynamic = []         # fn(t) -> list of Obj
        self.overlays = []        # fn(img, draw, cam, t) drawn over the 3D picture
        self.cam_overlays = {}    # shot index -> overlay (dashboards)
        self.shots = []           # (t0, t1, rig)
        self.sounds = []          # dict(kind, pos=fn(t) or None, level=fn(t), ...)
        self.hero = None          # actor whose noise the song features
        self.captions = []
        SCENES[spec["script"]](self)
        if spec.get("weather") == "snow":
            self.overlays.append(Snowfall(self.seed))
        if spec.get("weather") == "rain":
            self.overlays.append(Rain(self.seed))

    def add(self, objs):
        self.static.extend(objs)

    def shot_plan(self, rigs, overlays=None, actor=None):
        """Split the scene evenly between camera angles. Each entry is a fn(t) -> Camera, or a name
        ("side", "front", "chase", "top", "orbit", "cockpit", "low", "drone") or (name, kwargs) applied to the actor."""
        n = len(rigs)
        actor = actor or self.hero
        for k, rg in enumerate(rigs):
            t0, t1 = self.D * k / n, self.D * (k + 1) / n
            if not callable(rg):
                name, kw = (rg, {}) if isinstance(rg, str) else rg
                kw = dict(kw)
                if name in ("front", "low"):    # it reaches the camera near the end of the shot
                    kw.setdefault("t_pass", t0 + (t1 - t0) * kw.pop("at", 0.62))
                if name == "cockpit" and overlays is not None and k not in overlays:
                    ov = {"car": dash_car, "bus": dash_car, "truck": dash_car, "tractor": dash_car,
                          "steam": frame_train, "diesel": frame_train, "electric": frame_train,
                          "airliner": panel_plane, "small_plane": panel_plane, "helicopter": panel_plane}
                    nm = actor.model.name
                    ov = ov.get("car" if nm in ("sedan", "hatch", "suv", "pickup", "taxi", "van") else nm)
                    if ov:
                        overlays[k] = ov
                rg = RIGS[name](actor, **kw)
            self.shots.append((t0, t1, rg))
        for k, ov in (overlays or {}).items():
            self.cam_overlays[k] = ov

    def camera_at(self, t):
        """Camera position used for sound (the current shot)."""
        for t0, t1, rg in self.shots:
            if t0 <= t < t1:
                return rg(t)
        return self.shots[-1][2](t)

    def _render(self, k, t):
        t0, t1, rg = self.shots[k]
        cam = rg(t)
        objs = list(self.static)
        for a in self.actors:
            objs += a.objs(t)
        for fn in self.dynamic:
            objs += fn(t, cam)
        ovs = [lambda img, draw, c, fn=fn: fn(img, draw, c, t) for fn in self.overlays]
        if k in self.cam_overlays:
            ov = self.cam_overlays[k]
            ovs.append(lambda img, draw, c: ov(img, draw, c, t))
        return self.rend.render(objs, cam, ovs)

    def frame(self, t):
        XF = 1.2
        for k, (t0, t1, rg) in enumerate(self.shots):
            if t0 <= t < t1:
                if k + 1 < len(self.shots) and t > t1 - XF / 2:
                    u = smooth((t - (t1 - XF / 2)) / XF)
                    return Image.blend(self._render(k, t), self._render(k + 1, t), u)
                if k > 0 and t < t0 + XF / 2:
                    u = smooth((t - (t0 - XF / 2)) / XF)
                    return Image.blend(self._render(k - 1, t), self._render(k, t), u)
                return self._render(k, t)
        return self._render(len(self.shots) - 1, t)
