#!/usr/bin/env python3
"""QA Inspector: the final gate. A video ships only if every check passes.

    python studio/qa.py [output_dir]
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenes import safety_review  # noqa: E402

ROOT = Path(__file__).resolve().parent


def ffprobe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                          str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def loudness(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
                          "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = err[err.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    peak = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary).group(1))
    return i, peak


def flash_scan(path):
    """Largest frame-to-frame change in average brightness (0-255). Flashes are big jumps."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an",
                          "-vf", "scale=192:108,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
                          "-f", "null", "-"], capture_output=True, text=True).stdout
    ys = [float(v) for v in re.findall(r"YAVG=([\d.]+)", out)]
    jumps = [abs(b - a) for a, b in zip(ys, ys[1:])]
    return (max(jumps) if jumps else 0.0), len(ys)


def check_video(out_dir, meta, target):
    vid = meta["id"]
    res = {"id": vid, "checks": {}}

    def check(name, ok, detail):
        res["checks"][name] = {"pass": bool(ok), "detail": detail}

    mp4 = out_dir / meta["file"]
    if not mp4.exists():
        check("file", False, "missing")
        return res
    info = ffprobe(mp4)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    check("duration", abs(dur - target) <= 1.0, f"{dur:.1f}s (target {target}s)")
    check("resolution", (v["width"], v["height"]) == (1920, 1080), f"{v['width']}x{v['height']}")
    check("codec", v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p" and a and a[0]["codec_name"] == "aac",
          f"{v['codec_name']}/{v.get('pix_fmt')} + {a[0]['codec_name'] if a else 'no audio'}")
    lufs, peak = loudness(mp4)
    check("loudness", -21 <= lufs <= -15, f"{lufs} LUFS (calm target -18)")
    check("no_loud_peaks", peak <= -1.0, f"peak {peak} dBFS")
    jump, frames = flash_scan(mp4)
    check("no_flashing", jump <= 12.0, f"max brightness change between frames {jump:.1f}/255 over {frames} frames")
    issues = [f"scene {i + 1}: {p}" for i, s in enumerate(meta["scenes"]) for p in safety_review(s)]
    check("safety", not issues, "; ".join(issues) or f"all {len(meta['scenes'])} scenes approved")
    check("made_for_kids", meta.get("madeForKids") is True, str(meta.get("madeForKids")))
    check("title_length", len(meta["title"]) <= 100, f"{len(meta['title'])} chars")
    check("description_length", len(meta["description"]) <= 5000, f"{len(meta['description'])} chars")
    check("tags_length", sum(len(t) + 1 for t in meta["tags"]) <= 500, f"{len(meta['tags'])} tags")
    check("thumbnail", (out_dir / meta["thumbnail"]).exists(), meta["thumbnail"])
    return res


def check_unique_scenes(out_dir, metas):
    """Every scene's middle frame must differ visibly from every other scene in the batch."""
    keys = []
    for m in metas:
        for p in sorted((out_dir / "work" / m["id"]).glob("key_*.png")):
            keys.append((f"{m['id']}#{p.stem[4:]}", Image.open(p).convert("RGB")))
    worst = (999.0, None)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            diff = ImageStat.Stat(ImageChops.difference(keys[i][1], keys[j][1])).mean
            d = sum(diff) / 3
            if d < worst[0]:
                worst = (d, (keys[i][0], keys[j][0]))
    return worst, len(keys)


def main(out_dir=None):
    out_dir = Path(out_dir or ROOT.parent / "output")
    manifest = json.loads((ROOT / "plan" / "manifest.json").read_text())
    target = manifest["target_seconds"]
    metas = [json.loads(p.read_text()) for p in sorted(out_dir.glob("*.json"))
             if p.name not in ("qa_report.json", "uploaded.json")]
    results = [check_video(out_dir, m, target) for m in metas]
    (worst, pair), n = check_unique_scenes(out_dir, metas)
    uniq_ok = n == 0 or worst > 3.0
    for r in results:
        r["pass"] = all(c["pass"] for c in r["checks"].values()) and uniq_ok
    report = {"videos": results,
              "unique_scenes": {"pass": uniq_ok, "scenes_compared": n,
                                "closest_pair": pair, "closest_difference": round(worst, 2)}}
    (out_dir / "qa_report.json").write_text(json.dumps(report, indent=2))
    for r in results:
        print(("PASS " if r["pass"] else "FAIL ") + r["id"])
        for name, c in r["checks"].items():
            if not c["pass"]:
                print(f"   x {name}: {c['detail']}")
    print(f"scene uniqueness: {'PASS' if uniq_ok else 'FAIL'} ({n} scenes, closest pair differs by {worst:.1f})")
    return report


if __name__ == "__main__":
    rep = main(sys.argv[1] if len(sys.argv) > 1 else None)
    sys.exit(0 if all(r["pass"] for r in rep["videos"]) else 1)
