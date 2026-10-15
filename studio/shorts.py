#!/usr/bin/env python3
"""YouTube Shorts: vertical 1080x1920, ~40 s, hook in the first second, quick action shots.

Each shot renders a fresh engine-2 scene (new seed, so new scenery) and frames it vertically:
a sharp 1080x1080 window that follows the action, with the sky extended above and the ground
below, big bold pop-in text, counting pop-ups, fast upbeat music and the scene's sound effects.

    python studio/shorts.py                         # all Shorts in plan/shorts1.json -> output/shorts
    python studio/shorts.py --only short-trains --preview
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import music  # noqa: E402

ROOT = Path(__file__).resolve().parent
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
VW, VH = 1080, 1920
TOP = 420                  # the scene window sits between y=420 and y=1500
FPS = 24
XF = 12                    # 0.5 s crossfade between shots
SR = music.SR


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


_TXT = {}


def text_img(text, size, fill=(255, 255, 255), stroke=(24, 34, 70), width=980):
    key = (text, size, fill)
    if key in _TXT:
        return _TXT[key]
    font = ImageFont.truetype(FONT, size)
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.getlength(test) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    lines.append(cur)
    sw = max(4, size // 10)
    lh = int(size * 1.12)
    img = Image.new("RGBA", (width + 2 * sw + 40, lh * len(lines) + 2 * sw + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        x = (img.width - font.getlength(ln)) / 2
        d.text((x + 6, 10 + i * lh + 8), ln, font=font, fill=(0, 0, 0, 90), stroke_width=sw, stroke_fill=(0, 0, 0, 90))
        d.text((x, 10 + i * lh), ln, font=font, fill=fill, stroke_width=sw, stroke_fill=stroke)
    _TXT[key] = img
    return img


def pop(img, a):
    """Pop-in: grows past full size and settles (a = seconds since it appeared)."""
    if a < 0:
        return None
    s = 0.6 + 0.55 * smooth(a / 0.22) - 0.15 * smooth((a - 0.22) / 0.18)
    s = min(s, 1.0) if a > 0.4 else s
    if abs(s - 1) < 0.01:
        return img
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)


def vertical(land, cx, top_text=None, top_age=0.0, bottom_text=None, bottom_age=0.0, tag=True):
    """Frame a 1920x1080 landscape render as a 1080x1920 Short."""
    land = land.convert("RGB")
    x0 = int(max(0, min(1920 - VW, cx - VW / 2)))
    crop = land.crop((x0, 0, x0 + VW, 1080))
    arr = np.asarray(crop)
    top_col = arr[:6].reshape(-1, 3).mean(axis=0)
    bot_col = arr[-6:].reshape(-1, 3).mean(axis=0)
    canvas = np.zeros((VH, VW, 3), np.float32)
    yy = np.linspace(0, 1, TOP)[:, None, None]
    canvas[:TOP] = (top_col * 0.82 + np.array([10, 20, 60]) * 0.18) * (1 - yy) + top_col * yy
    yb = np.linspace(0, 1, VH - TOP - 1080)[:, None, None]
    canvas[TOP + 1080:] = bot_col * (1 - yb) + (bot_col * 0.55) * yb
    out = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    out.paste(crop, (0, TOP))
    if top_text:
        im = pop(text_img(top_text, 92), top_age)
        if im is not None:
            out.alpha_composite(im, ((VW - im.width) // 2, max(20, (TOP - im.height) // 2)))
    if bottom_text:
        im = pop(text_img(bottom_text, 84, fill=(255, 226, 90)), bottom_age)
        if im is not None:
            out.alpha_composite(im, ((VW - im.width) // 2, TOP + 1080 + (VH - TOP - 1080 - im.height) // 2 - 20))
    if tag:
        t = text_img("TheCalmLittleWorld", 34, fill=(255, 255, 255))
        out.alpha_composite(t, ((VW - t.width) // 2, VH - t.height - 26))
    return out


def _encode(path, frames):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
           "-pix_fmt", "yuv420p", "-threads", "1", str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.convert("RGB").tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError(path)


def render_shot(args):
    shot, work, idx, hook = args
    sys.path.insert(0, str(ROOT))
    from engine2 import sfx
    from engine2.scene import make
    spec = dict(shot["scene"])
    spec["no_captions"] = True
    t0, dur = shot["t0"], shot["dur"]
    D = t0 + dur + 2
    sc = make(spec, D)
    n = int(round(dur * FPS))
    frames = []
    for i in range(n):
        t = t0 + i / FPS
        land = sc.frame(t)
        a = i / FPS
        cx = shot.get("cx", 960) + shot.get("pan", 0) * a
        top = hook if (hook and a < 3.2) else shot.get("top")
        top_age = a if hook and a < 3.2 else a - (3.2 if hook else 0.15)
        frames.append(vertical(land, cx, top, top_age, shot.get("text"), a - (0.6 if not hook else 3.4)))
        if i == n // 2:
            frames[-1].convert("RGB").save(Path(work) / f"mid_{idx:02d}.jpg", quality=85)
    _encode(Path(work) / f"shot_{idx:02d}.mp4", frames)
    a = sfx.render_scene(sc.sounds, D, spec["seed"])
    np.save(Path(work) / f"sfx_{idx:02d}.npy", a[int(t0 * SR): int(t0 * SR) + int(n / FPS * SR)].astype(np.float32))
    return idx


def end_card(short, path):
    sky = Image.new("RGB", (1, VH))
    for y in range(VH):
        u = y / VH
        sky.putpixel((0, y), (int(70 + 120 * u), int(130 + 90 * u), int(230 - 20 * u)))
    base = sky.resize((VW, VH)).convert("RGBA")
    frames = []
    for i in range(int(3.5 * FPS)):
        a = i / FPS
        f = base.copy()
        for txt, size, y, delay, col in ((short["end"], 104, 640, 0.0, (255, 255, 255)),
                                         ("Watch the full video on", 56, 1000, 0.5, (255, 255, 255)),
                                         ("TheCalmLittleWorld", 78, 1090, 0.7, (255, 226, 90))):
            im = pop(text_img(txt, size, fill=col), a - delay)
            if im is not None:
                f.alpha_composite(im, ((VW - im.width) // 2, y - im.height // 2))
        frames.append(f)
    _encode(path, frames)
    return len(frames)


def render_short(short, out_dir, workers=None, log=print):
    out_dir = Path(out_dir)
    work = out_dir / "work" / short["id"]
    work.mkdir(parents=True, exist_ok=True)
    shots = short["shots"]
    t0 = time.time()
    jobs = [(s, str(work), i, short["hook"] if i == 0 else None) for i, s in enumerate(shots)]
    with ProcessPoolExecutor(max_workers=workers or os.cpu_count()) as pool:
        for i in pool.map(render_shot, jobs):
            log(f"[{short['id']}] shot {i + 1}/{len(shots)} done")
    end_frames = end_card(short, work / "end.mp4")
    lens = [int(round(s["dur"] * FPS)) for s in shots] + [end_frames]
    starts = [0]
    for ln in lens[:-1]:
        starts.append(starts[-1] + ln - XF)
    total = (starts[-1] + lens[-1]) / FPS
    N = int(total * SR)
    mono, info = music.compose_upbeat(short["seed"], total + 1, root=short.get("root"), bpm=short.get("bpm", 120),
                                      inst=short.get("instrument"))
    mono = mono[:N]
    fx = np.zeros(N)
    for i in range(len(shots)):
        a = np.load(work / f"sfx_{i:02d}.npy").astype(np.float64)
        st = int(starts[i] / FPS * SR)
        tt = np.arange(len(a)) / SR
        g = np.minimum(1, tt / 0.5) * np.minimum(1, (len(a) / SR - tt) / 0.5)
        end = min(N, st + len(a))
        fx[st:end] += (a * g)[: end - st]
    fx /= max(1e-9, np.percentile(np.abs(fx), 99.5)) * 1.6
    mix = 0.62 * mono + 0.5 * np.clip(fx, -0.9, 0.9)
    mix /= np.max(np.abs(mix)) + 1e-9
    music.write_wav(work / "audio.wav", mix * 0.7)
    inputs = [f"shot_{i:02d}.mp4" for i in range(len(shots))] + ["end.mp4"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in inputs:
        cmd += ["-i", str(work / f)]
    cmd += ["-i", str(work / "audio.wav")]
    chain, prev = [], "[0:v]"
    for k in range(1, len(inputs)):
        chain.append(f"{prev}[{k}:v]xfade=transition=fade:duration={XF / FPS}:offset={starts[k] / FPS:.4f}[v{k}]")
        prev = f"[v{k}]"
    mp4 = out_dir / f"{short['id']}.mp4"
    cmd += ["-filter_complex", ";".join(chain), "-map", prev, "-map", f"{len(inputs)}:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-af", "loudnorm=I=-15:TP=-2:LRA=9,alimiter=limit=0.7:attack=2:release=60:level=false",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    Image.open(work / "mid_01.jpg").save(out_dir / f"{short['id']}.jpg", quality=90)
    meta = {"id": short["id"], "engine": 2, "short": True, "file": mp4.name, "thumbnail": f"{short['id']}.jpg",
            "title": short["title"], "description": short["description"], "tags": short["tags"],
            "categoryId": "27", "madeForKids": True, "privacyStatus": "private",
            "scenes": [dict(s["scene"], caption=s.get("text", "")) for s in shots], "music": info,
            "duration": round(total, 2)}
    (out_dir / f"{short['id']}.json").write_text(json.dumps(meta, indent=2))
    (out_dir / f"{short['id']}.txt").write_text(
        f"TITLE\n{meta['title']}\n\nDESCRIPTION\n{meta['description']}\n\nTAGS\n{', '.join(meta['tags'])}\n\n"
        "SETTINGS\nUpload as a Short (vertical, under 60 seconds)\nAudience: Yes, it's made for kids\nCategory: Education\n")
    log(f"[{short['id']}] done: {total:.1f}s in {(time.time() - t0) / 60:.1f} min")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=str(ROOT / "plan" / "shorts1.json"))
    ap.add_argument("--out", default=str(ROOT.parent / "output" / "shorts"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    for sh in plan["shorts"]:
        if not a.only or sh["id"] in a.only:
            render_short(sh, a.out, a.workers)
