#!/usr/bin/env python3
"""Render one engine-3 video (batch 4): 3D scenes in parallel, soft dissolves between scenes, an original
song without words (a melody instrument, no lyrics), each vehicle's real engine sound in 3D, and a
vehicle noise in every song round.

    python studio/produce3.py 19-seaside-town --manifest studio/plan/batch4.json
    python studio/produce3.py 19-seaside-town --manifest studio/plan/batch4.json --seconds 120   # quick preview
"""
import argparse
import json
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import music  # noqa: E402
from produce import card  # noqa: E402
from produce2 import FPS, INTRO, XF, _encode, frames_plan, load, scene_seed  # noqa: E402
from scenes import FONT  # noqa: E402

ROOT = Path(__file__).resolve().parent
SR = music.SR


def render_scene(args):
    spec, frames, work = args
    sys.path.insert(0, str(ROOT))
    from engine3 import scenes4  # noqa: F401  (registers the scenes)
    from engine3 import sfx3
    from engine3.stage import Stage
    D = frames / FPS
    t0 = time.time()
    st = Stage(spec, D)
    out = Path(work) / f"scene_{spec['index']:02d}.mp4"
    key = {}

    from flashguard import FlashGuard
    guard = FlashGuard()

    def gen():
        for i in range(frames):
            img = guard(st.frame(i / FPS))
            if i == frames // 2:
                key["img"] = img.resize((160, 90))
            if i == int(min(frames - 1, 8 * FPS)):
                key["thumb"] = img
            yield img
    _encode(out, gen())
    key["img"].save(Path(work) / f"key_{spec['index']:02d}.png")
    key["thumb"].save(Path(work) / f"thumb_{spec['index']:02d}.png")
    np.save(Path(work) / f"sfx_{spec['index']:02d}.npy", sfx3.render_scene(st, D, spec["theme"]).astype(np.float32))
    return spec["index"], time.time() - t0


def la(n):
    return " ".join(["la"] * n)


def song_for(video, seed):
    """A song without words: the tune is generated from 'la' syllables and played on an instrument."""
    import song as songmod
    r = random.Random(seed)
    sp = dict(video["song"])
    sp.setdefault("chorus", [la(c) for c in r.choice([[5, 7, 7, 5], [6, 6, 8, 5], [5, 8, 6, 6]])])
    sp["voice"] = "instrumental"
    v = dict(video, song=sp)
    return songmod.Song(v, seed), songmod


def _song_audio(video, specs, starts, g0, L, n, N, total, bi, vi, work, log):
    """The original song without words, with the scenes' own sound effects."""
    sng, songmod = song_for(video, scene_seed(bi, vi, 77))
    bar = (L - XF) / FPS / songmod.BARS
    rr = random.Random(scene_seed(bi, vi, 78))
    plans = []
    for s in specs:
        sc = dict(s, verse=[la(rr.randint(5, 8)) for _ in range(4)], ask=la(6), ask2=la(7), echo="la la")
        plans.append(sng.scene_plan(sc, bar))
    log("composing the song ...")
    backing = sng.backing(g0, bar, total, plans)
    lead = sng.lead(plans, g0, total, inst=video["song"].get("lead", "whistle"))
    nz = sng.noise_track(plans, g0, total)
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
    mix = 0.36 * backing + 0.42 * lead + 0.55 * nz + 0.42 * fx
    mix /= np.max(np.abs(mix)) + 1e-9
    music.write_wav(work / "audio.wav", mix * 0.7)
    return {"style": "song without words", "lead": video["song"].get("lead", "whistle"), "root": sng.root,
            "bpm": round(60 / (bar / 4), 2)}


def render(vid, manifest, out_dir, total=600, workers=None, log=print, reuse=False):
    m, vi, video = load(manifest, vid)
    bi = m.get("batch_index", 4)
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
        s.setdefault("theme", video["theme"])
        specs.append(s)
    workers = workers or os.cpu_count() or 2
    t0 = time.time()
    log(f"[{vid}] rendering {n} scenes of {L / FPS:.1f}s with {workers} workers")

    def done(k):
        return all((work / f).exists() for f in (f"scene_{k:02d}.mp4", f"sfx_{k:02d}.npy", f"key_{k:02d}.png"))
    todo = [s for s in specs if not (reuse and done(s["index"]))]
    if m.get("engine") == 4 and todo:      # engine-4 scenes come from the Blender jobs; nothing to render here
        raise SystemExit(f"[{vid}] missing Blender scenes: {[s['index'] for s in todo]}")
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for k, secs in pool.map(render_scene, [(s, L, str(work)) for s in todo]):
            log(f"[{vid}] scene {k + 1}/{n} done ({secs / 60:.1f} min)")
    word = video["word"]
    intro = card([(word, 150, 255), ("TheCalmLittleWorld", 52, 220)], scenes[0].get("time", "day"))
    outro_img = card([(f"Bye-bye, {word.lower()}!", 110, 255), ("See you next time", 56, 220)], scenes[-1].get("time", "day"))
    _encode(work / "intro.mp4", (intro for _ in range(INTRO)))
    _encode(work / "outro.mp4", (outro_img for _ in range(outro)))

    # ---- audio
    lens = [INTRO] + [L] * n + [outro]
    starts = [0]
    for ln in lens[:-1]:
        starts.append(starts[-1] + ln - XF)
    N = int(total * SR)
    g0 = [starts[k + 1] / FPS for k in range(n)]
    if video.get("soundtrack"):           # recorded music and recorded animal calls
        import soundtrack
        log(f"[{vid}] mixing the recorded soundtrack ...")
        mix = soundtrack.mix(video, g0, L / FPS, video.get("shots_per_scene", 3), total, seed=scene_seed(bi, vi, 78))
        music.write_wav(work / "audio.wav", mix[:N] * 0.8)
        music_meta = {"style": "recorded music", "tracks": video["soundtrack"]["music"],
                      "credits": video["soundtrack"].get("credits", [])}
    else:
        music_meta = _song_audio(video, specs, starts, g0, L, n, N, total, bi, vi, work, log)


    # ---- assemble with soft dissolves
    xf = XF / FPS
    inputs = ["intro.mp4"] + [f"scene_{k:02d}.mp4" for k in range(n)] + ["outro.mp4"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in inputs:
        cmd += ["-i", str(work / f)]
    cmd += ["-i", str(work / "audio.wav")]
    chain, prev = [], "[0:v]"
    for k in range(1, len(inputs)):
        off = starts[k] / FPS
        lab = f"[v{k}]"
        chain.append(f"{prev}[{k}:v]xfade=transition=fade:duration={xf}:offset={off:.4f}{lab}")
        prev = lab
    mp4 = out_dir / f"{vid}.mp4"
    cmd += ["-filter_complex", ";".join(chain), "-map", prev, "-map", f"{len(inputs)}:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-tune", "animation", "-pix_fmt", "yuv420p",
            "-af", "loudnorm=I=-16:TP=-2:LRA=11,alimiter=limit=0.7:attack=2:release=60:level=false", "-c:a", "aac", "-b:a", "192k",
            "-ar", "48000", "-t", str(total), "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)
    log(f"[{vid}] assembled in {(time.time() - t0) / 60:.1f} min total")

    # ---- thumbnail and YouTube text
    th = Image.open(work / f"thumb_{video.get('thumb_scene', 0):02d}.png").convert("RGB").resize((1280, 720), Image.LANCZOS)
    d = ImageDraw.Draw(th, "RGBA")
    f = ImageFont.truetype(FONT, 104)
    l, t_, r, b = f.getbbox(word)
    pw, ph = r - l + 90, b - t_ + 60
    x0 = (1280 - pw) // 2
    d.rounded_rectangle([x0, 40, x0 + pw, 40 + ph], radius=ph // 2, fill=(30, 40, 66, 160))
    d.text((x0 + 45 - l, 70 - t_), word, font=f, fill=(255, 252, 244))
    thumb = out_dir / f"{vid}.jpg"
    th.save(thumb, quality=92)
    chapter_starts = [starts[k + 1] / FPS + XF / FPS for k in range(n)] + [starts[-1] / FPS + XF / FPS]
    meta = {
        "id": vid, "engine": m.get("engine", 3), "file": mp4.name, "thumbnail": thumb.name, "title": video["title"],
        "description": description(video, chapter_starts, int(total), m.get("subject", "vehicles")),
        "tags": video["tags"], "categoryId": "27", "madeForKids": True, "privacyStatus": "private",
        "scenes": specs, "music": music_meta,
    }
    (out_dir / f"{vid}.json").write_text(json.dumps(meta, indent=2))
    (out_dir / f"{vid}.txt").write_text(
        f"TITLE\n{meta['title']}\n\nDESCRIPTION\n{meta['description']}\n\nTAGS\n{', '.join(meta['tags'])}\n\n"
        f"SETTINGS\nAudience: Yes, it's made for kids\nCategory: Education\nThumbnail: {thumb.name}\n")
    return meta


def description(video, chapter_starts, total, subject="vehicles"):
    def stamp(s):
        s = int(s)
        return f"{s // 60}:{s % 60:02d}"
    lines = ["0:00 Hello!"]
    for sc, st in zip(video["scenes"], chapter_starts[:-1]):
        lines.append(f"{stamp(st)} {sc['caption']}")
    lines.append(f"{stamp(chapter_starts[-1])} Bye-bye!")
    tags = " ".join("#" + t.replace(" ", "") for t in video["tags"][:3])
    about = None
    if subject == "animals":
        about = (f"About {total // 60} minutes of gentle 3D animation with real animated animals. Every animal is shown from "
                 "different angles with its name on screen, and you hear its real voice (recorded on real farms). Cheerful, "
                 "gentle music. Calm, friendly animals only. No flashing and nothing scary. Animal and nature models by "
                 "Quaternius and other OpenGameArt artists (CC0), skies by Poly Haven (CC0), animal recordings by Joseph "
                 "Sardin, BigSoundBank.com (CC0).") if video.get("soundtrack") else \
                (f"About {total // 60} minutes of gentle 3D animation with real animated animals. Every animal is shown from "
                 "three different angles (from the side, from the front, from close to the ground and from above), so "
                 "children can see what it really looks like and how it moves. Real animal sounds, a happy song without "
                 "words, and an animal sound to copy in every song. Calm, friendly animals only. No flashing and nothing "
                 "scary. Original animation, music and sound effects made for TheCalmLittleWorld; animal and nature models "
                 "by Quaternius and other OpenGameArt artists (CC0), skies by Poly Haven (CC0).")
    return "\n".join([
        video["hook"],
        "",
        video["learn"],
        "",
        about or (f"About {total // 60} minutes of colourful 3D animation. Every vehicle is shown from three different "
                  "angles (from the side, from the front, from above, from behind, and from the driver's seat), so children "
                  "can see what it really looks like. Real engine sounds, a happy song without words, and a fun vehicle noise "
                  "in every song. Every driver, pilot and captain follows the safety rules. No flashing and nothing scary. "
                  "Original animation, music and sound effects, made for TheCalmLittleWorld."),
        "",
        "Chapters:",
        *lines,
        "",
        *([f"Music: {c}" for c in video.get("soundtrack", {}).get("credits", [])] + [""] if video.get("soundtrack", {}).get("credits") else []),
        *([f"Sound: {c}" for c in video.get("soundtrack", {}).get("sound_credits", [])] + [""] if video.get("soundtrack", {}).get("sound_credits") else []),
        tags,
    ])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--manifest", default=str(ROOT / "plan" / "batch4.json"))
    ap.add_argument("--out", default=str(ROOT.parent / "output"))
    ap.add_argument("--seconds", type=float, default=600)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    render(a.video_id, a.manifest, a.out, a.seconds, a.workers, reuse=a.reuse)
