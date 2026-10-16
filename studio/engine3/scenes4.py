"""Batch 4: four themed videos, each mixing many kinds of vehicles, each vehicle seen from three angles.

Every scene: a theme's scenery, one hero vehicle (plus some traffic), three camera angles that dissolve
into each other, the hero's engine sound (louder as it comes closer, with a real Doppler pass-by), and
the scene's vehicle noise for the song's noise break. Everyone drives on their own side of the road,
trains run on rails, planes use runways and flight paths, the helicopter lands on a helipad.
"""
import math
import random

import numpy as np

from . import models as Mo
from . import world as Wd
from .r3d import Obj
from .stage import Actor, TrainActor, scene, smoke, smooth
from .themes import THEMES

D_DEFAULT = 60.5


def lane_actor(st, model, lane, ln, speed, s_at_mid=None, offset=None, reverse=False, **kw):
    """Put a model on a theme lane so that it is near the middle of the lane at the middle of the scene."""
    path = ln[lane]
    v = speed if callable(speed) else (lambda t, sp=speed: sp)
    mid = s_at_mid if s_at_mid is not None else path.length * 0.5 + st.r.uniform(-500, 500)
    # integrate the speed profile to find the start that puts the actor at `mid` at D/2
    dist = sum(v(i / 24) / 24 for i in range(int(st.D / 2 * 24)))
    s0 = mid + dist if reverse else mid - dist
    off = ln.get(lane + "_off", 0.0) if offset is None else offset
    if lane == "road" and reverse:
        off = -ln.get("road_off", -1.8)
    return Actor(model, path, v, s0=s0, D=st.D, offset=off, reverse=reverse, **kw)


def traffic(st, ln, n=6, lane="road", kinds=("sedan", "hatch", "suv", "van", "taxi", "pickup"), speed=(12, 16), spacing=(70, 140),
            trucks=False):
    """Oncoming traffic in the other lane, spaced out like real traffic (each keeps its own lane)."""
    r = random.Random(st.seed + 31)
    path = ln[lane]
    cols = list(Mo.PAL)[:10]
    s = path.length * 0.5 + 900
    for i in range(n):
        if trucks and r.random() < 0.3:
            m = Mo.truck(r.choice(["box", "tanker", "logs"]), r.choice(["blue", "red", "white", "green"]), st.seed + 70 + i)
        else:
            m = Mo.car(r.choice(kinds), r.choice(cols), st.seed + 70 + i)
        sp = r.uniform(*speed)
        a = Actor(m, path, lambda t, sp=sp: sp, s0=s, D=st.D, offset=-ln.get("road_off", -1.8), reverse=True, bob=0.01)
        st.actors.append(a)
        st.sounds.append(dict(kind=engine_kind(m), src=a, level=0.45))
        s -= r.uniform(*spacing)


def engine_kind(m):
    n = m.name
    if n in ("sedan", "hatch", "suv", "pickup", "taxi", "van"):
        return "car"
    return {"bus": "bus", "truck": "truck", "tractor": "tractor", "steam": "steam", "diesel": "diesel", "electric": "electric",
            "airliner": "jet", "small_plane": "prop", "helicopter": "heli", "cable_car": "cable"}.get(n, "boat")


def hero(st, actor, shots, overlays=None, level=1.0):
    st.actors.append(actor)
    st.hero = actor
    st.sounds.append(dict(kind=engine_kind(actor.model), src=actor, level=level, hero=True))
    st.shot_plan(shots, overlays={} if overlays is None else overlays)


def exhaust(st, actor, local=(-2.0, 0.6, 0.4), col=(200, 200, 204), every=0.3, alpha=0.18):
    st.overlays.append(smoke(lambda t: actor.point(t, local), every=every, life=1.6, rise=0.5, drift=(0, 0), size=0.15,
                             grow=0.5, col=col, alpha=alpha))


def dust(st, actor, back=None):
    b = back if back is not None else -actor.model.length / 2
    st.overlays.append(smoke(lambda t: actor.point(t, (b, 0, 0.3)), every=0.2, life=2.6, rise=0.4, drift=(0, 0.3), size=0.5,
                             grow=1.1, col=(200, 178, 140), alpha=0.22))


def steam_smoke(st, actor):
    eng = actor.train.engine
    st.overlays.append(smoke(lambda t: actor.point(t, eng.chimney), every=0.22, life=5.0, rise=2.2, drift=(-1.5, 0.4), size=0.7,
                             grow=1.5, col=(238, 238, 238), alpha=0.6))


def wakes(st, actor):
    def fn(t, cam):
        pos, h, p, r, d, v = actor.state(t)
        w = Wd.wake(actor.point(t, (-actor.model.length / 2, 0, 0)), h, v)
        return [w] if w else []
    st.dynamic.append(fn)


def spray(st, actor):
    st.overlays.append(smoke(lambda t: actor.point(t, (actor.model.length * 0.3, 0, 0.1)), every=0.12, life=0.7, rise=0.8,
                             drift=(0, 0), size=0.15, grow=0.6, col=(250, 252, 255), alpha=0.35))


def train_actor(st, ln, engine, cars, speed, lane="rail", mid=None):
    tr = Mo.Train(engine, cars)
    path = ln[lane]
    v = speed if callable(speed) else (lambda t, sp=speed: sp)
    m = mid if mid is not None else path.length * 0.5 + st.r.uniform(-400, 400)
    dist = sum(v(i / 24) / 24 for i in range(int(st.D / 2 * 24)))
    a = TrainActor(tr, path, v, s0=m - dist + tr.offsets[0], D=st.D)
    a.model.length = engine.length
    return a


def theme(st, name):
    return THEMES[name](st, night=st.time == "night")


# ================================================================== SEASIDE TOWN

@scene("sea_car_coast")
def sea_car_coast(st):
    ln = theme(st, "seaside")
    a = lane_actor(st, Mo.car("sedan", st.spec.get("color", "red"), st.seed), "road", ln, 16, bob=0.01)
    traffic(st, ln, 5)
    exhaust(st, a)
    hero(st, a, [("side", {"side": 1}), "front", "drone"])


@scene("sea_coastal_train")
def sea_coastal_train(st):
    ln = theme(st, "seaside")
    cars = [Mo.railcar("coach", c, st.seed + i) for i, c in enumerate(["blue", "blue", "blue"])]
    a = train_actor(st, ln, Mo.diesel_loco("blue", st.seed), cars, 22)
    hero(st, a, ["drone", ("front", {"off": 26, "h": 3.0}), ("side", {"side": 1, "dist": 26})])


@scene("sea_sailboat")
def sea_sailboat(st):
    ln = theme(st, "seaside")
    a = lane_actor(st, Mo.boat("sailboat", "navy", st.seed, sail="white"), "sea", ln, 4.0, bob=0.25, offset=0)
    wakes(st, a)
    st.actors.append(lane_actor(st, Mo.boat("sailboat", "red", st.seed + 1, sail="cream"), "sea", ln, 4.2, offset=-40, bob=0.25))
    hero(st, a, [("orbit", {"radius": 22, "h": 6}), ("side", {"dist": 22, "h": 2.0}), ("low", {"off": 14})])


@scene("sea_speedboat")
def sea_speedboat(st):
    ln = theme(st, "seaside")
    a = lane_actor(st, Mo.boat("speedboat", "red", st.seed), "harbor", ln, 13.0, bob=0.12, offset=0)
    wakes(st, a)
    spray(st, a)
    hero(st, a, [("chase", {"h": 3.0}), ("top", {"alt": 34}), ("side", {"dist": 22, "h": 1.6})])


@scene("sea_bus")
def sea_bus(st):
    ln = theme(st, "seaside")
    a = lane_actor(st, Mo.bus("yellow", st.seed), "road", ln, 11, bob=0.01)
    traffic(st, ln, 4)
    exhaust(st, a, (-5.8, 0.8, 0.4))
    hero(st, a, [("side", {"side": 1}), "cockpit", "front"])


@scene("sea_fishing_boat")
def sea_fishing_boat(st):
    ln = theme(st, "seaside")
    a = lane_actor(st, Mo.boat("fishing", "red", st.seed), "harbor", ln, 5.0, bob=0.2, offset=-20)
    wakes(st, a)
    st.overlays.append(_gulls(st, a))
    hero(st, a, [("side", {"dist": 30, "h": 3}), ("drone", {"h": 30}), ("front", {"off": 18, "h": 2.5})])


@scene("sea_seaplane")
def sea_seaplane(st):
    ln = theme(st, "seaside")
    land = st.D * 0.55

    def speed(t):
        return 42 if t < land - 4 else max(6.0, 42 - (t - land + 4) * 5)

    def alt(t):
        return max(0.0, 70 * (1 - smooth(t / (land - 2)))) if t < land else 0.0
    a = lane_actor(st, Mo.small_plane("yellow", st.seed, floats=True), "sea", ln, speed, offset=40, alt_fn=alt,
                   pitch_fn=lambda t: 0.06 if t < land else 0.02, bob=0.0)
    wakes(st, a)
    hero(st, a, [("side", {"dist": 30, "h": 6}), ("low", {"off": 22}), ("chase", {"h": 6, "back": 18})])


@scene("sea_ferry")
def sea_ferry(st):
    ln = theme(st, "seaside")
    a = lane_actor(st, Mo.boat("ferry", "blue", st.seed), "sea", ln, 6.0, bob=0.08, offset=30)
    wakes(st, a)
    hero(st, a, [("top", {"alt": 120}), ("orbit", {"radius": 70, "h": 20, "speed": 0.08}), ("side", {"dist": 80, "h": 6})])


@scene("sea_helicopter")
def sea_helicopter(st):
    ln = theme(st, "seaside")
    a = lane_actor(st, Mo.helicopter("red", st.seed), "air", ln, 24, offset=10, z=-75, bob=0.4)
    hero(st, a, [("chase", {"h": 3, "back": 18}), ("side", {"dist": 22, "h": 0}), ("orbit", {"radius": 24, "h": 4})])


@scene("sea_pickup")
def sea_pickup(st):
    ln = theme(st, "seaside")
    a = lane_actor(st, Mo.car("pickup", "teal", st.seed), "road", ln, 15, bob=0.012)
    traffic(st, ln, 5)
    exhaust(st, a)
    hero(st, a, ["chase", ("side", {"side": 1}), ("top", {"alt": 26})])


def _gulls(st, actor):
    r = random.Random(st.seed + 9)
    birds = [(r.uniform(0, 6.28), r.uniform(0.4, 0.8), r.uniform(6, 14), r.uniform(6, 12)) for _ in range(6)]

    def draw_fn(img, draw, cam, t):
        c = actor.point(t, (0, 0, 0))
        for ph, sp, rad, hh in birds:
            a = ph + t * sp
            p = c + np.array([rad * math.cos(a), rad * math.sin(a), hh])
            s = cam.screen(p)
            if not s:
                continue
            x, y, z = s
            k = min(28.0, max(2.0, 0.9 * cam.f / z / 2))
            wing = k * 0.4 * math.sin(t * 7 + ph)
            from .r3d import SS
            draw.line([((x - k) * SS, (y - wing) * SS), (x * SS, y * SS), ((x + k) * SS, (y - wing) * SS)], fill=(250, 250, 250),
                      width=max(2, int(k * 0.25 * SS)))
    return draw_fn


# ================================================================== BUSY CITY

@scene("city_bus")
def city_bus(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.bus("red", st.seed), "road", ln, 10, bob=0.01)
    traffic(st, ln, 7)
    exhaust(st, a, (-5.8, 0.8, 0.4))
    hero(st, a, ["side", "cockpit", "front"])


@scene("city_taxi")
def city_taxi(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.car("taxi", "yellow", st.seed), "road", ln, 13, bob=0.01)
    traffic(st, ln, 8)
    hero(st, a, ["chase", ("top", {"alt": 30}), "side"])


@scene("city_tram")
def city_tram(st):
    ln = theme(st, "city")
    cars = [Mo.railcar("tram", "red", st.seed + 1)]
    eng = Mo.railcar("tram", "red", st.seed)
    eng.name = "electric"
    eng.length, eng.height = 16.0, 4.2
    eng.eye = np.array([7.2, 0.6, 2.6])
    a = train_actor(st, ln, eng, cars, 9)
    traffic(st, ln, 6)
    hero(st, a, [("front", {"off": 6.5, "h": 1.7}), ("side", {"dist": 18}), "cockpit"])


@scene("city_garbage")
def city_garbage(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.truck("garbage", "green", st.seed, load_color="green"), "road", ln, 8, bob=0.01)
    traffic(st, ln, 6)
    exhaust(st, a, (-4.2, 0.9, 0.5))
    hero(st, a, ["side", ("top", {"alt": 36}), "front"])


@scene("city_fire_truck")
def city_fire_truck(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.truck("fire", "red", st.seed), "road", ln, 11, bob=0.01)
    traffic(st, ln, 6)
    hero(st, a, ["side", "front", ("orbit", {"radius": 14, "h": 8})])


@scene("city_mixer")
def city_mixer(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.truck("mixer", "orange", st.seed), "road", ln, 9, bob=0.01)
    traffic(st, ln, 6, trucks=True)
    exhaust(st, a, (-4.0, 0.9, 0.5))
    hero(st, a, [("orbit", {"radius": 14, "h": 8}), "side", ("top", {"alt": 32})])


@scene("city_river_boat")
def city_river_boat(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.boat("lake", "blue", st.seed), "river", ln, 5.0, bob=0.06, offset=0)
    wakes(st, a)
    hero(st, a, [("side", {"dist": 24, "h": 3, "side": 1}), ("drone", {"h": 40, "side": 1}), ("front", {"off": 14, "h": 3})])


@scene("city_airliner")
def city_airliner(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.airliner("blue", st.seed, gear=True), "air", ln, 72, offset=0, bob=0.0,
                   alt_fn=lambda t: -60 * smooth(t / st.D), pitch_fn=lambda t: -0.03)
    hero(st, a, [("side", {"dist": 70, "h": 0}), ("chase", {"back": 55, "h": 8}), ("orbit", {"radius": 75, "h": 6, "speed": 0.05})])


@scene("city_helicopter")
def city_helicopter(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.helicopter("blue", st.seed), "road", ln, 18, offset=0, z=55, bob=0.4)
    traffic(st, ln, 8)
    hero(st, a, [("drone", {"h": 20, "back": 30}), ("top", {"alt": 30}), ("orbit", {"radius": 22, "h": 3})])


@scene("city_night_car")
def city_night_car(st):
    ln = theme(st, "city")
    a = lane_actor(st, Mo.car("sedan", "white", st.seed), "road", ln, 12, bob=0.01)
    traffic(st, ln, 7)
    hero(st, a, ["side", "cockpit", "front"])


# ================================================================== COUNTRYSIDE FARM

@scene("farm_tractor")
def farm_tractor(st):
    ln = theme(st, "farm")
    a = lane_actor(st, Mo.tractor("green", st.seed), "road", ln, 5, bob=0.02)
    dust(st, a, -1.8)
    exhaust(st, a, (1.4, 0.35, 2.8), col=(120, 120, 124), every=0.4, alpha=0.4)
    hero(st, a, [("side", {"dist": 13}), "front", ("orbit", {"radius": 13, "h": 4})])


@scene("farm_steam_train")
def farm_steam_train(st):
    ln = theme(st, "farm")
    cars = [Mo.railcar("coach", c, st.seed + i) for i, c in enumerate(["red", "cream", "red", "cream"])]
    a = train_actor(st, ln, Mo.steam_loco("green", st.seed), cars, 16)
    steam_smoke(st, a)
    hero(st, a, [("side", {"dist": 26, "side": -1}), ("drone", {"h": 30}), ("front", {"off": 26, "h": 3.0})])


@scene("farm_pickup")
def farm_pickup(st):
    ln = theme(st, "farm")
    a = lane_actor(st, Mo.car("pickup", "red", st.seed), "road", ln, 12, bob=0.015)
    dust(st, a)
    hero(st, a, ["chase", "front", ("top", {"alt": 26})])


@scene("farm_small_plane")
def farm_small_plane(st):
    ln = theme(st, "farm")
    a = lane_actor(st, Mo.small_plane("red", st.seed), "air", ln, 38, offset=0, bob=0.6)
    hero(st, a, [("chase", {"h": 2.5, "back": 16}), ("side", {"dist": 18, "h": 0}), ("top", {"alt": 40})])


@scene("farm_milk_tanker")
def farm_milk_tanker(st):
    ln = theme(st, "farm")
    a = lane_actor(st, Mo.truck("milk", "white", st.seed), "road", ln, 11, bob=0.012)
    dust(st, a)
    hero(st, a, ["side", "front", "drone"])


@scene("farm_canal_boat")
def farm_canal_boat(st):
    ln = theme(st, "farm")
    a = lane_actor(st, Mo.boat("canal", "green", st.seed), "river", ln, 2.5, bob=0.04, offset=0)
    wakes(st, a)
    hero(st, a, [("side", {"dist": 26, "h": 2.5}), ("orbit", {"radius": 22, "h": 6}), ("top", {"alt": 36})])


@scene("farm_freight_train")
def farm_freight_train(st):
    ln = theme(st, "farm")
    cyc = [("container", "blue"), ("hopper", "brown"), ("tanker", "silver"), ("container", "red"), ("box", "green"),
           ("container", "yellow")]
    cars = [Mo.railcar(k, c, st.seed + i) for i, (k, c) in enumerate(cyc)]
    a = train_actor(st, ln, Mo.diesel_loco("orange", st.seed), cars, 18)
    hero(st, a, [("front", {"off": 28, "h": 3.0}), ("side", {"dist": 30}), ("top", {"alt": 60})])


@scene("farm_tractor_hay")
def farm_tractor_hay(st):
    ln = theme(st, "farm")
    a = lane_actor(st, Mo.tractor("red", st.seed), "road", ln, 5.5, bob=0.02)
    dust(st, a, -1.8)
    hero(st, a, [("chase", {"back": 9, "h": 3.5}), ("side", {"dist": 10, "side": 1}), ("low", {"off": 10})])


@scene("farm_family_car")
def farm_family_car(st):
    ln = theme(st, "farm")
    a = lane_actor(st, Mo.car("hatch", "blue", st.seed), "road", ln, 12, bob=0.012)
    dust(st, a)
    hero(st, a, ["cockpit", "side", ("top", {"alt": 24})])


@scene("farm_plane_landing")
def farm_plane_landing(st):
    ln = theme(st, "farm")
    st.add(Wd.runway(-200, 900, y=-40, width=18))
    land = st.D * 0.6

    def speed(t):
        return 36 if t < land else max(0.0, 36 - (t - land) * 2.6)

    def alt(t):
        return 45 * (1 - smooth(t / land)) if t < land else 0.0
    a = lane_actor(st, Mo.small_plane("blue", st.seed), "strip", ln, speed, offset=0, s_at_mid=420, alt_fn=alt,
                   pitch_fn=lambda t: 0.05 if t < land else 0.0)
    hero(st, a, [("side", {"dist": 22, "h": 2}), ("chase", {"h": 3, "back": 16}), ("front", {"off": 14, "h": 1.5, "at": 0.4})])


# ================================================================== SNOWY MOUNTAINS

@scene("snow_plow")
def snow_plow(st):
    ln = theme(st, "mountains")
    a = lane_actor(st, Mo.truck("plow", "orange", st.seed), "road", ln, 8, bob=0.01)
    st.overlays.append(smoke(lambda t: a.point(t, (5.0, 1.8, 0.5)), every=0.1, life=1.0, rise=0.9, drift=(0, 2.0), size=0.25,
                             grow=0.8, col=(250, 252, 255), alpha=0.45))
    hero(st, a, [("front", {"off": 10, "h": 2.2}), "side", ("top", {"alt": 30})])


@scene("snow_electric_train")
def snow_electric_train(st):
    ln = theme(st, "mountains")
    cars = [Mo.railcar("coach", "red", st.seed + i) for i in range(3)]
    a = train_actor(st, ln, Mo.diesel_loco("red", st.seed, kind="electric"), cars, 20)
    hero(st, a, [("side", {"dist": 26}), ("drone", {"h": 32}), "cockpit"])


@scene("snow_log_truck")
def snow_log_truck(st):
    ln = theme(st, "mountains")
    a = lane_actor(st, Mo.truck("logs", "green", st.seed), "road", ln, 11, bob=0.012)
    exhaust(st, a, (-5.0, 0.9, 0.5))
    traffic(st, ln, 4, kinds=("suv", "pickup", "van"))
    hero(st, a, ["chase", "side", ("front", {"off": 10, "h": 2.2})])


@scene("snow_helicopter")
def snow_helicopter(st):
    ln = theme(st, "mountains")
    pad = st.D * 0.7
    path = Wd.straight(-900, 150, y=-30)
    ln["pad"] = path
    L = path.length

    def speed(t):
        return 30 if t < pad - 12 else max(0.0, 30 * (pad - t) / 12)

    dist_total = sum(speed(i / 24) / 24 for i in range(int(pad * 24)))

    def alt(t):
        return 90 * (1 - smooth((t - (pad - 16)) / 16)) if t < pad else 0.0
    a = Actor(Mo.helicopter("red", st.seed), path, speed, s0=L - dist_total, D=st.D, alt_fn=alt, bob=0.2)
    hero(st, a, [("orbit", {"radius": 26, "h": 6}), ("side", {"dist": 30, "h": 2}), ("low", {"off": 22, "at": 0.4})])


@scene("snow_lake_ferry")
def snow_lake_ferry(st):
    ln = theme(st, "mountains")
    a = lane_actor(st, Mo.boat("lake", "red", st.seed), "lake", ln, 5.0, bob=0.06, offset=0)
    wakes(st, a)
    hero(st, a, [("top", {"alt": 70}), ("side", {"dist": 40, "h": 4}), ("orbit", {"radius": 45, "h": 12, "speed": 0.08})])


@scene("snow_cable_car")
def snow_cable_car(st):
    ln = theme(st, "mountains")
    path = ln["cable"]
    st.add(Wd.cable_towers(path, [path.length * k / 5 for k in range(6)]))
    st.add(Wd.cable_line(path, 0, path.length))
    a = Actor(Mo.cable_car("red", st.seed), path, lambda t: 6.0, s0=path.length * 0.5 - 6.0 * st.D / 2, D=st.D, z=-4.2,
              bob=0.0)
    hero(st, a, [("side", {"dist": 18, "h": 0}), ("low", {"off": 25, "at": 0.5}), ("orbit", {"radius": 18, "h": 2})])


@scene("snow_suv_snowfall")
def snow_suv_snowfall(st):
    ln = theme(st, "mountains")
    a = lane_actor(st, Mo.car("suv", "blue", st.seed), "road", ln, 11, bob=0.01)
    traffic(st, ln, 4, kinds=("suv", "pickup", "van"), speed=(9, 12))
    hero(st, a, ["side", "cockpit", ("front", {"off": 10, "h": 2.2})])


@scene("snow_ski_plane")
def snow_ski_plane(st):
    ln = theme(st, "mountains")
    land = st.D * 0.55

    def speed(t):
        return 34 if t < land else max(0.0, 34 - (t - land) * 3)

    def alt(t):
        return 60 * (1 - smooth(t / land)) if t < land else 0.0
    path = Wd.straight(-1600, 1600, y=-40)
    ln["snowfield"] = path
    a = lane_actor(st, Mo.small_plane("orange", st.seed, skis=True), "snowfield", ln, speed, offset=0, alt_fn=alt,
                   pitch_fn=lambda t: 0.05 if t < land else 0.0)
    st.overlays.append(smoke(lambda t: a.point(t, (0.5, 0, 0.1)), every=0.12, life=1.2, rise=0.6, drift=(0, 0), size=0.25,
                             grow=0.9, col=(250, 252, 255), alpha=0.4, active=lambda t: t > land))
    hero(st, a, [("side", {"dist": 22, "h": 3}), ("front", {"off": 16, "h": 1.5, "at": 0.45}), ("top", {"alt": 40})])


@scene("snow_bus_pass")
def snow_bus_pass(st):
    ln = theme(st, "mountains")
    a = lane_actor(st, Mo.bus("blue", st.seed), "road", ln, 10, bob=0.01)
    exhaust(st, a, (-5.8, 0.8, 0.4))
    hero(st, a, ["chase", "side", ("top", {"alt": 34})])


@scene("snow_night_train")
def snow_night_train(st):
    ln = theme(st, "mountains")
    cars = [Mo.railcar("coach", "navy", st.seed + i) for i in range(4)]
    a = train_actor(st, ln, Mo.diesel_loco("blue", st.seed), cars, 17)
    hero(st, a, [("front", {"off": 9}), ("side", {"dist": 24}), ("top", {"alt": 50})])
