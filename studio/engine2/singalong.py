"""On-screen sing-along for engine 2: karaoke lyrics with a bouncing ball, comic-book noise bursts
(BEEP BEEP!, CHOO CHOO!) with sound waves coming out of the vehicle, a gentle camera push-in on the
vehicle when it makes its noise, and little music notes floating up during the chorus.

Everything moves smoothly (eased, no flashing): words fill with colour as they are sung.
"""
import functools
import math

from PIL import Image, ImageDraw, ImageFont

from .core import H, W, smooth

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GOLD = (255, 214, 64, 255)
WHITE = (255, 253, 246, 255)
INK = (24, 30, 58, 255)
BANNER_Y = 60
BANNER_H = 104
PART_COL = {"verse": (60, 120, 220), "chorus": (236, 92, 120), "ask": (60, 170, 120), "echo": (250, 150, 40)}


@functools.lru_cache(maxsize=16)
def _font(size):
    return ImageFont.truetype(FONT, size)


def _word_img(text, size, fill):
    f = _font(size)
    l, t, r, b = f.getbbox(text)
    img = Image.new("RGBA", (r - l + 12, b - t + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((6 - l, 6 - t), text, font=f, fill=fill, stroke_width=5, stroke_fill=INK)
    return img


class Line:
    """A pre-rendered lyric line: white words and gold copies to wipe in as they are sung."""

    def __init__(self, ln):
        self.ln = ln
        size = 64 if ln["part"] == "echo" else 54
        words = ln["words"]
        self.white = [_word_img(w["text"], size, WHITE) for w in words]
        self.gold = [_word_img(w["text"], size, GOLD) for w in words]
        gap = int(size * 0.32)
        self.width = sum(i.width for i in self.white) + gap * (len(words) - 1)
        self.xs, x = [], 0
        for i in self.white:
            self.xs.append(x)
            x += i.width + gap
        self.h = max(i.height for i in self.white)

    def draw(self, layer, t, alpha):
        ln = self.ln
        pad_x = 88
        bw = self.width + pad_x + 44
        x0 = (W - bw) // 2
        d = ImageDraw.Draw(layer)
        col = PART_COL.get(ln["part"], (60, 120, 220))
        d.rounded_rectangle([x0, BANNER_Y, x0 + bw, BANNER_Y + BANNER_H], radius=BANNER_H // 2,
                            fill=(22, 30, 62, int(178 * alpha)), outline=col + (int(230 * alpha),), width=5)
        _note_icon(d, x0 + 46, BANNER_Y + BANNER_H // 2 + 4, col, alpha)
        tx = x0 + pad_x
        ty = BANNER_Y + (BANNER_H - self.h) // 2 + 2
        words = ln["words"]
        for i, w in enumerate(words):
            img = self.white[i]
            p = (t - w["t"]) / max(0.12, min(w["d"], 0.6))
            layer.alpha_composite(_fade(img, alpha), (tx + self.xs[i], ty))
            if p > 0:
                cw = int(img.width * min(1.0, p))
                if cw > 0:
                    layer.alpha_composite(_fade(self.gold[i].crop((0, 0, cw, img.height)), alpha), (tx + self.xs[i], ty))
        # bouncing ball: lands on each word as it is sung
        if words and alpha > 0.3:
            cx = [tx + self.xs[i] + self.white[i].width / 2 for i in range(len(words))]
            ts = [w["t"] for w in words]
            if t < ts[0]:
                p = smooth(1 - (ts[0] - t) / 0.5) if ts[0] - t < 0.5 else 0.0
                x, hop = cx[0] - 70 * (1 - p), 1 - p
            else:
                i = max(j for j in range(len(ts)) if ts[j] <= t)
                if i + 1 < len(ts):
                    p = (t - ts[i]) / max(0.05, ts[i + 1] - ts[i])
                    x = cx[i] + (cx[i + 1] - cx[i]) * p
                    hop = math.sin(math.pi * min(1, p))
                else:
                    x, hop = cx[i], 0.0
            y = BANNER_Y - 4 - 44 * hop
            r = 13
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 112, 96, int(255 * alpha)), outline=(255, 255, 255, int(255 * alpha)), width=3)
            d.ellipse([x - 6, y - 8, x - 1, y - 3], fill=(255, 255, 255, int(200 * alpha)))


def _fade(img, a):
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return out


def _note_icon(d, x, y, col, a, s=1.0):
    al = int(255 * a)
    d.ellipse([x - 14 * s, y + 4 * s, x + 4 * s, y + 18 * s], fill=(255, 255, 255, al))
    d.line([(x + 2 * s, y + 10 * s), (x + 2 * s, y - 26 * s)], fill=(255, 255, 255, al), width=max(2, int(5 * s)))
    d.polygon([(x + 2 * s, y - 26 * s), (x + 18 * s, y - 16 * s), (x + 16 * s, y - 8 * s), (x + 2 * s, y - 16 * s)],
              fill=col + (al,))


@functools.lru_cache(maxsize=32)
def burst(word, col):
    """A comic-book starburst with the noise word in it."""
    f = _font(76)
    l, t, r, b = f.getbbox(word)
    tw, th = r - l, b - t
    w, h = tw + 280, th + 210
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = w / 2, h / 2
    pts_o, pts_i = [], []
    n = 16
    for k in range(n * 2):
        a = math.pi * k / n
        ro = (1.0 if k % 2 == 0 else 0.78)
        pts_o.append((cx + math.cos(a) * (w / 2 - 4) * ro, cy + math.sin(a) * (h / 2 - 4) * ro))
        pts_i.append((cx + math.cos(a) * (w / 2 - 18) * ro, cy + math.sin(a) * (h / 2 - 18) * ro))
    d.polygon(pts_o, fill=(255, 255, 255, 255))
    d.polygon(pts_i, fill=col + (255,))
    d.text((cx - tw / 2 - l, cy - th / 2 - t), word, font=f, fill=(255, 255, 255, 255), stroke_width=7, stroke_fill=INK)
    return img


def _waves(layer, x, y, a, direction, col):
    """Sound waves rippling out of the vehicle: ))) in its colour."""
    d = ImageDraw.Draw(layer)
    for i in range(4):
        ph = (a * 1.4 + i / 4) % 1.0
        r = 40 + ph * 230
        al = int(235 * (1 - ph) * min(1.0, a / 0.25))
        if al <= 4:
            continue
        box = [x - r, y - r, x + r, y + r]
        start, end = (-42, 42) if direction > 0 else (138, 222)
        d.arc(box, start, end, fill=(255, 255, 255, al), width=14)
        d.arc(box, start, end, fill=col + (al,), width=8)
        if direction == 0:
            d.arc(box, 138, 222, fill=col + (al,), width=8)


def _floating_notes(layer, t, seed):
    d = ImageDraw.Draw(layer)
    cols = [(255, 120, 150), (255, 200, 80), (110, 200, 255), (150, 230, 140)]
    for k in range(6):
        period = 5.0 + k * 0.7
        ph = ((t + k * 1.9 + seed % 7) / period) % 1.0
        side = k % 2
        x = (70 + 60 * (k // 2)) if side == 0 else (W - 70 - 60 * (k // 2))
        x += 18 * math.sin(t * 1.5 + k)
        y = H - 40 - ph * 420
        a = math.sin(math.pi * ph) * 0.75
        _note_icon(d, x, y, cols[k % 4], a, s=1.3)


class SingAlong:
    def __init__(self, song):
        self.song = song
        self.lines = [Line(ln) for ln in song["lines"]]
        self.noises = song["noises"]
        self.chorus = [(ln["t0"], ln["t1"]) for ln in song["lines"] if ln["part"] == "chorus"]

    def zoom(self, t):
        """Camera push-in amount while a noise plays."""
        z = 1.0
        for nz in self.noises:
            a = t - nz["t"] + 0.3
            if -0.1 < a < 3.0:
                z = max(z, 1 + 0.07 * smooth(a / 0.6) * (1 - smooth((a - 2.2) / 0.8)))
        return z

    def active_line(self, t):
        best = None
        for L in self.lines:
            ln = L.ln
            if ln["t0"] - 0.6 <= t:
                last = ln["words"][-1]
                end = max(ln["t1"] - 0.05, last["t"] + last["d"] + 0.8) if ln["part"] != "echo" else ln["t1"] + 0.6
                if t < end and (best is None or ln["t0"] > best.ln["t0"]):
                    best = L
        return best

    def draw(self, frame, t, hero, seed=0):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if any(a - 0.5 <= t <= b + 0.5 for a, b in self.chorus):
            _floating_notes(layer, t, seed)
        L = self.active_line(t)
        if L is not None:
            ln = L.ln
            last = ln["words"][-1]
            end = max(ln["t1"], last["t"] + last["d"] + 0.8) if ln["part"] != "echo" else ln["t1"] + 0.6
            nxt = [M for M in self.lines if M.ln["t0"] > ln["t0"]]
            seamless = nxt and nxt[0].ln["t0"] - 0.6 <= end
            a = smooth((t - ln["t0"] + 0.6) / 0.4) * (1.0 if seamless else 1 - smooth((t - end + 0.4) / 0.4))
            if a > 0.01:
                L.draw(layer, t, a)
        for nz in self.noises:
            a = t - nz["t"]
            if -0.05 <= a <= 2.4:
                col = tuple(nz.get("col", (255, 214, 64)))
                fx, fy = hero["front"]
                _waves(layer, fx, fy, max(0.0, a), hero.get("dir", 1), col)
                img = burst(nz["word"], col)
                s = (1 - math.exp(-a * 7) * math.cos(a * 15)) if a > 0 else 0.0
                s *= 1 - smooth((a - 2.0) / 0.4)
                if s > 0.05:
                    w, h = max(2, int(img.width * s)), max(2, int(img.height * s))
                    im = img.resize((w, h), Image.BILINEAR).rotate(-6 + 3 * math.sin(a * 5), Image.BILINEAR, expand=True)
                    tx, ty = hero["top"]
                    cx = min(W - im.width / 2 - 20, max(im.width / 2 + 20, tx))
                    lo = BANNER_Y + BANNER_H + im.height / 2 + 10
                    cy = max(lo, ty - 120)
                    if cy + im.height / 2 - ty > im.height * 0.45:   # would cover the vehicle: go below it
                        cy = hero["front"][1] + 160 + im.height / 2
                    cy = min(H - im.height / 2 - 20, max(BANNER_Y + BANNER_H + im.height / 2 + 10, cy))
                    layer.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))
        frame.alpha_composite(layer)
        return frame


def push_in(frame, z, cx, cy):
    """Zoom the finished picture by z around (cx, cy) (kept inside the frame)."""
    if z <= 1.001:
        return frame, (lambda x, y: (x, y))
    w, h = W / z, H / z
    x0 = min(max(cx - w / 2, 0), W - w)
    y0 = min(max(cy - h / 2, 0), H - h)
    out = frame.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h))
    return out, (lambda x, y: ((x - x0) * z, (y - y0) * z))
