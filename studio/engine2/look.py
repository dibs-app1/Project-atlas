"""The 'look' of engine 2: richer colour, 3D-style shading, textures, glow and depth.

grade()      final colour grade on every frame: vibrance, gentle contrast, warm bloom, soft vignette
shade3d()    rounds off a flat sprite: light from above, ambient occlusion below, a glossy highlight
texture()    fine grain and speckle on scenery so grass, roads and hills don't look flat
"""
import math

import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter

W, H = 1920, 1080

_LUT = None
_VIG = None


def _lut():
    global _LUT
    if _LUT is None:
        x = np.arange(256) / 255.0
        y = x + 0.10 * np.sin(2 * math.pi * (x - 0.5)) * 0.5   # soft S-curve: a little more punch
        y = np.clip(y * 1.02, 0, 1)
        _LUT = [int(v * 255 + 0.5) for v in y] * 3
    return _LUT


def _vignette():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H // 4, 0:W // 4]
        d = np.sqrt(((xx - W / 8) / (W / 8)) ** 2 + ((yy - H / 8) / (H / 8)) ** 2)
        v = np.clip(1 - 0.16 * np.clip(d - 0.55, 0, None) ** 1.6, 0, 1)
        _VIG = Image.fromarray((v * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    return _VIG


def grade(frame, vibrance=1.3, bloom=0.16, time="day"):
    """Frame (RGBA or RGB, 1920x1080) -> graded RGB."""
    img = frame.convert("RGB")
    img = ImageEnhance.Color(img).enhance(vibrance)
    img = img.point(_lut())
    # bloom: bright areas glow softly (sun, sky, lit windows, foam)
    small = img.resize((W // 6, H // 6), Image.BILINEAR)
    bright = small.point(lambda v: max(0, (v - 226) * 6))
    glow = bright.filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR)
    if time in ("golden", "dusk", "dawn"):
        glow = ImageChops.multiply(glow, Image.new("RGB", (W, H), (255, 214, 170)))
    img = ImageChops.add(img, ImageEnhance.Brightness(glow).enhance(bloom))
    # soft vignette keeps the eye on the middle of the frame
    img = ImageChops.multiply(img, Image.merge("RGB", (_vignette(),) * 3))
    return img


def shade3d(sprite, strength=1.0):
    """Give a flat RGBA sprite volume: lit top, shaded bottom, a glossy streak near the top."""
    w, h = sprite.size
    if w < 4 or h < 4:
        return sprite
    a = np.asarray(sprite.getchannel("A"), dtype=np.float32) / 255.0
    rgb = np.asarray(sprite.convert("RGB"), dtype=np.float32)
    # find each column's opaque span so shading follows the shape, not the whole box
    opaque = a > 0.5
    rows = np.arange(h, dtype=np.float32)[:, None]
    has = opaque.any(axis=0)
    top = np.where(has, opaque.argmax(axis=0), 0).astype(np.float32)
    bot = np.where(has, h - 1 - opaque[::-1].argmax(axis=0), h - 1).astype(np.float32)
    span = np.maximum(bot - top, 1.0)
    u = np.clip((rows - top[None, :]) / span[None, :], 0, 1)           # 0 at top edge, 1 at bottom edge
    light = 1.13 - 0.30 * u ** 1.3                                     # light from above
    light += 0.10 * np.exp(-((u - 0.16) / 0.06) ** 2)                  # glossy highlight band
    light -= 0.10 * np.clip((u - 0.85) / 0.15, 0, 1)                   # ambient occlusion at the bottom
    light = 1 + (light - 1) * strength
    out = np.clip(rgb * light[:, :, None], 0, 255).astype(np.uint8)
    res = Image.fromarray(out, "RGB").convert("RGBA")
    res.putalpha(sprite.getchannel("A"))
    return res


def texture(img, rng_seed, amount=0.06, speckle=0.0):
    """Multiply fine noise into the opaque parts of a scenery chunk (once per chunk, so it is cheap)."""
    w, h = img.size
    rng = np.random.default_rng(rng_seed)
    n = rng.normal(0, 1, (h // 2 + 1, w // 2 + 1)).astype(np.float32)
    n = np.kron(n, np.ones((2, 2), dtype=np.float32))[:h, :w]
    f = 1 + amount * n
    if speckle:
        f += speckle * (rng.random((h, w)) < 0.004)
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) * f[:, :, None]
    out = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    out.putalpha(img.getchannel("A"))
    return out


def sky(time, weather, sun):
    """A richer sky: deep zenith, warm horizon, a big soft glow around the sun."""
    from art import TIMES, mix
    top, bot, _, sn = TIMES[time]
    deep = {"day": (64, 140, 222), "morning": (92, 162, 228), "golden": (110, 120, 200), "dusk": (52, 56, 120),
            "dawn": (96, 108, 178), "night": (14, 20, 52)}[time]
    horizon = {"day": (214, 236, 250), "morning": (236, 244, 250), "golden": (255, 200, 140), "dusk": (250, 150, 120),
               "dawn": (255, 196, 170), "night": (54, 64, 112)}[time]
    if weather in ("rain", "snow"):
        deep, horizon = mix(deep, (150, 160, 176), 0.6), mix(horizon, (190, 196, 206), 0.6)
    yy = np.linspace(0, 1, H)[:, None]
    t = np.clip(yy * 1.1, 0, 1) ** 0.9
    col = np.array(deep)[None, None, :] * (1 - t[:, :, None]) + np.array(horizon)[None, None, :] * t[:, :, None]
    arr = np.repeat(col, W, axis=1)
    sx, sy, sr, sc = sun
    if time != "night" and weather not in ("rain", "snow"):
        yy2, xx2 = np.mgrid[0:H, 0:W]
        d = np.sqrt((xx2 - sx * W) ** 2 + (yy2 - sy * H) ** 2)
        g = np.exp(-(d / (sr * 4.5)) ** 2)[:, :, None]
        arr = arr * (1 - 0.35 * g) + np.array(sc)[None, None, :] * 0.35 * g + 8 * g
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    from PIL import ImageDraw
    import random
    d = ImageDraw.Draw(img)
    x, y = sx * W, sy * H
    if time == "night":
        r = random.Random(7)
        for _ in range(220):
            px, py, rr = r.uniform(0, W), r.uniform(0, H * 0.55), r.choice((1, 1, 1.5, 2))
            d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(250, 248, 230, r.randint(140, 255)))
        glow = Image.new("RGBA", (int(sr * 8), int(sr * 8)), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([sr * 2, sr * 2, sr * 6, sr * 6], fill=(220, 226, 255, 90))
        glow = glow.filter(ImageFilter.GaussianBlur(sr * 0.8))
        img.alpha_composite(glow, (int(x - sr * 4), int(y - sr * 4)))
        d.ellipse([x - sr, y - sr, x + sr, y + sr], fill=(246, 244, 226))
        d.ellipse([x - sr * 0.55, y - sr * 1.2, x + sr * 1.35, y + sr * 0.7], fill=tuple(int(v) for v in arr[int(y), int(x)]))
    elif weather not in ("rain", "snow"):
        d.ellipse([x - sr, y - sr, x + sr, y + sr], fill=tuple(min(255, c + 20) for c in sc) + (255,))
    return img


def cloud(rng, w, h, base=(255, 255, 255), alpha=240):
    """A fluffy, shaded cloud: white tops, soft blue-grey underside."""
    from art import mix
    from .vehicles import FastPen
    under = mix(base, (150, 166, 196), 0.35)
    p = FastPen(w, h)
    puffs = []
    n = rng.randint(5, 8)
    for i in range(n):
        cx = w * (0.12 + 0.76 * i / (n - 1)) + rng.uniform(-10, 10)
        r = h * rng.uniform(0.24, 0.40) * (1.2 if 0 < i < n - 1 else 0.8)
        cy = h * 0.6 - r * rng.uniform(0.2, 0.6)
        puffs.append((cx, cy, r))
    for cx, cy, r in puffs:                       # shadow side first
        p.circle(cx, cy + r * 0.18, r, under + (alpha,))
    p.rect(w * 0.08, h * 0.55, w * 0.92, h * 0.9, under + (alpha,), r=h * 0.17)
    for cx, cy, r in puffs:                       # lit tops
        p.circle(cx, cy - r * 0.06, r * 0.9, base + (alpha,))
    for cx, cy, r in puffs[1:-1]:                 # bright rims
        p.circle(cx - r * 0.2, cy - r * 0.3, r * 0.45, mix(base, (255, 255, 255), 0.6) + (alpha,))
    return p.done().filter(ImageFilter.GaussianBlur(1.2))
