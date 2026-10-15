#!/usr/bin/env python3
"""Render one finished video (picture + music + thumbnail + YouTube metadata).

    python studio/produce.py 01-sailboats-mountain-lake            # full 10:00 video
    python studio/produce.py 01-sailboats-mountain-lake --seconds 60 --out /tmp/preview
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import music  # noqa: E402
from art import H, W, TIMES, mix  # noqa: E402
from scenes import FONT, FPS, Scene, smooth  # noqa: E402

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "plan" / "manifest.json"
INTRO, OUTRO, XFADE = 6.0, 7.0, 3.0


def load_video(vid):
    m = json.loads(MANIFEST.read_text())
    for i, v in enumerate(m["videos"]):
        if v["id"] == vid:
            return i, v, m
    raise SystemExit(f"unknown video id {vid}")


def scene_seed(video_index, scene_index):
    return 10007 * (video_index + 1) + 101 * scene_index + 7


def timeline(n, total):
    """Start time and length of each segment: intro, n scenes, outro (overlapping by XFADE)."""
    L = (total - INTRO - OUTRO + (n + 1) * XFADE) / n
    segs, t = [("intro", 0.0, INTRO)], INTRO - XFADE
    for k in range(n):
        segs.append((k, t, L))
        t += L - XFADE
    segs.append(("outro", t, OUTRO))
    return segs, L


def card(lines, time_of_day):
    top, bot = TIMES[time_of_day][0], TIMES[time_of_day][1]
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        grad.putpixel((0, y), mix(top, bot, y / H))
    img = grad.resize((W, H)).convert("RGBA")
    d = ImageDraw.Draw(img)
    y = H * 0.36
    for text, size, alpha in lines:
        f = ImageFont.truetype(FONT, size)
        l, t, r, b = f.getbbox(text)
        d.text(((W - (r - l)) / 2 - l, y - t + 3), text, font=f, fill=(40, 50, 80, 60))
        d.text(((W - (r - l)) / 2 - l, y - t), text, font=f, fill=(255, 252, 244, alpha))
        y += (b - t) + size * 0.55
    return img


def chapters(video, segs):
    out = ["0:00 Hello!"]
    for k, start, _ in segs[1:-1]:
        s = int(start + XFADE)
        out.append(f"{s // 60}:{s % 60:02d} {video['scenes'][k]['caption']}")
    s = int(segs[-1][1] + XFADE)
    out.append(f"{s // 60}:{s % 60:02d} Bye-bye!")
    return out


def description(video, segs, total):
    tags = " ".join("#" + t.replace(" ", "") for t in video["tags"][:3])
    return "\n".join([
        f"{video['hook']} No flashing, no fast cuts, no loud sounds.",
        "",
        video["learn"],
        "",
        f"About {total // 60} minutes of slow, quiet viewing for quiet time, snack time and the wind-down "
        "before a nap. Original animation and an original soft instrumental soundtrack, made for "
        "TheCalmLittleWorld. Every vehicle is shown moving slowly and safely.",
        "",
        "Chapters:",
        *chapters(video, segs),
        "",
        tags,
    ])


def thumbnail(scene, word, path):
    img = scene.frame(min(30.0, scene.D / 2)).convert("RGB").resize((1280, 720), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(FONT, 112)
    l, t, r, b = f.getbbox(word)
    pw, ph = r - l + 90, b - t + 60
    x0, y0 = (1280 - pw) // 2, 60
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph // 2, fill=(30, 40, 66, 120))
    d.text((x0 + 45 - l, y0 + 30 - t), word, font=f, fill=(255, 252, 244))
    img.save(path, quality=92)


def render(vid, out_dir, total=None, threads=2, crf=21, log=print):
    vi, video, manifest = load_video(vid)
    total = total or manifest["target_seconds"]
    out_dir = Path(out_dir)
    work = out_dir / "work" / vid
    work.mkdir(parents=True, exist_ok=True)
    specs = []
    for k, s in enumerate(video["scenes"]):
        s = dict(s)
        s["seed"] = scene_seed(vi, k)
        specs.append(s)
    segs, L = timeline(len(specs), total)

    # --- music (Sound Designer)
    t0 = time.time()
    mu = video.get("music", {})
    wav = work / "music.wav"
    mono, info = music.compose(scene_seed(vi, 99), total + 1, root=mu.get("root"), bpm=mu.get("bpm"),
                               inst=mu.get("instrument"), amb=mu.get("ambience"))
    music.write_wav(wav, mono)
    log(f"[{vid}] music: {info['instrument']} {info['bpm']}bpm root {info['root']} ({time.time() - t0:.0f}s)")

    # --- picture (Animators + Editor), piped straight into the encoder
    mp4 = out_dir / f"{vid}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(wav), "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-tune", "animation",
           "-pix_fmt", "yuv420p", "-threads", str(threads),
           "-af", "loudnorm=I=-18:TP=-3:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", str(total), "-movflags", "+faststart", str(mp4)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    intro = card([(video["word"], 150, 255), ("TheCalmLittleWorld", 52, 220)], specs[0]["time"])
    outro = card([(f"Bye-bye, {video['word'].lower()}!", 120, 255), ("See you next time", 56, 220)],
                 specs[-1]["time"])
    live, keyframes = {}, []
    nframes = int(total * FPS)
    t0 = time.time()
    for fi in range(nframes):
        t = fi / FPS
        layers = []
        for key, start, length in segs:
            if start <= t < start + length:
                local = t - start
                a = 1.0
                if key != "intro" and local < XFADE:
                    a = smooth(local / XFADE)
                layers.append((key, local, a))
        frame = None
        for key, local, a in layers:
            if key == "intro":
                img = intro
            elif key == "outro":
                img = outro
            else:
                if key not in live:
                    live[key] = Scene(specs[key], L)
                    for old in [k for k in live if k != key and k < key - 1]:
                        del live[old]
                img = live[key].frame(local)
                if abs(local - L / 2) < 0.5 / FPS:
                    keyframes.append((key, img.convert("RGB").resize((160, 90))))
            frame = img if frame is None else Image.blend(frame, img, a)
        enc.stdin.write(frame.convert("RGB").tobytes())
        if fi % (FPS * 60) == 0 and fi:
            el = time.time() - t0
            log(f"[{vid}] {t / 60:.0f}/{total / 60:.0f} min rendered, eta {el / fi * (nframes - fi) / 60:.1f} min")
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError(f"encoder failed for {vid}")
    log(f"[{vid}] picture done in {(time.time() - t0) / 60:.1f} min")

    # --- thumbnail + metadata (Publisher's packet)
    thumb = out_dir / f"{vid}.jpg"
    tscene = Scene(specs[0], L)
    tscene.caption = None  # thumbnails never carry scene captions
    thumbnail(tscene, video["word"], thumb)
    for key, im in keyframes:
        im.save(work / f"key_{key:02d}.png")
    meta = {
        "id": vid,
        "file": mp4.name,
        "thumbnail": thumb.name,
        "title": video["title"],
        "description": description(video, segs, int(total)),
        "tags": video["tags"],
        "categoryId": "27",
        "madeForKids": True,
        "privacyStatus": "private",
        "scenes": specs,
        "music": info,
    }
    (out_dir / f"{vid}.json").write_text(json.dumps(meta, indent=2))
    (out_dir / f"{vid}.txt").write_text(
        f"TITLE\n{meta['title']}\n\nDESCRIPTION\n{meta['description']}\n\nTAGS\n{', '.join(meta['tags'])}\n\n"
        "SETTINGS\nAudience: Yes, it's made for kids\nCategory: Education\nThumbnail: "
        f"{thumb.name}\n")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--out", default=str(ROOT.parent / "output"))
    ap.add_argument("--seconds", type=float, default=None, help="shorter preview length")
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    render(a.video_id, a.out, a.seconds, a.threads)
