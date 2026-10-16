#!/usr/bin/env python3
"""Render one engine-4 scene with Blender (run with the Python that has the `bpy` package).

    python studio/engine4/render4.py --manifest studio/plan/batch5.json --video 23-birds --scene 0 --out out/
    python studio/engine4/render4.py ... --seconds 6 --res 640     # quick look

A scene is written exactly like an engine-3 scene (scenery, actors on paths, three camera angles that
dissolve, sounds) but drawn by EEVEE, with artist-made animals (engine4.cast) and scenery props.
Outputs: scene_KK.mp4, sfx_KK.npy, key_KK.png and thumb_KK.png (the same files produce3 assembles).
"""
import argparse
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

FPS = 24
OUT_W, OUT_H = 1920, 1080


def scene_seed(bi, vi, k):
    return 1000 * bi + 37 * vi + k * 7 + 11


def load_spec(manifest, vid, k):
    m = json.load(open(manifest))
    vi = next(i for i, v in enumerate(m["videos"]) if v["id"] == vid)
    video = m["videos"][vi]
    s = dict(video["scenes"][k])
    s["seed"] = scene_seed(m.get("batch_index", 5), vi, k)
    s["index"] = k
    s.setdefault("theme", video.get("theme", "park"))
    return s


class Renderer4:
    def __init__(self, spec, D, res=1280, samples=4, work=None):
        from engine3.stage import Stage
        from engine4 import scenes5  # noqa: F401  (registers the scenes)
        from engine4.bridge import Bridge
        from engine3 import world as Wd
        self.spec, self.D = spec, D
        self.st = st = Stage(spec, D)
        look = getattr(st, "look", {}) or {}
        tod = spec.get("time", "day")
        sky = look.get("hdri")
        self.res = (res, res * 9 // 16)
        self.br = Bridge(time=tod, sun_dir=tuple(st.rend.light.dir), res=self.res, samples=samples,
                         sky_cols=(Wd.TIMES.get(tod, Wd.TIMES["day"])[0], Wd.TIMES.get(tod, Wd.TIMES["day"])[1]),
                         hdri=sky, hdri_strength=look.get("hdri_strength", 1.0), hdri_rot=look.get("hdri_rot", 0.0),
                         underwater=look.get("underwater"), fog=look.get("fog"))
        self.br.static_ids = {id(o.mesh) for o in st.static}
        self.work = Path(work or "/tmp")
        self.animals = {}
        self._props()
        self.br.fog_all()

    def _props(self):
        from engine4 import cast
        for item in getattr(self.st, "props", []):
            kind, pos, yaw, scale = item
            path = cast.find(kind) if "." in kind else cast.kit_file(kind, random.Random(hash((pos[0], pos[1])) & 0xFFFF))
            small = any(k in kind for k in ("grass", "flowers", "lilypad", "plant"))
            self.br.prop(path, pos, yaw, scale, shadow=not small, size=None if "." in kind else cast.KIT_SIZE.get(kind))

    def _animal(self, pose):
        from engine4 import cast, rigs
        key = pose.model.uid
        if key not in self.animals:
            info = pose.model.info
            inst = rigs.Instance(cast.find(info["file"]), length=pose.model.length, palette=info.get("palette"),
                                 texture=cast.find(info["texture"]) if info.get("texture") else None)
            gait = rigs.Gait(inst, walk_speed=info.get("walk", 1.0) * pose.model.length / info["length"],
                             run_speed=info.get("run", info.get("walk", 1.0) * 3.5), eat=info.get("eat", True))
            self.animals[key] = (inst, gait)
            self.br.fog_all()
        return self.animals[key]

    def pose_world(self, t, cam):
        st = self.st
        objs = list(st.static)
        seen = set()
        for a in st.actors:
            for o in a.objs(t):
                if getattr(o, "mesh", None) is None and hasattr(o, "model"):      # an animal
                    inst, gait = self._animal(o)
                    mood = o.model.mood_fn(t) if o.model.mood_fn else None
                    inst.place(o.pos, o.yaw, o.pitch, o.roll)
                    gait.update(t, o.v, mood)
                    seen.add(o.model.uid)
                else:
                    objs.append(o)
        for fn in st.dynamic:
            objs += fn(t, cam)
        self.br.sync(objs, 0)
        for uid, (inst, _) in self.animals.items():
            inst.hide(uid not in seen)

    def shot_image(self, k, t, path):
        from engine4.bridge import overlay
        t0, t1, rg = self.st.shots[k]
        cam = rg(t)
        self.pose_world(t, cam)
        self.br.camera(cam)
        img = self.br.render(path)
        fns = list(self.st.overlays)
        if k in self.st.cam_overlays:
            fns.append(self.st.cam_overlays[k])
        if fns:
            img = img.resize((OUT_W, OUT_H), Image.LANCZOS)
            img = overlay(img, cam, fns, t)
        return img.resize((OUT_W, OUT_H), Image.LANCZOS) if img.size != (OUT_W, OUT_H) else img

    def frame(self, t, path):
        XF = 1.2
        shots = self.st.shots
        for k, (t0, t1, rg) in enumerate(shots):
            if t0 <= t < t1:
                if k + 1 < len(shots) and t > t1 - XF / 2:
                    u = _smooth((t - (t1 - XF / 2)) / XF)
                    return Image.blend(self.shot_image(k, t, path), self.shot_image(k + 1, t, path), u)
                if k > 0 and t < t0 + XF / 2:
                    u = _smooth((t - (t0 - XF / 2)) / XF)
                    return Image.blend(self.shot_image(k - 1, t, path), self.shot_image(k, t, path), u)
                return self.shot_image(k, t, path)
        return self.shot_image(len(shots) - 1, t, path)


def _smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def render_scene(spec, frames, out_dir, res=1280, samples=4, log=print):
    from engine3 import sfx3
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    k = spec["index"]
    D = frames / FPS
    t0 = time.time()
    R = Renderer4(spec, D, res=res, samples=samples, work=out_dir)
    log(f"scene {k} ({spec['script']}): set up in {time.time() - t0:.0f}s, {len(R.st.static)} scenery objects, "
        f"{len(getattr(R.st, 'props', []))} props")
    mp4 = out_dir / f"scene_{k:02d}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                           str(mp4)], stdin=subprocess.PIPE)
    tmp = out_dir / f"_frame_{k:02d}.png"
    from flashguard import FlashGuard
    guard = FlashGuard()
    for i in range(frames):
        t = i / FPS
        img = guard(R.frame(t, tmp))
        ff.stdin.write(np.asarray(img.convert("RGB"), np.uint8).tobytes())
        if i == frames // 2:
            img.resize((160, 90)).save(out_dir / f"key_{k:02d}.png")
        if i == int(min(frames - 1, 8 * FPS)):
            img.save(out_dir / f"thumb_{k:02d}.png")
        if i % 48 == 0:
            el = time.time() - t0
            log(f"scene {k}: frame {i}/{frames} ({el / max(1, i):.1f}s per frame, {el / 60:.0f} min so far)")
    ff.stdin.close()
    ff.wait()
    np.save(out_dir / f"sfx_{k:02d}.npy", sfx3.render_scene(R.st, D, spec["theme"]).astype(np.float32))
    log(f"scene {k}: done in {(time.time() - t0) / 60:.1f} min")
    tmp.unlink(missing_ok=True)
    return mp4


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--scene", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=None, help="frames to render (default: the scene's full length)")
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--res", type=int, default=1280)
    ap.add_argument("--samples", type=int, default=4)
    a = ap.parse_args()
    spec = load_spec(a.manifest, a.video, a.scene)
    if a.frames:
        n = a.frames
    elif a.seconds:
        n = int(a.seconds * FPS)
    else:
        from produce2 import frames_plan
        m = json.load(open(a.manifest))
        video = next(v for v in m["videos"] if v["id"] == a.video)
        n, _ = frames_plan(len(video["scenes"]), int(600 * FPS))
    render_scene(spec, n, a.out, res=a.res, samples=a.samples)
