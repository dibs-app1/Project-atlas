"""Boat scenes: ocean sailing with dolphins, busy container port, river kayaks, speedboat and buoys,
rain on the lake, car ferry, fishing trawler with gulls, paddle steamer, sailing race, night harbour."""
import math
import random

from PIL import Image, ImageDraw

from art import COLORS, TIMES, mix, shade
from settings import periodic

from . import props as P
from . import vehicles as V
from .core import CW, FPS, M, W, Mover, Water, smooth
from .scene import script
from .vehicles import FastPen as Pen

TOP = 640          # water line at the horizon
ZS = 1.4


def far_shore(s, kind, z=1, depth=0.06, top=TOP):
    hv = int(top / ZS) + 4
    f = periodic(random.Random(s.seed + 3), 5)

    def draw(p, g, X0, X1, rng):
        base = hv
        if kind == "islands":
            x = X0 + rng.uniform(0, 400)
            while x < X1:
                w = rng.uniform(160, 380)
                lx = x - X0 + M
                p.ellipse(lx, base - 40, lx + w, base + 20, (100, 146, 118))
                for j in range(rng.randint(1, 3)):
                    P.tree(p, lx + w * (0.3 + 0.2 * j), base - 26, rng.uniform(40, 60), rng, "palm")
                x += w + rng.uniform(500, 900)
        elif kind == "hills":
            P.mountains(p, f, X0, X1, M, base - 40, 70, hv + 10, (110, 150, 120))
        elif kind == "mountains":
            P.mountains(p, f, X0, X1, M, base - 90, 160, hv + 10, (120, 136, 168), snow=(244, 246, 250))
        elif kind == "city":
            x = X0 + rng.uniform(0, 40)
            while x < X1:
                w = rng.uniform(50, 110)
                h = rng.uniform(60, 230)
                c = rng.choice([(170, 160, 150), (150, 160, 176), (190, 172, 150), (160, 150, 170)])
                lx = x - X0 + M
                p.rect(lx, base - h, lx + w, base, c)
                for wy in range(int(base - h + 10), int(base - 10), 20):
                    for wx in range(int(lx + 8), int(lx + w - 10), 16):
                        if (wx * 7 + wy) % 3:
                            g.rect(wx, wy, wx + 8, wy + 10, (255, 214, 140, 230))
                x += w + rng.uniform(0, 20)
        elif kind == "coast":
            P.mountains(p, f, X0, X1, M, base - 30, 60, hv + 10, (120, 170, 110))
            for xw in range(int(X0 // 1800 * 1800 + 900), int(X1), 1800):
                lx = xw - X0 + M
                y = base - 30 - 60 * f(xw)
                p.rect(lx - 12, y - 110, lx + 12, y + 4, (246, 244, 236))
                for k in range(3):
                    p.rect(lx - 12, y - 100 + k * 36, lx + 12, y - 84 + k * 36, COLORS["red"])
                p.rect(lx - 16, y - 126, lx + 16, y - 110, (250, 230, 150))
                g.rect(lx - 16, y - 126, lx + 16, y - 110, (255, 240, 170, 255))
    s.layer("shore", top - hv * ZS + 6, hv, depth, draw, z, atmos=0.3, zoom=ZS)


def water(s, c_top=(110, 168, 200), c_bot=(40, 96, 150), amp=12, choppy=1.0, rain=None, top=TOP, z=2, lane=230):
    w = Water(s.world, top, mix(c_top, TIMES[s.time][1], 0.25), c_bot, amp, choppy, rain)
    w.lane = lane
    s.world.water = w
    s.add(z, lambda f, t, cam: w.render_back(f, t, cam))
    s.ground_y = top + lane
    return w


def glints(s, w, z=2.2):
    """Shimmering reflection of the sun or moon on the water."""
    sx = TIMES[s.time][3][0] * W
    r = random.Random(s.seed)
    marks = [(r.uniform(-120, 120), r.uniform(0, 1), r.uniform(20, 80), r.uniform(0, 6)) for _ in range(40)]
    col = TIMES[s.time][3][3]

    def draw(f, t, cam):
        d = ImageDraw.Draw(f)
        for dx, v, ln, ph in marks:
            y = TOP + 16 + v * 300
            a = 0.5 + 0.5 * math.sin(t * 2 + ph)
            x = sx + dx * (0.5 + v)
            d.line([(x - ln / 2, y), (x + ln / 2, y)], fill=col + (int(150 * a * (1 - v * 0.6)),), width=3)
    s.add(z, draw)


def follow_boat(s, veh, mv, w, anchor=0.3, z=5, **kw):
    s.follow(mv, anchor)
    s.boat_actor(veh, mv, w, z, **kw)
    s.sound("waves", level=lambda t: 0.6)
    s.sound("motor", level=lambda t: min(1.0, mv.at(t)[1] / 300 + 0.2))


def gulls(s, center, n=5, z=6.5, radius=(160, 70)):
    """Seagulls circling above a point (center(t) -> screen x, y)."""
    r = random.Random(s.seed + 8)
    birds = [(r.uniform(0, 6.28), r.uniform(0.5, 0.9), r.uniform(0.7, 1.2)) for _ in range(n)]

    def draw(f, t, cam):
        cx, cy = center(t, cam)
        d = ImageDraw.Draw(f)
        for ph, sp, sc in birds:
            a = ph + t * sp
            x, y = cx + radius[0] * sc * math.cos(a), cy + radius[1] * sc * math.sin(a)
            wing = 12 * math.sin(t * 7 + ph)
            d.line([(x - 20, y - wing), (x, y), (x + 20, y - wing)], fill=(250, 250, 250, 255), width=5)
            d.line([(x - 20, y - wing), (x - 26, y - wing - 3)], fill=(60, 60, 66, 255), width=4)
            d.line([(x + 20, y - wing), (x + 26, y - wing - 3)], fill=(60, 60, 66, 255), width=4)
    s.add(z, draw)


def buoys(s, w, xs, z=4.5):
    def draw(f, t, cam):
        for i, xw in enumerate(xs):
            x = xw - cam
            if -60 < x < W + 60:
                y = w.surface(xw, t) + 30
                c = (214, 60, 54) if i % 2 == 0 else (70, 160, 90)
                q = Pen(60, 130)
                q.rect(16, 40, 44, 110, c, r=6)
                q.poly([(16, 40), (44, 40), (30, 6)], c)
                q.rect(16, 70, 44, 80, (250, 250, 250))
                f.alpha_composite(q.done().rotate(-math.degrees(math.atan(w.slope(xw, t))), resample=Image.BICUBIC),
                                  (int(x - 30), int(y - 110)))
    s.add(z, draw)


_DOLPHIN = None


def dolphin_img():
    global _DOLPHIN
    if _DOLPHIN is None:
        q = V.Pen(220, 90, 1.5)
        q.ellipse(20, 26, 190, 70, (120, 140, 166))
        q.ellipse(40, 46, 170, 72, (226, 232, 240))
        q.poly([(180, 44), (214, 50), (182, 56)], (120, 140, 166))      # beak
        q.poly([(90, 30), (110, 4), (120, 32)], (110, 130, 156))        # fin
        q.poly([(24, 46), (0, 26), (6, 50), (0, 72)], (110, 130, 156))  # tail
        q.circle(166, 42, 3, (30, 30, 40))
        _DOLPHIN = q.done()
    return _DOLPHIN


def dolphins(s, w, base_x, z=4.8, every=5.5):
    """Dolphins leaping in arcs beside the boat, with a splash on the way in and out."""
    r = random.Random(s.seed + 9)
    jumps = []
    t = 3.0
    while t < s.D - 3:
        jumps.append((t, r.uniform(-500, 500), r.uniform(220, 320)))
        t += r.uniform(every * 0.7, every * 1.3)

    def draw(f, t, cam):
        img = dolphin_img()
        d = ImageDraw.Draw(f)
        for t0, dx, span in jumps:
            a = (t - t0) / 1.6
            if not (-0.2 <= a <= 1.25):
                continue
            bx = base_x(t0) + dx
            xw = bx + span * a
            y0 = w.surface(xw, t) + 40
            if 0 <= a <= 1:
                y = y0 - 230 * math.sin(math.pi * a)
                ang = math.degrees(math.atan2(230 * math.pi * math.cos(math.pi * a), span))
                im = img.rotate(ang, resample=Image.BICUBIC, expand=True)
                f.alpha_composite(im, (int(xw - cam - im.width / 2), int(y - im.height / 2)))
            for sx, ta in ((bx, 0.0), (bx + span, 1.0)):
                k = abs(a - ta)
                if k < 0.25:
                    for j in range(8):
                        ang2 = math.pi * (0.15 + 0.7 * j / 7)
                        rr = 80 * (k / 0.25 + 0.2)
                        px, py = sx - cam + rr * math.cos(ang2) * 0.8, w.surface(sx, t) + 30 - rr * math.sin(ang2)
                        d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(250, 252, 255, int(230 * (1 - k / 0.25))))
    s.add(z, draw)
    for t0, _, _ in jumps:
        s.sound("splash", at=t0)


# ------------------------------------------------------------------ scripts

@script("ocean_dolphins")
def ocean_dolphins(s):
    V.SCALE = 1.5
    far_shore(s, "islands")
    w = water(s, amp=16, choppy=1.2)
    glints(s, w)
    boat = V.boat("sailboat", s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 150, s.D, lambda x, t, v: 150)
    follow_boat(s, boat, mv, w, anchor=0.3, heel=-7.0)
    dolphins(s, w, lambda t: mv.at(t)[0] + W * 0.55)
    s.say(8, 14, "The wind fills the sails")
    s.say(20, 26, "Dolphins jump out of the water!")
    s.say(40, 46, "Everyone on board wears a life jacket")


@script("busy_port")
def busy_port(s):
    V.SCALE = 1.0
    far_shore(s, "city", depth=0.03)

    def dock(p, g, X0, X1, rng):
        p.rect(0, 140, CW + 2 * M, 180, (150, 140, 128))
        x = X0 + rng.uniform(0, 300)
        while x < X1:
            P.containers(p, x - X0 + M, 140, rng, cols=rng.randint(3, 5), rows=rng.randint(2, 4))
            x += rng.uniform(600, 900)
        for xw in range(int(X0 // 70 * 70), int(X1), 70):
            p.rect(xw - X0 + M, 140, xw - X0 + M + 10, 186, (110, 100, 90))
    s.layer("dock", TOP - 180 * ZS + 40, 186, 0.4, dock, 1.5, zoom=ZS)
    w = water(s, c_top=(100, 150, 186), c_bot=(50, 96, 140), amp=6, lane=120)
    s._cam = [i / FPS * 22 for i in range(int(s.D * FPS) + 3)]
    ship = V.boat("container", "red", s.seed, s.time)
    still = Mover(0.0, 0.0, s.D, lambda x, t, v: 0.0)
    s.boat_actor(ship, still, w, 3.5, x0=200, wake=False)
    # gantry crane unloading containers, one every 12 seconds
    cols = [COLORS[c] for c in ("red", "blue", "yellow", "green", "orange", "teal")]
    cx0, dock_y = 1350, TOP - 30

    def crane(f, t, cam):
        q = Pen(900, 760)
        x = cx0 - cam
        q.rect(560, 120, 600, 760, (220, 70, 60))
        q.rect(760, 120, 800, 760, (220, 70, 60))
        q.rect(0, 100, 900, 140, (220, 70, 60))
        for k in range(14):
            q.line([(k * 64, 140), (k * 64 + 32, 100)], (190, 60, 50), 4)
        cyc = (t % 12.0) / 12.0
        # trolley path: over the ship (left), down, up, over the dock (right), down, up
        if cyc < 0.15:
            tx, drop, carry = 120 + (680 - 120) * (1 - cyc / 0.15), 0.0, False
        elif cyc < 0.3:
            tx, drop, carry = 120, math.sin((cyc - 0.15) / 0.15 * math.pi), False
        elif cyc < 0.35:
            tx, drop, carry = 120, 0.0, True
        elif cyc < 0.55:
            tx, drop, carry = 120 + (680 - 120) * smooth((cyc - 0.35) / 0.2), 0.0, True
        elif cyc < 0.75:
            u = (cyc - 0.55) / 0.2
            tx, drop, carry = 680, math.sin(u * math.pi), u < 0.5
        else:
            tx, drop, carry = 680, 0.0, False
        q.rect(tx - 40, 140, tx + 40, 170, (60, 60, 66), r=4)
        cable = 200 + drop * 300
        q.line([(tx - 20, 170), (tx - 20, 170 + cable)], (60, 60, 66), 3)
        q.line([(tx + 20, 170), (tx + 20, 170 + cable)], (60, 60, 66), 3)
        q.rect(tx - 64, 170 + cable, tx + 64, 180 + cable, (60, 60, 66))
        if carry:
            c = cols[int(t // 12) % len(cols)]
            q.rect(tx - 60, 180 + cable, tx + 60, 236 + cable, c, r=2)
            for k in range(1, 9):
                q.line([(tx - 60 + k * 13, 184 + cable), (tx - 60 + k * 13, 232 + cable)], shade(c, 0.85), 2)
        f.alpha_composite(q.done(), (int(x), int(dock_y - 760 + 60)))
    s.add(4.0, crane)
    for k in range(int(s.D // 12)):
        s.pop(k * 12 + 7.5, lambda tt: (cx0 + 680 - s.cam(tt), TOP - 520), str(k + 1))
    tug = V.boat("tug", "red", s.seed + 1, s.time)
    tmv = Mover(0.0, 120, s.D, lambda x, t, v: 120)
    s.boat_actor(tug, tmv, w, 5, x0=-tug.w - 200)
    s.say(8, 14, "A crane lifts the containers off the ship")
    s.say(26, 32, "Let's count the containers")
    s.say(44, 50, "A little tugboat helps big ships")
    s.sound("waves", level=lambda t: 0.5)
    s.sound("motor", level=lambda t: 0.4)


@script("river_kayaks")
def river_kayaks(s):
    V.SCALE = 1.9
    far_shore(s, "hills", top=560)

    def bank(p, g, X0, X1, rng):
        p.rect(0, 120, CW + 2 * M, 160, (120, 170, 100))
        x = X0 + rng.uniform(0, 100)
        while x < X1:
            P.tree(p, x - X0 + M, 130, rng.uniform(110, 170), rng, rng.choice(["round", "pine", "birch", "round"]))
            x += rng.uniform(60, 140)
    s.layer("bank", int(560 - 150 * ZS) + 10, 160, 0.5, bank, 1.5, zoom=ZS)
    w = water(s, c_top=(110, 170, 170), c_bot=(60, 120, 120), amp=5, top=560)
    cols = [s.spec["vehicle"]["color"], "red", "green"]
    lead = None
    for i in range(3):
        k = V.boat("kayak", cols[i], s.seed + i, s.time)
        mv = Mover(0.0, 120, s.D, lambda x, t, v, i=i: 120 + 6 * math.sin(t / 5 + i))
        if i == 0:
            follow_boat(s, k, mv, w, anchor=0.5, z=5.2)
            lead = mv
        else:
            s.boat_actor(k, mv, w, 5.2 - i * 0.1, x0=-i * 520)

    def ducks(f, t, cam):
        from art import duck
        for j in range(5):
            xw = 2600 + j * 2300 + 30 * t
            x = xw - cam
            if -80 < x < W + 80:
                im = duck(j).resize((90, 66))
                f.alpha_composite(im, (int(x), int(w.surface(xw, t) + 60)))
    s.add(5.6, ducks)

    def front_bank(p, g, X0, X1, rng):
        p.rect(0, 60, CW + 2 * M, 200, (110, 160, 90))
        x = X0 + rng.uniform(0, 300)
        while x < X1:
            P.bush(p, x - X0 + M, 70, rng.uniform(40, 70), rng.choice(P.LEAF))
            P.flowers(p, x - X0 + M + 60, 74, rng, 6)
            x += rng.uniform(300, 700)
    s.layer("frontbank", 1000, 200, 1.25, front_bank, 7)
    s.say(8, 14, "Paddle left, paddle right")
    s.say(26, 32, "Can you count the ducks?")
    s.say(42, 48, "Three kayaks in a row")
    s.sound("water", level=lambda t: 0.4)
    _ = lead


@script("speedboat_buoys")
def speedboat_buoys(s):
    V.SCALE = 1.7
    far_shore(s, "mountains")
    w = water(s, c_top=(90, 150, 200), c_bot=(30, 80, 140), amp=10)
    glints(s, w)
    boat = V.boat("speedboat", s.spec["vehicle"]["color"], s.seed, s.time)
    v = s.spec.get("speed", 320)
    mv = Mover(0.0, 120, s.D, lambda x, t, vv: v, accel=60)
    follow_boat(s, boat, mv, w, anchor=0.3, spray=1.0, heel=-3.0)
    xs = [2400 + i * 1600 for i in range(14)]
    buoys(s, w, xs)
    s.say(6, 12, "Zoom! A speedboat makes a big wake")
    s.say(22, 28, "Red buoy, green buoy")
    s.say(40, 46, "The buoys show where it is safe to go")


@script("rain_lake")
def rain_lake(s):
    V.SCALE = 2.0
    far_shore(s, "hills")
    w = water(s, c_top=(120, 160, 180), c_bot=(60, 100, 130), amp=5,
              rain=lambda t: s.world.weather.rain_level(t, s.D))
    boat = V.boat("rowboat", s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 30, s.D, lambda x, t, v: 28)
    follow_boat(s, boat, mv, w, anchor=0.4)

    def fish(f, t, cam):
        for t0 in (14.0, 33.0, 47.0):
            a = (t - t0) / 1.0
            if 0 <= a <= 1:
                x = 1300 + 120 * a
                y = w.surface(x + cam, t) + 30 - 160 * math.sin(math.pi * a)
                q = Pen(90, 44)
                q.ellipse(10, 8, 74, 36, (240, 150, 70))
                q.poly([(10, 22), (0, 6), (0, 38)], (240, 150, 70))
                q.circle(62, 18, 3, (30, 30, 30))
                im = q.done().rotate(40 - 80 * a, resample=Image.BICUBIC, expand=True)
                f.alpha_composite(im, (int(x), int(y)))
    s.add(4.8, fish)
    s.say(8, 14, "Pitter-patter: raindrops make circles on the water")
    s.say(22, 28, "A fish jumps! Splash!")
    s.say(s.D * 0.62, s.D * 0.62 + 7, "The rain stopped. A rainbow!")
    s.sound("rain", level=lambda t: s.world.weather.rain_level(t, s.D))
    for t0 in (14.0, 33.0, 47.0):
        s.sound("splash", at=t0 + 1.0)


@script("car_ferry")
def car_ferry(s):
    V.SCALE = 1.6
    far_shore(s, "city", depth=0.04)
    w = water(s, c_top=(100, 160, 200), c_bot=(40, 90, 150), amp=9)
    ferry = V.boat("ferry", s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 110, s.D, lambda x, t, v: 110)
    follow_boat(s, ferry, mv, w, anchor=0.18)
    gulls(s, lambda t, cam: (W * 0.75, 260), n=4)
    for i in range(6):
        s.pop(9 + i * 1.4, lambda tt, i=i: (W * 0.18 + (60 + i * 110 + 60) * ferry.k, w.surface(mv.at(tt)[0] + 300, tt) - 260 * ferry.k), str(i + 1))
    s.say(6, 11, "A ferry carries cars across the water")
    s.say(20, 26, "Count the cars on the ferry")
    s.say(38, 44, "Seagulls follow the boat")
    s.sound("horn", at=30.0)


@script("trawler_sunset")
def trawler_sunset(s):
    V.SCALE = 1.6
    far_shore(s, "coast")
    w = water(s, c_top=(120, 150, 190), c_bot=(50, 70, 120), amp=14, choppy=1.1)
    glints(s, w)
    boat = V.boat("trawler", s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 90, s.D, lambda x, t, v: 90)
    follow_boat(s, boat, mv, w, anchor=0.3)
    gulls(s, lambda t, cam: (W * 0.3 + 160 * boat.k, 330), n=7, radius=(260, 100))
    s.say(8, 14, "A fishing boat heads home")
    s.say(24, 30, "Hungry seagulls fly around it")
    s.say(40, 46, "The sun is setting over the sea")


@script("paddle_steamer")
def paddle_steamer(s):
    V.SCALE = 1.4
    far_shore(s, "hills", top=600)
    w = water(s, c_top=(130, 170, 170), c_bot=(70, 110, 120), amp=4, top=600)
    boat = V.boat("steamer", s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 70, s.D, lambda x, t, v: 70)
    follow_boat(s, boat, mv, w, anchor=0.28, wake=True)
    k = boat.k
    for fx in (320, 420):
        s.smoke(mv, lambda d, fx=fx: (d + W * 0.28 + (fx + 17) * k, 600 + 230 - (400 - 10) * k), 6,
                every=0.7, life=5.0, col=(200, 202, 208), drift=(-40, -40), size=16 * k, x0=0)
    s.say(8, 14, "A paddle steamer: the big wheel turns round and round")
    s.say(26, 32, "Puff, puff, smoke from the chimneys")
    s.sound("chug", level=lambda t: 0.5)


@script("sail_race")
def sail_race(s):
    V.SCALE = 1.2
    far_shore(s, "coast")
    w = water(s, amp=14, choppy=1.1)
    glints(s, w)
    cols = ["red", "blue", "yellow"]
    movers = []
    for i, c in enumerate(cols):
        b = V.boat("sailboat", c, s.seed + i, s.time)
        mv = Mover(0.0, 140, s.D, lambda x, t, v, i=i: 140 + 22 * math.sin(t / 7 + i * 2.1))
        movers.append(mv)
        s.boat_actor(b, mv, w, 5 - i * 0.2, x0=-i * 380, heel=-8.0)
    s.follow(movers[0], 0.45)
    buoys(s, w, [3000 + i * 3000 for i in range(5)])
    s.say(8, 14, "A sailing race! Red, blue and yellow")
    s.say(26, 32, "Which boat is in front?")
    s.say(44, 50, "Everyone wears a life jacket")
    s.sound("waves", level=lambda t: 0.6)


@script("night_harbor")
def night_harbor(s):
    V.SCALE = 1.6
    far_shore(s, "city", depth=0.04)
    w = water(s, c_top=(50, 66, 110), c_bot=(20, 30, 60), amp=6)
    glints(s, w)
    tug = V.boat("tug", s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, 80, s.D, lambda x, t, v: 80)
    follow_boat(s, tug, mv, w, anchor=0.35)

    def lights_reflect(f, t, cam):
        d = ImageDraw.Draw(f)
        r = random.Random(s.seed)
        for j in range(26):
            x = (r.uniform(0, W * 3) - cam * 0.04) % W
            for k in range(5):
                y = TOP + 14 + k * 14
                a = 0.5 + 0.5 * math.sin(t * 3 + j + k)
                d.line([(x - 8 + 4 * math.sin(t + k), y), (x + 8, y)], fill=(255, 214, 140, int(120 * a)), width=3)
    s.add(2.3, lights_reflect)
    s.say(8, 14, "The harbour at night")
    s.say(26, 32, "Boats have lights so others can see them")
    s.say(44, 50, "Goodnight, little tugboat")
