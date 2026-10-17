#!/usr/bin/env python3
"""Real-footage videos for TheCalmLittleWorld: free HD clips from Pixabay, gentle crossfades and the studio's own
calm music (studio/music.py), no voices.

    PIXABAY_API_KEY=... python footage/make.py footage/plans/test.json out/

A plan names the video and its segments; each segment is a Pixabay search and how many clips of how many seconds
to take from it. A clip is never used twice (ids are remembered in out/used_ids.json across videos), clips tagged
with anything scary or with people are skipped, and every clip used is listed in the credits file.
"""
import json
import os
import random
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "studio"))
import music  # noqa: E402

W, H, FPS = 1920, 1080, 30
XF = 1.2  # crossfade seconds
API = "https://pixabay.com/api/videos/"
UA = {"User-Agent": "TheCalmLittleWorld/1.0 (calm videos for toddlers)"}
AVOID = {"attack", "hunt", "hunting", "prey", "blood", "dead", "death", "fight", "fighting", "angry", "aggressive",
         "scary", "horror", "halloween", "snake", "spider", "shark", "teeth", "bite", "cage", "zoo", "slaughter",
         "meat", "butcher", "storm", "fire", "accident", "crash", "smoke", "night", "dark", "fireworks", "flash",
         "people", "person", "man", "woman", "girl", "boy", "child", "children", "kid", "baby", "hand", "hands",
         "human", "family", "couple", "text", "logo", "slow motion", "timelapse", "time lapse", "drone"}


def log(*a):
    print(*a, flush=True)


def search(key, query, page=1):
    q = urllib.parse.urlencode(dict(key=key, q=query, safesearch="true", per_page=100, page=page, order="popular"))
    with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=60) as r:
        return json.load(r).get("hits", [])


def rendition(hit):
    """The 1080p file if there is one (a 4K original is twice the download for nothing)."""
    vids = hit.get("videos", {})
    for k in ("medium", "large"):
        v = vids.get(k) or {}
        if v.get("url") and v.get("width", 0) >= W and v.get("height", 0) >= H:
            return v
    return None


def safe(hit):
    tags = {t.strip().lower() for t in hit.get("tags", "").split(",")}
    words = set(" ".join(tags).split())
    return not (tags & AVOID or words & AVOID)


def pick(key, query, n, seconds, used, rng):
    picked = []
    for page in (1, 2):
        hits = [h for h in search(key, query, page) if h["id"] not in used and h.get("duration", 0) >= seconds + 1
                and safe(h) and rendition(h)]
        rng.shuffle(hits)
        for h in hits:
            if len(picked) == n:
                return picked
            picked.append(h)
            used.add(h["id"])
        if len(picked) == n:
            break
        time.sleep(1)
    if len(picked) < n:
        log(f"  only {len(picked)} of {n} clips for '{query}'")
    return picked


def fetch(url, path):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r, open(path, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            return
        except Exception as e:  # noqa: BLE001  (network hiccups: retry)
            log(f"  download retry {attempt + 1}: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"could not download {url}")


def prepare(src, dst, start, seconds):
    """Trim, fill 1920x1080 (crop, never stretch), 30 fps, no audio, gently stabilised exposure."""
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,"
          f"deflicker=size=5,format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(src), "-t", f"{seconds:.2f}",
                    "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(dst)], check=True)


def join(parts, durs, dst):
    """Crossfade every clip into the next, fade in from and out to black."""
    inputs, chain = [], []
    for p in parts:
        inputs += ["-i", str(p)]
    prev, t = "[0:v]", durs[0]
    for i in range(1, len(parts)):
        off = t - XF
        chain.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[v{i}]")
        prev, t = f"[v{i}]", off + durs[i]
    total = t
    chain.append(f"{prev}fade=t=in:st=0:d=1.5,fade=t=out:st={total - 2:.3f}:d=2,format=yuv420p[out]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(chain), "-map", "[out]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS), str(dst)], check=True)
    return total


def make(plan, out_dir):
    key = os.environ["PIXABAY_API_KEY"]
    out_dir = Path(out_dir)
    work = out_dir / "work" / plan["id"]
    work.mkdir(parents=True, exist_ok=True)
    used_path = out_dir / "used_ids.json"
    used = set(json.loads(used_path.read_text())) if used_path.exists() else set()
    rng = random.Random(plan.get("seed", 1))

    clips = []
    for seg in plan["segments"]:
        log(f"searching '{seg['query']}'")
        for h in pick(key, seg["query"], seg["clips"], seg["seconds"], used, rng):
            clips.append((seg, h))

    parts, durs, credits = [], [], []
    for i, (seg, h) in enumerate(clips):
        r = rendition(h)
        src = work / f"src_{h['id']}.mp4"
        if not src.exists():
            fetch(r["url"], src)
        d = seg["seconds"]
        start = max(0.0, (h["duration"] - d) / 2)  # the middle of the clip: no fade-ins or edits from the source
        dst = work / f"part_{i:03d}.mp4"
        prepare(src, dst, start, d)
        src.unlink(missing_ok=True)
        parts.append(dst)
        durs.append(d)
        credits.append(f"{h['pageURL']}  (by {h.get('user', '?')}, Pixabay Content License)")
        log(f"clip {i + 1}/{len(clips)}: {h['id']} {seg['query']!r} {r['width']}x{r['height']}")

    silent = work / "video.mp4"
    total = join(parts, durs, silent)
    tune, info = music.compose(plan.get("seed", 1), total, inst=plan.get("instrument"))
    wav = work / "music.wav"
    music.write_wav(wav, tune)
    final = out_dir / f"{plan['id']}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", "loudnorm=I=-18:TP=-2:LRA=7", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart", str(final)], check=True)
    (out_dir / f"{plan['id']}_credits.txt").write_text(
        f"{plan.get('title', plan['id'])}\nMusic: original, made by TheCalmLittleWorld studio ({info['instrument']}).\n"
        f"Footage (free to use, Pixabay Content License):\n" + "\n".join(credits) + "\n")
    used_path.write_text(json.dumps(sorted(used)))
    for p in parts:
        p.unlink(missing_ok=True)
    log(f"done: {final} ({total:.0f} s, {len(parts)} clips, music {info})")
    return final


if __name__ == "__main__":
    plan = json.load(open(sys.argv[1]))
    out = sys.argv[2] if len(sys.argv) > 2 else "out"
    for p in plan["videos"] if "videos" in plan else [plan]:
        make(p, out)
