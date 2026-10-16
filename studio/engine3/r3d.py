"""A small software 3D renderer for engine 3 (no GPU, no external 3D libraries).

Low-poly meshes built from boxes, cylinders, cones, spheres and extruded side profiles; a perspective
camera that can sit anywhere (side, front, behind, above, in the driver's seat); a warm sun with soft
sky light, soft ground shadows, distance haze, and 2x supersampled anti-aliasing. Faces are painted
back to front (painter's algorithm), so models are kept as simple convex-ish parts.

World axes: x east, y north, z up (metres). Vehicle models: x forward, y left, z up, origin on the
ground under the middle of the vehicle.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1920, 1080
SS = 2  # supersampling


# ------------------------------------------------------------------ math helpers

def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ypr(yaw=0.0, pitch=0.0, roll=0.0):
    """Heading (about z), nose-up pitch (about -y), roll (about x)."""
    return rot_z(yaw) @ rot_y(-pitch) @ rot_x(roll)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


# ------------------------------------------------------------------ meshes

class Mesh:
    """Vertices + polygon faces, one colour per face.
    flags: 1 = emissive (unlit), 2 = two-sided, 4 = decal (painted after the surface it sits on)."""

    def __init__(self):
        self.v = []
        self.f = []
        self.c = []
        self.fl = []
        self._done = False

    def poly(self, pts, color, flags=0):
        i0 = len(self.v)
        self.v.extend([tuple(map(float, p)) for p in pts])
        self.f.append(tuple(range(i0, i0 + len(pts))))
        self.c.append(tuple(color))
        self.fl.append(flags)
        self._done = False
        return self

    def extend(self, other, R=None, t=(0, 0, 0)):
        R = np.eye(3) if R is None else R
        o = np.asarray(other.v, float) @ R.T + np.asarray(t, float)
        i0 = len(self.v)
        self.v.extend(map(tuple, o))
        self.f.extend(tuple(i + i0 for i in f) for f in other.f)
        self.c.extend(other.c)
        self.fl.extend(other.fl)
        self._done = False
        return self

    def finalize(self):
        if self._done:
            return self
        self.V = np.asarray(self.v, float)
        n = len(self.f)
        N = np.zeros((n, 3))
        Cn = np.zeros((n, 3))
        for k, f in enumerate(self.f):
            P = self.V[list(f)]
            Cn[k] = P.mean(axis=0)
            nx = ny = nz = 0.0
            for i in range(len(f)):   # Newell's method: robust for any planar polygon
                a, b = P[i], P[(i + 1) % len(f)]
                nx += (a[1] - b[1]) * (a[2] + b[2])
                ny += (a[2] - b[2]) * (a[0] + b[0])
                nz += (a[0] - b[0]) * (a[1] + b[1])
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            N[k] = (nx / ln, ny / ln, nz / ln)
        self.N, self.Cn = N, Cn
        self.C = np.asarray(self.c, float)
        self.FL = np.asarray(self.fl, int)
        self.radius = float(np.sqrt(((self.V - self.V.mean(axis=0)) ** 2).sum(axis=1)).max()) if n else 0.0
        self.center = self.V.mean(axis=0) if n else np.zeros(3)
        self._done = True
        return self


# ------------------------------------------------------------------ primitives (all add to a Mesh)

def box(m, c, size, color, R=None, top=None, flags=0, outward=False, decal=True):
    """Axis box centred at c with size (sx, sy, sz); optional rotation R about its centre.
    Thin boxes are decals (windows, stripes, lights). With outward=True (vehicle models, built around their own
    origin) a decal keeps only its outside face, so it never blocks the view from inside a cab."""
    if decal and min(size) <= 0.05:
        flags |= 4
    sx, sy, sz = (s / 2 for s in size)
    P = np.array([[-sx, -sy, -sz], [sx, -sy, -sz], [sx, sy, -sz], [-sx, sy, -sz],
                  [-sx, -sy, sz], [sx, -sy, sz], [sx, sy, sz], [-sx, sy, sz]])
    if R is not None:
        P = P @ R.T
    P = P + np.asarray(c, float)
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    keep = list(range(6))
    if outward and flags & 4:
        ax = int(np.argmin(size))
        local = [(2, -1), (2, 1), (1, -1), (0, 1), (1, 1), (0, -1)]     # (axis, sign) of each face's normal
        cand = [k for k in range(6) if local[k][0] == ax]
        Rm = np.eye(3) if R is None else R
        cen = np.asarray(c, float)
        ref = np.array([cen[0], cen[1], max(0.0, cen[2] - 1.0)])
        best = max(cand, key=lambda k: np.dot(Rm[:, ax] * local[k][1], ref))
        keep = [best]
    for k in keep:
        f = faces[k]
        col = top if (k == 1 and top is not None) else color
        m.poly([P[i] for i in f], col, flags)
    return m


def extrude(m, profile, y0, y1, color, side=None, cap=None, flags=0):
    """Extrude a side profile [(x, z), ...] (counter-clockwise seen from +y... any order) across y0..y1."""
    pts = list(profile)
    # make the profile counter-clockwise in (x, z) so caps face outwards
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if area < 0:
        pts = pts[::-1]
    capc = cap or color
    m.poly([(x, y0, z) for x, z in pts], capc, flags)                 # faces -y
    m.poly([(x, y1, z) for x, z in reversed(pts)], capc, flags)       # faces +y
    n = len(pts)
    for i in range(n):
        (xa, za), (xb, zb) = pts[i], pts[(i + 1) % n]
        col = side(i) if callable(side) else (side or color)
        m.poly([(xa, y0, za), (xa, y1, za), (xb, y1, zb), (xb, y0, zb)], col, flags)
    return m


def cylinder(m, c, r, length, color, axis="y", n=12, cap=None, r2=None, flags=0):
    """Cylinder (or frustum with r2) centred at c along an axis."""
    r2 = r if r2 is None else r2
    c = np.asarray(c, float)
    ring0, ring1 = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        u, v = math.cos(a), math.sin(a)
        if axis == "x":
            ring0.append(c + (-length / 2, u * r, v * r))
            ring1.append(c + (length / 2, u * r2, v * r2))
        elif axis == "y":
            ring0.append(c + (u * r, -length / 2, v * r))
            ring1.append(c + (u * r2, length / 2, v * r2))
        else:
            ring0.append(c + (u * r, v * r, -length / 2))
            ring1.append(c + (u * r2, v * r2, length / 2))
    for i in range(n):
        j = (i + 1) % n
        m.poly([ring0[i], ring0[j], ring1[j], ring1[i]], color, flags)
    capc = cap or color
    m.poly(ring0[::-1], capc, flags)
    m.poly(ring1, capc, flags)
    # make all faces point outwards (orientation depends on axis handedness)
    return _fix_outwards(m, c, len(ring0) + 2)


def _fix_outwards(m, c, count):
    """Flip the last `count` faces so their normals point away from point c."""
    V = m.v
    for k in range(len(m.f) - count, len(m.f)):
        f = m.f[k]
        P = np.array([V[i] for i in f])
        cen = P.mean(axis=0)
        n = np.cross(P[1] - P[0], P[2] - P[0])
        if np.linalg.norm(n) < 1e-12 and len(P) > 3:
            n = np.cross(P[2] - P[0], P[3] - P[0])
        if np.dot(n, cen - c) < 0:
            m.f[k] = tuple(reversed(f))
    m._done = False
    return m


def cone(m, base, r, h, color, n=10, flags=0):
    base = np.asarray(base, float)
    apex = base + (0, 0, h)
    ring = [base + (r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), 0) for i in range(n)]
    for i in range(n):
        m.poly([ring[i], ring[(i + 1) % n], apex], color, flags)
    m.poly(ring[::-1], color, flags)
    return _fix_outwards(m, base + (0, 0, h / 3), n + 1)


def sphere(m, c, r, color, n=8, scale=(1, 1, 1), flags=0):
    c = np.asarray(c, float)
    sx, sy, sz = scale
    rows = max(3, n // 2)
    pts = []
    for i in range(rows + 1):
        th = math.pi * i / rows
        pts.append([c + (r * sx * math.sin(th) * math.cos(2 * math.pi * j / n),
                         r * sy * math.sin(th) * math.sin(2 * math.pi * j / n),
                         r * sz * math.cos(th)) for j in range(n)])
    count = 0
    for i in range(rows):
        for j in range(n):
            a, b = pts[i][j], pts[i][(j + 1) % n]
            cc, d = pts[i + 1][(j + 1) % n], pts[i + 1][j]
            if i == 0:
                m.poly([a, d, cc], color, flags)
            elif i == rows - 1:
                m.poly([a, b, d], color, flags)
            else:
                m.poly([a, b, cc, d], color, flags)
            count += 1
    return _fix_outwards(m, c, count)


def wedge_wing(m, root_x, root_len, tip_x, tip_len, span, z, thick, color, y0=0.0, dihedral=0.0, side=1, tip_z=None):
    """A wing panel: a thin slab from the root (at y0) to the tip (at y0 + side*span). x = leading edge."""
    zt = z + span * math.tan(dihedral) if tip_z is None else tip_z
    y1 = y0 + side * span
    a = (root_x, y0, z)
    b = (root_x - root_len, y0, z)
    c = (tip_x - tip_len, y1, zt)
    d = (tip_x, y1, zt)
    t = thick / 2
    top = [(p[0], p[1], p[2] + t) for p in (a, b, c, d)]
    bot = [(p[0], p[1], p[2] - t * 0.6) for p in (a, b, c, d)]
    k0 = len(m.f)
    m.poly(top, color)
    m.poly(bot[::-1], color)
    for i in range(4):
        j = (i + 1) % 4
        m.poly([top[i], bot[i], bot[j], top[j]], color)
    cen = np.mean(np.array(top + bot), axis=0)
    return _fix_outwards(m, cen, len(m.f) - k0)


# ------------------------------------------------------------------ camera

class Camera:
    def __init__(self, pos, target=None, fov=50.0, yaw=None, pitch=0.0, roll=0.0):
        self.pos = np.asarray(pos, float)
        self.fov = fov
        if target is not None:
            d = np.asarray(target, float) - self.pos
            yaw = math.atan2(d[1], d[0])
            pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
        self.yaw, self.pitch, self.roll = yaw or 0.0, pitch, roll
        cy, sy, cp, sp = math.cos(self.yaw), math.sin(self.yaw), math.cos(self.pitch), math.sin(self.pitch)
        fwd = np.array([cy * cp, sy * cp, sp])
        right = np.array([sy, -cy, 0.0])
        if abs(cp) < 1e-6:   # looking straight down/up: pick right from yaw anyway
            right = np.array([sy, -cy, 0.0])
        up = np.cross(right, fwd)
        if roll:
            cr, sr = math.cos(roll), math.sin(roll)
            right, up = right * cr + up * sr, up * cr - right * sr
        self.B = np.stack([right, up, fwd])
        self.f = (W * SS / 2) / math.tan(math.radians(fov) / 2)
        self.fwd = fwd

    def to_cam(self, P):
        return (np.asarray(P, float) - self.pos) @ self.B.T

    def project(self, Pc):
        z = np.maximum(Pc[..., 2], 1e-4)
        return np.stack([W * SS / 2 + self.f * Pc[..., 0] / z, H * SS / 2 - self.f * Pc[..., 1] / z], axis=-1)

    def screen(self, P):
        """World point -> (x, y) in final 1920x1080 pixels, and depth."""
        pc = self.to_cam(np.asarray(P, float)[None])[0]
        if pc[2] <= 0.05:
            return None
        s = self.project(pc[None])[0] / SS
        return float(s[0]), float(s[1]), float(pc[2])


# ------------------------------------------------------------------ objects and lighting

class Obj:
    """A mesh placed in the world. layer 0 = ground (drawn first), 1 = things on the ground."""

    def __init__(self, mesh, pos=(0, 0, 0), R=None, layer=1, shadow=True, name="", order=0):
        self.mesh = mesh.finalize()
        self.pos = np.asarray(pos, float)
        self.R = np.eye(3) if R is None else R
        self.layer = layer
        self.order = order      # ground objects are painted in this order (terrain, roads, markings...)
        self.shadow = shadow
        self.name = name
        self.visible = True


class Light:
    def __init__(self, sun_dir=(-0.5, 0.35, -0.8), sun=(1.0, 0.96, 0.88), sky=(0.55, 0.62, 0.72), amb=0.42, dif=0.72):
        d = np.asarray(sun_dir, float)
        self.dir = d / np.linalg.norm(d)          # direction the light travels
        self.to_sun = -self.dir
        self.sun = np.asarray(sun)
        self.sky = np.asarray(sky)
        self.amb, self.dif = amb, dif


def _clip_near(Pc, near=0.12):
    out = []
    n = len(Pc)
    for i in range(n):
        a, b = Pc[i], Pc[(i + 1) % n]
        ina, inb = a[2] >= near, b[2] >= near
        if ina:
            out.append(a)
        if ina != inb:
            t = (near - a[2]) / (b[2] - a[2])
            out.append(a + (b - a) * t)
    return np.array(out) if len(out) >= 3 else None


def _hull(pts):
    pts = sorted(set(map(tuple, np.round(pts, 3))))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


class Renderer:
    def __init__(self, sky_top, sky_horizon, fog_color=None, fog_dist=900.0, light=None, ground_z=0.0,
                 shadow_alpha=0.32, night=False):
        self.sky_top, self.sky_hz = np.asarray(sky_top, float), np.asarray(sky_horizon, float)
        self.fog_color = np.asarray(fog_color if fog_color is not None else sky_horizon, float)
        self.fog_dist = fog_dist
        self.light = light or Light()
        self.ground_z = ground_z
        self.shadow_alpha = shadow_alpha
        self.night = night
        self._sky_cache = {}
        self.sprites = []   # (world pos, PIL RGBA image, world height) drawn as billboards (clouds, sun)

    # -------------------------------------------------------------- sky
    def _sky(self, cam):
        hz = H * SS / 2 - cam.f * math.tan(cam.pitch)      # horizon line on the canvas
        key = int(hz // 8)
        if key not in self._sky_cache:
            y = np.arange(H * SS)[:, None]
            u = np.clip((hz - y) / (H * SS * 0.75), 0, 1) ** 0.8
            col = self.sky_hz[None, :] * (1 - u) + self.sky_top[None, :] * u
            below = y >= hz
            col = np.where(below, self.fog_color[None, :], col)
            img = np.repeat(col[:, None, :], W * SS, axis=1).astype(np.uint8)
            self._sky_cache[key] = Image.fromarray(img, "RGB")
            if len(self._sky_cache) > 4:
                self._sky_cache.pop(next(iter(self._sky_cache)))
        return self._sky_cache[key].copy()

    # -------------------------------------------------------------- shading
    def _shade(self, obj, cam):
        m = obj.mesh
        R = obj.R
        Nw = m.N @ R.T
        Cw = m.Cn @ R.T + obj.pos
        view = Cw - cam.pos
        facing = (Nw * view).sum(axis=1) < 0
        two = (m.FL & 2) > 0
        Nl = np.where((~facing & two)[:, None], -Nw, Nw)
        vis = facing | two
        L = self.light
        ndl = np.clip(Nl @ L.to_sun, 0, 1)
        sky = np.clip(0.55 + 0.45 * Nl[:, 2], 0, 1)
        lightc = L.amb * sky[:, None] * L.sky[None, :] * 1.6 + L.dif * ndl[:, None] * L.sun[None, :]
        col = m.C * lightc
        emis = (m.FL & 1) > 0
        col = np.where(emis[:, None], m.C, col)
        dist = np.sqrt((view ** 2).sum(axis=1))
        fog = 1 - np.exp(-dist / self.fog_dist)
        fog = np.where(emis, fog * 0.4, fog)
        col = col * (1 - fog[:, None]) + self.fog_color[None, :] * fog[:, None]
        return vis, np.clip(col, 0, 255), Cw

    def _faces(self, obj, cam, out):
        m = obj.mesh
        cen = m.center @ obj.R.T + obj.pos
        pc = cam.to_cam(cen[None])[0]
        rad = m.radius
        if pc[2] < -rad:
            return
        lim = (abs(pc[2]) + rad) * (W / 2) / (cam.f / SS) * 1.1 + rad
        if abs(pc[0]) > lim + rad or abs(pc[1]) > lim * H / W + rad * 2:
            return
        vis, col, Cw = self._shade(obj, cam)
        Vw = m.V @ obj.R.T + obj.pos
        Vc = cam.to_cam(Vw)
        S = cam.project(Vc)
        Cz = cam.to_cam(Cw)[:, 2] - np.where((m.FL & 4) > 0, 0.35, 0.0)
        fz = Vc[:, 2]
        for k in np.nonzero(vis)[0]:
            f = m.f[k]
            zs = fz[list(f)]
            if zs.max() < 0.12:
                continue
            if zs.min() < 0.12:
                P = _clip_near(Vc[list(f)])
                if P is None:
                    continue
                pts = cam.project(P).tolist()
            else:
                pts = S[list(f)].tolist()
            c = col[k]
            out.append((Cz[k], [tuple(p) for p in pts], (int(c[0]), int(c[1]), int(c[2]))))

    # -------------------------------------------------------------- shadows
    def _shadows(self, objs, cam):
        """Soft shadows on the ground: each object's outline squashed onto the ground along the sun."""
        mask = Image.new("L", (W // 2, H // 2), 0)
        d = ImageDraw.Draw(mask)
        L = self.light.dir
        if L[2] > -0.15:
            return None
        drew = False
        for o in objs:
            if not (o.shadow and o.visible):
                continue
            Vw = o.mesh.V @ o.R.T + o.pos
            gz = self.ground_z if not callable(o.shadow) else o.shadow(o)
            h = Vw[:, 2] - gz
            P = Vw - L[None, :] * (h / L[2])[:, None]
            hull = _hull(P[:, :2])
            if len(hull) < 3:
                continue
            ring = np.array([(x, y, gz + 0.02) for x, y in hull])
            Pc = cam.to_cam(ring)
            if (Pc[:, 2] < 0.12).all():
                continue
            if (Pc[:, 2] < 0.12).any():
                Pc = _clip_near(Pc)
                if Pc is None:
                    continue
            s = cam.project(Pc) / SS / 2
            alt = max(0.0, float(o.pos[2] - gz))
            a = int(255 * max(0.0, 1 - alt / 12.0))
            if a > 8:
                d.polygon([tuple(p) for p in s.tolist()], fill=a)
                drew = True
        if not drew:
            return None
        return mask.filter(ImageFilter.GaussianBlur(3)).resize((W * SS, H * SS), Image.BILINEAR)

    # -------------------------------------------------------------- frame
    def render(self, objs, cam, overlays=()):
        img = self._sky(cam)
        draw = ImageDraw.Draw(img)
        for pos, spr, hgt in self.sprites:          # far-away billboards (clouds, sun, moon)
            s = cam.screen(pos)
            if s is None:
                continue
            x, y, z = s
            sc = hgt * (cam.f / SS) / z / spr.height
            if sc <= 0.01:
                continue
            w2, h2 = int(spr.width * sc * SS), int(spr.height * sc * SS)
            if w2 < 4 or h2 < 2 or w2 > W * SS * 3:
                continue
            x0, y0 = int(x * SS - w2 / 2), int(y * SS - h2 / 2)
            if x0 > W * SS or y0 > H * SS or x0 + w2 < 0 or y0 + h2 < 0:
                continue
            sp = spr.resize((w2, h2), Image.BILINEAR)
            img.paste(sp.convert("RGB"), (x0, y0), sp)
        ground = [o for o in objs if o.visible and o.layer == 0]
        things = [o for o in objs if o.visible and o.layer != 0]
        for o in sorted(ground, key=lambda o: o.order):
            faces = []
            self._faces(o, cam, faces)
            faces.sort(key=lambda t: -t[0])
            for _, pts, c in faces:
                draw.polygon(pts, fill=c)
        sh = self._shadows(things, cam)
        if sh is not None:
            dark = Image.new("RGB", img.size, (30, 36, 52))
            img = Image.composite(dark, img, sh.point(lambda v: int(v * self.shadow_alpha)))
            draw = ImageDraw.Draw(img)
        faces = []
        for o in things:
            self._faces(o, cam, faces)
        faces.sort(key=lambda t: -t[0])
        for _, pts, c in faces:
            draw.polygon(pts, fill=c)
        for fn in overlays:     # 2D extras at supersampled size (rain, spray, dust...)
            fn(img, draw, cam)
        return img.reduce(SS)
