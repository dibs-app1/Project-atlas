"""Low-poly 3D animals for engine 3 (batch 5), built with correct anatomy and gentle, natural motion.

Four-legged animals walk with a real diagonal gait (front-left with back-right), legs swinging with the
distance travelled (so feet never slide), heads that bob and can lower to graze, tails that wag or swish.
Birds flap (or glide) with wings hinged at the shoulder; fish swim by sweeping their tails; dolphins and
whales beat their tails up and down (as real ones do); jellyfish pulse. Every model faces +x.
"""
import math
import random

import numpy as np

from . import r3d as R
from .models import Model, Part, loft, shade, col
from .r3d import Mesh, cone, cylinder, sphere
from .r3d import box as _box

EYE = (24, 22, 26)


def box(m, c, size, color, R=None, **k):
    """Animals are small, so thin boxes stay solid (never decals)."""
    k.setdefault("decal", False)
    return _box(m, c, size, color, R=R, **k)
WHITE = (240, 240, 236)
PINK = (236, 160, 170)


def _eye(m, x, y, z, r=0.05, white=True):
    if white:
        sphere(m, (x, y, z), r * 1.4, WHITE, n=6)
    sphere(m, (x + r * 0.5, y + (r * 0.5 if y > 0 else -r * 0.5), z), r, EYE, n=6)


def tube(m, pts, radii, color, n=7, cap=True, colors=None):
    """A smooth tube swept along a 3D polyline (tails, necks, legs) with a radius at every point."""
    P = [np.asarray(p, float) for p in pts]
    rings = []
    for i, p in enumerate(P):
        d = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)])
        d = d / (np.linalg.norm(d) + 1e-9)
        ref = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
        u = np.cross(d, ref)
        u /= np.linalg.norm(u) + 1e-9
        w = np.cross(d, u)
        rings.append([p + radii[i] * (math.cos(2 * math.pi * k / n) * u + math.sin(2 * math.pi * k / n) * w) for k in range(n)])
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        cen_axis = (P[i] + P[i + 1]) / 2
        for k in range(n):
            j = (k + 1) % n
            q = [a[k], b[k], b[j], a[j]]
            nrm = np.cross(q[1] - q[0], q[3] - q[0])
            if np.dot(nrm, np.mean(q, axis=0) - cen_axis) < 0:
                q = q[::-1]
            m.poly([tuple(x) for x in q], colors(i, k) if colors else color)
    if cap and radii[-1] > 1e-3:
        d = P[-1] - P[-2]
        ring = rings[-1]
        nrm = np.cross(ring[1] - ring[0], ring[2] - ring[0])
        m.poly([tuple(x) for x in (ring if np.dot(nrm, d) > 0 else ring[::-1])], color)
    return m


# ================================================================== four-legged animals

QUAD = {
    # body length, body radius (y, z), leg length, leg thickness, neck (len, angle), head (len, r), snout (len, r)
    "dog":     dict(L=0.9, ry=0.2, rz=0.22, leg=0.42, lt=0.07, neck=(0.25, 0.9), head=(0.28, 0.15), snout=(0.16, 0.08),
                    ears="floppy", tail="up", feet="paw"),
    "puppy":   dict(L=0.55, ry=0.15, rz=0.16, leg=0.24, lt=0.06, neck=(0.12, 0.9), head=(0.24, 0.14), snout=(0.1, 0.07),
                    ears="floppy", tail="up", feet="paw"),
    "dachshund": dict(L=0.85, ry=0.13, rz=0.14, leg=0.16, lt=0.06, neck=(0.15, 0.8), head=(0.24, 0.11), snout=(0.14, 0.06),
                      ears="floppy", tail="straight", feet="paw"),
    "sheepdog": dict(L=0.85, ry=0.2, rz=0.22, leg=0.42, lt=0.07, neck=(0.22, 0.9), head=(0.26, 0.14), snout=(0.14, 0.07),
                     ears="pointy", tail="low", feet="paw"),
    "cat":     dict(L=0.55, ry=0.12, rz=0.13, leg=0.26, lt=0.045, neck=(0.12, 0.9), head=(0.17, 0.1), snout=(0.05, 0.05),
                    ears="cat", tail="cat", feet="paw"),
    "kitten":  dict(L=0.34, ry=0.08, rz=0.09, leg=0.16, lt=0.035, neck=(0.06, 0.9), head=(0.14, 0.085), snout=(0.03, 0.04),
                    ears="cat", tail="cat", feet="paw"),
    "cow":     dict(L=2.1, ry=0.42, rz=0.55, leg=0.85, lt=0.13, neck=(0.45, 0.35), head=(0.55, 0.22), snout=(0.2, 0.17),
                    ears="cow", tail="rope", feet="hoof", horns="small"),
    "calf":    dict(L=1.1, ry=0.24, rz=0.3, leg=0.6, lt=0.08, neck=(0.25, 0.5), head=(0.32, 0.15), snout=(0.12, 0.11),
                    ears="cow", tail="rope", feet="hoof"),
    "horse":   dict(L=1.9, ry=0.33, rz=0.42, leg=1.0, lt=0.1, neck=(0.85, 0.95), head=(0.6, 0.17), snout=(0.15, 0.13),
                    ears="pointy", tail="horse", feet="hoof", mane=True),
    "foal":    dict(L=1.0, ry=0.18, rz=0.24, leg=0.8, lt=0.07, neck=(0.5, 0.95), head=(0.38, 0.11), snout=(0.1, 0.09),
                    ears="pointy", tail="horse", feet="hoof", mane=True),
    "donkey":  dict(L=1.3, ry=0.28, rz=0.34, leg=0.7, lt=0.09, neck=(0.5, 0.8), head=(0.48, 0.15), snout=(0.12, 0.12),
                    ears="donkey", tail="rope", feet="hoof", mane=True),
    "pig":     dict(L=1.2, ry=0.34, rz=0.36, leg=0.32, lt=0.08, neck=(0.08, 0.2), head=(0.32, 0.25), snout=(0.12, 0.12),
                    ears="pig", tail="curly", feet="hoof", disc=True),
    "piglet":  dict(L=0.55, ry=0.16, rz=0.17, leg=0.16, lt=0.045, neck=(0.04, 0.2), head=(0.18, 0.13), snout=(0.06, 0.07),
                    ears="pig", tail="curly", feet="hoof", disc=True),
    "sheep":   dict(L=1.1, ry=0.35, rz=0.38, leg=0.45, lt=0.06, neck=(0.2, 0.7), head=(0.3, 0.12), snout=(0.08, 0.08),
                    ears="sheep", tail="short", feet="hoof", wool=True),
    "lamb":    dict(L=0.6, ry=0.2, rz=0.21, leg=0.35, lt=0.045, neck=(0.12, 0.7), head=(0.2, 0.09), snout=(0.05, 0.06),
                    ears="sheep", tail="short", feet="hoof", wool=True),
    "goat":    dict(L=1.0, ry=0.22, rz=0.28, leg=0.55, lt=0.06, neck=(0.3, 0.8), head=(0.32, 0.11), snout=(0.1, 0.08),
                    ears="goat", tail="up", feet="hoof", horns="goat", beard=True),
}


COLOURS = {   # (main, belly, spots)
    "dog": ((196, 140, 80), (236, 214, 180), None), "puppy": ((230, 200, 150), (246, 236, 214), None),
    "dachshund": ((140, 74, 40), (176, 104, 60), None), "sheepdog": ((40, 36, 36), (240, 238, 232), None),
    "cat": ((236, 150, 70), (250, 230, 200), None), "kitten": ((150, 150, 156), (236, 236, 236), None),
    "cow": ((246, 244, 238), (246, 236, 230), ((36, 34, 36), 6)), "calf": ((150, 96, 60), (236, 220, 200), None),
    "horse": ((130, 80, 46), (150, 96, 60), None), "foal": ((176, 120, 76), (196, 146, 100), None),
    "donkey": ((140, 136, 132), (226, 222, 216), None), "pig": ((246, 180, 186), (250, 196, 200), None),
    "piglet": ((250, 196, 200), (252, 210, 214), None), "sheep": ((246, 244, 236), (246, 244, 236), None),
    "lamb": ((250, 250, 246), (250, 250, 246), None), "goat": ((236, 232, 222), (246, 244, 236), None),
}
FACE = {"sheep": (60, 54, 52), "lamb": (236, 226, 214)}


def quadruped(kind="dog", color=None, belly=None, seed=0, spots=None, gait=None, head_fn=None, tail_fn=None):
    """Build a four-legged animal. head_fn(t, dist, v) -> extra head pitch (e.g. grazing)."""
    P = dict(QUAD[kind])
    dc, db, ds = COLOURS[kind]
    c = col(color) if color else dc
    bc = col(belly) if belly else (db if not color else shade(c, 1.1))
    if spots is None and not color:
        spots = ds
    r = random.Random(seed)
    L, ry, rz, leg, lt = P["L"], P["ry"], P["rz"], P["leg"], P["lt"]
    m = Model(kind, L * 1.6, ry * 2.2, leg + rz * 2 + 0.3)
    b = m.body
    zc = leg + rz * 0.85
    hl = L / 2
    body_secs = [(-hl - rz * 0.35, ry * 0.25, rz * 0.3, zc + 0.02), (-hl, ry * 0.85, rz * 0.9, zc), (-hl * 0.3, ry, rz, zc),
                 (hl * 0.4, ry * 0.98, rz * 0.98, zc + 0.02), (hl, ry * 0.8, rz * 0.85, zc + 0.04),
                 (hl + rz * 0.3, ry * 0.3, rz * 0.35, zc + 0.08)]
    if P.get("wool"):     # a fluffy fleece: a cluster of puffy balls
        fleece = c
        loft(b, [(-hl - rz * 0.3, ry * 0.5, rz * 0.5, zc + 0.02), (-hl * 0.8, ry * 1.02, rz * 1.02, zc), (0, ry * 1.08, rz * 1.08, zc + 0.02),
                 (hl * 0.7, ry, rz, zc + 0.04), (hl + rz * 0.15, ry * 0.55, rz * 0.6, zc + 0.08)], fleece, n=12,
             colors=lambda s, i: shade(fleece, 0.97 + 0.04 * ((s + i) % 2)))
        for k in range(9):      # soft curls on the back and sides
            x = -hl * 0.75 + k / 8 * L * 0.85
            a = r.uniform(0.6, 2.5)
            sphere(b, (x, math.cos(a) * ry * 0.8, zc + math.sin(a) * rz * 0.8), rz * 0.42, shade(fleece, r.uniform(0.95, 1.03)), n=8)
    else:
        patch = set()
        if spots:      # coat patches (a cow's black-and-white pattern) painted on the body itself
            while len(patch) < spots[1] * 2:
                s0, i0 = r.randint(0, 4), r.choice((0, 1, 2, 3, 4, 5, 9))
                patch |= {(s0, i0), (s0, (i0 + 1) % 10)} if r.random() < 0.6 else {(s0, i0), (min(4, s0 + 1), i0)}
        loft(b, body_secs, c, n=10, colors=lambda s, i: spots[0] if (s, i) in patch else (bc if i in (6, 7, 8) else c))
    # ---- legs: upper parts hinge at the hips/shoulders, swinging with the distance walked
    stride = max(0.3, leg * 1.4)
    gait = gait or {"FL": 0.0, "BR": 0.0, "FR": math.pi, "BL": math.pi}
    hoof = (60, 52, 48) if P["feet"] == "hoof" else shade(c, 0.85)
    hip = zc - rz * 0.25
    leg_full = leg
    for name, x, y in (("FL", hl * 0.72, ry * 0.55), ("FR", hl * 0.72, -ry * 0.55), ("BL", -hl * 0.72, ry * 0.55),
                       ("BR", -hl * 0.72, -ry * 0.55)):
        leg = hip            # from the hip/shoulder joint right down to the ground
        lm = Mesh()
        top_z = 0.0
        thick = lt * (1.35 if name[0] == "B" else 1.15)
        loft(lm, [(0, thick, thick, top_z), (0.001, thick * 0.9, thick * 0.9, top_z)], c, n=6)  # cap
        cylinder(lm, (0, 0, -leg * 0.5 + 0.02), thick * 0.85, leg - 0.04, c, axis="z", n=7, r2=thick * 1.05)
        cylinder(lm, (0.01, 0, -leg + 0.04), lt * 0.95, 0.08, hoof, axis="z", n=7)
        ph = gait[name]

        def swing(t, dist, v, ph=ph, leg=leg):
            amp = min(0.5, v / max(0.2, leg) * 0.32)
            return amp * math.sin(2 * math.pi * dist / stride + ph)
        m.parts.append(Part(lm, (x, y, hip), "y", "fn", fn=swing))
    leg = leg_full
    m.body_shadow_parts = True
    # ---- neck and head on one hinge at the shoulders (so they can bob and lower to graze)
    hd = Mesh()
    nl, na = P["neck"]
    hlen, hr = P["head"]
    sl, sr = P["snout"]
    nx, nz = math.cos(na) * nl, math.sin(na) * nl
    loft(hd, [(0, rz * 0.55, rz * 0.6, 0), (nx * 0.5, rz * 0.45 + hr * 0.3, rz * 0.45 + hr * 0.3, nz * 0.5),
              (nx, hr * 0.85, hr * 0.85, nz)], c, n=8)
    hx, hz = nx + hlen * 0.35, nz + hr * 0.15
    loft(hd, [(nx - hr * 0.6, hr * 0.5, hr * 0.6, hz), (nx, hr, hr * 1.05, hz), (nx + hlen * 0.6, hr * 0.85, hr * 0.85, hz - hr * 0.1),
              (nx + hlen * 0.6 + sl, sr, sr * 0.95, hz - hr * 0.3), (nx + hlen * 0.6 + sl + 0.02, sr * 0.6, sr * 0.5, hz - hr * 0.3)],
         FACE.get(kind, c), n=9, colors=lambda s, i: (bc if s >= 2 and kind in ("cow", "calf", "horse", "foal", "goat", "donkey")
                                                      else FACE.get(kind, c)))
    tip = nx + hlen * 0.6 + sl
    if P.get("disc"):   # pig snout
        cylinder(hd, (tip + 0.02, 0, hz - hr * 0.3), sr * 0.95, 0.04, PINK, axis="x", n=10)
        for s in (-1, 1):
            box(hd, (tip + 0.045, s * sr * 0.35, hz - hr * 0.3), (0.01, sr * 0.2, sr * 0.3), (120, 60, 70))
    else:
        sphere(hd, (tip + 0.01, 0, hz - hr * 0.22), sr * 0.42, (40, 34, 36), n=6)          # nose
    for s in (-1, 1):
        _eye(hd, nx + hlen * 0.3, s * hr * 0.72, hz + hr * 0.3, r=max(0.018, hr * 0.14))
    ears = P["ears"]
    for s in (-1, 1):
        ex, ey, ez = nx + hlen * 0.05, s * hr * 0.62, hz + hr * 0.75
        if ears == "floppy":
            box(hd, (ex, s * hr * 0.95, hz + hr * 0.1), (hr * 0.6, hr * 0.12, hr * 1.1), shade(c, 0.75), R=R.rot_x(s * 0.25))
        elif ears in ("pointy", "cat"):
            k = 0.9 if ears == "cat" else 0.7
            cone(hd, (ex, ey * 0.9, ez - hr * 0.1), hr * 0.32 * k + 0.01, hr * 0.9 * k + 0.02, shade(c, 0.95), n=4)
        elif ears == "donkey":
            box(hd, (ex, ey, ez + hr * 0.6), (hr * 0.3, hr * 0.14, hr * 1.8), c, R=R.rot_x(s * 0.2))
        elif ears in ("cow", "sheep", "goat"):
            box(hd, (ex, s * hr * 1.2, hz + hr * 0.45), (hr * 0.35, hr * 0.8, hr * 0.12), shade(c, 0.9), R=R.rot_x(s * 0.35))
        elif ears == "pig":
            box(hd, (ex + hr * 0.2, s * hr * 0.55, ez), (hr * 0.5, hr * 0.4, hr * 0.06), shade(c, 0.95), R=R.rot_y(-0.6))
    if P.get("horns") == "small":
        for s in (-1, 1):
            cone(hd, (nx, s * hr * 0.55, hz + hr * 0.8), hr * 0.1, hr * 0.45, (236, 226, 200), n=5)
    elif P.get("horns") == "goat":
        for s in (-1, 1):
            box(hd, (nx - hr * 0.3, s * hr * 0.35, hz + hr * 1.1), (hr * 0.9, hr * 0.12, hr * 0.12), (170, 150, 120), R=R.rot_y(0.7))
    if P.get("beard"):
        cone(hd, (tip - sl * 0.6, 0, hz - hr * 0.95), hr * 0.18, -hr * 0.6, (236, 230, 216), n=5)
    if P.get("mane"):
        for k in range(6):
            u = k / 5
            box(hd, (nx * u - 0.04, 0, nz * u + rz * 0.5 + hr * 0.2), (0.14, 0.06, 0.2), shade(c, 0.5), R=R.rot_y(-na * 0.8))
    bob_k = 2.0 * math.pi / stride * 2

    def head(t, dist, v):
        extra = head_fn(t, dist, v) if head_fn else 0.0
        return 0.04 * math.sin(dist * bob_k) * min(1.0, v) + extra
    m.parts.append(Part(hd, (hl + rz * 0.1, 0, zc + rz * 0.35), "y", "fn", fn=head))
    # ---- tail
    tl = Mesh()
    tail = P["tail"]
    if tail in ("up", "cat"):
        tlen = L * (0.45 if tail == "up" else 0.8)
        pts, rad = [], []
        for i in range(8):
            u = i / 7
            a = 0.5 + u * (1.4 if tail == "up" else 1.1)       # sweeps back, then curves up
            pts.append((-math.cos(a) * tlen * u * 0.7 - 0.02, 0, math.sin(a) * tlen * u * 0.8))
            rad.append(lt * (0.5 - 0.25 * u) if tail == "up" else lt * 0.45)
        tube(tl, pts, rad, c, n=6)
    elif tail in ("rope", "low", "straight", "horse"):
        ln = L * (0.45 if tail != "straight" else 0.35)
        tc = (40, 34, 30) if tail == "horse" else shade(c, 0.6)
        k = 1.0 if tail == "straight" else 0.0
        pts = [(-0.02 - ln * (0.25 + 0.6 * k) * u, 0, -ln * (1 - k) * u * 0.95 + ln * 0.08 * math.sin(u * 3)) for u in (0, .25, .5, .75, 1)]
        tube(tl, pts, [lt * 0.32, lt * 0.28, lt * 0.24, lt * 0.2, lt * 0.16], c, n=6, cap=False)
        if tail != "straight":
            bush = lt * (1.1 if tail == "horse" else 0.5)
            tube(tl, [pts[2 if tail == "horse" else 3], pts[4], (pts[4][0] - 0.03, 0, pts[4][2] - ln * 0.25)],
                 [bush * 0.6, bush, 0.01], tc, n=6)
    elif tail == "curly":
        for k in range(8):
            a = k / 7 * 2 * math.pi
            sphere(tl, (-0.04 - 0.03 * math.cos(a), 0, 0.03 * math.sin(a)), lt * 0.35, PINK if kind in ("pig", "piglet") else c, n=5)
    else:
        sphere(tl, (-0.02, 0, 0), lt * 0.9, c, n=6)
    wag_speed = {"dog": 9.0, "puppy": 11.0, "sheepdog": 7.0, "cat": 1.4, "kitten": 2.0}.get(kind, 1.2)
    wag_amp = {"dog": 0.5, "puppy": 0.6, "sheepdog": 0.4, "cat": 0.35, "kitten": 0.4}.get(kind, 0.25)

    def wag(t, dist, v, ph=r.uniform(0, 6)):
        if tail_fn:
            return tail_fn(t, dist, v)
        return wag_amp * math.sin(t * wag_speed + ph)
    m.parts.append(Part(tl, (-hl - rz * 0.25, 0, zc + rz * 0.4), "z", "fn", fn=wag))
    m.horn = np.array([hl + nx + hlen, 0, zc + nz])
    m.eye = np.array([hl + nx + hlen * 0.4, 0, zc + nz + hr])
    return m


# ================================================================== birds

BIRDS = {
    # length, body r, wing span, colour, belly, beak colour, legs, neck, tail
    "songbird": dict(L=0.16, r=0.045, span=0.26, c=(220, 90, 60), belly=(250, 200, 150), beak=(250, 190, 60), legs=0.04, neck=0.0),
    "bluebird": dict(L=0.17, r=0.045, span=0.28, c=(60, 120, 220), belly=(250, 170, 110), beak=(60, 60, 60), legs=0.04, neck=0.0),
    "duck":     dict(L=0.55, r=0.14, span=0.9, c=(120, 100, 80), belly=(200, 180, 160), beak=(250, 180, 50), legs=0.08, neck=0.12,
                     head_c=(40, 110, 70)),
    "swan":     dict(L=1.3, r=0.25, span=2.2, c=(246, 246, 242), belly=(240, 240, 236), beak=(240, 120, 40), legs=0.1, neck=0.55),
    "parrot":   dict(L=0.4, r=0.075, span=0.6, c=(220, 40, 40), belly=(250, 200, 40), beak=(240, 230, 210), legs=0.05, neck=0.02,
                     wing_c=(40, 110, 220), long_tail=True),
    "flamingo": dict(L=0.8, r=0.16, span=1.4, c=(246, 140, 160), belly=(250, 170, 180), beak=(40, 30, 30), legs=0.85, neck=0.6),
    "eagle":    dict(L=0.9, r=0.15, span=2.1, c=(100, 70, 46), belly=(120, 86, 56), beak=(250, 200, 50), legs=0.12, neck=0.04,
                     head_c=(246, 246, 240)),
    "seagull":  dict(L=0.55, r=0.1, span=1.3, c=(236, 238, 240), belly=(246, 246, 246), beak=(250, 200, 50), legs=0.08, neck=0.03,
                     wing_c=(170, 176, 186)),
    "owl":      dict(L=0.45, r=0.15, span=1.0, c=(150, 116, 80), belly=(220, 196, 160), beak=(90, 80, 70), legs=0.06, neck=0.0,
                     owl=True),
    "pigeon":   dict(L=0.32, r=0.08, span=0.6, c=(150, 156, 170), belly=(170, 176, 190), beak=(60, 60, 60), legs=0.05, neck=0.03,
                     head_c=(110, 130, 140)),
    "hen":      dict(L=0.45, r=0.15, span=0.6, c=(176, 110, 60), belly=(196, 130, 76), beak=(250, 190, 60), legs=0.14, neck=0.08,
                     comb=True),
    "rooster":  dict(L=0.55, r=0.17, span=0.7, c=(196, 70, 40), belly=(60, 70, 60), beak=(250, 190, 60), legs=0.18, neck=0.12,
                     comb=True, long_tail=True, wing_c=(160, 90, 40)),
    "chick":    dict(L=0.12, r=0.055, span=0.12, c=(250, 220, 90), belly=(250, 230, 120), beak=(250, 160, 40), legs=0.04, neck=0.0),
    "penguin":  dict(L=0.6, r=0.18, span=0.5, c=(30, 32, 40), belly=(246, 246, 242), beak=(250, 150, 40), legs=0.04, neck=0.0,
                     upright=True),
}


def bird(kind="songbird", seed=0, flap=None, glide=False, perched=False):
    """flap(t) -> 0..1 how hard the wings beat (0 = folded). Upright birds (penguins) waddle."""
    P = BIRDS[kind]
    L, r, span = P["L"], P["r"], P["span"]
    c, belly = P["c"], P["belly"]
    up = P.get("upright")
    folded = (perched or (flap is None and not glide)) and not up
    m = Model(kind, L * 1.3, span if not folded else r * 2.4, P["legs"] + r * 2.5 + P["neck"])
    b = m.body
    zc = P["legs"] + r * (1.0 if not up else 2.2)
    if up:   # penguin: standing body
        loft(b, [(0, 0.01, 0.01, zc - r * 2.2), (0, r * 0.9, r * 0.95, zc - r * 1.6)], c, n=8)
        for k, (zz, rr) in enumerate([(-1.6, 0.95), (-0.6, 1.05), (0.4, 0.95), (1.2, 0.7), (1.7, 0.4)]):
            pass
        sphere(b, (0, 0, zc - r * 0.3), r * 1.05, c, n=10, scale=(1, 0.95, 1.9))
        sphere(b, (r * 0.35, 0, zc - r * 0.35), r * 0.85, belly, n=10, scale=(0.75, 0.85, 1.7))
        sphere(b, (0.02, 0, zc + r * 1.75), r * 0.62, c, n=8)
        cone(b, (r * 0.55, 0, zc + r * 1.65), r * 0.12, r * 0.0 + 0.001, P["beak"], n=4)
        box(b, (r * 0.75, 0, zc + r * 1.62), (r * 0.5, r * 0.12, r * 0.1), P["beak"])
        for s in (-1, 1):
            _eye(b, r * 0.45, s * r * 0.35, zc + r * 1.9, r=r * 0.08)
            box(b, (r * 0.2, s * r * 0.35, P["legs"] * 0.5), (r * 0.5, r * 0.25, 0.03), (250, 150, 40))
    else:
        loft(b, [(-L * 0.5, r * 0.15, r * 0.15, zc + r * 0.2), (-L * 0.25, r * 0.85, r * 0.85, zc + r * 0.05), (L * 0.1, r, r, zc),
                 (L * 0.3, r * 0.75, r * 0.8, zc + r * 0.2)], c, n=10, colors=lambda s, i: belly if i in (6, 7, 8) else c)
        nk = P["neck"]
        hx, hz = L * 0.3 + nk * 0.5, zc + r * 0.5 + nk
        if nk > 0.05:
            loft(b, [(L * 0.25, r * 0.45, r * 0.45, zc + r * 0.3), (L * 0.3 + nk * 0.3, r * 0.25, r * 0.25, zc + r * 0.4 + nk * 0.6),
                     (hx, r * 0.25, r * 0.25, hz)], c, n=7)
        hc = P.get("head_c", c)
        hr = r * (0.55 if kind not in ("owl", "chick", "songbird", "bluebird") else 0.8)
        sphere(b, (hx, 0, hz), hr, hc, n=8)
        bl = hr * (1.6 if kind in ("duck", "swan", "flamingo") else 0.9)
        if kind == "duck":
            loft(b, [(hx + hr * 0.6, hr * 0.42, hr * 0.2, hz - hr * 0.2), (hx + hr + bl * 0.5, hr * 0.42, hr * 0.13, hz - hr * 0.3),
                     (hx + hr + bl * 0.75, hr * 0.32, hr * 0.08, hz - hr * 0.32)], P["beak"], n=8)
        elif kind == "flamingo":
            loft(b, [(hx + hr * 0.6, hr * 0.3, hr * 0.35, hz), (hx + hr + bl * 0.5, hr * 0.2, hr * 0.25, hz - hr * 0.2),
                     (hx + hr + bl * 0.8, hr * 0.1, hr * 0.1, hz - hr * 0.6)], P["beak"], n=6)
        else:
            cone_m = Mesh()
            cone(cone_m, (0, 0, 0), hr * 0.32, bl, P["beak"], n=5)
            b.extend(cone_m, R=R.rot_y(math.pi / 2), t=(hx + hr * 0.8, 0, hz - hr * 0.15))
        for s in (-1, 1):
            _eye(b, hx + hr * 0.5, s * hr * 0.7, hz + hr * 0.25, r=max(0.008, hr * (0.22 if kind == "owl" else 0.14)))
        if P.get("comb"):
            for k in range(3):
                sphere(b, (hx - hr * 0.2 + k * hr * 0.35, 0, hz + hr * (0.9 + 0.1 * (k == 1))), hr * 0.3, (220, 40, 40), n=6)
            sphere(b, (hx + hr * 0.8, 0, hz - hr * 0.7), hr * 0.25, (220, 40, 40), n=6)
        tail_c = P.get("wing_c", c)
        if P.get("long_tail"):
            for k in range(3):
                box(b, (-L * 0.65 - k * 0.02, (k - 1) * r * 0.2, zc + r * 0.1 - k * 0.02), (L * 0.6, r * 0.25, 0.012), tail_c,
                    R=R.rot_y(0.3 + 0.1 * k))
        else:
            box(b, (-L * 0.55, 0, zc + r * 0.25), (L * 0.3, r * 0.9, 0.012), tail_c, R=R.rot_y(0.15))
        if True:
            for s in (-1, 1):
                cylinder(b, (0, s * r * 0.35, P["legs"] / 2 + 0.005), max(0.006, r * 0.08), P["legs"], P["beak"] if kind != "flamingo"
                         else (240, 140, 160), axis="z", n=5)
    # wings hinged at the shoulders (or folded neatly along the body when the bird is resting)
    wc = P.get("wing_c", shade(c, 0.9))
    for s in ((-1, 1) if not folded else ()):
        wm = Mesh()
        semi = span / 2
        pts = [(L * 0.15, 0), (-L * 0.25, 0), (-L * 0.3, s * semi * 0.95), (-L * 0.05, s * semi), (L * 0.1, s * semi * 0.7)]
        top = [(x, y, 0.01) for x, y in pts]
        bot = [(x, y, -0.01) for x, y in pts]
        if s < 0:
            top, bot = top[::-1], bot[::-1]
        wm.poly(top, wc, flags=2)
        wm.poly(bot[::-1], shade(wc, 0.8), flags=2)
        base_flap = flap or (lambda t: 0.0)
        ph = random.Random(seed).uniform(0, 6)
        rate = 3.0 if span > 1.5 else (6.0 if span > 0.5 else 14.0)

        def wing(t, dist, v, s=s, ph=ph, rate=rate):
            k = base_flap(t)
            if glide:
                return s * (0.08 + 0.05 * math.sin(t * 0.7 + ph))
            if k <= 0.01:     # folded along the body
                return s * -1.35 if not up else s * -0.25
            return s * (0.15 + 0.75 * k * math.sin(t * rate * 2 * math.pi / 2 + ph))
        y0 = s * r * (0.7 if not up else 1.0)
        m.parts.append(Part(wm, (L * 0.0, y0, zc + r * (0.55 if not up else 0.4)), "x", "fn", fn=wing))
    if folded:
        for s in (-1, 1):
            sphere(b, (-L * 0.12, s * r * 0.8, zc + r * 0.2), r, wc, n=8, scale=(L * 0.42 / r, 0.28, 0.62))
            box(b, (-L * 0.42, s * r * 0.45, zc + r * 0.25), (L * 0.22, r * 0.22, 0.02), shade(wc, 0.8), R=R.rot_y(0.15))
    m.horn = np.array([L * 0.4, 0, zc + r])
    m.zc = zc
    return m


# ================================================================== fish and sea animals

def fish(kind="clownfish", seed=0, size=1.0):
    r = random.Random(seed)
    spec = {
        "clownfish": ((240, 120, 30), "bands", 0.12),
        "bluetang": ((40, 90, 210), "tang", 0.2),
        "yellowtang": ((250, 210, 40), None, 0.18),
        "goldfish": ((250, 140, 40), None, 0.15),
        "angelfish": ((240, 220, 120), "stripes", 0.2),
        "small": ((150, 190, 220), None, 0.08),
        "puffer": ((230, 200, 120), "spots", 0.2),
    }[kind]
    c, pat, L = spec
    L *= size
    m = Model(kind, L, L * 0.4, L * 0.6)
    b = m.body
    tall = 0.55 if kind in ("bluetang", "yellowtang", "angelfish") else 0.32
    if kind == "puffer":
        tall = 0.45
    secs = [(L * 0.5, 0.01, 0.01, 0), (L * 0.42, L * 0.08, L * tall * 0.5, 0), (L * 0.1, L * 0.12, L * tall, 0),
            (-L * 0.25, L * 0.09, L * tall * 0.75, 0), (-L * 0.42, L * 0.03, L * tall * 0.2, 0)]

    def colors(s, i):
        if pat == "bands" and s in (1, 3):
            return WHITE
        if pat == "tang" and i in (2, 3):
            return (20, 30, 60)
        if pat == "stripes" and s == 2:
            return (40, 40, 50)
        return c
    loft(b, secs, c, n=10, colors=colors)
    for s in (-1, 1):
        _eye(b, L * 0.33, s * L * 0.07, L * tall * 0.15, r=L * 0.045)
    b.poly([(L * 0.15, 0, L * tall * 0.95), (-L * 0.3, 0, L * tall * 0.6), (-L * 0.1, 0, L * tall * 1.35)], shade(c, 0.9), flags=2)  # dorsal
    b.poly([(L * 0.0, 0, -L * tall * 0.9), (-L * 0.3, 0, -L * tall * 0.55), (-L * 0.15, 0, -L * tall * 1.2)], shade(c, 0.9), flags=2)
    tm = Mesh()
    tm.poly([(0, 0, 0), (-L * 0.32, 0, L * 0.25), (-L * 0.26, 0, 0), (-L * 0.32, 0, -L * 0.25)], shade(c, 0.95), flags=2)
    ph = r.uniform(0, 6)
    m.parts.append(Part(tm, (-L * 0.4, 0, 0), "z", "fn", fn=lambda t, d, v, ph=ph: 0.45 * math.sin(t * (6 + v * 3) + ph)))
    for s in (-1, 1):
        fm = Mesh()
        fm.poly([(0, 0, 0), (-L * 0.12, s * L * 0.12, -L * 0.04), (-L * 0.1, s * L * 0.02, -L * 0.08)], shade(c, 1.1), flags=2)
        m.parts.append(Part(fm, (L * 0.2, s * L * 0.1, -L * 0.05), "x", "fn", fn=lambda t, d, v, s=s, ph=ph: s * 0.4 * math.sin(t * 5 + ph)))
    m.horn = np.array([L * 0.5, 0, 0])
    return m


def dolphin(seed=0, whale=False):
    L = 13.0 if whale else 2.5
    c = (70, 80, 110) if whale else (120, 136, 156)
    belly = (200, 206, 214) if not whale else (210, 214, 220)
    m = Model("whale" if whale else "dolphin", L, L * 0.3, L * 0.25)
    b = m.body
    secs = ([(L * 0.5, 0.05, 0.05, -0.02 * L), (L * 0.42, L * 0.07, L * 0.06, -0.01 * L), (L * 0.3, L * 0.11, L * 0.11, 0),
             (0, L * 0.12, L * 0.12, 0), (-L * 0.3, L * 0.06, L * 0.07, 0), (-L * 0.45, L * 0.02, L * 0.025, 0)] if not whale else
            [(L * 0.5, L * 0.08, L * 0.07, -0.02 * L), (L * 0.35, L * 0.13, L * 0.12, 0), (0, L * 0.12, L * 0.11, 0),
             (-L * 0.3, L * 0.06, L * 0.06, 0), (-L * 0.45, L * 0.02, L * 0.02, 0)])
    loft(b, secs, c, n=12, colors=lambda s, i: belly if i in (8, 9, 10) else c)
    for s in (-1, 1):
        _eye(b, L * 0.33, s * L * 0.09, L * 0.01, r=L * 0.012, white=False)
        b.poly([(L * 0.2, s * L * 0.1, -L * 0.04), (L * 0.05, s * L * 0.28, -L * 0.1), (L * 0.1, s * L * 0.1, -L * 0.07)], c, flags=2)
    if not whale:
        b.poly([(L * 0.02, 0, L * 0.11), (-L * 0.16, 0, L * 0.12), (-L * 0.12, 0, L * 0.24)], c, flags=2)    # dorsal fin
    tm = Mesh()
    tm.poly([(0, 0, 0), (-L * 0.1, L * 0.14, 0.0), (-L * 0.06, 0, 0), (-L * 0.1, -L * 0.14, 0)], c, flags=2)    # flukes
    m.parts.append(Part(tm, (-L * 0.44, 0, 0), "y", "fn", fn=lambda t, d, v: 0.4 * math.sin(t * (2.5 if not whale else 1.0))))
    m.horn = np.array([L * 0.45, 0, 0])
    return m


def turtle(seed=0):
    m = Model("turtle", 1.0, 0.8, 0.35)
    b = m.body
    sphere(b, (0, 0, 0.0), 0.45, (110, 130, 70), n=10, scale=(1.1, 0.95, 0.38))
    sphere(b, (0, 0, -0.04), 0.42, (220, 210, 150), n=10, scale=(1.05, 0.9, 0.2))
    for k in range(7):
        a = k / 7 * 2 * math.pi
        sphere(b, (0.25 * math.cos(a), 0.22 * math.sin(a), 0.13), 0.1, (90, 110, 60), n=6, scale=(1, 1, 0.4))
    sphere(b, (0.6, 0, 0.02), 0.12, (150, 160, 100), n=8, scale=(1.3, 1, 0.9))
    for s in (-1, 1):
        _eye(b, 0.7, s * 0.07, 0.07, r=0.02, white=False)
        fm = Mesh()
        fm.poly([(0, 0, 0), (-0.05, s * 0.45, 0), (-0.25, s * 0.3, 0)], (150, 160, 100), flags=2)
        m.parts.append(Part(fm, (0.2, s * 0.35, 0), "x", "fn", fn=lambda t, d, v, s=s: s * 0.5 * math.sin(t * 1.6)))
        bm = Mesh()
        bm.poly([(0, 0, 0), (-0.25, s * 0.18, 0), (-0.15, s * 0.05, 0)], (150, 160, 100), flags=2)
        m.parts.append(Part(bm, (-0.35, s * 0.25, 0), "x", "fn", fn=lambda t, d, v, s=s: s * 0.3 * math.sin(t * 1.6 + 1)))
    m.horn = np.array([0.6, 0, 0])
    return m


def jellyfish(seed=0, color=(240, 170, 220)):
    m = Model("jellyfish", 0.5, 0.5, 0.8)
    b = m.body
    sphere(b, (0, 0, 0), 0.25, color, n=10, scale=(1, 1, 0.7), flags=1)
    for k in range(8):
        a = k / 8 * 2 * math.pi
        tm = Mesh()
        tm.poly([(0, 0, 0), (0.02, 0.0, -0.6), (-0.02, 0, -0.6)], shade(color, 0.9), flags=3)
        m.parts.append(Part(tm, (0.18 * math.cos(a), 0.18 * math.sin(a), -0.05), "x", "fn",
                            fn=lambda t, d, v, k=k: 0.3 * math.sin(t * 1.5 + k)))
    m.horn = np.array([0, 0, 0])
    return m


def seahorse(seed=0, color=(250, 170, 60)):
    m = Model("seahorse", 0.2, 0.08, 0.3)
    b = m.body
    loft(b, [(0, 0.02, 0.02, -0.12), (0.005, 0.035, 0.035, -0.05), (0.01, 0.045, 0.045, 0.03), (0.02, 0.03, 0.03, 0.09)], color, n=8)
    sphere(b, (0.03, 0, 0.12), 0.035, color, n=7)
    box(b, (0.08, 0, 0.11), (0.06, 0.015, 0.015), color)
    for s in (-1, 1):
        _eye(b, 0.04, s * 0.025, 0.13, r=0.007, white=False)
    return m


def crab(seed=0):
    m = Model("crab", 0.3, 0.4, 0.15)
    b = m.body
    sphere(b, (0, 0, 0.08), 0.12, (220, 80, 50), n=8, scale=(0.8, 1.2, 0.45))
    for s in (-1, 1):
        sphere(b, (0.1, s * 0.16, 0.1), 0.045, (230, 90, 60), n=6)
        _eye(b, 0.09, s * 0.04, 0.16, r=0.012)
        for k in range(3):
            lm = Mesh()
            box(lm, (0, s * 0.08, -0.02), (0.02, 0.16, 0.02), (200, 70, 46), outward=False)
            m.parts.append(Part(lm, (-0.04 + k * 0.05, s * 0.1, 0.06), "x", "fn",
                                fn=lambda t, d, v, s=s, k=k: s * (0.4 + 0.2 * math.sin(d * 12 + k * 2))))
    return m


REGISTRY = {"quadruped": quadruped, "bird": bird, "fish": fish, "dolphin": dolphin, "turtle": turtle, "jellyfish": jellyfish,
            "seahorse": seahorse, "crab": crab}
