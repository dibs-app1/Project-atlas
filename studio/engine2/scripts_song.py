"""New scenes for the sing-along batch (batch 3), one set per vehicle type.

Cars & trucks: ice cream truck, tow truck, delivery truck.
Boats: tugboat pushing a big ship to the dock, fireboat water show, lighthouse in the fog.
Airplanes: air show with smoke trails, small/big/biggest take-offs, glider on tow.
Trains: city tram, two trains passing on two tracks, steam train at the water tower.

Each scene keeps its hero vehicle on screen (or tells the scene where it is) around the song's noise
moments, so BEEP BEEP / TOOT TOOT / ZOOM bursts and sound waves come out of the right vehicle.
"""
import math
import random

from PIL import Image, ImageDraw

from art import COLORS, GLASS, light, mix, shade

from . import props as P
from . import vehicles as V
from .core import FPS, H, W, Mover, smooth, stop_target
from .scene import script
from .vehicles import FastPen as Pen
from . import scripts_cars as SC
from . import scripts_boats as SB
from . import scripts_planes as SPL
from . import scripts_trains as ST


# ------------------------------------------------------------------ motion helpers

class SpeedPath:
    """Position from a speed profile [(t, v), ...] (linear between keys). Same API as Mover; v may go negative."""

    def __init__(self, x0, keys, D):
        n = int(D * FPS) + 3
        self.x, self.v = [], []
        x = x0
        for i in range(n):
            t = i / FPS
            v = _interp(keys, t)
            self.x.append(x)
            self.v.append(abs(v))
            x += v / FPS

    def at(self, t):
        i = min(max(0, int(t * FPS)), len(self.x) - 1)
        return self.x[i], self.v[i]


class Offset:
    def __init__(self, mover, dx):
        self.m, self.dx = mover, dx

    def at(self, t):
        x, v = self.m.at(t)
        return x + self.dx, v


def _interp(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            u = (t - t0) / max(1e-6, t1 - t0)
            return v0 + (v1 - v0) * u
    return keys[-1][1]


def _cam_from(s, mover, anchor, offset=0.0):
    s._cam = [mover.at(i / FPS)[0] - W * anchor + offset for i in range(int(s.D * FPS) + 3)]
    s.focus_x = W * anchor - offset


# ================================================================== CARS AND TRUCKS

def ice_cream_van(color="pink", seed=0, time="day"):
    k = V.SCALE
    rng = random.Random(seed)
    body = COLORS.get(color, color)
    L, Hs, gy, r = 600, 360, 350, 34
    p, g = V.Pen(L + 260, Hs), V.Pen(L + 260, Hs)
    cab_x = L - 160
    V._cab(p, g, cab_x, gy, body, rng, h=150, w=150)
    top = gy - 300
    p.rect(14, top, cab_x - 4, gy - 66, (252, 248, 240), r=16)                 # the box
    p.rect(14, gy - 140, cab_x - 4, gy - 66, body, r=12)                        # coloured skirt
    for i in range(12):                                                         # scalloped trim
        x = 26 + i * ((cab_x - 40) / 12)
        p.circle(x + 15, gy - 140, 15, body if i % 2 == 0 else (130, 200, 230))
    # pictures on the side: a cone, a lolly and a sundae
    cx = 90
    p.poly([(cx - 26, top + 90), (cx + 26, top + 90), (cx, top + 170)], (226, 176, 104))
    for j in range(3):
        p.line([(cx - 22 + j * 14, top + 92), (cx - 4 + j * 10, top + 160)], (196, 146, 80), 2)
    p.circle(cx, top + 80, 28, (250, 170, 196))
    p.circle(cx - 6, top + 56, 18, (160, 220, 180))
    lx = 210
    p.rect(lx - 22, top + 50, lx + 22, top + 140, (240, 110, 110), r=20)
    p.rect(lx - 22, top + 50, lx + 22, top + 80, (250, 200, 90), r=20)
    p.rect(lx - 3, top + 140, lx + 3, top + 176, (226, 196, 150))
    sx = 330
    p.poly([(sx - 40, top + 120), (sx + 40, top + 120), (sx + 24, top + 176), (sx - 24, top + 176)], (200, 230, 250))
    p.circle(sx - 18, top + 110, 22, (250, 240, 220))
    p.circle(sx + 18, top + 110, 22, (150, 100, 70))
    p.circle(sx, top + 92, 22, (250, 170, 196))
    p.circle(sx + 4, top + 66, 9, (220, 50, 60))
    # the giant cone on the roof
    rx = cab_x / 2
    p.rect(rx - 60, top - 16, rx + 60, top + 2, (200, 200, 206), r=4)
    p.poly([(rx - 44, top - 70), (rx + 44, top - 70), (rx, top - 4)], (226, 176, 104))
    p.circle(rx, top - 86, 46, (250, 170, 196))
    p.circle(rx - 24, top - 112, 26, (160, 220, 180))
    p.circle(rx + 22, top - 118, 26, (250, 240, 210))
    p.circle(rx + 2, top - 140, 10, (220, 50, 60))
    V._lights(p, g, 12, gy - 110, 8, 18, False)
    wheels = [(110, gy - r, r, "truck"), (cab_x + 80, gy - r, r, "truck")]
    for wx, wy, rr, _ in wheels:
        p.circle(wx, wy, rr + 7, shade(body, 0.5))
    return V.Vehicle(light(p.done(), time), wheels, gy, time, glow=g.done(), kind="truck")


def _kid(q, x, y, s, rng, phase=None, cone=None):
    V.person(q, x, y, s, rng, phase=phase, kid=True)
    if cone:
        hx, hy = x + 12 * s, y + 18 * s
        q.poly([(hx - 6 * s, hy), (hx + 6 * s, hy), (hx, hy + 16 * s)], (226, 176, 104))
        q.circle(hx, hy - 3 * s, 7 * s, cone)


@script("ice_cream_truck")
def ice_cream_truck(s):
    """The ice cream truck drives down the street playing its tune, stops at the kerb, children queue on the
    pavement (never in the road) and come back with ice creams; then it drives on."""
    SC.hills(s, col=(140, 186, 140), amp=50)
    SC.street(s)
    SC.road(s, markings=False)
    truck = ice_cream_van(s.spec["vehicle"].get("color", "pink"), s.seed, s.time)
    stop_t, go_t = 12.0, 40.0
    mv = SpeedPath(0.0, [(0, 160), (stop_t - 4, 160), (stop_t, 0), (go_t, 0), (go_t + 4, 120), (s.D, 140)], s.D)
    SC.hero_car(s, truck, mv, anchor=0.3)
    xs, _ = mv.at(stop_t + 1)
    body = SC.body_len(truck)
    r = random.Random(s.seed)
    flav = [(250, 170, 196), (160, 220, 180), (250, 240, 210), (150, 100, 70), (250, 200, 90), (200, 170, 250)]
    base = SC.ROAD_TOP + 2
    kids = []
    for i in range(6):
        # each child waits on the far pavement in front of the truck, walks behind it to the serving window
        # (on the pavement side) and comes back out at the back with an ice cream
        q_x = xs + body + 60 + i * 70
        t_turn = stop_t + 3 + i * 3.6
        kids.append((q_x, t_turn, flav[i % len(flav)], r.random()))

    def draw(f, t, cam):
        for i, (qx, tt, col, rr) in enumerate(kids):
            if t < stop_t - 2:
                x, ph, cone = qx + 400 - 400 * smooth((t - stop_t + 6) / 4), t * 7, None
                if t < stop_t - 6:
                    continue
            elif t < tt:
                x, ph, cone = qx, None, None
            elif t < tt + 3.0:            # behind the truck (hidden), at the window
                continue
            else:
                u = smooth((t - tt - 3.0) / 3.0)
                x, ph, cone = xs - 60 - u * (180 + i * 40), (t * 7 if u < 1 else None), col
            q = Pen(120, 160)
            _kid(q, 50, 50, 1.6, random.Random(s.seed + 40 + i), phase=ph, cone=cone)
            f.alpha_composite(q.done(), (int(x - cam - 50), int(base - 160)))
    s.add(5.5, draw)
    s.say(stop_t + 1, stop_t + 7, "Wait on the pavement, never in the road")
    s.say(30, 36, "Everyone gets an ice cream!")
    s.sound("traffic", level=lambda t: 0.2)


@script("tow_truck")
def tow_truck(s):
    """A little car has broken down at the kerb (its driver waits safely on the pavement). The tow truck
    overtakes it carefully in the empty other lane, pulls back in ahead of it, reverses slowly, lifts the
    car's front wheels and tows it away."""
    V.SCALE = 1.25
    SC.hills(s, col=(136, 176, 136), amp=60)
    SC.roadside(s, "country")
    SC.road(s)
    truck = V.truck("tow", s.spec["vehicle"].get("color", "orange"), s.seed, s.time)
    keys = [(0, 230), (27, 230), (33, 0), (39, 0), (40, -70), (45.5, -70), (46.5, 0), (52, 0), (55, 110), (s.D, 150)]
    mv = SpeedPath(0.0, keys, s.D)
    body = SC.body_len(truck)
    hook_x = 30 * truck.k
    t_hook = 47.0
    x_hook, _ = mv.at(t_hook)
    car = V.car("hatch", "purple", s.seed + 3, s.time)
    car_body = SC.body_len(car)
    car_rest = x_hook + hook_x - 16 - car_body
    car_front = car_rest + car_body
    t_out = next(i / FPS for i, x in enumerate(mv.x) if x + body > car_rest - 350)
    t_in = next(i / FPS for i, x in enumerate(mv.x) if x > car_front + 60)

    def lane(t):
        u = smooth((t - t_out) / 1.6) * (1 - smooth((t - t_in) / 1.6))
        return SC.NEAR + (SC.FAR - SC.NEAR) * u
    _cam_from(s, mv, 0.3)
    s.sound("engine", level=lambda t: min(1.0, mv.at(t)[1] / 300 + 0.25), kind2="truck")
    state = {}

    def tdraw(f, t, cam):
        x, v = mv.at(t)
        sx = x - cam
        gy = lane(t)
        lift = 1.2 * math.sin(t * 17) * min(1.0, v / 120)
        ox, oy = truck.draw(f, sx, gy, x, t, lift=lift)
        state["pt"] = dict(front=(sx + body, oy + truck.h * 0.45), top=(sx + body / 2, oy), dir=1)
    # the truck is drawn behind the parked car while it is out in the far lane, in front of it otherwise
    s.add(5.8, lambda f, t, cam: tdraw(f, t, cam) if lane(t) < SC.NEAR - 40 else None)
    s.add(6.2, lambda f, t, cam: tdraw(f, t, cam) if lane(t) >= SC.NEAR - 40 else None)
    s.hero_fn = lambda t: state.get("pt") or dict(front=(W * 0.6, 700), top=(W * 0.5, 600), dir=1)
    lift_u = lambda t: smooth((t - 48) / 3.0)

    def cdraw(f, t, cam):
        x = car_rest if t < t_hook else car_rest + (mv.at(t)[0] - x_hook)
        sx = x - cam
        if sx > W + 40 or sx + car.w < -40:
            return
        u = lift_u(t)
        car.draw(f, sx, SC.NEAR, x - car_rest, t, tilt=7 * u, lift=34 * u)
        if t > t_hook - 0.5:
            tx = mv.at(t)[0] - cam + hook_x
            ImageDraw.Draw(f).line([(tx, SC.NEAR - 120 * truck.k), (sx + car_body, SC.NEAR - 60 - 34 * u)],
                                   fill=(60, 60, 66), width=5)
    s.add(6.0, cdraw)
    SC.walker(s, lambda t: (car_rest + 60, False), SC.ROAD_TOP + 4, (0, 52), s.seed + 5, z=4.5)
    s.say(8, 14, "Oh no! The little car has broken down")
    s.say(t_out, t_out + 6, "The tow truck goes round it carefully")
    s.say(34, 40, "Now it backs up slowly")
    s.say(49, 55, "Up goes the car. Off to the garage!")
    s.sound("lift", at=48.0)


@script("delivery_truck")
def delivery_truck(s):
    """A delivery truck stops at three houses; the driver carries a parcel to each front door."""
    SC.hills(s, col=(150, 184, 140), amp=40)
    SC.street(s)
    SC.road(s, markings=False)
    truck = V.truck("box", s.spec["vehicle"].get("color", "white"), s.seed, s.time)
    stops = [(7, 18), (25, 36), (44, 56)]
    keys = [(0, 170)]
    for a, b in stops:
        keys += [(a - 3, 170), (a, 0), (b, 0), (b + 3, 170)]
    mv = SpeedPath(0.0, keys, s.D)
    SC.hero_car(s, truck, mv, anchor=0.12)
    base = SC.ROAD_TOP + 4
    boxes = [(200, 150, 100), (226, 190, 130), (180, 140, 100)]
    deliveries = []
    for i, (a, b) in enumerate(stops):
        x_rear, _ = mv.at(a + 0.5)
        deliveries.append((a + 1.0, x_rear - 30, boxes[i], s.cam(a + 1.0)))

    def draw(f, t, cam):
        for i, (t0, xr, col, cam0) in enumerate(deliveries):
            a = t - t0
            if a < 0:
                continue
            if a > 9:   # the parcel waits on the doorstep (it moves with the houses' layer)
                x = (xr - cam0) + (cam0 - cam) * 0.7
                q = Pen(80, 60)
                q.rect(10, 14, 64, 56, col, r=4)
                q.rect(34, 14, 40, 56, shade(col, 0.8))
                f.alpha_composite(q.done(), (int(x), int(base - 120 * 0.7 - 60)))
                continue
            # walk to the door (up the path), put the parcel down, walk back
            if a < 3.5:
                u, carry = smooth(a / 3.5), True
            elif a < 4.5:
                u, carry = 1.0, False
            else:
                u, carry = 1 - smooth((a - 4.5) / 3.5), False
            y = base - 120 * 0.7 * u
            sc = 1.6 * (1 - 0.18 * u)
            q = Pen(140, 200)
            V.person(q, 60, 60, sc, random.Random(s.seed + 9), phase=(t * 7 if 0 < u < 1 else None), body=(130, 90, 60))
            if carry:
                q.rect(60 - 26 * sc / 1.6, 60 + 14 * sc, 60 + 26 * sc / 1.6, 60 + 46 * sc, col, r=3)
            f.alpha_composite(q.done(), (int(xr - cam - 60), int(y - 200 + 24)))
            if a >= 4.5:
                x = xr - cam
                q2 = Pen(80, 60)
                q2.rect(10, 14, 64, 56, col, r=4)
                q2.rect(34, 14, 40, 56, shade(col, 0.8))
                f.alpha_composite(q2.done(), (int(x - 30), int(base - 120 * 0.7 - 60)))
    s.add(5.5, draw)
    s.say(8, 14, "A parcel for the blue house!")
    s.say(26, 32, "The truck stops at every house")
    s.sound("door", at=8.0)
    s.sound("door", at=26.0)
    s.sound("door", at=45.0)


# ================================================================== BOATS

@script("tugboat_push")
def tugboat_push(s):
    """A big container ship comes in to the dock; a little tugboat pushes it into place, then ropes go on."""
    V.SCALE = 1.0
    SB.far_shore(s, "city", depth=0.04)
    w = SB.water(s, c_top=(104, 160, 196), c_bot=(44, 94, 146), amp=7, lane=150)
    SB.glints(s, w)
    ship = V.boat("container", "blue", s.seed, s.time)
    dock_x = 5200.0
    smv = SpeedPath(0.0, [(0, 120), (20, 110), (36, 20), (40, 0), (s.D, 0)], s.D)
    # scale the profile so the ship's bow stops right at the dock
    end = smv.at(s.D)[0]
    k = (dock_x - ship.w - 20) / max(1.0, end)
    smv.x = [x * k for x in smv.x]
    smv.v = [v * k for v in smv.v]
    tug = V.boat("tug", s.spec["vehicle"].get("color", "red"), s.seed + 1, s.time)
    tmv = Offset(smv, -tug.w + 40)
    s.boat_actor(tug, tmv, w, 5.2)          # first actor: the tug is the singer
    s.boat_actor(ship, smv, w, 4.8, wake=True)
    _cam_from(s, smv, 0.35, offset=ship.w * 0.15)

    def dock(f, t, cam):
        x = dock_x - cam
        if x > W + 40:
            return
        q = Pen(1500, 300)
        q.rect(0, 40, 1500, 300, (150, 140, 128))
        q.rect(0, 40, 1500, 60, (120, 112, 104))
        for bx in range(60, 1500, 220):
            q.rect(bx, 10, bx + 30, 44, (60, 62, 70), r=8)
        for j in range(4):
            P.containers(q, 300 + j * 300, 40, random.Random(j + s.seed), cols=2, rows=2)
        f.alpha_composite(q.done(), (int(x - 40), int(SB.TOP + 150 - 40 - 220)))
        u = smooth((t - 42) / 3)
        if u > 0:   # mooring ropes
            d = ImageDraw.Draw(f)
            sx = smv.at(t)[0] - cam
            for j, bx in enumerate((x + 20, x + 240)):
                d.line([(sx + ship.w * (0.7 + 0.2 * j), SB.TOP + 150 - 120), (bx, SB.TOP + 150 - 210)],
                       fill=(230, 210, 160, int(255 * u)), width=5)
    s.add(4.6, dock)
    SB.gulls(s, lambda t, cam: (dock_x - cam + 400, SB.TOP - 260))
    s.say(8, 14, "A little tugboat pushes the big ship")
    s.say(26, 32, "Gently, gently, into the dock")
    s.say(44, 50, "Ropes hold the ship. Safe and sound!")
    s.sound("waves", level=lambda t: 0.4)
    s.sound("motor", level=lambda t: 0.5)


def _fire_jets(boat_pos, nozzles, start, seed, sun):
    """Arcs of water: droplets travelling along parabolas from each nozzle, with misty spray."""
    r = random.Random(seed)
    drops = [(r.uniform(0, 1), r.uniform(-1, 1), r.uniform(2.5, 5.5)) for _ in range(90)]

    def draw(f, t, cam):
        u_on = smooth((t - start) / 2.0)
        if u_on <= 0:
            return
        bx, by = boat_pos(t)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for j, (nx, ny, ang0, power) in enumerate(nozzles):
            ang = math.radians(ang0 + 10 * math.sin(t * 0.5 + j * 2))
            v = power * u_on
            x0, y0 = bx + nx - cam, by + ny
            vx, vy = v * math.cos(ang), -v * math.sin(ang)
            g = 900.0
            T = 2 * -vy / g if vy < 0 else 1
            pts = [(x0 + vx * T * a, y0 + vy * T * a + 0.5 * g * (T * a) ** 2) for a in (i / 24 for i in range(25))]
            d.line(pts, fill=(250, 252, 255, 150), width=16)
            d.line(pts, fill=(255, 255, 255, 220), width=6)
            for ph, off, rad in drops:
                a = (ph + t * 0.9) % 1.0
                x = x0 + vx * T * a + off * 14 * a
                y = y0 + vy * T * a + 0.5 * g * (T * a) ** 2 + off * 10 * a
                d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(240, 248, 255, int(220 * (1 - a * 0.6))))
            ex, ey = pts[-1]
            for m in range(10):   # splash where it lands
                a = (m / 10 + t * 1.3) % 1.0
                rr = 8 + 26 * a
                d.ellipse([ex - rr + m * 4 - 20, ey - rr * 0.6, ex + rr + m * 4 - 20, ey + rr * 0.3],
                          fill=(255, 255, 255, int(120 * (1 - a))))
        if sun:   # a small rainbow in the spray
            cx, cy = bx + nozzles[0][0] - cam + 160, by - 40
            for i, c in enumerate([(230, 80, 80), (240, 150, 70), (240, 220, 90), (110, 190, 110), (90, 140, 220), (140, 100, 200)]):
                rr = 260 - i * 10
                d.arc([cx - rr, cy - rr, cx + rr, cy + rr], 200, 340, fill=c + (int(90 * u_on),), width=10)
        f.alpha_composite(lay)
    return draw


@script("fireboat_show")
def fireboat_show(s):
    """A red fireboat sails into the harbour and sprays a big water show to welcome the boats."""
    V.SCALE = 1.35
    SB.far_shore(s, "coast")
    w = SB.water(s, amp=9, lane=220)
    SB.glints(s, w)
    boat = V.boat("tug", s.spec["vehicle"].get("color", "red"), s.seed, s.time)
    mv = SpeedPath(0.0, [(0, 120), (8, 100), (14, 30), (s.D - 10, 30), (s.D, 60)], s.D)
    SB.follow_boat(s, boat, mv, w, anchor=0.3)
    nozzles = [(boat.w * 0.55, -boat.h * 0.75, 62, 760), (boat.w * 0.3, -boat.h * 0.6, 118, 620),
               (boat.w * 0.8, -boat.h * 0.6, 48, 640)]

    def pos(t):
        x, _ = mv.at(t)
        return x, w.surface(x + boat.w / 2, t)
    s.add(5.3, _fire_jets(pos, nozzles, 12.0, s.seed, s.time in ("day", "morning", "golden")))
    sail = V.boat("sailboat", "yellow", s.seed + 2, s.time)
    s.boat_actor(sail, Mover(0.0, 70, s.D, lambda x, t, v: 70), w, 4.2, x0=2600)
    s.say(4, 10, "Here comes the fireboat!")
    s.say(14, 20, "Whoosh! A big water show")
    s.say(30, 36, "Can you see the rainbow in the spray?")
    s.sound("water", level=lambda t: 0.25 + 0.5 * smooth((t - 12) / 2))


@script("lighthouse_fog")
def lighthouse_fog(s):
    """A foggy morning: the lighthouse beam sweeps slowly while a big ship feels its way past."""
    V.SCALE = 1.1
    SB.far_shore(s, "hills", depth=0.05)
    w = SB.water(s, c_top=(150, 176, 196), c_bot=(70, 110, 146), amp=8, lane=170)
    ship = V.boat("container", s.spec["vehicle"].get("color", "blue"), s.seed, s.time)
    mv = Mover(0.0, 90, s.D, lambda x, t, v: 90)
    SB.follow_boat(s, ship, mv, w, anchor=0.12)
    lh_x = 2600.0

    def lighthouse(f, t, cam):
        x = lh_x - cam * 0.55
        if x < -600 or x > W + 600:
            return
        q = Pen(700, 700)
        q.poly([(0, 700), (120, 560), (300, 520), (480, 540), (700, 700)], (110, 104, 100))   # rocks
        q.poly([(310, 540), (390, 540), (374, 200), (326, 200)], (246, 244, 236))
        for j in range(4):
            yy = 500 - j * 90
            q.poly([(312, yy), (388, yy), (386, yy - 40), (314, yy - 40)], (214, 70, 64))
        q.rect(310, 150, 390, 204, (60, 62, 70), r=6)
        q.rect(322, 160, 378, 200, (255, 240, 170))
        q.poly([(300, 152), (400, 152), (350, 110)], (214, 70, 64))
        f.alpha_composite(q.done(), (int(x - 350), int(SB.TOP + 40 - 700)))
        # the slow sweeping beam (a soft wedge, never pointing at the viewer)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        cx, cy = x, SB.TOP + 40 - 700 + 180
        ang = math.sin(t * 0.45) * 1.15
        length = 900
        side = 1 if math.cos(t * 0.45) >= 0 else -1
        for wdt, al in ((0.12, 50), (0.07, 70), (0.03, 90)):
            a1, a2 = ang - wdt, ang + wdt
            pts = [(cx, cy), (cx + side * length * math.cos(a1), cy + length * math.sin(a1) * 0.35),
                   (cx + side * length * math.cos(a2), cy + length * math.sin(a2) * 0.35)]
            d.polygon(pts, fill=(255, 246, 200, al))
        f.alpha_composite(lay)
    s.add(1.6, lighthouse)
    s.say(6, 12, "It is foggy. It's hard to see")
    s.say(24, 30, "The lighthouse shows ships where the rocks are")
    s.sound("waves", level=lambda t: 0.4)


# ================================================================== AIRPLANES

def _ground_strip(s, crowd=True, field=(132, 182, 112)):
    hv = 300

    def draw(p, g, X0, X1, rng):
        p.rect(0, 120, 1600 + 720, 300, field)
        x = X0 + rng.uniform(0, 200)
        while x < X1:
            lx = x - X0 + 360
            P.tree(p, lx, 130, rng.uniform(70, 110), rng, rng.choice(["round", "pine"]))
            x += rng.uniform(140, 320)
        if crowd:
            for i in range(int((X1 - X0) / 26)):
                xx = 360 + i * 26 + rng.uniform(-6, 6)
                c = rng.choice([COLORS["red"], COLORS["blue"], COLORS["yellow"], COLORS["green"], COLORS["purple"]])
                p.rect(xx - 9, 236, xx + 9, 300, c, r=6)
                p.circle(xx, 226, 9, rng.choice([(241, 205, 175), (204, 152, 112), (150, 104, 74)]))
    s.layer("ground", H - hv, hv, 0.5, draw, 3)


def _rot_plane(plane, f, x, y, ang, t, flip=False):
    """Draw a plane centred at (x, y), nose pointing at angle ang (degrees, counter-clockwise)."""
    img = plane.sprite(0, t, {"gear": 0.0})
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    img = img.rotate(ang, resample=Image.BICUBIC, expand=True)
    f.alpha_composite(img, (int(x - img.width / 2), int(y - img.height / 2)))


@script("air_show")
def air_show(s):
    """Three little planes fly side by side, draw coloured smoke and loop the loop above the field."""
    V.SCALE = 0.9
    _ground_strip(s)
    s._cam = [i / FPS * 20 for i in range(int(s.D * FPS) + 3)]
    cols = ["red", "blue", "yellow"]
    smoke = [(240, 110, 110), (110, 150, 240), (250, 210, 90)]
    planes = [V.small_plane(c, s.seed + i, s.time) for i, c in enumerate(cols)]
    period = 15.0

    def path(t, i):
        """Screen position and heading of plane i: pass to the right with a loop, then back to the left."""
        k, a = int(t // period), t % period
        dirn = 1 if k % 2 == 0 else -1
        lag = i * 0.55
        a = a - lag
        v = (W + 900) / period
        y0 = 470 + i * 75
        if dirn > 0:
            x = -400 + v * a
            loop0, loop_t = 5.0, 4.0
            if loop0 < a < loop0 + loop_t:
                ph = (a - loop0) / loop_t * 2 * math.pi
                R = 170
                cx = -400 + v * loop0
                x = cx + R * math.sin(ph) + v * 0 * ph
                y = y0 - R * (1 - math.cos(ph))
                return x, y, math.degrees(ph), False
            if a >= loop0 + loop_t:
                x = -400 + v * (a - loop_t)
            return x, y0 + 14 * math.sin(a * 0.8), 2 * math.cos(a * 0.8), False
        x = W + 400 - v * a
        return x, y0 + 40 + 14 * math.sin(a * 0.8), -2 * math.cos(a * 0.8), True

    def draw(f, t, cam):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        for i in range(3):
            pts = []
            for j in range(48):
                tt = t - j * 0.08
                if tt < 0 or int(tt // period) != int(t // period):
                    break
                x, y, ang, fl = path(tt, i)
                pts.append((x - (plane_len := planes[i].w * 0.45) * math.cos(math.radians(ang)) * (-1 if fl else 1),
                            y + plane_len * math.sin(math.radians(ang)) * (-1 if fl else 1)))
            for j in range(len(pts) - 1):
                al = int(200 * (1 - j / len(pts)))
                d.line([pts[j], pts[j + 1]], fill=smoke[i] + (al,), width=int(14 + j * 0.6))
        f.alpha_composite(lay)
        for i in range(3):
            x, y, ang, fl = path(t, i)
            _rot_plane(planes[i], f, x, y, ang if not fl else -ang, t, flip=fl)
    s.add(6, draw)

    def hero(t):
        x, y, ang, fl = path(t, 0)
        dirn = -1 if fl else 1
        return dict(front=(x + dirn * planes[0].w * 0.5, y), top=(x, y - 60), dir=dirn)
    s.hero_fn = hero
    s.say(4, 10, "Welcome to the air show!")
    s.say(20, 26, "Loop the loop!")
    s.say(34, 40, "Coloured smoke draws lines in the sky")
    s.sound("prop", level=lambda t: 0.5)


@script("runway_parade")
def runway_parade(s):
    """Small, big, biggest: a little plane, a jet and a jumbo jet take off one after another."""
    V.SCALE = 1.0
    SPL.airport(s)
    small = V.small_plane("red", s.seed, s.time)
    jet = V.airliner(s.spec["vehicle"].get("color", "blue"), s.seed + 1, s.time)
    jumbo = V.airliner("white", s.seed + 2, s.time, jumbo=True)
    plan = [(small, 3.0, 150, 44), (jet, 17.0, 150, 40), (jumbo, 36.5, 140, 34)]
    rot_x = 1150.0

    def make(plane, t0, v0, acc):
        x0 = -plane.w - 60
        dist = rot_x - 0.4 * plane.w - x0
        t_rot = (-v0 + math.sqrt(v0 * v0 + 2 * acc * dist)) / acc
        v_rot = v0 + acc * t_rot

        def path(t):
            a = max(0.0, t - t0)
            if a <= t_rot:
                x = x0 + v0 * a + 0.5 * acc * a * a
            else:
                x = x0 + dist + v_rot * (a - t_rot) + 0.5 * acc * 0.3 * (a - t_rot) ** 2
            b = max(0.0, a - t_rot)
            climb = min(620.0, 12 * b * b + 36 * b)
            pitch = 8 * smooth(b / 2.5) * (1 - 0.6 * smooth((b - 7) / 4))
            gear = 1 - smooth((b - 2.5) / 3)
            return x, SPL.GROUND - climb, pitch, {"gear": gear, "flaps": 0.5}
        return path, t0 + t_rot
    paths = [make(p, t0, v0, acc) for p, t0, v0, acc in plan]
    # the camera stays still for the first two, then follows the jumbo once it is in the air
    jpath, jrot = paths[2]
    cams, c = [], 0.0
    for i in range(int(s.D * FPS) + 3):
        t = i / FPS
        if t > jrot:
            x, *_ = jpath(t)
            c = max(c, x - 900)
        cams.append(c)
    s._cam = cams
    for (plane, t0, _, _), (path, _) in zip(plan, paths):
        SPL.plane_actor(s, plane, lambda t, path=path, t0=t0: path(t) if t >= t0 - 0.1 else (-99999, SPL.GROUND, 0, {}),
                        z=6, shadow_ground=SPL.GROUND)
    s.pop(9.5, lambda t: (W * 0.5, 420), "Small")
    s.pop(23.5, lambda t: (W * 0.5, 420), "Big")
    s.pop(43.5, lambda t: (W * 0.5, 380), "Biggest!")

    def hero(t):
        cam = s.cam(t)
        for (plane, t0, _, _), (path, _) in reversed(list(zip(plan, paths))):
            if t >= t0:
                x, y, pitch, st = path(t)
                x -= cam
                if -plane.w < x < W:
                    oy = y - plane.ground
                    return dict(front=(x + plane.w * 0.97, oy + plane.h * 0.5), top=(x + plane.w * 0.5, oy), dir=1)
        return dict(front=(W * 0.6, 700), top=(W * 0.5, 600), dir=1)
    s.hero_fn = hero
    s.say(4, 10, "First, a little propeller plane")
    s.say(18, 24, "Next, a big jet")
    s.say(37, 43, "Last, the biggest jumbo jet!")
    s.sound("jet", level=lambda t: 0.3 + 0.4 * smooth((t - 17) / 4))


def glider(seed=0, time="day"):
    p = V.Pen(560, 120)
    body = (248, 248, 246)
    p.ellipse(60, 54, 520, 84, body)                         # slim fuselage
    p.poly([(60, 64), (10, 18), (40, 18), (110, 62)], body)   # tail fin
    p.rect(20, 56, 90, 62, (220, 220, 222), r=3)
    p.ellipse(330, 46, 430, 70, GLASS)                         # canopy
    V.person(p, 380, 62, 0.8, random.Random(seed), bust=True)
    p.rect(150, 62, 470, 70, (226, 226, 230), r=4)            # the long wing, edge-on
    p.rect(150, 62, 470, 64, (250, 250, 252), r=2)
    p.rect(300, 70, 330, 74, COLORS["red"])
    return V.Vehicle(light(p.done(), time), [], 84, time, kind="plane")


@script("glider_tow")
def glider_tow(s):
    """A tow plane pulls a glider up on a long rope; the rope is let go and the glider soars on its own."""
    V.SCALE = 1.2
    s.world.weather.wind = 18
    SPL.sky_clouds(s, front=False)
    _ground_strip(s, crowd=False, field=(150, 180, 110))
    tow = V.small_plane("yellow", s.seed, s.time)
    gl = glider(s.seed + 1, s.time)
    release = 47.0
    v = 200.0
    s._cam = [i / FPS * v for i in range(int(s.D * FPS) + 3)]
    rope = 420

    def tow_xy(t):
        x = 1150 + 30 * math.sin(t * 0.3) + (0 if t < release else 160 * (t - release) + 40 * (t - release) ** 2)
        y = 420 + 20 * math.sin(t * 0.5) + (0 if t < release else 60 * (t - release))
        return x, y

    def gl_xy(t):
        x = 1150 - rope - gl.w + 20 * math.sin(t * 0.3 + 0.6)
        y = 450 + 22 * math.sin(t * 0.5 - 0.4)
        if t > release:
            a = t - release
            y -= 40 * smooth(a / 4) + 6 * a
        return x, y

    def draw(f, t, cam):
        tx, ty = tow_xy(t)
        gx, gy = gl_xy(t)
        if t < release:
            ImageDraw.Draw(f).line([(gx + gl.w - 20, gy + 66), (tx + 20, ty + 108)], fill=(70, 70, 76), width=3)
        elif t < release + 4:   # the released rope trails behind the tow plane
            a = (t - release) / 4
            ImageDraw.Draw(f).line([(tx + 20, ty + 108), (tx - 220 * (1 - a * 0.5), ty + 160 + 80 * a)],
                                   fill=(70, 70, 76, int(255 * (1 - a))), width=3)
        gl.draw(f, gx, gy + 84 * gl.k, 0, t, tilt=2 * math.sin(t * 0.5), shadow=False)
        if tx < W + 50:
            tow.draw(f, tx, ty + tow.ground, t * 300, t, tilt=(-6 if t > release else 0) + 2 * math.sin(t * 0.5), shadow=False)
    s.add(6, draw)

    def hero(t):
        tx, ty = tow_xy(t)
        if tx > W - 60:
            gx, gy = gl_xy(t)
            return dict(front=(gx + gl.w, gy + 60), top=(gx + gl.w / 2, gy), dir=1)
        return dict(front=(tx + tow.w, ty + tow.h * 0.55), top=(tx + tow.w * 0.5, ty + 20), dir=1)
    s.hero_fn = hero
    s.say(8, 14, "Look: no propeller!")
    s.say(20, 26, "The tow plane pulls it up high")
    s.say(release, release + 6, "Let go! The glider flies on the wind")
    s.sound("prop", level=lambda t: 0.6 if t < release else max(0.0, 0.6 - (t - release) * 0.08))
    s.sound("wind", level=lambda t: 0.4)


# ================================================================== TRAINS

def _pantograph(train, mv, x0=0.0):
    def draw(f, t, cam):
        d, _ = mv.at(t)
        q = ImageDraw.Draw(f)
        for j, u in enumerate(train.units):
            if j % 2:
                continue
            x = x0 + d + train.offsets[j] - cam + u.w * 0.5
            top = ST.TRACK - u.ground + 6 * u.k
            q.line([(x - 40, top), (x, top - 70), (x + 40, top)], fill=(60, 62, 70), width=5)
            q.line([(x - 30, top - 70), (x + 30, top - 70)], fill=(60, 62, 70), width=6)
    return draw


@script("city_tram")
def city_tram(s):
    """A tram glides through the city on rails in the street, stops at the tram stop, people get on."""
    V.SCALE = 1.2
    SC.town(s, tall=True)

    def street(p, g, X0, X1, rng):
        w = 1600 + 720
        p.rect(0, 0, w, 400, (98, 102, 112))
        p.rect(0, 0, w, 16, (190, 186, 180))
        for xw in range(int((X0 - 360) // 46 * 46), int(X1 + 360), 46):
            x = xw - X0 + 360
            p.rect(x, 44, x + 30, 52, (80, 82, 90))
        p.rect(0, 38, w, 44, (170, 174, 184))
    s.layer("street", ST.TRACK - 60 + 18, 400, 1.0, street, 4)
    s.ground_y = ST.TRACK
    s.track = ST.TRACK
    ST.catenary(s)
    col = s.spec["vehicle"].get("color", "red")
    units = [V.railcar("metro", col, s.seed + i, s.time) for i in range(3)]
    tram = V.Train(units[0], units[1:], gap=4)
    stop_line = 5200.0
    t_stop, t_go = 20.0, 34.0
    mv = Mover(0.0, 200, s.D, stop_target(200, [(stop_line, t_go)], tram.front(), a=70))
    ST.run(s, tram, mv, anchor=0.5, smoke=False)
    s.add(5.6, _pantograph(tram, mv))

    def shelter(f, t, cam):
        x = stop_line - 900 - cam
        if x > W + 40 or x < -900:
            return
        q = Pen(800, 300)
        q.rect(40, 30, 760, 50, (60, 120, 190), r=6)
        q.rect(60, 50, 72, 290, (120, 126, 138))
        q.rect(728, 50, 740, 290, (120, 126, 138))
        q.rect(80, 70, 300, 260, (200, 226, 240, 140), r=4)
        P.sign(q, 600, 290, "bus", 0)
        f.alpha_composite(q.done(), (int(x), ST.TRACK - 60 - 290))
    s.add(3.7, shelter)
    for k in range(4):
        def walker(f, t, cam, k=k):
            t0 = t_stop + 2.5 + k * 2.0
            if t > t0 + 2.4:
                return
            u = smooth((t - t0) / 2.2)
            x = stop_line - 760 + k * 150 - cam
            q = Pen(140, 200)
            V.person(q, 60, 60, 1.7, random.Random(s.seed + 30 + k), phase=(t * 7 if 0 < u < 1 else None))
            f.alpha_composite(q.done(), (int(x), int(ST.TRACK - 60 - 190 + 40 * u)))
        s.add(3.8, walker)
    s.say(6, 12, "The tram runs on rails in the street")
    s.say(t_stop, t_stop + 6, "The tram stop! People get on")
    s.say(44, 50, "It gets power from the wire above")
    s.sound("traffic", level=lambda t: 0.25)
    s.sound("chime", at=t_stop + 1)


class _Mirror:
    """Draw a train going right-to-left: draw it mirrored in a band, then flip the band.
    front(t) -> screen x of the train's front (its left end); dist(t) -> distance travelled (turns the wheels)."""

    def __init__(self, train, front, dist, track, band=520):
        self.train, self.front, self.dist, self.track, self.band = train, front, dist, track, band

    def __call__(self, f, t, cam):
        L = self.train.length
        mx = W - self.front(t) - L
        if mx > W or mx + L < 0:
            return
        lay = Image.new("RGBA", (W, self.band), (0, 0, 0, 0))
        self.train.draw(lay, mx, self.band - 20, self.dist(t), t)
        lay = lay.transpose(Image.FLIP_LEFT_RIGHT)
        f.alpha_composite(lay, (0, int(self.track - self.band + 20)))


@script("double_track")
def double_track(s):
    """Two tracks: a passenger train goes right on the near track while a long freight train goes left on
    the far track. Each stays on its own track."""
    ST.scenery(s, "country", depth=0.5)
    far = ST.TRACK - 120
    s._cam = [0.0] * (int(s.D * FPS) + 3)
    V.SCALE = 0.95
    freight = ST.make_train(s, "diesel", "orange", 9, cargo_cycle=["container", "tanker", "hopper"],
                            car_colors=["blue", "red", "green", "yellow"])
    fv = 72.0
    ST.rails(s, y=far, z=3.2)
    s.add(3.4, _Mirror(freight, lambda t: W + 20 - fv * t, lambda t: fv * t, far))
    V.SCALE = 1.25
    ST.rails(s, z=4)
    pas = ST.make_train(s, "diesel", s.spec["vehicle"].get("color", "blue"), 4, "coach", ["red", "blue", "yellow", "green"])
    pv = 130.0
    pmv = Mover(-pas.length - 40 - pv * 16, pv, s.D, lambda x, t, v: pv)
    ST.run(s, pas, pmv, follow=False, smoke=False)
    s.say(5, 11, "Two tracks, two trains")
    s.say(22, 28, "The freight train goes one way...")
    s.say(30, 36, "...the passenger train goes the other way")
    s.sound("horn", at=26.0)


@script("water_tower")
def water_tower(s):
    """The steam train stops under the water tower; the spout swings down and fills the tender."""
    V.SCALE = 1.35
    ST.scenery(s, "country")
    ST.rails(s)
    tr = ST.make_train(s, "steam", s.spec["vehicle"].get("color", "green"), 3, "coach", ["red", "yellow", "blue"])
    eng = tr.engine
    tower_x = 5600.0
    t_go = 36.0
    mv = Mover(0.0, 220, s.D, stop_target(220, [(tower_x + eng.w * 0.25, t_go)], tr.front(), a=60))
    ST.run(s, tr, mv, anchor=0.55)
    fill = (21.0, 31.0)

    def tower(f, t, cam):
        x = tower_x - cam
        if x > W + 400 or x < -500:
            return
        q = Pen(520, 760)
        for lx in (110, 390):
            q.rect(lx, 300, lx + 20, 760, (120, 84, 60))
        q.line([(120, 360), (400, 700)], (120, 84, 60), 8)
        q.line([(400, 360), (120, 700)], (120, 84, 60), 8)
        q.rect(60, 100, 460, 320, (160, 104, 70), r=10)
        for k in range(8):
            q.rect(70 + k * 50, 104, 74 + k * 50, 316, (140, 90, 60))
        q.poly([(40, 104), (480, 104), (260, 20)], (110, 70, 56))
        u = smooth((t - fill[0] + 2) / 2) * (1 - smooth((t - fill[1]) / 2))
        ang = math.radians(10 + 50 * u)
        px, py = 440, 260
        ex, ey = px + 200 * math.cos(ang), py + 200 * math.sin(ang)
        q.line([(px, py), (ex, ey)], (90, 92, 100), 18)
        f.alpha_composite(q.done(), (int(x - 260), ST.TRACK - 760 - 60))
        if fill[0] < t < fill[1]:
            dr = ImageDraw.Draw(f)
            sx, sy = x - 260 + ex * eng.k / 1.35 * 1.0, ST.TRACK - 760 - 60 + ey
            for j in range(16):
                a = (j / 16 + t * 2.5) % 1.0
                dr.ellipse([sx - 10 + a * 6, sy + a * 70 - 8, sx + 10 + a * 6, sy + a * 70 + 8], fill=(150, 200, 240, 220))
    s.add(5.7, tower)
    s.say(6, 12, "A steam train needs water to make steam")
    s.say(fill[0], fill[0] + 6, "Glug glug! The tank fills up")
    s.say(t_go + 1, t_go + 7, "All full. Off we go!")
    s.sound("water", level=lambda t: 0.5 if fill[0] < t < fill[1] else 0.0)
    s.sound("whistle", at=t_go - 1)
