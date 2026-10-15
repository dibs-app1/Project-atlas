"""Scenery props for engine 2. Each function draws onto a Pen (p) and its glow pen (g)."""
import math

from art import COLORS, GLASS, WARM_LIGHT, mix, shade

LEAF = [(92, 150, 96), (110, 168, 104), (78, 132, 90), (128, 176, 98)]
AUTUMN = [(222, 140, 70), (232, 182, 80), (200, 98, 70), (210, 160, 60)]
WALLS = [(236, 214, 190), (190, 210, 220), (226, 190, 190), (210, 220, 190), (240, 226, 170), (220, 200, 230)]
ROOFS = [(150, 82, 74), (90, 96, 116), (120, 90, 80), (170, 110, 80), (80, 110, 130)]


def tree(p, x, base, h, rng, kind="round", col=None):
    if kind == "pine":
        c = col or rng.choice([(66, 110, 80), (58, 100, 76), (74, 120, 86)])
        p.rect(x - h * 0.04, base - h * 0.16, x + h * 0.04, base, (110, 84, 60))
        for i in range(3):
            y0 = base - h * (0.16 + 0.27 * i)
            wd = h * (0.33 - 0.08 * i)
            p.poly([(x - wd, y0), (x + wd, y0), (x, y0 - h * 0.42)], shade(c, 1 + 0.06 * i))
        return
    if kind == "palm":
        p.line([(x, base), (x + h * 0.08, base - h * 0.5), (x + h * 0.04, base - h)], (150, 116, 80), h * 0.06)
        for a in (-2.6, -2.0, -1.2, -0.6, 0.0):
            p.line([(x + h * 0.04, base - h), (x + h * 0.04 + h * 0.4 * math.cos(a), base - h + h * 0.25 * math.sin(a) + h * 0.15)],
                   (90, 150, 90), h * 0.05)
        return
    if kind == "cypress":
        p.ellipse(x - h * 0.12, base - h, x + h * 0.12, base, col or (70, 110, 80))
        return
    if kind == "birch":
        p.rect(x - h * 0.03, base - h * 0.7, x + h * 0.03, base, (240, 240, 232))
        for k in range(4):
            p.rect(x - h * 0.03, base - h * (0.2 + 0.12 * k), x, base - h * (0.18 + 0.12 * k), (60, 60, 60))
        c = col or (150, 190, 100)
        p.ellipse(x - h * 0.22, base - h, x + h * 0.22, base - h * 0.45, c)
        return
    c = col or rng.choice(LEAF)
    p.rect(x - h * 0.05, base - h * 0.45, x + h * 0.05, base, (120, 90, 64))
    p.circle(x, base - h * 0.64, h * 0.32, c)
    p.circle(x - h * 0.2, base - h * 0.52, h * 0.22, shade(c, 0.92))
    p.circle(x + h * 0.2, base - h * 0.54, h * 0.22, shade(c, 1.06))
    p.circle(x - h * 0.06, base - h * 0.76, h * 0.16, mix(c, (255, 255, 255), 0.12))


def bush(p, x, base, s, col):
    for dx, r in ((-s * 0.5, s * 0.45), (0, s * 0.6), (s * 0.5, s * 0.45)):
        p.circle(x + dx, base - r * 0.8, r, col)


def flowers(p, x, base, rng, n=6):
    for _ in range(n):
        fx = x + rng.uniform(-30, 30)
        fy = base - rng.uniform(4, 16)
        p.line([(fx, base), (fx, fy)], (90, 140, 80), 2)
        p.circle(fx, fy, 4, rng.choice([(240, 120, 140), (250, 220, 90), (250, 250, 250), (180, 130, 220)]))


def house(p, g, x, base, w, h, rng, snow=False):
    wall, roof = rng.choice(WALLS), rng.choice(ROOFS)
    p.rect(x, base - h, x + w, base, wall)
    p.poly([(x - 12, base - h), (x + w + 12, base - h), (x + w / 2, base - h - h * 0.62)], roof)
    if snow:
        p.poly([(x - 8, base - h - 2), (x + w + 8, base - h - 2), (x + w / 2, base - h - h * 0.56)], (246, 248, 252))
    p.rect(x + w * 0.7, base - h - h * 0.5, x + w * 0.8, base - h - h * 0.2, shade(roof, 0.8))  # chimney
    for wx in (x + w * 0.14, x + w * 0.56):
        p.rect(wx, base - h * 0.72, wx + w * 0.22, base - h * 0.4, (176, 206, 228), r=3)
        p.line([(wx + w * 0.11, base - h * 0.72), (wx + w * 0.11, base - h * 0.4)], wall, 2)
        g.rect(wx, base - h * 0.72, wx + w * 0.22, base - h * 0.4, WARM_LIGHT + (235,), r=3)
    p.rect(x + w * 0.4, base - h * 0.5, x + w * 0.56, base, shade(roof, 0.9), r=3)
    p.circle(x + w * 0.53, base - h * 0.25, 2.5, (240, 210, 120))


def building(p, g, x, base, w, h, rng, shop=False):
    c = rng.choice([(176, 186, 200), (200, 186, 170), (170, 190, 186), (196, 176, 186), (214, 206, 190), (150, 164, 184)])
    p.rect(x, base - h, x + w, base, c)
    p.rect(x - 4, base - h - 12, x + w + 4, base - h, shade(c, 0.8))
    for wy in range(int(base - h + 24), int(base - (110 if shop else 40)), 46):
        for wx in range(int(x + 16), int(x + w - 30), 40):
            lit = rng.random() < 0.7
            p.rect(wx, wy, wx + 24, wy + 30, (186, 210, 230), r=3)
            if lit:
                g.rect(wx, wy, wx + 24, wy + 30, WARM_LIGHT + (230,), r=3)
    if shop:
        aw = rng.choice([COLORS["red"], COLORS["teal"], COLORS["yellow"], COLORS["blue"], COLORS["green"]])
        for k in range(int(w // 30)):
            p.rect(x + 6 + k * 30, base - 100, x + 30 + k * 30, base - 78, aw if k % 2 == 0 else (250, 250, 246))
        p.rect(x + 14, base - 74, x + w * 0.6, base, (176, 206, 228), r=4)
        g.rect(x + 14, base - 74, x + w * 0.6, base, WARM_LIGHT + (200,), r=4)
        p.rect(x + w * 0.66, base - 76, x + w * 0.86, base, shade(c, 0.6), r=3)


def lamp(p, g, x, base, h=200):
    p.rect(x - 4, base - h, x + 4, base, (70, 74, 86))
    p.line([(x, base - h), (x + 40, base - h - 10)], (70, 74, 86), 6)
    p.rect(x + 30, base - h - 14, x + 56, base - h - 4, (240, 230, 190), r=3)
    g.rect(x + 30, base - h - 14, x + 56, base - h - 4, (255, 236, 170, 255), r=3)
    g.poly([(x + 32, base - h - 4), (x + 54, base - h - 4), (x + 74, base - h + 40), (x + 12, base - h + 40)],
           (255, 230, 160, 40))


def pole(p, x, base, h=240):
    p.rect(x - 5, base - h, x + 5, base, (130, 100, 76))
    p.rect(x - 40, base - h + 14, x + 40, base - h + 22, (120, 92, 70))
    for dx in (-34, 0, 34):
        p.rect(x + dx - 3, base - h + 4, x + dx + 3, base - h + 14, (220, 220, 210))


def wires(p, X0, X1, M, base, h=240, spacing=420, sag=24, col=(60, 60, 66)):
    """Continuous power lines (drawn only inside [X0, X1) so chunks join without seams)."""
    for dy in (-226, -226 + 0):
        pts = []
        for xw in range(int(X0), int(X1) + 9, 8):
            u = (xw % spacing) / spacing
            pts.append((xw - X0 + M, base - h + 4 + 14 + sag * 4 * u * (1 - u)))
        p.line(pts, col, 2)


def sign(p, x, base, kind, h=150):
    """Educational road and rail signs."""
    p.rect(x - 4, base - h, x + 4, base, (150, 154, 162))
    top = base - h
    if kind == "bump":
        p.poly([(x, top - 44), (x + 44, top), (x, top + 44), (x - 44, top)], (246, 200, 50))
        p.poly([(x - 30, top + 12), (x - 12, top - 8), (x + 12, top - 8), (x + 30, top + 12)], (40, 40, 40))
    elif kind == "slow":
        p.poly([(x, top - 44), (x + 44, top), (x, top + 44), (x - 44, top)], (246, 150, 50))
        p.rect(x - 26, top - 6, x + 26, top + 6, (40, 40, 40))
    elif kind == "stop":
        pts = [(x + 40 * math.cos(math.pi / 8 + k * math.pi / 4), top + 40 * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]
        p.poly(pts, (210, 54, 48))
        p.rect(x - 24, top - 5, x + 24, top + 5, (250, 250, 250))
    elif kind == "limit":
        p.rect(x - 30, top - 40, x + 30, top + 40, (250, 250, 250), r=6)
        p.rect(x - 22, top - 4, x + 22, top + 26, (40, 40, 40), r=3)
    elif kind == "school":
        p.poly([(x, top - 46), (x + 40, top - 6), (x + 40, top + 40), (x - 40, top + 40), (x - 40, top - 6)], (220, 230, 80))
        for dx in (-14, 14):
            p.circle(x + dx, top - 2, 7, (40, 40, 40))
            p.rect(x + dx - 6, top + 6, x + dx + 6, top + 28, (40, 40, 40), r=3)
    elif kind == "rail":
        for a in (0.6, -0.6):
            dx, dy = 46 * math.cos(a), 46 * math.sin(a)
            p.line([(x - dx, top - dy), (x + dx, top + dy)], (250, 250, 250), 12)
        p.circle(x, top, 6, (40, 40, 40))
    elif kind == "bus":
        p.rect(x - 34, top - 40, x + 34, top + 30, (60, 120, 200), r=8)
        p.rect(x - 22, top - 26, x + 22, top + 8, (250, 250, 250), r=4)
    elif kind == "taxiway":
        p.rect(x - 60, top - 26, x + 60, top + 26, (250, 210, 60), r=4)
        p.rect(x - 50, top - 16, x - 4, top + 16, (40, 40, 40), r=2)


def cone(p, x, base, s=1.0):
    p.poly([(x - 16 * s, base), (x + 16 * s, base), (x + 5 * s, base - 46 * s), (x - 5 * s, base - 46 * s)], (246, 130, 50))
    p.rect(x - 12 * s, base - 28 * s, x + 12 * s, base - 20 * s, (250, 250, 250))
    p.rect(x - 22 * s, base - 4 * s, x + 22 * s, base, (230, 110, 40))


def fence(p, X0, X1, M, base, col=(250, 250, 246), h=40):
    for xw in range(int(math.ceil(X0 / 26) * 26), int(X1), 26):
        x = xw - X0 + M
        p.rect(x, base - h, x + 10, base, col)
        p.poly([(x, base - h), (x + 10, base - h), (x + 5, base - h - 8)], col)
    p.rect(M, base - h * 0.7, X1 - X0 + M, base - h * 0.6, col)
    p.rect(M, base - h * 0.3, X1 - X0 + M, base - h * 0.2, col)


def guardrail(p, X0, X1, M, base):
    p.rect(M, base - 42, X1 - X0 + M, base - 26, (190, 196, 206))
    p.rect(M, base - 36, X1 - X0 + M, base - 32, (150, 156, 166))
    for xw in range(int(math.ceil(X0 / 120) * 120), int(X1), 120):
        p.rect(xw - X0 + M, base - 42, xw - X0 + M + 8, base, (130, 136, 146))


def mountains(p, f, X0, X1, M, base, amp, height, col, snow=None):
    pts = [(xw - X0 + M, base - amp * f(xw)) for xw in range(int(X0 - M), int(X1 + M) + 9, 8)]
    p.poly([(0, height)] + pts + [(X1 - X0 + 2 * M, height)], col)
    if snow:
        for xw in range(int(X0 - M), int(X1 + M), 8):
            y = base - amp * f(xw)
            if f(xw) > 0.55:
                p.rect(xw - X0 + M, y, xw - X0 + M + 8, y + (f(xw) - 0.55) * amp * 0.6, snow)


def animal(p, x, base, kind, rng):
    if kind == "cow":
        p.rect(x - 34, base - 46, x + 30, base - 18, (250, 250, 246), r=10)
        p.ellipse(x - 20, base - 44, x + 4, base - 28, (50, 50, 54))
        p.rect(x + 22, base - 54, x + 46, base - 30, (250, 250, 246), r=6)
        p.rect(x + 38, base - 42, x + 48, base - 32, (240, 170, 170), r=3)
        for dx in (-28, -14, 12, 24):
            p.rect(x + dx, base - 20, x + dx + 6, base, (60, 60, 64))
    elif kind == "sheep":
        p.ellipse(x - 22, base - 34, x + 18, base - 10, (250, 250, 246))
        p.circle(x + 20, base - 26, 8, (60, 60, 64))
        for dx in (-14, 8):
            p.rect(x + dx, base - 12, x + dx + 4, base, (60, 60, 64))
    elif kind == "horse":
        c = rng.choice([(140, 96, 66), (90, 66, 50), (230, 220, 200)])
        p.rect(x - 34, base - 60, x + 26, base - 30, c, r=12)
        p.poly([(x + 20, base - 56), (x + 44, base - 84), (x + 56, base - 78), (x + 34, base - 48)], c)
        for dx in (-28, -16, 10, 20):
            p.rect(x + dx, base - 32, x + dx + 6, base, shade(c, 0.8))


def barn(p, g, x, base, rng):
    c = rng.choice([(190, 70, 60), (170, 60, 56)])
    p.rect(x, base - 120, x + 180, base, c)
    p.poly([(x - 10, base - 120), (x + 190, base - 120), (x + 150, base - 170), (x + 30, base - 170)], (90, 90, 96))
    p.rect(x + 60, base - 80, x + 120, base, (240, 236, 226))
    p.line([(x + 60, base - 80), (x + 120, base)], c, 6)
    p.line([(x + 120, base - 80), (x + 60, base)], c, 6)
    p.rect(x + 200, base - 190, x + 250, base, (210, 214, 222), r=20)  # silo
    p.ellipse(x + 200, base - 210, x + 250, base - 170, (170, 174, 184))


def crane(p, x, base, h, col):
    p.rect(x, base - h, x + 16, base, col)
    for k in range(int(h // 30)):
        y = base - k * 30
        p.line([(x, y), (x + 16, y - 30)], shade(col, 0.8), 3)
    p.rect(x - 120, base - h, x + 260, base - h + 16, col)
    p.rect(x - 110, base - h + 16, x - 70, base - h + 50, (90, 90, 96))


def containers(p, x, base, rng, cols=4, rows=3):
    palette = [COLORS[c] for c in ("red", "blue", "yellow", "green", "orange", "teal", "purple")]
    for r in range(rows):
        for c in range(cols):
            if r > 0 and rng.random() < 0.25:
                continue
            col = rng.choice(palette)
            x0, y0 = x + c * 92, base - (r + 1) * 46
            p.rect(x0, y0, x0 + 88, y0 + 44, col, r=2)
            for k in range(1, 7):
                p.line([(x0 + k * 12, y0 + 4), (x0 + k * 12, y0 + 40)], shade(col, 0.85), 2)


def platform(p, X0, X1, M, base, h=60):
    p.rect(M, base - h, X1 - X0 + M, base, (196, 196, 200))
    p.rect(M, base - h, X1 - X0 + M, base - h + 10, (246, 210, 60))  # yellow safety line


GLASS_ = GLASS
