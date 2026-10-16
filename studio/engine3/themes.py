"""The four settings of batch 4. Each builds its scenery on a stage and returns the lanes vehicles use.

Lanes (all travel towards +x unless noted):
  road     right-hand lane of the main road        road_back  the other lane (travels towards -x)
  rail     railway                                  sea / river / lake   water lanes
  air      a flight path                            (themes add their own extras)
"""
import math
import random

import numpy as np

from . import world as Wd
from .r3d import Mesh, Obj, box, cylinder


class Lanes(dict):
    pass


def _coast_path(seed):
    r = random.Random(seed)
    pts = [(x, 6 * math.sin(x / 260 + r.uniform(0, 1)), 0) for x in np.arange(-1600, 1601, 100)]
    return Wd.Path(pts, step=2.0)


def seaside(st, night=False):
    s = st.seed
    L = st.rend.light            # the sun shines from the land side, so boats and cars seen against the sea are lit
    L.dir = L.dir * np.array([1, -1, 1])
    L.to_sun = -L.dir
    road = _coast_path(s)
    rail = Wd.straight(-1800, 1800, y=26)
    st.add(Wd.ground(s, (118, 160, 92), y0=-40, y1=700))
    st.add(Wd.water(-40, -4000, color=(40, 112, 170), shore=(222, 206, 160)))
    rip = Wd.Ripples(s, -45, -400)
    st.dynamic.append(lambda t, cam: [rip.obj(t, cam.pos[0])])
    st.add(Wd.road(road, width=7.0, seed=s))
    st.add(Wd.rails(rail, seed=s))
    st.add(Wd.street_houses(s + 1, rail, 100, rail.length - 100, off=24, gap=(16, 30)))
    st.add(Wd.hills(s + 2, (104, 150, 90), 140, 900, height=90))
    st.add(Wd.fence(road, 60, road.length - 60, off=-5.2, color=(240, 240, 236)))
    st.add(Wd.forest(s + 3, (-1500, 1500, -30, -24), density=0.004, kinds=("palm",)))
    m = Mesh()
    Wd.lighthouse(m, 640, -95)
    box(m, (640, -95, -1), (30, 26, 4), (120, 116, 110))
    Wd.pier(m, 180, 260, -60, width=5)
    Wd.pier(m, 210, 214, -110, width=60)
    for k in range(8):
        cylinder(m, (-300 + k * 90, -30.5, 0.6), 2.2, 0.2, [(230, 80, 70), (60, 120, 200), (250, 210, 70)][k % 3], axis="z", n=10)
    st.add([Obj(m, layer=1)])
    return Lanes(road=road, rail=rail, sea=Wd.straight(-1800, 1800, y=-160), harbor=Wd.straight(-1800, 1800, y=-85),
                 air=Wd.straight(-2500, 2500, y=-60, z=120), road_off=-1.8)


def city(st, night=False):
    s = st.seed
    road = Wd.straight(-1600, 1600, y=0)
    river = Wd.straight(-1800, 1800, y=-70)
    st.add(Wd.ground(s, (120, 124, 120), y0=-50, y1=600, var=4))
    st.add(Wd.water(-46, -96, color=(60, 110, 140)))
    m = Mesh()
    for y in (-46, -96):   # river walls
        box(m, (0, y, -0.4), (3600, 1.2, 1.4), (150, 146, 140))
    st.add([Obj(m, layer=1, shadow=False)])
    st.add(Wd.road(road, width=14.0, kind="city", seed=s, center=False))
    st.add(Wd.rails(Wd.straight(-1600, 1600, y=0.0), bed=(84, 86, 94), seed=s))   # tram tracks down the middle
    st.add(Wd.city_blocks(s + 1, road, 60, road.length - 60, off=10.0, night=night))
    st.add(Wd.city_blocks(s + 3, river, 60, river.length - 60, off=-30.0, night=night, hmin=18, hmax=60))
    st.add(Wd.lamps(road, 60, road.length - 60, 9.0, night=night))
    st.add(Wd.lamps(road, 60, road.length - 60, -9.0, night=night))
    return Lanes(road=road, rail=Wd.straight(-1600, 1600, y=0.0), river=river, air=Wd.straight(-3000, 3000, y=-200, z=220),
                 road_off=-4.6)


def farm(st, night=False):
    s = st.seed
    road = Wd.Path([(x, 10 * math.sin(x / 300), 0) for x in np.arange(-1600, 1601, 100)], step=2.0)
    rail = Wd.straight(-1800, 1800, y=55)
    st.add(Wd.ground(s, (110, 156, 80), y0=-200, y1=700))
    st.add(Wd.fields(s + 1, (-1500, 1500, 12, 46), [(196, 170, 90), (120, 160, 70), (150, 110, 70), (210, 190, 110)]))
    st.add(Wd.fields(s + 2, (-1500, 1500, -80, -12), [(130, 170, 80), (200, 176, 96), (160, 120, 80)]))
    st.add(Wd.water(-92, -130, color=(70, 124, 150)))
    st.add(Wd.road(road, width=5.0, kind="dirt", seed=s))
    st.add(Wd.rails(rail, seed=s))
    st.add(Wd.fence(road, 60, road.length - 60, off=4.2, color=(150, 120, 90)))
    st.add(Wd.poles(road, 60, road.length - 60, off=6.5))
    st.add(Wd.hills(s + 3, (100, 150, 84), 160, 900, height=110))
    st.add(Wd.hills(s + 4, (100, 150, 84), -160, -900, height=80))
    st.add(Wd.forest(s + 5, (-1500, 1500, 70, 150), density=0.002, kinds=("round", "pine")))
    m = Mesh()
    r = random.Random(s)
    for x in (-700, -150, 420, 900):
        Wd.barn(m, x, 30 + r.uniform(-3, 3), yaw=0.0)
        Wd.house(m, x + 30, 32, r, w=10, d=8, h=4)
        Wd.haybales(m, x - 40, 20, r)
    st.add([Obj(m, layer=1)])
    return Lanes(road=road, rail=rail, river=Wd.straight(-1800, 1800, y=-111), air=Wd.straight(-2500, 2500, y=-20, z=60),
                 strip=Wd.straight(-200, 900, y=-40), road_off=-1.3)


def mountains(st, night=False, snowing=False):
    s = st.seed
    road = Wd.Path([(x, 14 * math.sin(x / 240), 0) for x in np.arange(-1600, 1601, 80)], step=2.0)
    rail = Wd.straight(-1800, 1800, y=34)
    st.add(Wd.ground(s, (236, 240, 246), y0=-60, y1=700, var=4))
    st.add(Wd.water(-60, -600, color=(60, 104, 140), shore=(220, 224, 232)))
    st.add(Wd.road(road, width=7.0, kind="asphalt", seed=s))
    st.add(Wd.snowbanks(road, 7.0, 60, road.length - 60, s))
    st.add(Wd.rails(rail, bed=(170, 168, 170), seed=s))
    st.add(Wd.overhead_wires(rail, 60, rail.length - 60))
    st.add(Wd.forest(s + 1, (-1500, 1500, 48, 200), density=0.0025, kinds=("pine",), snow=True))
    st.add(Wd.hills(s + 3, (226, 232, 240), 220, 1000, height=180, snow_above=-1))
    st.add(Wd.mountains(s + 4, 26, 1200, 3600, hmin=500, hmax=1200, color=(118, 126, 146), snow=0.5))
    st.add(Wd.mountains(s + 5, 14, -900, -3000, hmin=400, hmax=1000, color=(118, 126, 146), snow=0.5))
    m = Mesh()
    r = random.Random(s)
    for x in (-500, 300, 1000):
        Wd.house(m, x, 60, r, w=9, d=8, h=5, snow=True)
    Wd.helipad(m, 150, -30)
    st.add([Obj(m, layer=1)])
    cable = Wd.Path([(-900, 260, 20), (-300, 180, 140), (300, 120, 260), (900, 80, 380)], step=4.0)
    return Lanes(road=road, rail=rail, lake=Wd.straight(-2000, 2000, y=-180), air=Wd.straight(-2500, 2500, y=-40, z=90),
                 cable=cable, road_off=-1.8)


THEMES = {"seaside": seaside, "city": city, "farm": farm, "mountains": mountains}
