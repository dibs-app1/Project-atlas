#!/usr/bin/env python3
"""Real-footage videos for TheCalmLittleWorld: free HD clips from Pixabay, gentle crossfades and the studio's own
calm music (studio/music.py), no voices.

    PIXABAY_API_KEY=... python footage/make.py footage/plans/animals1.json out/

A plan lists videos; each video is a run of chapters, and each chapter a few Pixabay searches with how many clips to
take. A clip is never used twice (ids are remembered in footage/used_ids.json across runs). Clips tagged with anything
scary or with people are skipped, and so are clips with black bars or a cut in the middle. Each video gets an mp4, a
thumbnail and a .txt with its title, description (with chapters and footage credits) and tags.
"""
import json
import os
import random
import re
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
XF = 1.5  # crossfade seconds
GROUP = 12  # clips joined per ffmpeg pass (keeps memory low)
API = "https://pixabay.com/api/videos/"
UA = {"User-Agent": "TheCalmLittleWorld/1.0 (calm videos for toddlers)"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
USED = ROOT / "footage" / "used_ids.json"
AVOID = {"attack", "hunt", "hunting", "prey", "blood", "dead", "death", "fight", "fighting", "angry", "aggressive",
         "scary", "horror", "halloween", "snake", "spider", "shark", "teeth", "bite", "cage", "zoo", "slaughter",
         "meat", "butcher", "storm", "fire", "accident", "crash", "smoke", "night", "dark", "fireworks", "flash",
         "people", "person", "man", "woman", "girl", "boy", "child", "children", "kid", "baby", "hand", "hands",
         "human", "family", "couple", "text", "logo", "timelapse", "drone", "fast", "sick", "injured", "rain"}


def log(*a):
    print(*a, flush=True)


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def search(key, query, page=1):
    q = urllib.parse.urlencode(dict(key=key, q=query, safesearch="true", per_page=100, page=page, order="popular"))
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=60) as r:
                return json.load(r).get("hits", [])
        except Exception as e:  # noqa: BLE001
            log(f"  search retry {attempt + 1}: {e}")
            time.sleep(2 + 3 * attempt)
    return []


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
    return not (tags & AVOID or set(" ".join(tags).split()) & AVOID)


def fetch(url, path):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r, open(path, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            return True
        except Exception as e:  # noqa: BLE001  (network hiccups: retry)
            log(f"  download retry {attempt + 1}: {e}")
            time.sleep(2 ** attempt)
    return False


def clean(src, start, seconds):
    """No black bars (letterboxed or pillarboxed sources) and no cut inside the part we use."""
    out = subprocess.run(["ffmpeg", "-ss", f"{start:.2f}", "-t", f"{seconds:.2f}", "-i", str(src), "-vf",
                          "cropdetect=limit=24:round=2:reset=0,select='gt(scene,0.32)',metadata=print", "-an", "-f",
                          "null", "-"], capture_output=True, text=True).stderr
    crops = re.findall(r"crop=(\d+):(\d+):", out)
    if crops:
        cw, ch = map(int, crops[-1])
        size = re.search(r"Stream.*Video.* (\d{3,5})x(\d{3,5})", out)
        if size:
            sw, sh = int(size.group(1)), int(size.group(2))
            if cw < 0.94 * sw or ch < 0.94 * sh:
                return "black bars"
    if "lavfi.scene_score" in out:
        return "a cut"
    return None


def prepare(src, dst, start, seconds):
    """Trim, fill 1920x1080 (crop, never stretch), 30 fps, no audio, steady exposure."""
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,deflicker=size=5,format=yuv420p"
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(src), "-t", f"{seconds:.2f}", "-an",
         "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(dst)])


def xfade(parts, durs, dst, fade_ends=False):
    inputs, chain = [], []
    for p in parts:
        inputs += ["-i", str(p)]
    prev, t = "[0:v]", durs[0]
    for i in range(1, len(parts)):
        off = t - XF
        chain.append(f"{prev}[{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[v{i}]")
        prev, t = f"[v{i}]", off + durs[i]
    tail = f",fade=t=in:st=0:d=2,fade=t=out:st={t - 3:.3f}:d=3" if fade_ends else ""
    chain.append(f"{prev}format=yuv420p{tail}[out]")
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(chain), "-map", "[out]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "16" if not fade_ends else "21", "-r", str(FPS), str(dst)])
    return t


def join(parts, durs, dst, work):
    """Crossfade everything in groups, then the groups (same fades at the seams), fading in from and out to black."""
    if len(parts) <= GROUP:
        return xfade(parts, durs, dst, fade_ends=True)
    gparts, gdurs = [], []
    for g in range(0, len(parts), GROUP):
        p = work / f"group_{g // GROUP:02d}.mp4"
        gdurs.append(xfade(parts[g:g + GROUP], durs[g:g + GROUP], p))
        gparts.append(p)
    total = xfade(gparts, gdurs, dst, fade_ends=True)
    for p in gparts:
        p.unlink(missing_ok=True)
    return total


def stamp(s):
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


def thumbnail(video_path, at, title, dst, top=False):
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    frame = dst.with_suffix(".frame.png")
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", str(video_path), "-frames:v", "1", str(frame)])
    img = Image.open(frame).convert("RGB").resize((1280, 720), Image.LANCZOS)
    frame.unlink()
    d = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.truetype(FONT, 92)
    words, lines = title.split(), [""]
    for w in words:
        if d.textlength((lines[-1] + " " + w).strip(), font=font) > 1100:
            lines.append(w)
        else:
            lines[-1] = (lines[-1] + " " + w).strip()
    y = 44 if top else 720 - 70 - 104 * len(lines)
    pad = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(pad).rounded_rectangle((40, y - 24, 1240, y + 104 * len(lines) + 6), 36, fill=(255, 255, 255, 215))
    img = Image.alpha_composite(img.convert("RGBA"), pad.filter(ImageFilter.GaussianBlur(1))).convert("RGB")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        w = d.textlength(line, font=font)
        d.text(((1280 - w) / 2, y + i * 104), line, font=font, fill=(40, 70, 110))
    img.save(dst, quality=92)


def make(video, out_dir, key, used):
    out_dir = Path(out_dir)
    work = out_dir / "work" / video["id"]
    work.mkdir(parents=True, exist_ok=True)
    rng = random.Random(video.get("seed", 1))
    secs = video.get("clip_seconds", 10)
    parts, durs, credits, chapters = [], [], [], []
    t_now = 0.0
    goal = video.get("minutes", 10.25) * 60
    for ci, ch in enumerate(video["chapters"]):
        chapters.append((max(0.0, t_now), ch["title"]))
        queries = list(ch["queries"])
        if ci == len(video["chapters"]) - 1:  # the last chapter tops the video up to its full length
            queries += [(q, 99) for q in video.get("extra", [])]
        for query, n in queries:
            n = min(n, max(0, int((goal - t_now) / (secs - XF)) + 1)) if ci == len(video["chapters"]) - 1 else n
            if n == 0:
                break
            got = 0
            pool = [h for page in (1, 2) for h in search(key, query, page)]
            pool = [h for h in pool if h["id"] not in used and h.get("duration", 0) >= secs + 2 and safe(h) and rendition(h)]
            rng.shuffle(pool)
            for h in pool:
                if got == n:
                    break
                src = work / f"src_{h['id']}.mp4"
                if not fetch(rendition(h)["url"], src):
                    continue
                start = max(0.0, (h["duration"] - secs) / 2)  # the middle: no fades or edits from the source
                why = clean(src, start, secs)
                if why:
                    log(f"  skip {h['id']} ({query}): {why}")
                    src.unlink(missing_ok=True)
                    used.add(h["id"])
                    continue
                dst = work / f"part_{len(parts):03d}.mp4"
                prepare(src, dst, start, secs)
                src.unlink(missing_ok=True)
                used.add(h["id"])
                parts.append(dst)
                durs.append(secs)
                t_now += secs - XF
                credits.append(f"{h['pageURL']} by {h.get('user', '?')}")
                got += 1
            log(f"{video['id']}: {ch['title']} / {query}: {got}/{n} clips (total {len(parts)}, {t_now / 60:.1f} min)")
    silent = work / "video.mp4"
    total = join(parts, durs, silent, work)
    tune, info = music.compose(video.get("seed", 1), total, inst=video.get("instrument"))
    wav = work / "music.wav"
    music.write_wav(wav, tune)
    final = out_dir / f"{video['id']}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-af", "loudnorm=I=-18:TP=-2:LRA=7", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-shortest", "-movflags", "+faststart", str(final)])
    thumbnail(final, video.get("thumb_at", 40), video["thumb_text"], out_dir / f"{video['id']}.jpg")
    chap = [f"0:00 {chapters[0][1]}"] + [f"{stamp(t)} {c}" for t, c in chapters[1:]]
    desc = "\n".join([
        video["hook"], "", video["about"], "",
        f"About {round(total / 60)} minutes of real, calm footage with gentle music and no words: soft fades, no "
        "flashing, nothing scary. The music is original, made for TheCalmLittleWorld.", "",
        "Chapters:", *chap, "",
        "Footage: free videos from Pixabay (Pixabay Content License). Thank you to the filmmakers:", *credits, "",
        " ".join("#" + t.replace(" ", "") for t in video["tags"][:3])])
    (out_dir / f"{video['id']}.txt").write_text(
        f"TITLE:\n{video['title']}\n\nDESCRIPTION:\n{desc}\n\nTAGS:\n{', '.join(video['tags'])}\n\n"
        "AUDIENCE: Yes, it's made for kids.\n")
    silent.unlink(missing_ok=True)
    for p in parts:
        p.unlink(missing_ok=True)
    USED.write_text(json.dumps(sorted(used)))
    log(f"done: {final} ({total / 60:.1f} min, {len(parts)} clips, music {info})")
    return final, total


if __name__ == "__main__":
    plan = json.load(open(sys.argv[1]))
    out = sys.argv[2] if len(sys.argv) > 2 else "out"
    only = sys.argv[3] if len(sys.argv) > 3 else None
    key = os.environ["PIXABAY_API_KEY"]
    used = set(json.loads(USED.read_text())) if USED.exists() else set()
    for v in plan["videos"]:
        if not only or v["id"] == only:
            make(v, out, key, used)
