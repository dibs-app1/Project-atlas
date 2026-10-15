#!/usr/bin/env python3
"""Studio Manager: runs the whole production like a small studio.

    python studio/manager.py                 # produce all 10 videos (about 1 hour on 4 cores)
    python studio/manager.py --only 01-...   # one video
    python studio/manager.py --plan-only     # gates only, no rendering

Stages (each one is a gate; nothing moves on until it passes):
  1. Producer         - plan check: 10 videos, all six vehicle types, own settings per type
  2. Safety Reviewer  - every scene checked against the safe-driving rules
  3. Continuity Clerk - every scene is new: never used before in this batch or any past batch
  4. Crews            - Animator + Sound Designer + Editor render each video (in parallel)
  5. QA Inspector     - length, loudness, no flashing, no reused scenes, YouTube limits
  6. Publisher        - writes the morning report; upload.py sends passed videos as PRIVATE
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa  # noqa: E402
from produce import render, scene_seed  # noqa: E402
from scenes import safety_review  # noqa: E402

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "plan" / "scene_ledger.json"
VEHICLES = {"boats", "airplanes", "cars", "trains", "hot air balloons", "helicopters"}


def say(role, msg):
    print(f"{dt.datetime.now():%H:%M:%S}  {role:<17} {msg}", flush=True)


def fingerprint(scene):
    """What makes a scene a scene: place, light, vehicle, action. Captions and seeds don't count."""
    core = {k: scene.get(k) for k in ("setting", "time", "vehicle", "motion", "direction", "extras", "count")}
    if scene.get("script"):  # engine-2 scenes are defined by their script and weather
        core.update(script=scene["script"], weather=scene.get("weather", "clear"))
    core["extras"] = sorted(core["extras"] or [])
    core["direction"] = core["direction"] or "right"
    return hashlib.sha1(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]


def producer_gate(m):
    vids = m["videos"]
    problems = []
    want = m.get("count", 10)
    if len(vids) != want:
        problems.append(f"need {want} videos, have {len(vids)}")
    missing = set(m.get("require", VEHICLES)) - {v["vehicle"] for v in vids}
    if missing:
        problems.append(f"vehicle types missing: {sorted(missing)}")
    for key in ("id", "title"):
        seen = [v[key] for v in vids]
        if len(set(seen)) != len(seen):
            problems.append(f"duplicate {key}")
    for v in vids:
        if len(v["title"]) > 100:
            problems.append(f"{v['id']}: title is {len(v['title'])} chars (YouTube max 100)")
    owner = {}
    for v in vids:
        for s in v["scenes"]:
            place = s.get("setting") or s.get("script")
            if owner.setdefault(place, v["vehicle"]) != v["vehicle"]:
                problems.append(f"setting '{place}' used by both {owner[place]} and {v['vehicle']}")
    return problems


def safety_gate(m):
    problems = []
    if m.get("engine") == 2:
        from engine2.safety import review
    else:
        review = safety_review
    for vi, v in enumerate(m["videos"]):
        for k, s in enumerate(v["scenes"]):
            for p in review(s):
                problems.append(f"{v['id']} scene {k + 1}: {p}")
    return problems


def continuity_gate(m, ledger):
    problems, seen = [], {}
    for v in m["videos"]:
        for k, s in enumerate(v["scenes"]):
            fp = fingerprint(s)
            where = f"{v['id']} scene {k + 1}"
            if fp in seen:
                problems.append(f"{where} repeats {seen[fp]}")
            seen[fp] = where
            past = ledger.get(fp)
            if past and past["video"] != v["id"]:
                problems.append(f"{where} was already used in {past['video']} ({past['date']})")
    return problems


def crew(vid, out_dir, threads, manifest=None, engine=1):
    t0 = time.time()
    if engine == 2:
        from produce2 import render as render2
        render2(vid, manifest, out_dir, log=lambda msg: say("Crew", msg))
    else:
        render(vid, out_dir, threads=threads, log=lambda msg: say("Crew", msg))
    return vid, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "output"))
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--crews", type=int, default=2, help="videos rendered at the same time")
    ap.add_argument("--threads", type=int, default=2, help="encoder threads per crew")
    ap.add_argument("--plan-only", action="store_true")
    ap.add_argument("--manifest", default=str(ROOT / "plan" / "manifest.json"))
    a = ap.parse_args()

    m = json.loads(Path(a.manifest).read_text())
    engine = m.get("engine", 1)
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    say("Manager", f"Good evening. Today's order: {len(m['videos'])} videos for {m['channel']}.")

    for role, gate in (("Producer", lambda: producer_gate(m)), ("Safety Reviewer", lambda: safety_gate(m)),
                       ("Continuity Clerk", lambda: continuity_gate(m, ledger))):
        problems = gate()
        if problems:
            for p in problems:
                say(role, "REJECTED " + p)
            say("Manager", f"{role} gate failed. Fix the plan and run again.")
            sys.exit(1)
        say(role, "approved")
    if a.plan_only:
        return

    ids = a.only or [v["id"] for v in m["videos"]]
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if engine == 2:  # each engine-2 video already spreads its scenes over every core
        for vid in ids:
            say("Manager", f"Scene crews: please make {vid}")
            _, secs = crew(vid, str(out_dir), a.threads, a.manifest, 2)
            say("Manager", f"received {vid} ({secs / 60:.1f} min). Sending to QA.")
    else:
        say("Manager", f"Assigning {len(ids)} videos to {a.crews} crews.")
        with ProcessPoolExecutor(max_workers=a.crews) as pool:
            jobs = {}
            for n, vid in enumerate(ids):
                say("Manager", f"Crew {n % a.crews + 1}: please make {vid}")
                jobs[pool.submit(crew, vid, str(out_dir), a.threads)] = vid
            for f in as_completed(jobs):
                vid, secs = f.result()
                say("Manager", f"received {vid} ({secs / 60:.1f} min). Sending to QA.")

    say("QA Inspector", "checking every finished video")
    report = qa.main(out_dir, a.manifest)
    passed = [r["id"] for r in report["videos"] if r["pass"]]

    today = dt.date.today().isoformat()
    for v in m["videos"]:
        if v["id"] in passed:
            for k, s in enumerate(v["scenes"]):
                ledger[fingerprint(s)] = {"video": v["id"], "scene": k + 1, "date": today}
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True))

    lines = [f"# Morning report: {m['channel']}", "",
             f"{len(passed)} of {len(ids)} videos passed every check (total studio time "
             f"{(time.time() - t0) / 60:.0f} min).", "",
             "| # | Video | Length | Loudness | Flash check | Result |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(report["videos"], 1):
        c = r["checks"]
        lines.append(f"| {i} | {r['id']} | {c.get('duration', {}).get('detail', '-')} | "
                     f"{c.get('loudness', {}).get('detail', '-')} | {c.get('no_flashing', {}).get('detail', '-')} | "
                     f"{'PASS' if r['pass'] else 'FAIL'} |")
    u = report["unique_scenes"]
    lines += ["", f"Scene uniqueness: {'PASS' if u['pass'] else 'FAIL'}: {u['scenes_compared']} scenes, "
              f"closest two differ by {u['closest_difference']} (0 would be identical).", "",
              "Each video has a `.txt` with the title, description (with chapters) and tags to paste into "
              "YouTube Studio, and a `.jpg` thumbnail. Set **Made for kids: Yes**."]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")
    say("Manager", f"Done. {len(passed)}/{len(ids)} ready. Report: {out_dir / 'REPORT.md'}")
    sys.exit(0 if len(passed) == len(ids) else 1)


if __name__ == "__main__":
    main()
