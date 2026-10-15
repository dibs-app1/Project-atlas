"""Cars & trucks scenes: highway, speed bumps, construction, rainy city bus, garbage day,
car carrier counting, school bus stop, car wash, snowplow, night city."""
import math
import random

from art import COLORS, mix, shade
from settings import periodic

from . import props as P
from . import vehicles as V
from .core import CW, FPS, M, W, Mover, smooth, stop_target
from .vehicles import FastPen as Pen
from .scene import script

ROAD_TOP, ROAD_BOT = 772, 1046
FAR, NEAR = 884, 1018          # wheel lines of the far (oncoming) lane and the near (our) lane
ZS = 1.5                       # scenery zoom: houses and trees in scale with the big vehicles
K = 1.6                        # people / small props drawn next to vehicles


# ------------------------------------------------------------------ shared scenery

def back_layer(s, name, hv, draw, z=3, depth=0.7, atmos=0.06):
    """A scenery strip that sits on the far kerb. Drawn in virtual units (hv tall), zoomed by ZS."""
    s.layer(name, int(ROAD_TOP - hv * ZS), hv, depth, draw, z, atmos=atmos, zoom=ZS)


def hills(s, col=(130, 170, 128), amp=70, depth=0.08, snow=None, z=1):
    hv = int(ROAD_TOP / ZS)
    f = periodic(random.Random(s.seed + 3), 6)
    s.layer("hills", 0, hv, depth,
            lambda p, g, X0, X1, rng: P.mountains(p, f, X0, X1, M, hv - 90, amp, hv, col, snow),
            z, atmos=0.35, zoom=ZS)


def road(s, bumps=(), snow=False, wet=False, crosswalks=(), markings=True, z=4):
    asphalt = (206, 212, 222) if snow else (88, 92, 102)
    side = (236, 242, 250) if snow else (198, 194, 188)
    y0 = ROAD_TOP - 20
    mid = (FAR + NEAR) / 2 - 22 - y0

    def draw(p, g, X0, X1, rng):
        w = CW + 2 * M
        p.rect(0, 0, w, 20, side)
        p.rect(0, 20, w, ROAD_BOT - y0, asphalt)
        p.rect(0, ROAD_BOT - y0, w, 400, side)
        for xw in range(int((X0 - M) // 60 * 60), int(X1 + M), 60):   # kerb stones
            x = xw - X0 + M
            p.rect(x, ROAD_BOT - y0 - 2, x + 56, ROAD_BOT - y0 + 10, shade(side, 0.9))
            p.rect(x, 14, x + 56, 22, shade(side, 0.9))
        if markings:
            for xw in range(int((X0 - M) // 200 * 200), int(X1 + M), 200):
                x = xw - X0 + M
                p.rect(x, mid, x + 110, mid + 10, (246, 210, 80) if not snow else (220, 200, 120))
        if wet:
            for xw in range(int((X0 - M) // 90 * 90), int(X1 + M), 90):
                x = xw - X0 + M
                yy = mid + 30 + (xw * 7) % 120
                p.rect(x, yy, x + 46, yy + 3, (140, 150, 168))
        for b in bumps:
            if X0 - M <= b < X1 + M:
                x = b - X0 + M
                top, bot = NEAR - y0 - 40, NEAR - y0 + 20
                p.rect(x - 34, top, x + 34, bot, (60, 62, 70), r=16)
                for k in range(5):
                    p.rect(x - 30 + k * 12, top + 4, x - 22 + k * 12, bot - 4,
                           (246, 200, 50) if k % 2 == 0 else (40, 40, 40))
        for c in crosswalks:
            if X0 - M <= c < X1 + M:
                x = c - X0 + M
                for k in range(8):
                    yy = 30 + k * 32
                    p.poly([(x, yy), (x + 150, yy), (x + 160, yy + 18), (x + 10, yy + 18)], (240, 240, 236))
    s.layer("road", y0, 400, 1.0, draw, z)
    s.ground_y = NEAR


def oncoming(s, every=(4.0, 7.0), speed=(180, 260), z=5, kinds=None, snow=False, start=2.0, until=None):
    """Traffic in the far lane coming the other way, spaced out like real traffic."""
    r = random.Random(s.seed + 11)
    kinds = kinds or ["sedan", "hatch", "suv", "van", "pickup", "taxi", "truck", "bus"]
    cols = ["red", "blue", "yellow", "green", "white", "orange", "purple", "teal", "grey"]
    t, i = start, 0
    while t < (until or s.D - 2):
        k = r.choice(kinds)
        if k == "truck":
            veh = V.truck(r.choice(["box", "tanker", "dump", "mixer"]), r.choice(cols[:8]), s.seed + 50 + i, s.time)
        elif k == "bus":
            veh = V.bus(r.choice(["red", "blue", "green"]), s.seed + 50 + i, s.time)
        else:
            veh = V.car(k, r.choice(cols), s.seed + 50 + i, s.time, snow=snow)
        v = r.uniform(*speed)
        start_x = s.cam(t) + W + veh.w + 40 + v * t          # its back end enters the right edge at time t
        mv = Mover(0.0, v, s.D, lambda x, tt, vv, v=v: v)
        s.road_vehicle(veh, mv, FAR, z, direction=-1, x0=start_x)
        t += r.uniform(*every)
        i += 1


def roadside(s, kind, z=3, front_z=7, snow=False):
    """Countryside or snowy scenery behind the far kerb, plus a guardrail and bushes in front."""
    def back(p, g, X0, X1, rng):
        base = 120
        p.rect(0, base, CW + 2 * M, 150, (246, 248, 252) if snow else (128, 176, 104))
        x = X0 + rng.uniform(0, 160)
        while x < X1:
            lx = x - X0 + M
            if kind == "country":
                c = rng.random()
                if c < 0.45:
                    P.tree(p, lx, base, rng.uniform(100, 150), rng, rng.choice(["round", "round", "pine", "birch"]))
                elif c < 0.6:
                    P.house(p, g, lx, base, rng.uniform(120, 150), rng.uniform(70, 90), rng)
                    x += 120
                elif c < 0.68:
                    P.barn(p, g, lx, base, rng)
                    x += 220
                elif c < 0.8:
                    for j in range(rng.randint(1, 3)):
                        P.animal(p, lx + j * 70, base + 4, rng.choice(["cow", "sheep", "horse"]), rng)
                    x += 120
                else:
                    P.bush(p, lx, base, rng.uniform(26, 40), rng.choice(P.LEAF))
                x += rng.uniform(120, 240)
            else:
                P.tree(p, lx, base, rng.uniform(110, 160), rng, "pine", col=(70, 108, 92))
                p.poly([(lx - 22, base - 70), (lx + 22, base - 70), (lx, base - 140)], (246, 248, 252))
                x += rng.uniform(80, 180)
    back_layer(s, "roadside", 150, back, z)

    def front(p, g, X0, X1, rng):
        if not snow:
            P.guardrail(p, X0, X1, M, 62)
        x = X0 + rng.uniform(0, 400)
        while x < X1:
            lx = x - X0 + M
            P.bush(p, lx, 110, rng.uniform(30, 50), (240, 244, 250) if snow else rng.choice(P.LEAF))
            x += rng.uniform(300, 600)
    s.layer("front", ROAD_BOT - 6, 140, 1.15, front, front_z)


def street(s, signs=(), z=3, snow=False):
    """Neighbourhood scenery: houses with fences, trees and flowers. signs: [(world x, kind)]."""
    def back(p, g, X0, X1, rng):
        base = 150
        p.rect(0, base, CW + 2 * M, 190, (240, 244, 250) if snow else (126, 176, 104))
        x = X0 + rng.uniform(0, 80)
        while x < X1:
            lx = x - X0 + M
            w = rng.uniform(150, 190)
            P.house(p, g, lx, base, w, rng.uniform(90, 115), rng, snow=snow)
            P.tree(p, lx + w + 40, base + 6, rng.uniform(110, 150), rng, rng.choice(["round", "round", "birch", "pine"]))
            if rng.random() < 0.5:
                P.flowers(p, lx + 30, base + 30, rng, 5)
            x += w + rng.uniform(110, 160)
        P.fence(p, X0, X1, M, base + 36, col=(250, 250, 246))
        for xs, kind_ in signs:  # signs are given in world (screen-scale) units
            xv = xs * 0.7 / ZS    # this layer scrolls at depth 0.7
            if X0 <= xv < X1:
                P.sign(p, xv - X0 + M, base + 36, kind_, 100)
    back_layer(s, "street", 190, back, z)


def town(s, z=3, lamps=True, tall=False):
    def back(p, g, X0, X1, rng):
        base = 230 if tall else 200
        x = X0 + rng.uniform(0, 60)
        while x < X1:
            w = rng.uniform(170, 240)
            P.building(p, g, x - X0 + M, base, w, rng.uniform(220, 380 if not tall else 470), rng, shop=rng.random() < 0.8)
            x += w + rng.uniform(8, 30)
        if lamps:
            for xw in range(int(X0 // 420 * 420 + 420), int(X1), 420):
                P.lamp(p, g, xw - X0 + M, base + 20, 190)
    hv = 250 if tall else 220
    back_layer(s, "town", hv, back, z, depth=0.65)


def hero_car(s, veh, mover, anchor=0.38, bumps=(), z=6, state=None):
    s.follow(mover, anchor)
    s.road_vehicle(veh, mover, NEAR, z, bumps=bumps, state=state)
    s.sound("engine", level=lambda t: min(1.0, mover.at(t)[1] / 300 + 0.25), kind2=getattr(veh, "kind", "car"))


def body_len(veh):
    """Length of the vehicle body (sprites carry extra room in front for the headlight beam)."""
    return veh.w - 260 * veh.k if veh.kind in ("car", "bus", "truck") else veh.w


def walker(s, x_fn, base, t_range, seed, z=6.6, s_=1.6, **kw):
    t0, t1 = t_range

    def draw(f, t, cam):
        if not (t0 <= t <= t1):
            return
        x, moving = x_fn(t)
        q = Pen(160, 200)
        V.person(q, 70, 70, s_, random.Random(seed), phase=(t * 7 if moving else None), **kw)
        f.alpha_composite(q.done(), (int(x - cam - 70), int(base - 200 + 24)))
    s.add(z, draw)


# ------------------------------------------------------------------ scripts

@script("highway")
def highway(s):
    """A car follows a truck at a safe distance along a country highway, traffic coming the other way."""
    hills(s)
    roadside(s, "country")
    road(s)
    v = s.spec.get("speed", 300)
    hero = V.car(s.spec["vehicle"].get("kind", "sedan"), s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, v, s.D, lambda x, t, vv: v)
    hero_car(s, hero, mv, anchor=0.04)
    lead = V.truck(s.spec.get("lead", "box"), s.spec.get("lead_color", "teal"), s.seed + 1, s.time)
    gap = body_len(hero) * 1.1             # a safe gap: more than a whole car length
    s.road_vehicle(lead, Mover(0.0, v, s.D, lambda x, t, vv: v), NEAR, 6, x0=body_len(hero) + gap)
    oncoming(s)
    s.say(10, 16, "Keep a safe distance behind the truck")
    s.say(32, 38, "Cars coming the other way stay in their lane")
    s.sound("wind", level=lambda t: 0.4)


@script("speed_bumps")
def speed_bumps(s):
    """Neighbourhood street: the car slows down for every speed bump, then rolls gently over it."""
    hills(s, col=(140, 180, 140), amp=50)
    r = random.Random(s.seed)
    bumps = [1700 + i * 2100 + r.uniform(-120, 120) for i in range(8)]
    street(s, signs=[(b - 520, "bump") for b in bumps])
    road(s, bumps=bumps, markings=False)
    v = s.spec.get("speed", 230)
    slow = 45
    hero = V.car(s.spec["vehicle"].get("kind", "hatch"), s.spec["vehicle"]["color"], s.seed, s.time)
    xs = sorted(w[0] for w in hero.wheels)
    front = xs[-1] + 50

    def target(x, t, vv):
        for b in bumps:
            ahead = b - (x + front)
            if -(front - xs[0]) - 60 < ahead < 520:
                return slow
        return v
    mv = Mover(0.0, 80, s.D, target, accel=70, decel=95)
    hero_car(s, hero, mv, anchor=0.3, bumps=bumps)
    n = 0
    for b in bumps:
        for i in range(len(mv.x)):
            if mv.x[i] + xs[-1] >= b:
                n += 1
                t0 = i / FPS
                if t0 < s.D - 3:
                    s.pop(t0, lambda tt, b=b: (b - s.cam(tt), NEAR - 330), str(n))
                    s.sound("bump", at=t0)
                    s.sound("bump", at=t0 + (xs[-1] - xs[0]) / slow)
                break
    s.say(8, 14, "Speed bump! Slow down")
    s.say(28, 34, "Speed bumps keep streets safe for children")


@script("construction")
def construction(s):
    """Road works: an excavator digs, a dump truck tips its load, a mixer turns; cars wait for the flagger."""
    hills(s, col=(150, 170, 140), amp=60)

    def lot(p, g, X0, X1, rng):
        p.rect(0, 140, CW + 2 * M, 210, (196, 168, 120))
        for k in range(-2, 4):
            xw = k * 1300 + 700
            if X0 <= xw < X1:
                x = xw - X0 + M
                P.crane(p, x + 420, 150, 300, COLORS["yellow"])
                for fy in range(4):  # a building going up
                    p.rect(x, 150 - fy * 62, x + 330, 156 - fy * 62, (150, 154, 164))
                for fx in range(5):
                    p.rect(x + fx * 80, -40, x + 6 + fx * 80, 150, (150, 154, 164))
        x = X0 + rng.uniform(0, 200)
        while x < X1:
            P.cone(p, x - X0 + M, 208, 0.8)
            x += 120
    back_layer(s, "lot", 210, lot, 3, depth=0.6)
    road(s)
    pan = s.spec.get("pan", 12.0)
    s._cam = [i / FPS * pan for i in range(int(s.D * FPS) + 3)]
    ex = V.excavator("yellow", s.seed, s.time)
    s.add(3.5, lambda f, t, cam: ex.draw(f, 100 - cam * 0.6, ROAD_TOP + 6, 0, t,
                                         state={"dig": (t / 6.0) % 1.0, "track": 0}, shadow=False))
    # the dump truck drives in the far lane in its own direction (right to left) and stops by the lot
    dump = V.truck("dump", "orange", s.seed + 1, s.time)
    d_start, d_stop = 3000.0, 1700.0
    dmv = Mover(0.0, 140, s.D, stop_target(140, [(d_stop, 40.0)], 0.0, a=80))
    rear = d_start - d_stop - 30
    s.add(3.6, _pile(lambda t: 0.25 + 0.75 * smooth((t - 27) / 6), rear - 30, ROAD_TOP + 6, 1.0))

    def dstate(t, d, v):
        a = smooth((t - 24) / 4) * (1 - smooth((t - 36) / 4))
        return {"bed": a, "dirt": 1 - smooth((t - 27) / 6)}
    s.road_vehicle(dump, dmv, FAR, 5, direction=-1, x0=d_start, state=dstate)
    s.sound("beep", at=23.0)
    mixer = V.truck("mixer", "blue", s.seed + 2, s.time)
    s.road_vehicle(mixer, Mover(0.0, 120, s.D, lambda x, t, v: 120), FAR, 5, direction=-1, x0=W + 6200)
    release = s.D * 0.5
    pick = V.car("pickup", s.spec["vehicle"]["color"], s.seed + 3, s.time)
    flag_x = 1500
    pmv = Mover(-pick.w - 100, 150, s.D, stop_target(150, [(flag_x - 60, release)], max(w[0] for w in pick.wheels) + 70, a=100))
    s.road_vehicle(pick, pmv, NEAR, 6)
    s.add(6.5, _flagger(flag_x, NEAR + 30, release, s))
    s.say(8, 14, "An excavator digs with its big bucket")
    s.say(24, 30, "The dump truck tips its bed")
    s.say(release, release + 6, "The sign says SLOW, so the cars can go")
    s.say(46, 52, "A cement mixer keeps its drum turning")
    s.sound("engine", level=lambda t: 0.5, kind2="truck")


def _pile(amount, x, base, depth):
    def draw(f, t, cam):
        a = amount(t)
        w, h = int(380 * a + 80), int(130 * a + 14)
        q = Pen(w, h)
        q.poly([(0, h), (w * 0.45, 0), (w * 0.6, h * 0.1), (w, h)], (150, 108, 72))
        q.circle(w * 0.3, h * 0.6, h * 0.1, (126, 90, 60))
        f.alpha_composite(q.done(), (int(x - cam * depth), int(base - h)))
    return draw


def _flagger(x, base, release, s):
    def draw(f, t, cam):
        q = Pen(200, 300)
        V.person(q, 80, 100, 2.4, rng=random.Random(s.seed + 9), vest=True)
        q.line([(104, 150), (140, 60)], (90, 90, 96), 6)
        if t < release:
            pts = [(140 + 40 * math.cos(math.pi / 8 + k * math.pi / 4), 46 + 40 * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
            q.poly(pts, (210, 54, 48))
            q.rect(116, 40, 164, 52, (250, 250, 250))
        else:
            q.poly([(140, 2), (184, 46), (140, 90), (96, 46)], (246, 150, 50))
            q.rect(116, 40, 164, 52, (40, 40, 40))
        f.alpha_composite(q.done(), (int(x - cam), int(base - 300)))
    return draw


@script("city_bus")
def city_bus(s):
    """A city bus in the rain stops for people with umbrellas; then the sun comes out (and a rainbow)."""
    town(s)
    road(s, wet=True)
    stop_at = 3000
    bus = V.bus(s.spec["vehicle"]["color"], s.seed, s.time)
    door = bus.w - (260 + 118) * bus.k
    t_open = 18.0

    def stopprop(f, t, cam):
        q = Pen(140, 330)
        P.sign(q, 70, 330, "bus", 260)
        f.alpha_composite(q.done(), (int(stop_at + 40 - cam), ROAD_BOT - 330 + 20))
    s.add(6.8, stopprop)
    mv = Mover(0.0, 160, s.D, stop_target(230, [(stop_at, t_open + 12)], door + 40, a=90))
    hero_car(s, bus, mv, anchor=0.12)
    r = random.Random(s.seed + 4)
    for k in range(3):
        col = r.choice([COLORS["red"], COLORS["yellow"], COLORS["purple"], COLORS["blue"]])
        t_go, t_in = t_open + 1 + k * 2.6, t_open + 3 + k * 2.6

        def xf(t, k=k, t_go=t_go):
            u = smooth((t - t_go) / 2.0)
            return stop_at + 140 + k * 90 - u * (100 + k * 90), 0 < u < 1
        walker(s, xf, ROAD_BOT + 30, (0, t_in + 0.4), s.seed + 40 + k, umbrella=col, z=6.9)
    oncoming(s, kinds=["sedan", "hatch", "taxi", "van", "suv"])
    s.say(t_open - 2, t_open + 5, "The bus stops so people can get on")
    s.say(s.D * 0.62, s.D * 0.62 + 7, "The rain stopped. Look, a rainbow!")
    s.sound("rain", level=lambda t: s.world.weather.rain_level(t, s.D))
    s.sound("door", at=t_open + 1)
    s.sound("door", at=t_open + 11)


@script("garbage_day")
def garbage_day(s):
    """Garbage truck stops at each house; its arm lifts the bin and empties it."""
    hills(s, col=(140, 182, 140), amp=50)
    street(s)
    road(s, markings=False)
    r = random.Random(s.seed)
    bins = [1500 + i * 1500 + r.uniform(-80, 80) for i in range(8)]
    bin_cols = [COLORS["blue"], COLORS["green"], (70, 74, 84)]
    tr = V.truck("garbage", s.spec["vehicle"]["color"], s.seed, s.time)
    arm_off = tr.cab_x - 4 * tr.k
    release = {}

    def target(x, t, v):
        for b in bins:
            gap = b - (x + arm_off)
            rel = release.get(b)
            if gap > -4 and (rel is None or t < rel):
                if gap < 3 and rel is None:
                    release[b] = t + 7.0
                return min(160, math.sqrt(max(0.0, 2 * 80 * max(0.0, gap - 2))))
        return 160
    mv = Mover(0.0, 80, s.D, target)
    cycles = sorted((b, rel - 7.0) for b, rel in release.items())

    def st(t, d, v):
        for b, t0 in cycles:
            u = (t - t0 - 0.8) / 5.2
            if 0 <= u <= 1:
                return {"arm": math.sin(u * math.pi), "bin": 1, "bin_color": bin_cols[bins.index(b) % 3]}
        return {"arm": 0.0}
    hero_car(s, tr, mv, anchor=0.2, state=st)

    def bin_draw(f, t, cam):
        for i, b in enumerate(bins):
            if any(bb == b and t0 + 0.8 < t < t0 + 6.0 for bb, t0 in cycles):
                continue
            x = b - cam
            if -160 < x < W + 160:
                q = V.Pen(90, 120, K)
                c = bin_cols[i % 3]
                q.rect(10, 18, 80, 114, c, r=6)
                q.rect(4, 8, 86, 24, shade(c, 0.8), r=5)
                q.rect(30, 50, 60, 60, (250, 250, 250), r=3)
                q.circle(20, 112, 7, (40, 40, 40))
                img = q.done()
                f.alpha_composite(img, (int(x - img.width / 2), int(1078 - img.height)))
    s.add(6.8, bin_draw)  # bins stand on the near kerb, in front of the truck
    for k, (b, t0) in enumerate(cycles[:6]):
        s.pop(t0 + 2, lambda tt, b=b: (b - s.cam(tt), ROAD_TOP - 260), str(k + 1))
        s.sound("lift", at=t0 + 1.0)
    s.say(8, 14, "It's garbage day!")
    s.say(24, 30, "The arm lifts the bin and empties it")


@script("car_carrier")
def car_carrier(s):
    """A car carrier on the highway at golden hour. Count the cars it carries!"""
    hills(s, col=(170, 160, 140), amp=90)
    roadside(s, "country")
    road(s)
    v = s.spec.get("speed", 260)
    tr = V.truck("carrier", s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(0.0, v, s.D, lambda x, t, vv: v)
    hero_car(s, tr, mv, anchor=0.04)
    oncoming(s, kinds=["sedan", "hatch", "suv", "van", "pickup"])
    k = tr.k
    for i in range(6):
        dx = (40 + (i % 3) * 205 + 50) * k
        dy = (290 - (152 if i < 3 else 72) - 70) * k
        s.pop(8 + i * 1.6, lambda tt, dx=dx, dy=dy: (mv.at(tt)[0] + dx - s.cam(tt), NEAR - 290 * k + dy), str(i + 1))
    s.say(5, 10, "Let's count the cars on the truck")
    s.say(18, 23, "Six cars going to their new homes!")


@script("school_bus")
def school_bus(s):
    """The school bus stops, its stop sign swings out, and every car waits while children climb aboard."""
    hills(s, col=(150, 186, 140), amp=50)
    street(s, signs=[(1700 + i * 2400, "school") for i in range(6)])
    road(s)
    stop_at = 2800
    bus = V.bus(seed=s.seed, time=s.time, school=True)
    hold = 18.0
    t_stop = 15.0
    mv = Mover(0.0, 120, s.D, stop_target(210, [(stop_at, t_stop + hold)], body_len(bus), a=80))
    arrive = next((i / FPS for i in range(FPS, len(mv.v)) if mv.v[i] == 0), t_stop)
    arm = lambda t: smooth((t - arrive - 0.5) / 1.2) * (1 - smooth((t - (t_stop + hold) + 1.5) / 1.2))  # noqa: E731
    hero_car(s, bus, mv, anchor=0.1, state=lambda t, d, v: {"stop_arm": arm(t)})
    car = V.car("suv", "red", s.seed + 5, s.time)
    start = stop_at + 360 + car.w + 170 * (arrive + 4)
    cmv = Mover(0.0, 170, s.D, lambda x, t, v: 0 if (start - x - car.w) < stop_at + 360 and arm(t) > 0.05 else 170)
    s.road_vehicle(car, cmv, FAR, 5, direction=-1, x0=start)
    door = stop_at - 118 * bus.k
    for k in range(4):
        t_go = arrive + 2.5 + k * 2.2

        def xf(t, k=k, t_go=t_go):
            u = smooth((t - t_go) / 2.0)
            return door + 120 + k * 80 - u * (120 + k * 80), 0 < u < 1
        walker(s, xf, ROAD_BOT + 30, (0, t_go + 2.2), s.seed + 60 + k, kid=True, z=6.9)
    s.say(arrive, arrive + 6, "The stop sign is out. All cars wait!")
    s.say(arrive + 9, arrive + 15, "Children climb on board safely")


@script("car_wash")
def car_wash(s):
    """A car rolls slowly through the car wash: soap, spinning brushes, rinse and dry."""
    def back(p, g, X0, X1, rng):
        base = 200
        p.rect(0, base - 20, CW + 2 * M, base + 10, (196, 194, 190))
        for xw in range(int(X0 // 260 * 260), int(X1), 260):
            P.tree(p, xw - X0 + M + 100, base - 10, 150, rng)
    back_layer(s, "lot", 210, back, 3, depth=0.5)
    road(s, markings=False)
    s._cam = [i / FPS * 16 for i in range(int(s.D * FPS) + 3)]
    car = V.car(s.spec["vehicle"].get("kind", "sedan"), s.spec["vehicle"]["color"], s.seed, s.time)
    mv = Mover(-car.w - 50, 55, s.D, lambda x, t, v: 55)
    s.road_vehicle(car, mv, NEAR, 6)
    x_wash, ww, wh = 360, 1500, 720

    def wash_back(f, t, cam):
        q = Pen(ww, wh)
        q.rect(0, 0, ww, 80, (70, 130, 200), r=12)
        q.rect(20, 80, 70, wh, (180, 186, 196))
        q.rect(ww - 70, 80, ww - 20, wh, (180, 186, 196))
        q.rect(ww / 2 - 260, 18, ww / 2 + 260, 62, (250, 250, 250), r=10)
        f.alpha_composite(q.done(), (int(x_wash - cam), NEAR + 10 - wh))
    s.add(5.8, wash_back)

    def wash_front(f, t, cam):
        q = Pen(ww, wh)
        for k, bx in enumerate((420, 780)):  # spinning brushes (stripes scroll to show rotation)
            q.rect(bx - 56, 96, bx + 56, wh - 20, (60, 120, 210), r=40)
            for j in range(11):
                y = 96 + ((j * 56 + t * 200 * (1 if k else -1)) % (wh - 120))
                q.rect(bx - 56, y, bx + 56, y + 20, (110, 170, 240), r=10)
        r = random.Random(int(t * 12))
        for _ in range(60):  # soap bubbles
            x, y = r.uniform(100, 960), r.uniform(100, wh - 40)
            q.circle(x, y, r.uniform(8, 20), (250, 250, 255, 150))
        for kk in range(18):  # rinse water
            x = 1100 + kk * 10
            q.line([(x, 96), (x - 14, wh - 20)], (170, 210, 250, 140), 4)
        f.alpha_composite(q.done(), (int(x_wash - cam), NEAR + 10 - wh))
    s.add(6.5, wash_front)

    def sparkle(f, t, cam):
        d, _ = mv.at(t)
        x = d - cam
        if x > x_wash + ww - 80:
            from PIL import ImageDraw
            dr = ImageDraw.Draw(f)
            r = random.Random(int(t * 6))
            for _ in range(7):
                sx, sy = x + r.uniform(60, 480), NEAR - r.uniform(60, 240)
                dr.line([(sx - 14, sy), (sx + 14, sy)], fill=(255, 255, 255, 230), width=4)
                dr.line([(sx, sy - 14), (sx, sy + 14)], fill=(255, 255, 255, 230), width=4)
    s.add(6.7, sparkle)
    s.say(9, 15, "Soap bubbles and spinning brushes")
    s.say(28, 34, "Rinse with water...")
    s.say(42, 48, "Sparkly clean!")
    s.sound("water", level=lambda t: 0.6)


@script("snowplow")
def snowplow(s):
    """Snow day: a plow clears the road and spreads salt; a car follows slowly behind."""
    hills(s, col=(226, 234, 246), amp=90, snow=(250, 252, 255))
    roadside(s, "snow", snow=True)
    road(s, snow=True)
    v = s.spec.get("speed", 130)
    car = V.car("suv", s.spec["vehicle"]["color"], s.seed, s.time, snow=True)
    mv = Mover(0.0, v, s.D, lambda x, t, vv: v)
    hero_car(s, car, mv, anchor=0.0)
    plow = V.truck("plow", "yellow", s.seed + 1, s.time)
    px0 = body_len(car) + 260
    pmv = Mover(0.0, v, s.D, lambda x, t, vv: v)
    s.road_vehicle(plow, pmv, NEAR, 6, x0=px0, state=lambda t, d, vv: {"salt": 1})

    def spray(f, t, cam):
        from PIL import ImageDraw
        d, _ = pmv.at(t)
        x = px0 + d - cam + body_len(plow) + 40
        dr = ImageDraw.Draw(f)
        r = random.Random(int(t * 24))
        for _ in range(60):
            u = r.uniform(0, 1)
            sx, sy = x + u * 170, NEAR - 30 - u * 130 + r.uniform(-14, 14)
            rr = r.uniform(4, 9)
            dr.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(250, 252, 255, int(220 * (1 - u * 0.6))))
    s.add(6.4, spray)
    oncoming(s, speed=(100, 140), kinds=["suv", "pickup", "van", "sedan"], snow=True, every=(6, 9))
    s.say(8, 14, "The snowplow pushes the snow away")
    s.say(26, 32, "It spreads salt so tyres don't slip")
    s.say(42, 48, "Drive slowly in the snow")
    s.sound("wind", level=lambda t: 0.7)


@script("night_city")
def night_city(s):
    """A taxi drives through the city at night and stops at a red light."""
    town(s, tall=True)
    lights = [3600, 8600]
    road(s, crosswalks=[x + 60 for x in lights])
    taxi = V.car("taxi", (246, 200, 60), s.seed, s.time)
    front = max(w[0] for w in taxi.wheels) + 60
    mv = Mover(0.0, 220, s.D, stop_target(220, [(lights[0], 22.0), (lights[1], 46.0)], front, a=90))
    hero_car(s, taxi, mv, anchor=0.3)

    def signals(f, t, cam):
        for x, g_t in zip(lights, (22.0, 46.0)):
            sx = x + 260 - cam
            if -120 < sx < W + 120:
                q = Pen(100, 470)
                q.rect(44, 200, 56, 470, (60, 64, 76))
                q.rect(10, 0, 90, 210, (40, 44, 52), r=16)
                gg = smooth((t - g_t) / 1.0)
                q.circle(50, 38, 26, mix((236, 84, 72), (70, 70, 74), gg))
                q.circle(50, 104, 26, (70, 70, 74))
                q.circle(50, 170, 26, mix((70, 70, 74), (96, 210, 120), gg))
                f.alpha_composite(q.done(), (int(sx), ROAD_TOP - 470 + 30))
    s.add(3.5, signals)
    oncoming(s, kinds=["sedan", "hatch", "taxi", "bus", "van"])
    s.say(14, 20, "Red light: the taxi stops")
    s.say(23, 29, "Green light: go!")
    s.say(44, 50, "The city lights are shining")
