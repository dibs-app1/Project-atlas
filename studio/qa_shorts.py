#!/usr/bin/env python3
"""QA for Shorts: vertical 1080x1920, under 60 s, loudness, no loud peaks, no flashing, YouTube limits."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine2.safety import review  # noqa: E402
from qa import ffprobe, flash_scan, loudness  # noqa: E402


def main(out_dir):
    out_dir = Path(out_dir)
    results, ok_all = [], True
    for p in sorted(out_dir.glob("*.json")):
        if p.name == "qa_report.json":
            continue
        m = json.loads(p.read_text())
        mp4 = out_dir / m["file"]
        info = ffprobe(mp4)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        dur = float(info["format"]["duration"])
        lufs, peak = loudness(mp4)
        jump, _ = flash_scan(mp4)
        issues = [f"shot {i + 1}: {x}" for i, s in enumerate(m["scenes"])
                  for x in review(dict(s, caption=s.get("caption") or "shot"))]
        checks = {
            "vertical": ((v["width"], v["height"]) == (1080, 1920), f"{v['width']}x{v['height']}"),
            "under_60s": (dur <= 59.5, f"{dur:.1f}s"),
            "loudness": (-18 <= lufs <= -12, f"{lufs} LUFS"),
            "no_loud_peaks": (peak <= -1.0, f"peak {peak} dBFS"),
            "no_flashing": (jump <= 12.0, f"max change {jump:.1f}/255"),
            "safety": (not issues, "; ".join(issues) or "all shots approved"),
            "title_length": (len(m["title"]) <= 100, f"{len(m['title'])} chars"),
            "made_for_kids": (m.get("madeForKids") is True, str(m.get("madeForKids"))),
        }
        ok = all(c[0] for c in checks.values())
        ok_all &= ok
        results.append({"id": m["id"], "pass": ok,
                        "checks": {k: {"pass": c[0], "detail": c[1]} for k, c in checks.items()}})
        print(("PASS " if ok else "FAIL ") + m["id"])
        for k, c in checks.items():
            print(f"   {'ok' if c[0] else 'XX'} {k}: {c[1]}")
    (out_dir / "qa_report.json").write_text(json.dumps({"shorts": results}, indent=2))
    return ok_all


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else "output/shorts") else 1)
