#!/usr/bin/env python3
"""Render one engine-2 video: scenes in parallel, crossfades, upbeat music + sound effects.

    python studio/produce2.py 11-cars-and-trucks --manifest studio/plan/batch2.json
    python studio/produce2.py 11-cars-and-trucks --manifest studio/plan/batch2.json --seconds 90   # quick preview
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
from art import H, W  # noqa: E402
from produce import card  # noqa: E402
from scenes import FONT  # noqa: E402

ROOT = Path(__file__).resolve().parent
FPS = 24
XF = 30            # crossfade frames (1.25 s)
INTRO = 96         # 4 s title card
SR = music.SR


def frames_plan(n, total_frames):
    """Scene length (frames) and outro length so everything adds up to exactly total_frames."""
    base = total_frames - INTRO + (n + 1) * XF
    outro = 120 + (base - 120) % n
    L = (base - outro) // n
    return L, outro


def load(manifest, vid):
    m = json.loads(Path(manifest).read_text())
    for i, v in enumerate(m["videos"]):
        if v["id"] == vid:
            return m, i, v
    raise SystemExit(f"unknown video {vid}")


def scene_seed(batch_index, vi, k):
    return 500009 * (batch_index + 1) + 10007 * (vi + 1) + 101 * k + 13


def _encode(path, frames_iter, crf=14, preset="veryfast"):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-threads", "1", str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames_iter:
        p.stdin.write(f.convert("RGB").tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError(f"encode failed: {path}")


def render_scene(args):
    """Worker: render one scene to an mp4 segment, its sound effects to .npy, and a key frame."""
    spec, frames, work = args
    sys.path.insert(0, str(ROOT))
    from engine2 import sfx
    from engine2.scene import make
    D = frames / FPS
    t0 = time.time()
    sc = make(spec, D)
    out = Path(work) / f"scene_{spec['index']:02d}.mp4"
    key = {}

    def gen():
        for i in range(frames):
            img = sc.frame(i / FPS)
            if i == frames // 2:
                key["img"] = img.convert("RGB").resize((160, 90))
            if i == int(min(frames - 1, 22 * FPS)):
                key["thumb"] = img.convert("RGB")
            yield img
    _encode(out, gen())
    key["img"].save(Path(work) / f"key_{spec['index']:02d}.png")
    key["thumb"].save(Path(work) / f"thumb_{spec['index']:02d}.png")
    np.save(Path(work) / f"sfx_{spec['index']:02d}.npy", sfx.render_scene(sc.sounds, D, spec["seed"]).astype(np.float32))
    return spec["index"], time.time() - t0


def render(vid, manifest, out_dir, total=600, workers=None, log=print, reuse=False):
    m, vi, video = load(manifest, vid)
    bi = m.get("batch_index", 1)
    out_dir = Path(out_dir)
    work = out_dir / "work" / vid
    work.mkdir(parents=True, exist_ok=True)
    scenes = video["scenes"]
    n = len(scenes)
    total_frames = int(total * FPS)
    L, outro = frames_plan(n, total_frames)
    specs = []
    for k, s in enumerate(scenes):
        s = dict(s)
        s["seed"] = scene_seed(bi, vi, k)
        s["index"] = k
        specs.append(s)
    workers = workers or os.cpu_count() or 2
    t0 = time.time()
    log(f"[{vid}] rendering {n} scenes of {L / FPS:.1f}s with {workers} workers")
    def done(k):
        return all((work / f).exists() for f in (f"scene_{k:02d}.mp4", f"sfx_{k:02d}.npy", f"key_{k:02d}.png"))
    todo = [s for s in specs if not (reuse and done(s["index"]))]
    if len(todo) < len(specs):
        log(f"[{vid}] reusing {len(specs) - len(todo)} scenes already rendered")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for k, secs in pool.map(render_scene, [(s, L, str(work)) for s in todo]):
            log(f"[{vid}] scene {k + 1}/{n} done ({secs / 60:.1f} min)")
    # title and goodbye cards
    word = video["word"]
    intro = card([(word, 150, 255), ("TheCalmLittleWorld", 52, 220)], scenes[0].get("time", "day"))
    outro_img = card([(f"Bye-bye, {word.lower()}!", 120, 255), ("See you next time", 56, 220)], scenes[-1].get("time", "day"))
    _encode(work / "intro.mp4", (intro for _ in range(INTRO)))
    _encode(work / "outro.mp4", (outro_img for _ in range(outro)))

    # ---- audio: music under the whole video, each scene's sound effects crossfaded like the picture
    lens = [INTRO] + [L] * n + [outro]
    starts = [0]
    for ln in lens[:-1]:
        starts.append(starts[-1] + ln - XF)
    N = int(total * SR)
    mu = video.get("music", {})
    mono, info = music.compose_upbeat(scene_seed(bi, vi, 99), total + 1, root=mu.get("root"), bpm=mu.get("bpm"),
                                      inst=mu.get("instrument"))
    mono = mono[:N]
    fx = np.zeros(N)
    xf = XF / FPS
    for k in range(n):
        a = np.load(work / f"sfx_{k:02d}.npy").astype(np.float64)
        st = int(starts[k + 1] / FPS * SR)
        ln = len(a)
        tt = np.arange(ln) / SR
        g = np.minimum(1, tt / xf) * np.minimum(1, (ln / SR - tt) / xf)
        end = min(N, st + ln)
        fx[st:end] += (a * g)[: end - st]
    fx /= max(1e-9, np.percentile(np.abs(fx), 99.5)) * 1.6
    fx = np.clip(fx, -0.9, 0.9)
    mix = 0.62 * mono + 0.5 * fx
    mix /= np.max(np.abs(mix)) + 1e-9
    music.write_wav(work / "audio.wav", mix * 0.7)

    # ---- assemble with crossfades
    inputs = ["intro.mp4"] + [f"scene_{k:02d}.mp4" for k in range(n)] + ["outro.mp4"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in inputs:
        cmd += ["-i", str(work / f)]
    cmd += ["-i", str(work / "audio.wav")]
    chain, prev = [], "[0:v]"
    for k in range(1, len(inputs)):
        off = (starts[k]) / FPS
        lab = f"[v{k}]"
        chain.append(f"{prev}[{k}:v]xfade=transition=fade:duration={xf}:offset={off:.4f}{lab}")
        prev = lab
    mp4 = out_dir / f"{vid}.mp4"
    cmd += ["-filter_complex", ";".join(chain), "-map", prev, "-map", f"{len(inputs)}:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-tune", "animation", "-pix_fmt", "yuv420p",
            "-af", "loudnorm=I=-16:TP=-2:LRA=11,alimiter=limit=0.7:attack=2:release=60:level=false", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-t", str(total), "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    log(f"[{vid}] assembled in {(time.time() - t0) / 60:.1f} min total")

    # ---- thumbnail and YouTube text
    th = Image.open(work / "thumb_00.png").resize((1280, 720), Image.LANCZOS)
    d = ImageDraw.Draw(th, "RGBA")
    f = ImageFont.truetype(FONT, 112)
    l, t_, r, b = f.getbbox(word)
    pw, ph = r - l + 90, b - t_ + 60
    x0 = (1280 - pw) // 2
    d.rounded_rectangle([x0, 50, x0 + pw, 50 + ph], radius=ph // 2, fill=(30, 40, 66, 150))
    d.text((x0 + 45 - l, 80 - t_), word, font=f, fill=(255, 252, 244))
    thumb = out_dir / f"{vid}.jpg"
    th.convert("RGB").save(thumb, quality=92)
    chapter_starts = [starts[k + 1] / FPS + XF / FPS for k in range(n)] + [starts[-1] / FPS + XF / FPS]
    meta = {
        "id": vid, "engine": 2, "file": mp4.name, "thumbnail": thumb.name, "title": video["title"],
        "description": description(video, chapter_starts, int(total)),
        "tags": video["tags"], "categoryId": "27", "madeForKids": True, "privacyStatus": "private",
        "scenes": specs, "music": info,
    }
    (out_dir / f"{vid}.json").write_text(json.dumps(meta, indent=2))
    (out_dir / f"{vid}.txt").write_text(
        f"TITLE\n{meta['title']}\n\nDESCRIPTION\n{meta['description']}\n\nTAGS\n{', '.join(meta['tags'])}\n\n"
        f"SETTINGS\nAudience: Yes, it's made for kids\nCategory: Education\nThumbnail: {thumb.name}\n")
    return meta


def description(video, chapter_starts, total):
    def stamp(s):
        s = int(s)
        return f"{s // 60}:{s % 60:02d}"
    lines = ["0:00 Hello!"]
    for sc, st in zip(video["scenes"], chapter_starts[:-1]):
        lines.append(f"{stamp(st)} {sc['caption']}")
    lines.append(f"{stamp(chapter_starts[-1])} Bye-bye!")
    tags = " ".join("#" + t.replace(" ", "") for t in video["tags"][:3])
    return "\n".join([
        video["hook"],
        "",
        video["learn"],
        "",
        f"About {total // 60} minutes of colourful, original animation with real weather, real sounds and lots "
        "to spot and count. Every driver, pilot and captain follows the safety rules, and there is no flashing "
        "and nothing scary. Original music and sound effects, made for TheCalmLittleWorld.",
        "",
        "Chapters:",
        *lines,
        "",
        tags,
    ])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--manifest", default=str(ROOT / "plan" / "batch2.json"))
    ap.add_argument("--out", default=str(ROOT.parent / "output"))
    ap.add_argument("--seconds", type=float, default=600)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--reuse", action="store_true", help="keep scenes already rendered in the work folder")
    a = ap.parse_args()
    render(a.video_id, a.manifest, a.out, a.seconds, a.workers, reuse=a.reuse)
