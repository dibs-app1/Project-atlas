"""Train scenes: steam train, bullet train, freight counting, station stop, level crossing,
mountain tunnel, river bridge, snowplow train, elevated city metro, night sleeper."""
import math
import random

from PIL import ImageDraw

from art import COLORS, mix, shade
from settings import periodic

from . import props as P
from . import vehicles as V
from .core import CW, FPS, M, W, Mover, smooth, stop_target
from .scene import script
from .vehicles import FastPen as Pen

TRACK = 930        # wheel line
ZS = 1.4


def scenery(s, kind="country", snow=False, depth=0.55, z=3):
    hv = int((TRACK - 60) / ZS)
    f = periodic(random.Random(s.seed + 3), 6)
    if kind == "mountains" or snow:
        far = (226, 234, 246) if snow else (124, 140, 172)
        s.layer("far", 0, hv, 0.06, lambda p, g, X0, X1, rng: P.mountains(p, f, X0, X1, M, hv - 210, 230, hv, far, (250, 252, 255)),
                1, atmos=0.3, zoom=ZS)
    else:
        s.layer("far", 0, hv, 0.06, lambda p, g, X0, X1, rng: P.mountains(p, f, X0, X1, M, hv - 60, 60, hv, (140, 176, 130)),
                1, atmos=0.35, zoom=ZS)

    def mid(p, g, X0, X1, rng):
        base = 210
        ground = (244, 246, 252) if snow else ((222, 196, 140) if kind == "desert" else (128, 176, 104))
        p.rect(0, base, CW + 2 * M, 260, ground)
        if kind == "rice":
            for yy in range(base + 6, 260, 12):
                p.rect(0, yy, CW + 2 * M, yy + 4, (150, 196, 120))
        x = X0 + rng.uniform(0, 200)
        while x < X1:
            lx = x - X0 + M
            c = rng.random()
            if kind == "desert":
                if c < 0.5:
                    h = rng.uniform(40, 80)
                    p.rect(lx - 8, base - h, lx + 8, base, (106, 150, 100), r=8)
                    p.rect(lx - 26, base - h * 0.7, lx - 18, base - h * 0.35, (106, 150, 100), r=4)
                    p.rect(lx - 26, base - h * 0.4, lx, base - h * 0.33, (106, 150, 100), r=3)
                else:
                    w = rng.uniform(140, 260)
                    p.poly([(lx, base), (lx + 30, base - rng.uniform(60, 120)), (lx + w - 30, base - 100), (lx + w, base)], (200, 130, 96))
                x += rng.uniform(200, 400)
            elif snow:
                P.tree(p, lx, base, rng.uniform(100, 160), rng, "pine", col=(70, 108, 92))
                p.poly([(lx - 20, base - 70), (lx + 20, base - 70), (lx, base - 140)], (246, 248, 252))
                x += rng.uniform(70, 160)
            elif kind == "rice":
                if c < 0.2:
                    P.house(p, g, lx, base, 110, 70, rng)
                    x += 100
                else:
                    P.tree(p, lx, base, rng.uniform(70, 110), rng)
                x += rng.uniform(220, 420)
            else:
                if c < 0.4:
                    P.tree(p, lx, base, rng.uniform(100, 160), rng, rng.choice(["round", "round", "pine", "birch"]))
                elif c < 0.55:
                    P.house(p, g, lx, base, rng.uniform(110, 150), rng.uniform(70, 90), rng)
                    x += 120
                elif c < 0.65:
                    P.barn(p, g, lx, base, rng)
                    x += 220
                elif c < 0.85:
                    for j in range(rng.randint(1, 3)):
                        P.animal(p, lx + j * 70, base + 10, rng.choice(["cow", "sheep", "horse"]), rng)
                    x += 120
                else:
                    P.bush(p, lx, base, 36, rng.choice(P.LEAF))
                x += rng.uniform(120, 240)
    s.layer("mid", int(TRACK - 70 - 230 * ZS), 260, depth, mid, z, atmos=0.06, zoom=ZS)


def rails(s, snow=False, bridge=False, elevated=False, z=4, y=None):
    track = y or TRACK
    s.track = track

    def draw(p, g, X0, X1, rng):
        w = CW + 2 * M
        top = 60
        if not (bridge or elevated):
            p.poly([(0, top + 30), (w, top + 30), (w, top + 70), (0, top + 70)], (170, 160, 150) if not snow else (236, 240, 248))
            p.rect(0, top + 70, w, 400, (128, 176, 104) if not snow else (244, 246, 252))
        for xw in range(int((X0 - M) // 46 * 46), int(X1 + M), 46):
            x = xw - X0 + M
            p.rect(x, top + 22, x + 30, top + 34, (120, 92, 70))
        p.rect(0, top + 14, w, top + 22, (150, 154, 164))
        p.rect(0, top + 16, w, top + 18, (210, 214, 222))
        if elevated:
            p.rect(0, top + 34, w, top + 70, (190, 194, 202))
            for xw in range(int((X0 - M) // 600 * 600), int(X1 + M), 600):
                x = xw - X0 + M
                p.rect(x - 30, top + 70, x + 30, 400, (176, 180, 190))
        if bridge:
            p.rect(0, top + 34, w, top + 54, (180, 70, 60))
            for xw in range(int((X0 - M) // 160 * 160), int(X1 + M), 160):
                x = xw - X0 + M
                p.line([(x, top + 54), (x + 80, top + 300), (x + 160, top + 54)], (180, 70, 60), 12)
            for xw in range(int((X0 - M) // 1600 * 1600), int(X1 + M), 1600):
                x = xw - X0 + M
                p.rect(x - 40, top + 54, x + 40, 420, (150, 140, 130))
    s.layer("rails", track - 60 - 18, 420, 1.0, draw, z)
    s.ground_y = track


def catenary(s, z=7.2, depth=1.3):
    """Overhead electric wires on tall poles that whoosh past in front."""
    def draw(p, g, X0, X1, rng):
        for xw in range(int((X0) // 700 * 700), int(X1), 700):
            x = xw - X0 + M
            p.rect(x - 9, 0, x + 9, 760, (120, 126, 138))
            p.rect(x - 9, 100, x + 120, 112, (120, 126, 138))
        p.rect(M, 120, CW + M, 124, (60, 64, 76))
    s.layer("catenary", 120, 800, depth, draw, z)


def poles(s, z=7.2, depth=1.3):
    def draw(p, g, X0, X1, rng):
        for xw in range(int(math.ceil(X0 / 520) * 520), int(X1), 520):
            P.pole(p, xw - X0 + M, 760, 640)
        for dy in (0, 26):
            pts = [(xw - X0 + M, 140 + dy + 40 * 4 * ((xw % 520) / 520) * (1 - (xw % 520) / 520))
                   for xw in range(int(X0), int(X1) + 9, 8)]
            p.line(pts, (60, 60, 66), 3)
    s.layer("poles", 160, 800, depth, draw, z)


def make_train(s, engine_kind, color, cars, car_kind="coach", car_colors=None, numbered=False, cargo_cycle=None):
    eng = V.loco(engine_kind, color, s.seed, s.time)
    units = []
    for i in range(cars):
        kind = cargo_cycle[i % len(cargo_cycle)] if cargo_cycle else car_kind
        col = car_colors[i % len(car_colors)] if car_colors else color
        units.append(V.railcar(kind, col, s.seed + 10 + i, s.time, number=(i + 1) if numbered else None))
    return V.Train(eng, units)


def run(s, train, mv, anchor=0.55, z=5.5, x0=0.0, follow=True, smoke=None):
    if follow:
        s.follow(mv, anchor, offset=train.front())
    track = getattr(s, "track", TRACK)
    s.train_actor(train, mv, track, z, x0=x0)
    eng = train.engine
    if hasattr(eng, "chimney") and smoke is not False:
        cx, cy = eng.chimney
        ox = train.offsets[-1]
        s.smoke(mv, lambda d: (x0 + d + ox + cx, track - eng.ground + cy), z + 0.1, every=0.35, life=3.6,
                col=(236, 236, 240), drift=(-30, -60), size=18)
    s.sound("train", speed=lambda t: mv.at(t)[1], car=train.units[0].w)
    if hasattr(eng, "chimney"):
        s.sound("chug", speed=lambda t: mv.at(t)[1], wheel=2 * math.pi * 46 * eng.k)


# ------------------------------------------------------------------ scripts

@script("steam_country")
def steam_country(s):
    V.SCALE = 1.4
    scenery(s, "country")
    rails(s)
    tr = make_train(s, "steam", s.spec["vehicle"]["color"], 4, "coach", ["red", "blue", "yellow", "green"])
    mv = Mover(0.0, 260, s.D, lambda x, t, v: 260)
    run(s, tr, mv, anchor=0.62)
    poles(s)
    s.say(6, 12, "Choo choo! A steam train")
    s.say(20, 26, "Watch the rods push the big wheels round")
    s.say(38, 44, "Puff, puff! Steam comes out of the chimney")
    for t0 in (16, 40):
        s.sound("whistle", at=t0)


@script("bullet_train")
def bullet_train(s):
    V.SCALE = 1.3
    scenery(s, "rice", depth=0.4)
    rails(s)
    eng = V.loco("highspeed", s.spec["vehicle"]["color"], s.seed, s.time)
    tr = V.Train(eng, [V.railcar("coach", (246, 246, 244), s.seed + i, s.time) for i in range(4)])
    mv = Mover(0.0, 300, s.D, lambda x, t, v: 760, accel=40)
    run(s, tr, mv, anchor=0.6, smoke=False)
    catenary(s)
    s.say(6, 12, "A bullet train is very, very fast")
    s.say(22, 28, "It gets power from the wires above")
    s.say(40, 46, "Whoosh! Past the rice fields")


@script("freight_count")
def freight_count(s):
    V.SCALE = 1.3
    scenery(s, "desert", depth=0.5)
    rails(s)
    s._cam = [0.0] * (int(s.D * FPS) + 3)
    cols = ["red", "blue", "yellow", "green", "orange", "teal", "purple", "red", "blue", "green"]
    tr = make_train(s, "diesel", s.spec["vehicle"]["color"], 10, car_colors=cols, numbered=True,
                    cargo_cycle=["container"])
    v = tr.length / (s.D - 8)
    mv = Mover(-tr.length - 40, v, s.D, lambda x, t, vv: v)
    run(s, tr, mv, follow=False)
    # numbers pop above each car as it passes the middle of the screen
    for i in range(10):
        ox = tr.offsets[9 - i] + tr.units[9 - i].w / 2
        for fi in range(len(mv.x)):
            if mv.x[fi] + ox >= W / 2:
                s.pop(fi / FPS, lambda tt, ox=ox: (mv.at(tt)[0] + ox, TRACK - 340), str(i + 1))
                break
    s.say(3, 9, "A long freight train! Let's count the cars")
    s.say(s.D - 9, s.D - 3, "Ten cars full of things for people")


@script("station_stop")
def station_stop(s):
    V.SCALE = 1.35
    scenery(s, "country")
    rails(s)

    def station(f, t, cam):
        q = Pen(1700, 520)
        q.rect(0, 420, 1700, 520, (196, 196, 200))
        q.rect(0, 420, 1700, 432, (246, 210, 60))
        q.rect(60, 20, 1640, 60, (190, 70, 60), r=8)
        for x in range(120, 1640, 300):
            q.rect(x, 60, x + 16, 420, (120, 126, 138))
        q.rect(700, 80, 1000, 140, (40, 60, 110), r=6)
        q.rect(720, 94, 980, 126, (250, 210, 90), r=3)
        f.alpha_composite(q.done(), (int(100 - cam * 0.9), TRACK - 520 - 40))
    s.add(3.6, station)
    tr = make_train(s, "diesel", s.spec["vehicle"]["color"], 3, "metro")
    stop_line = 100 + 1500
    t_open = 18.0
    mv = Mover(-tr.length - 300, 220, s.D, stop_target(220, [(stop_line, t_open + 14)], tr.front(), a=60))
    s.follow(mv, 0.0, offset=tr.front() - W * 0.0)
    s._cam = [max(0.0, c - 1700) for c in s._cam]
    run(s, tr, mv, follow=False)

    def doors(f, t, cam):
        u = smooth((t - t_open) / 1.2) * (1 - smooth((t - t_open - 11) / 1.2))
        if u <= 0:
            return
        d, _ = mv.at(t)
        dr = ImageDraw.Draw(f)
        for j, unit in enumerate(tr.units[:-1]):
            x = d + tr.offsets[j] - cam + unit.w / 2
            w = 40 * unit.k * u
            dr.rectangle([x - w, TRACK - 196 * unit.k, x + w, TRACK - 40 * unit.k], fill=(40, 44, 52))
    s.add(5.7, doors)
    r = random.Random(s.seed)
    for k in range(5):
        def walker(f, t, cam, k=k):
            t0 = t_open + 1.5 + k * 1.6
            if t > t0 + 2.2:
                return
            u = smooth((t - t0) / 2.0)
            x = 300 + k * 260 + 120 - u * 120 - cam * 0.9
            q = Pen(140, 200)
            V.person(q, 60, 60, 1.8, random.Random(s.seed + 30 + k), phase=(t * 7 if 0 < u < 1 else None))
            f.alpha_composite(q.done(), (int(x), TRACK - 40 - 190 + int(-30 * u)))
        s.add(5.8 if k % 2 else 3.8, walker)
    s.say(4, 10, "The train is coming into the station")
    s.say(t_open, t_open + 6, "The doors open. People get on")
    s.say(t_open + 13, t_open + 19, "Stand behind the yellow line!")
    s.sound("chime", at=t_open - 0.5)
    s.sound("chime", at=t_open + 11)


@script("level_crossing")
def level_crossing(s):
    V.SCALE = 1.25
    scenery(s, "country")
    rails(s)
    s._cam = [0.0] * (int(s.D * FPS) + 3)
    road_x = 1180
    down = (8.0, s.D - 10)

    def road(f, t, cam):
        q = Pen(700, 480)
        q.poly([(300, 0), (400, 0), (700, 480), (0, 480)], (92, 96, 106))
        for k in range(6):
            y0 = 20 + k * 80
            q.rect(345 + (y0 / 480) * 2, y0, 355, y0 + 40, (246, 210, 80))
        f.alpha_composite(q.done(), (road_x - 350, TRACK - 120))
    s.add(3.9, road)

    def gate(f, t, cam):
        a = smooth((t - down[0]) / 3) * (1 - smooth((t - down[1]) / 3))
        q = Pen(700, 420)
        q.rect(80, 120, 96, 420, (240, 240, 240))
        q.rect(60, 90, 116, 130, (40, 40, 44), r=8)
        q.circle(74, 110, 13, (236, 70, 60) if a > 0.05 else (90, 40, 40))
        q.circle(102, 110, 13, (236, 70, 60) if a > 0.05 else (90, 40, 40))
        P.sign(q, 88, 160, "rail", 0)
        ang = math.radians(-80 * (1 - a))
        x0, y0 = 96, 300
        L = 540
        for k in range(9):
            sx = x0 + (L * k / 9) * math.cos(ang)
            sy = y0 + (L * k / 9) * math.sin(ang)
            ex = x0 + (L * (k + 1) / 9) * math.cos(ang)
            ey = y0 + (L * (k + 1) / 9) * math.sin(ang)
            q.line([(sx, sy), (ex, ey)], (230, 60, 54) if k % 2 == 0 else (250, 250, 250), 16)
        f.alpha_composite(q.done(), (road_x + 140, TRACK + 140 - 420))
    s.add(7.0, gate)

    def car_wait(f, t, cam):
        q = Pen(260, 220)
        q.rect(20, 40, 240, 180, (70, 120, 200), r=26)
        q.rect(50, 10, 210, 70, (70, 120, 200), r=20)
        q.rect(62, 20, 198, 64, (180, 210, 230), r=10)
        q.rect(30, 110, 70, 132, (230, 72, 64), r=4)
        q.rect(190, 110, 230, 132, (230, 72, 64), r=4)
        q.rect(100, 140, 160, 160, (250, 250, 240), r=3)
        q.rect(26, 176, 76, 214, (44, 46, 54), r=8)
        q.rect(184, 176, 234, 214, (44, 46, 54), r=8)
        yy = 1080 - 230 + (0 if t < down[1] + 3 else -int(140 * smooth((t - down[1] - 3) / 4)))
        f.alpha_composite(q.done(), (road_x - 130, yy))
    s.add(7.1, car_wait)
    tr = make_train(s, "diesel", s.spec["vehicle"]["color"], 4, "coach", ["red", "blue", "yellow", "green"])
    v = (W + tr.length + 200) / (down[1] - down[0] - 8)
    mv = Mover(-tr.length - 300 - v * (down[0] + 3), v, s.D, lambda x, t, vv: v)
    run(s, tr, mv, follow=False)
    s.say(4, 10, "Ding ding! The gate comes down")
    s.say(14, 20, "Cars wait behind the gate")
    s.say(down[1] - 1, down[1] + 5, "The train has gone. The gate goes up")
    s.sound("bell", level=lambda t: 0.5 if down[0] - 1 < t < down[1] else 0.0)
    s.sound("horn", at=down[0] + 3)


@script("tunnel")
def tunnel(s):
    V.SCALE = 1.35
    scenery(s, "mountains")
    rails(s)
    tr = make_train(s, "diesel", s.spec["vehicle"]["color"], 4, "coach", ["red", "teal", "yellow", "blue"])
    mv = Mover(0.0, 340, s.D, lambda x, t, v: 340)
    run(s, tr, mv, anchor=0.62, smoke=False)
    x_in, length = 340 * 16 + 1800, 340 * 11
    ceil = TRACK - 440
    cache = {}

    def mountain_img():
        if "m" not in cache:
            w = int(length + 1800)
            q = Pen(w, TRACK + 20)
            pts = [(0, TRACK + 20)]
            for i in range(0, 41):
                u = i / 40
                hgt = math.sin(math.pi * u) ** 0.7 * 560 + 30 * math.sin(u * 23)
                pts.append((u * w, TRACK + 20 - 160 - hgt if 0.05 < u < 0.95 else TRACK + 20 - 160 * math.sin(math.pi * u / 0.1) if u <= 0.05 else TRACK + 20 - 160 * math.sin(math.pi * (1 - u) / 0.1)))
            pts.append((w, TRACK + 20))
            q.poly(pts, (112, 142, 112))
            q.poly([(w * 0.3, TRACK - 600), (w * 0.5, TRACK - 760), (w * 0.7, TRACK - 600)], (246, 248, 252))
            for _ in range(40):  # rocks and grass tufts
                rx, ry = random.uniform(200, w - 200), random.uniform(TRACK - 520, ceil - 20)
                q.ellipse(rx - 30, ry - 14, rx + 30, ry + 14, (100, 128, 100))
            # the tunnel: a lit cutaway through the mountain
            q.rect(880, ceil, w - 880, TRACK + 20, (52, 50, 56))
            q.rect(880, ceil, w - 880, ceil + 30, (90, 84, 80))
            for lx in range(1000, w - 880, 320):
                q.circle(lx, ceil + 50, 12, (255, 222, 150))
            for xx in (880, w - 880):  # stone portals
                q.rect(xx - 60, ceil - 40, xx + 60, TRACK + 20, (160, 154, 146))
                for yy in range(int(ceil - 30), TRACK, 50):
                    q.line([(xx - 60, yy), (xx + 60, yy)], (130, 124, 118), 3)
            cache["m"] = q.done()
        return cache["m"]

    def mountain(f, t, cam):
        x = x_in - 880 - cam
        img = mountain_img()
        if x > W or x + img.width < 0:
            return
        f.alpha_composite(img, (int(x), 0))
    s.add(3.95, mountain)
    s.say(6, 12, "The train goes into a tunnel")
    s.say(22, 28, "Inside the tunnel, lamps light the way")
    s.say(40, 46, "Out into the sunshine again!")
    s.sound("horn", at=16.0)


@script("river_bridge")
def river_bridge(s):
    from .scripts_boats import water
    V.SCALE = 1.25
    hv = int(600 / ZS)
    f = periodic(random.Random(s.seed + 3), 6)
    s.layer("far", 0, hv, 0.06, lambda p, g, X0, X1, rng: P.mountains(p, f, X0, X1, M, hv - 60, 70, hv, (130, 170, 128)),
            1, atmos=0.35, zoom=ZS)
    w = water(s, c_top=(110, 168, 200), c_bot=(40, 96, 150), amp=6, top=600, lane=380)
    rails(s, bridge=True)
    tr = make_train(s, "steam", s.spec["vehicle"]["color"], 4, "coach", ["red", "blue", "green", "yellow"])
    mv = Mover(0.0, 220, s.D, lambda x, t, v: 220)
    run(s, tr, mv, anchor=0.6)
    boat = V.boat("sailboat", "yellow", s.seed + 4, s.time)
    bmv = Mover(0.0, 50, s.D, lambda x, t, v: 50)
    s.boat_actor(boat, bmv, w, 6.5, x0=600)
    s.say(6, 12, "Over the big red bridge")
    s.say(22, 28, "Boats sail under the bridge")
    s.say(40, 46, "Wave to the boats!")
    s.sound("waves", level=lambda t: 0.3)


@script("snow_train")
def snow_train(s):
    V.SCALE = 1.4
    scenery(s, "mountains", snow=True)
    rails(s, snow=True)
    tr = make_train(s, "diesel", s.spec["vehicle"]["color"], 3, "coach", ["red", "red", "red"])
    mv = Mover(0.0, 200, s.D, lambda x, t, v: 200)
    run(s, tr, mv, anchor=0.6, smoke=False)

    def plow(f, t, cam):
        d, v = mv.at(t)
        x = d + tr.front() - cam
        q = Pen(120, 140)
        q.poly([(0, 20), (100, 120), (0, 120)], (240, 170, 50))
        f.alpha_composite(q.done(), (int(x - 6), TRACK - 130))
        dr = ImageDraw.Draw(f)
        r = random.Random(int(t * 24))
        for _ in range(70):
            u = r.uniform(0, 1)
            sx, sy = x + 60 + u * 260, TRACK - 60 - math.sin(u * math.pi) * 200 + r.uniform(-16, 16)
            rr = r.uniform(4, 10)
            dr.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(250, 252, 255, int(230 * (1 - u * 0.5))))
    s.add(5.8, plow)
    s.say(6, 12, "A snow train! The plow pushes the snow away")
    s.say(26, 32, "Snow flies up in the air")
    s.sound("wind", level=lambda t: 0.6)


@script("city_metro")
def city_metro(s):
    V.SCALE = 1.25
    hv = 520

    def city(p, g, X0, X1, rng):
        x = X0 + rng.uniform(0, 40)
        while x < X1:
            w = rng.uniform(150, 260)
            P.building(p, g, x - X0 + M, hv, w, rng.uniform(260, 500), rng)
            x += w + rng.uniform(6, 30)
    s.layer("city", int(880 - hv * ZS * 0.9), hv, 0.4, city, 2, atmos=0.1, zoom=ZS * 0.9)

    def street(p, g, X0, X1, rng):
        p.rect(0, 0, CW + 2 * M, 300, (92, 96, 106))
        for xw in range(int((X0 - M) // 200 * 200), int(X1 + M), 200):
            p.rect(xw - X0 + M, 120, xw - X0 + M + 100, 128, (246, 210, 80))
    s.layer("street", 880, 300, 1.0, street, 3)
    rails(s, elevated=True, y=700)
    tr = make_train(s, "diesel", s.spec["vehicle"]["color"], 3, "metro")
    mv = Mover(0.0, 300, s.D, lambda x, t, v: 300)
    run(s, tr, mv, anchor=0.6, smoke=False)
    for i in range(6):
        car = V.car(random.Random(i).choice(["sedan", "taxi", "hatch", "van"]), ["red", "yellow", "blue", "green", "white", "orange"][i],
                    s.seed + 20 + i, s.time)
        speed = 200 + 25 * (i % 3)
        s.road_vehicle(car, Mover(0.0, speed, s.D, lambda x, t, v, sp=speed: sp), 1040, 3.5, x0=1200 + i * 2600)
    s.say(6, 12, "A metro train runs high above the street")
    s.say(26, 32, "Cars drive on the road below")
    s.sound("traffic", level=lambda t: 0.3)


@script("night_sleeper")
def night_sleeper(s):
    V.SCALE = 1.35
    scenery(s, "country")
    rails(s)
    tr = make_train(s, "diesel", s.spec["vehicle"]["color"], 5, "sleeper", ["navy", "navy", "navy", "navy", "navy"])
    mv = Mover(0.0, 220, s.D, lambda x, t, v: 220)
    run(s, tr, mv, anchor=0.65, smoke=False)
    poles(s)
    s.say(6, 12, "The night train carries people while they sleep")
    s.say(26, 32, "Look at the moon and the stars")
    s.say(44, 50, "Goodnight, little train")
