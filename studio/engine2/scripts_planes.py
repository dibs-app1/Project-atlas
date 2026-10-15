"""Airplane scenes: ground crew at the gate, pushback & taxi, take-off, climbing through clouds,
cruising above the clouds, rainy landing, seaplane, de-icing in snow, farm flight, night cargo."""
import math
import random

from PIL import Image, ImageDraw

from art import COLORS, cloud, light, mix, shade
from settings import periodic

from . import props as P
from . import vehicles as V
from .core import CW, FPS, M, W, Mover, smooth
from .scene import script
from .vehicles import FastPen as Pen

GROUND = 960       # wheel line on the apron / runway
APRON_TOP = 760
ZS = 1.4


def airport(s, snow=False, z=3):
    """Terminal, tower, hangars behind the apron; runway and taxiway markings in front."""
    hv = int(ROADLESS_TOP() / ZS)
    f = periodic(random.Random(s.seed + 3), 5)
    s.layer("hills", 0, hv, 0.06,
            lambda p, g, X0, X1, rng: P.mountains(p, f, X0, X1, M, hv - 60, 50, hv, (226, 234, 246) if snow else (140, 170, 140)),
            1, atmos=0.35, zoom=ZS)

    def build(p, g, X0, X1, rng):
        base = 290
        p.rect(0, base - 10, CW + 2 * M, 320, (240, 244, 250) if snow else (140, 186, 116))
        x = X0 + rng.uniform(0, 200)
        while x < X1:
            lx = x - X0 + M
            c = rng.random()
            if c < 0.45:   # terminal with big windows and a jet bridge
                p.rect(lx, base - 110, lx + 420, base, (214, 220, 230))
                p.rect(lx, base - 120, lx + 420, base - 108, (170, 178, 190))
                for wx in range(int(lx + 14), int(lx + 400), 34):
                    p.rect(wx, base - 96, wx + 26, base - 40, (160, 200, 230))
                    g.rect(wx, base - 96, wx + 26, base - 40, (255, 220, 150, 230))
                p.rect(lx + 300, base - 70, lx + 470, base - 44, (190, 196, 206), r=6)
                x += 520
            elif c < 0.6:  # control tower
                p.rect(lx + 30, base - 220, lx + 56, base, (220, 224, 232))
                p.poly([(lx, base - 262), (lx + 86, base - 262), (lx + 74, base - 214), (lx + 12, base - 214)], (120, 170, 210))
                g.poly([(lx, base - 262), (lx + 86, base - 262), (lx + 74, base - 214), (lx + 12, base - 214)], (255, 230, 160, 220))
                p.rect(lx - 4, base - 272, lx + 90, base - 260, (200, 204, 212))
                x += 160
            elif c < 0.8:  # hangar
                p.rect(lx, base - 90, lx + 260, base, (196, 200, 206))
                p.ellipse(lx - 4, base - 140, lx + 264, base - 40, (176, 182, 190))
                p.rect(lx + 60, base - 70, lx + 200, base, (120, 126, 136))
                x += 320
            else:
                P.tree(p, lx, base, rng.uniform(80, 120), rng, "pine" if snow else "round")
                x += 60
            x += rng.uniform(60, 200)
    s.layer("buildings", int(APRON_TOP - 320 * ZS), 320, 0.45, build, z, atmos=0.08, zoom=ZS)

    def apron(p, g, X0, X1, rng):
        w = CW + 2 * M
        base = (226, 232, 240) if snow else (150, 154, 162)
        p.rect(0, 0, w, 400, base)
        p.rect(0, 0, w, 18, (210, 216, 224) if snow else (128, 176, 104))
        for xw in range(int((X0 - M) // 240 * 240), int(X1 + M), 240):   # centre-line dashes and lights
            x = xw - X0 + M
            p.rect(x, GROUND - APRON_TOP - 56, x + 140, GROUND - APRON_TOP - 46, (246, 210, 80))
            p.circle(x, 30, 6, (250, 240, 200))
            g.circle(x, 30, 10, (255, 236, 170, 230))
        p.rect(0, GROUND - APRON_TOP + 50, w, 400, (220, 228, 238) if snow else (128, 176, 104))
    s.layer("apron", APRON_TOP, 400, 1.0, apron, 4)
    s.ground_y = GROUND


def ROADLESS_TOP():
    return APRON_TOP


def plane_actor(s, plane, path, z=6, shadow_ground=None):
    """path(t) -> (world x, ground y for the wheels, pitch degrees, state dict)."""
    def draw(f, t, cam):
        x, y, pitch, st = path(t)
        sx = x - cam
        if sx > W + 60 or sx + plane.w < -60:
            return
        if shadow_ground is not None:
            alt = shadow_ground - y
            if 0 < alt < 500:
                q = Pen(int(plane.w * 0.8), 30)
                q.ellipse(0, 0, plane.w * 0.8, 26, (20, 24, 30, int(80 * (1 - alt / 500))))
                f.alpha_composite(q.done(), (int(sx + plane.w * 0.1), int(shadow_ground - 14)))
        plane.draw(f, sx, y, x, t, tilt=pitch, state=st, shadow=False)
    s.add(z, draw)


def sky_clouds(s, z_back=1.5, z_front=7.5, front=True, sea=False, speed_scale=1.0):
    """Deep sky: cloud layers at several depths; some pass in front of the plane."""
    for name, depth, y, n, sc, z in (("c1", 0.12, 120, 5, 0.9, z_back), ("c2", 0.35, 260, 6, 1.3, z_back + 0.1),
                                     ("c3", 0.6, 560, 5, 1.6, z_back + 0.15)):
        def draw(p, g, X0, X1, rng, n=n, sc=sc):
            for _ in range(n):
                w = int(rng.uniform(220, 420) * sc)
                x = rng.uniform(X0, X1) - X0 + M
                yy = rng.uniform(0, 300)
                col = (255, 255, 255)
                for k in range(5):
                    p.circle(x + w * (0.15 + 0.7 * k / 4), yy + 60, w * rng.uniform(0.13, 0.2), col + (240,))
                p.rect(x, yy + 50, x + w, yy + 90, col + (240,), r=20)
        s.layer(name, y, 420, depth * speed_scale, draw, z)
    if sea:
        def floor(p, g, X0, X1, rng):
            p.rect(0, 120, CW + 2 * M, 500, (250, 250, 252))
            for _ in range(70):
                x = rng.uniform(X0 - M, X1 + M) - X0 + M
                p.circle(x, rng.uniform(90, 160), rng.uniform(50, 110), (252, 252, 254))
        s.layer("floor", 700, 500, 0.5 * speed_scale, floor, z_back + 0.2)
    if front:
        def near(p, g, X0, X1, rng):
            if rng.random() < 0.8:
                w = rng.uniform(500, 800)
                x = rng.uniform(X0, X1) - X0 + M
                yy = rng.uniform(60, 700)
                for k in range(6):
                    p.circle(x + w * k / 5, yy + 80, w * 0.16, (255, 255, 255, 235))
        s.layer("near", 0, 1000, 1.6 * speed_scale, near, z_front)


# ------------------------------------------------------------------ scripts

@script("airport_gate")
def airport_gate(s):
    """At the gate: bags go in, fuel goes in, food goes in, and the marshaller waves the plane in."""
    V.SCALE = 1.25
    airport(s)
    s._cam = [i / FPS * 10 for i in range(int(s.D * FPS) + 3)]
    plane = V.airliner(s.spec["vehicle"]["color"], s.seed, s.time)
    px = 200
    still = lambda t: (px + 0, GROUND, 0.0, {"gear": 1.0})  # noqa: E731
    plane_actor(s, plane, still, z=5.5)
    fuel = V.ground_vehicle("fuel", "red", s.seed + 1, s.time)
    s.road_vehicle(fuel, Mover(0, 0, s.D, lambda x, t, v: 0), GROUND + 40, 6.2, x0=px + plane.w * 0.30)
    cat = V.ground_vehicle("catering", "white", s.seed + 2, s.time)
    s.road_vehicle(cat, Mover(0, 0, s.D, lambda x, t, v: 0), GROUND + 50, 6.3, x0=px + plane.w * 0.62,
                   state=lambda t, d, v: {"lift": smooth((t - 18) / 6) * (1 - smooth((t - 44) / 6))})
    bag = V.ground_vehicle("baggage", "yellow", s.seed + 3, s.time)
    bmv = Mover(-bag.w - 100, 90, s.D, lambda x, t, v: 0 if 14 < t < 30 and x > px - 100 else 110)
    s.road_vehicle(bag, bmv, GROUND + 80, 6.6)

    def crew(f, t, cam):
        q = Pen(160, 240)
        V.marshaller(q, 70, 60, t, random.Random(s.seed), s=2.0)
        f.alpha_composite(q.done(), (int(px + plane.w + 160 - cam), GROUND + 60 - 220))
    s.add(6.8, crew)
    s.say(6, 12, "The baggage train brings the suitcases")
    s.say(19, 25, "Count the suitcases on the carts!")
    s.say(30, 36, "The fuel truck fills the tanks")
    s.say(42, 48, "The catering truck lifts up the food")
    s.sound("jet", level=lambda t: 0.25)


@script("pushback_taxi")
def pushback_taxi(s):
    """A pushback tug pushes the plane back from the gate, then the plane taxis to the runway."""
    V.SCALE = 1.25
    airport(s)
    plane = V.airliner(s.spec["vehicle"]["color"], s.seed, s.time)
    tug = V.ground_vehicle("pushback", "yellow", s.seed + 1, s.time)
    # first 18 s: pushed backwards slowly; then rolls forward along the taxiway
    def tgt(x, t, v):
        return 0.0 if t < 3 else (-40 if t < 18 else (0 if t < 22 else 150))
    xs, x, v = [], 0.0, 0.0
    for i in range(int(s.D * FPS) + 3):
        t = i / FPS
        want = tgt(x, t, v)
        v += max(-40 / FPS, min(40 / FPS, want - v))
        x += v / FPS
        xs.append(x)

    def pos(t):
        return xs[min(int(t * FPS), len(xs) - 1)]
    cams = [max(0.0, xx) * 0.9 - 200 for xx in xs]
    s._cam = cams
    plane_actor(s, plane, lambda t: (600 + pos(t), GROUND, 0.0, {"gear": 1.0}), z=5.5)

    def tug_draw(f, t, cam):
        if t > 21:
            return
        x = 600 + pos(t) + plane.w - 150 * plane.k
        tug.draw(f, x - cam, GROUND + 6, pos(t), t, flip=True)
    s.add(5.7, tug_draw)
    other = V.airliner("green", s.seed + 5, s.time)
    s.road_vehicle(other, Mover(0, 0, s.D, lambda x, t, v: 0), GROUND - 60, 5.0, x0=4200)

    def signs(f, t, cam):
        for i, xw in enumerate((2600, 5600)):
            x = xw - cam
            if -100 < x < W + 100:
                q = Pen(160, 200)
                P.sign(q, 80, 190, "taxiway", 110)
                f.alpha_composite(q.done(), (int(x), GROUND + 70 - 200))
    s.add(6.9, signs)
    s.say(4, 10, "A pushback tug pushes the plane backwards")
    s.say(24, 30, "Now the plane taxis to the runway")
    s.say(40, 46, "Yellow signs show the pilots the way")
    s.sound("jet", level=lambda t: 0.3 + 0.3 * smooth((t - 22) / 4))


@script("takeoff")
def takeoff(s):
    """Faster and faster down the runway, nose up, wheels up, and into the sky."""
    V.SCALE = 1.25
    airport(s)
    plane = V.airliner(s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 0.0, s.D, lambda x, t, v: 0 if t < 3 else 520, accel=26)
    s.follow(mv, 0.25)
    t_rot = next((i / FPS for i, v in enumerate(mv.v) if v > 380), 20)

    def path(t):
        x, v = mv.at(t)
        a = max(0.0, t - t_rot)
        climb = 46 * a * a / (1 + a * 0.6) if a > 0 else 0
        pitch = 7 * smooth(a / 2.5)
        gear = 1 - smooth((a - 3) / 3)
        return x, GROUND - min(climb, 560), pitch, {"gear": gear, "flaps": 0.6 * (1 - smooth((a - 8) / 4))}
    plane_actor(s, plane, path, z=6, shadow_ground=GROUND)
    s.say(4, 10, "The engines roar... faster and faster!")
    s.say(t_rot - 1, t_rot + 5, "Nose up! The plane takes off")
    s.say(t_rot + 6, t_rot + 12, "The wheels fold up inside the plane")
    s.sound("jet", level=lambda t: 0.3 + 0.7 * smooth((t - 3) / 6))


@script("cloud_climb")
def cloud_climb(s):
    """Climbing through layers of clouds: some float behind the plane, some whoosh past in front."""
    V.SCALE = 1.2
    sky_clouds(s, sea=False, speed_scale=1.0)
    plane = V.airliner(s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 340, s.D, lambda x, t, v: 340)
    s.follow(mv, 0.3)
    plane_actor(s, plane, lambda t: (mv.at(t)[0], 640 + 30 * math.sin(t / 4), 4.0 + 1.5 * math.sin(t / 6), {"gear": 0.0}))
    s.say(6, 12, "Up, up through the clouds")
    s.say(26, 32, "Clouds are made of tiny drops of water")
    s.sound("jet", level=lambda t: 0.6)


@script("above_clouds")
def above_clouds(s):
    """Cruising above a sea of clouds; other planes far away draw white contrails."""
    V.SCALE = 1.0
    sky_clouds(s, sea=True, front=False, speed_scale=0.8)
    plane = V.airliner(s.spec["vehicle"]["color"], s.seed, s.time, jumbo=s.spec["vehicle"].get("jumbo", False))
    mv = Mover(0.0, 300, s.D, lambda x, t, v: 300)
    s.follow(mv, 0.3)
    plane_actor(s, plane, lambda t: (mv.at(t)[0], 560 + 14 * math.sin(t / 3), 0.0, {"gear": 0.0}))

    def far_planes(f, t, cam):
        d = ImageDraw.Draw(f)
        for i, (t0, y, sp) in enumerate(((4, 160, 60), (22, 230, -50), (38, 120, 70))):
            a = t - t0
            if a < 0:
                continue
            x = -100 + a * sp if sp > 0 else W + 100 + a * sp
            tail = x - 360 * (1 if sp > 0 else -1)
            d.line([(tail, y + 4), (x, y + 4)], fill=(255, 255, 255, 190), width=6)
            d.polygon([(x - 18, y), (x + 18 * (1 if sp > 0 else -1), y + 3), (x - 18, y + 8)], fill=(240, 240, 244))
    s.add(1.4, far_planes)
    s.say(6, 12, "High above the clouds")
    s.say(22, 28, "Look! Another plane makes a white line called a contrail")
    s.sound("jet", level=lambda t: 0.5)


@script("rain_landing")
def rain_landing(s):
    """Landing in the rain: wheels down, flaps out, a puff of smoke as the tyres touch."""
    V.SCALE = 1.25
    airport(s)
    plane = V.airliner(s.spec["vehicle"]["color"], s.seed, s.time)
    v0 = 420
    t_touch = 16.0
    mv = Mover(0.0, v0, s.D, lambda x, t, v: v0 if t < t_touch else (60 if t < t_touch + 20 else 60), decel=22)
    s.follow(mv, 0.3)

    def path(t):
        x, v = mv.at(t)
        a = max(0.0, t_touch - t)
        alt = min(520, 32 * a * (1 + a * 0.1))
        return x, GROUND - alt, -2.0 * smooth(a / 4) + 1.5 * smooth(1 - a / 2), {"gear": smooth((t - 2) / 3), "flaps": 0.9}
    plane_actor(s, plane, path, z=6, shadow_ground=GROUND)

    def puff(f, t, cam):
        a = t - t_touch
        if 0 <= a <= 2.0:
            d = ImageDraw.Draw(f)
            x0 = 0.3 * W + plane.w * 0.5 - 60 * a
            for k in range(6):
                r = 20 + 30 * a + k * 6
                d.ellipse([x0 - k * 30 - r, GROUND - r - 10, x0 - k * 30 + r, GROUND + r * 0.4 - 10],
                          fill=(240, 240, 240, int(170 * (1 - a / 2))))
    s.add(6.5, puff)
    s.say(4, 10, "Wheels down! Getting ready to land")
    s.say(t_touch, t_touch + 6, "Touchdown! Puff go the tyres")
    s.say(t_touch + 14, t_touch + 20, "The plane slows down on the wet runway")
    s.sound("rain", level=lambda t: 1.0)
    s.sound("jet", level=lambda t: 0.6 * (1 - smooth((t - t_touch - 6) / 6)) + 0.15)
    s.sound("bump", at=t_touch)


@script("seaplane")
def seaplane(s):
    """A seaplane glides down and lands on the lake with a big splash, then floats to the dock."""
    from .scripts_boats import far_shore, water
    V.SCALE = 1.6
    far_shore(s, "mountains")
    w = water(s, c_top=(110, 170, 200), c_bot=(40, 100, 150), amp=7, lane=200)
    plane = V.small_plane(s.spec["vehicle"]["color"], s.seed, s.time, floats=True)
    t_touch = 14.0
    mv = Mover(0.0, 300, s.D, lambda x, t, v: 300 if t < t_touch else 40, decel=24)
    s.follow(mv, 0.3)

    def path(t):
        x, v = mv.at(t)
        a = max(0.0, t_touch - t)
        surf = w.surface(x + plane.w / 2, t)
        alt = min(480, 28 * a * (1 + a * 0.1))
        return x, surf - alt + 14 * smooth(1 - a / 1.0), 2.0 * smooth(1 - a / 3), {}
    plane_actor(s, plane, path, z=6)

    def splash(f, t, cam):
        x, v = mv.at(t)
        if t > t_touch and v > 50:
            d = ImageDraw.Draw(f)
            r = random.Random(int(t * 24))
            sx = x - cam + plane.w * 0.4
            for _ in range(int(v / 4)):
                u = r.uniform(0, 1)
                px = sx - u * 220 + r.uniform(-30, 30)
                py = w.surface(x, t) - u * 80 * (v / 300) + r.uniform(-10, 10)
                rr = r.uniform(3, 8)
                d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(250, 252, 255, int(220 * (1 - u))))
    s.add(6.4, splash)
    s.say(4, 10, "A seaplane has floats instead of wheels")
    s.say(t_touch, t_touch + 6, "Splash! It lands on the water")
    s.say(34, 40, "Now it floats like a boat")
    s.sound("prop", level=lambda t: 0.7 - 0.4 * smooth((t - t_touch) / 6))
    s.sound("splash", at=t_touch)
    s.sound("waves", level=lambda t: 0.4)


@script("deicing")
def deicing(s):
    """Snow at the airport: the de-icing truck sprays the wings so the plane can fly safely."""
    V.SCALE = 1.25
    airport(s, snow=True)
    s._cam = [i / FPS * 8 for i in range(int(s.D * FPS) + 3)]
    plane = V.airliner(s.spec["vehicle"]["color"], s.seed, s.time)
    leave = 42.0
    mv = Mover(0.0, 0.0, s.D, lambda x, t, v: 0 if t < leave else 120, accel=20)
    plane_actor(s, plane, lambda t: (300 + mv.at(t)[0], GROUND, 0.0, {"gear": 1.0}), z=5.5)
    de = V.ground_vehicle("deicer", "orange", s.seed + 1, s.time)
    dmv = Mover(0.0, 0.0, s.D, lambda x, t, v: 0)
    s.road_vehicle(de, dmv, GROUND + 70, 6.5, x0=300 + plane.w * 0.36,
                   state=lambda t, d, v: {"boom": 0.4 + 0.6 * smooth((t - 6) / 4) * (1 - smooth((t - 38) / 3)),
                                           "spray": 1 if 10 < t < 37 else 0})
    s.say(6, 12, "Brrr! Snow on the airport")
    s.say(14, 20, "The de-icing truck sprays warm liquid on the plane")
    s.say(leave, leave + 6, "All clean! The plane is ready to go")
    s.sound("wind", level=lambda t: 0.6)
    s.sound("water", level=lambda t: 0.5 if 10 < t < 37 else 0.0)


@script("farm_flight")
def farm_flight(s):
    """A little plane flies low over farms: fields, barns, cows, a tractor and a red barn."""
    V.SCALE = 1.7
    hv = 400
    f = periodic(random.Random(s.seed + 3), 5)
    s.layer("hills", 0, hv, 0.05,
            lambda p, g, X0, X1, rng: P.mountains(p, f, X0, X1, M, hv - 50, 60, hv, (140, 176, 130)), 1, atmos=0.35, zoom=2.0)

    def fields(p, g, X0, X1, rng):
        x = X0 - M
        cols = [(214, 196, 110), (130, 176, 96), (170, 140, 96), (150, 190, 100), (226, 210, 120)]
        while x < X1 + M:
            w = rng.uniform(300, 700)
            c = rng.choice(cols)
            p.rect(x - X0 + M, 40, x - X0 + M + w, 420, c)
            for yy in range(60, 420, 26):
                p.rect(x - X0 + M, yy, x - X0 + M + w, yy + 6, shade(c, 0.9))
            x += w
        x = X0 + rng.uniform(0, 300)
        while x < X1:
            lx = x - X0 + M
            c = rng.random()
            if c < 0.35:
                P.barn(p, g, lx, 140, rng)
            elif c < 0.7:
                for j in range(rng.randint(2, 4)):
                    P.animal(p, lx + j * 70, 260 + rng.uniform(-20, 20), rng.choice(["cow", "sheep", "horse"]), rng)
            else:
                P.tree(p, lx, 160, rng.uniform(100, 150), rng)
            x += rng.uniform(400, 800)
    s.layer("farm", 600, 420, 0.45, fields, 2)
    plane = V.small_plane(s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 260, s.D, lambda x, t, v: 260)
    s.follow(mv, 0.35)
    plane_actor(s, plane, lambda t: (mv.at(t)[0], 400 + 40 * math.sin(t / 5), 2 * math.cos(t / 5), {}), z=6)
    tr = V.car("pickup", "red", s.seed + 4, s.time)
    s.say(6, 12, "A little propeller plane over the farm")
    s.say(22, 28, "Can you see the cows and the red barn?")
    s.say(38, 44, "The propeller spins round and round")
    s.sound("prop", level=lambda t: 0.7)
    _ = tr


@script("night_cargo")
def night_cargo(s):
    """At night, a cargo plane opens its nose and a loader drives the boxes inside."""
    V.SCALE = 1.25
    airport(s)
    s._cam = [i / FPS * 8 for i in range(int(s.D * FPS) + 3)]
    plane = V.airliner(s.spec["vehicle"]["color"], s.seed, s.time, cargo=True)
    px = 120
    plane_actor(s, plane, lambda t: (px, GROUND, 0.0, {"gear": 1.0, "nose": smooth((t - 4) / 4)}), z=5.5)
    cols = [COLORS[c] for c in ("red", "blue", "yellow", "green", "orange", "teal")]
    nose_x = px + plane.w - 80

    def loader(f, t, cam):
        cyc = (t - 8) % 10.0
        if t < 8:
            return
        n = int((t - 8) // 10)
        u = smooth(cyc / 4) if cyc < 5 else 1 - smooth((cyc - 5) / 4)
        x = nose_x + 900 - 760 * u
        q = Pen(360, 300)
        q.rect(10, 200, 350, 260, (230, 180, 60), r=10)
        q.rect(250, 120, 340, 200, (230, 180, 60), r=8)
        q.rect(266, 132, 330, 180, (180, 210, 230), r=6)
        V.person(q, 298, 150, 1.0, random.Random(2), vest=True, bust=True)
        for wx in (60, 300):
            q.circle(wx, 270, 26, (44, 46, 54))
        if cyc < 5:
            c = cols[n % len(cols)]
            q.rect(20, 110, 200, 200, c, r=4)
            for k in range(1, 6):
                q.line([(20 + k * 30, 114), (20 + k * 30, 196)], shade(c, 0.85), 3)
        f.alpha_composite(q.done(), (int(x - cam), GROUND + 40 - 300))
    s.add(6.4, loader)
    for k in range(5):
        s.pop(8 + k * 10 + 4.2, lambda tt: (nose_x - s.cam(tt) + 200, GROUND - 520), str(k + 1))
    s.say(4, 10, "The cargo plane opens its big nose")
    s.say(14, 20, "A loader drives the boxes inside")
    s.say(30, 36, "Let's count the boxes")
    s.sound("beep", at=9.0)
    s.sound("jet", level=lambda t: 0.2)
