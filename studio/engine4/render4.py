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
    if video.get("style") or m.get("style"):
        s.setdefault("style", video.get("style") or m.get("style"))
    return s


class Renderer4:
    def __init__(self, spec, D, res=1280, samples=4, work=None):
        from engine3.stage import Stage
        from engine4 import scenes5  # noqa: F401  (registers the scenes)
        from engine4.bridge import Bridge
        from engine3 import world as Wd
        from engine4 import rigs
        self.spec, self.D = spec, D
        self.soft = spec.get("style") == "soft"
        rigs.SOFT = self.soft
        self.st = st = Stage(spec, D)
        look = getattr(st, "look", {}) or {}
        if self.soft and look.get("fog"):           # the soft look keeps the distance clear: thinner haze
            look["fog"] = (look["fog"][0], look["fog"][1] * 3.0)
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
        if self.soft:
            self.br.soft()
            self._grass()
        self._props()
        self.br.fog_all()
        if self.soft:
            self._aim_shots()

    def _aim_shots(self):
        """Keep every camera angle clear: if a fence, wall or tree comes between the camera and the hero animal,
        or another animal walks right up to the lens, try the same angle from the other side, closer or further
        away, and keep the first one that stays clear for the whole shot (or the least blocked one)."""
        import bpy
        from mathutils import Vector
        from engine3.stage import RIGS
        st = self.st
        hero = getattr(st, "hero", None)
        specs = getattr(st, "shot_specs", [])
        if hero is None or len(specs) != len(st.shots):
            return
        self.pose_world(0.0, st.shots[0][2](0.0))          # build every object once
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        skip = {"meadow", "blade", "cam", "sun"}
        for inst, _ in self.animals.values():
            skip |= {o.name for o in inst.meshes}
            if inst.arm is not None:
                skip.add(inst.arm.name)
        others = [a for a in st.actors if a is not hero and hasattr(a, "state") and hasattr(a, "model")
                  and getattr(a.model, "info", None) is not None]

        def blocked(c, h):
            d = h - c
            dist = float(np.linalg.norm(d))
            d = d / max(1e-9, dist)
            o, left = c.copy(), dist
            for _ in range(8):
                hit, loc, _n, _i, ob, _m = bpy.context.scene.ray_cast(dg, Vector(o), Vector(d), distance=left)
                if not hit:
                    return False
                loc = np.array(loc)
                name = ob.name if ob is not None else ""
                if name in skip or name.startswith(("eye_", "coat")) or loc[2] < 0.25:
                    step = float(np.linalg.norm(loc - o)) + 0.02
                    o, left = loc + d * 0.02, left - step
                    if left <= 0:
                        return False
                    continue
                return True
            return False

        def score(rg, t0, t1):
            bad = 0
            for t in np.linspace(t0 + 0.4, t1 - 0.4, 28):
                cam = rg(t)
                c = np.asarray(cam.pos, float)
                h = np.asarray(hero.state(t)[0], float) + (0, 0, hero.model.height * 0.55)
                if blocked(c, h):
                    bad += 1
                    continue
                fwd = np.asarray(cam.B[2], float)
                for a in others:
                    q = np.asarray(a.state(t)[0], float) + (0, 0, a.model.height * 0.5)
                    v = q - c
                    dd = float(np.linalg.norm(v))
                    if dd < max(1.0, 2.6 * a.model.length) and v @ fwd > 0.3 * dd:     # right in front of the lens
                        bad += 1
                        break
            return bad

        for k, ((t0, t1, rg), sp) in enumerate(zip(st.shots, specs)):
            if sp is None:
                continue
            name, kw, actor = sp
            if actor is not hero:
                continue
            base = score(rg, t0, t1)
            if base == 0:
                continue
            tries = []
            if name == "side":
                sd, dist = kw.get("side", -1), kw.get("dist")
                for s_, f in ((-sd, 1.0), (sd, 0.7), (-sd, 0.7), (sd, 1.35), (-sd, 1.35)):
                    k2 = dict(kw, side=s_)
                    if dist is not None:
                        k2["dist"] = dist * f
                    elif f != 1.0:
                        k2["dist"] = max(11.0, hero.model.length * 1.6 + 3.0) * f
                    tries.append(k2)
            elif name in ("front", "low"):
                off = kw.get("off", 7.0 if name == "front" else 5.0)
                for f in (-1.0, 0.7, -0.7, 1.5, -1.5):
                    tries.append(dict(kw, off=off * f))
            elif name == "orbit":
                for ph, f in ((math.pi, 1.0), (0.0, 0.7), (math.pi, 0.7), (math.pi / 2, 1.0), (-math.pi / 2, 1.0)):
                    tries.append(dict(kw, phase=kw.get("phase", 0.0) + ph, radius=(kw.get("radius") or max(12.0, hero.model.length * 1.5)) * f))
            elif name == "chase":
                tries = [dict(kw, back=(kw.get("back") or max(10.0, hero.model.length * 1.4)) * f) for f in (0.7, 1.3)]
            best, best_s, best_kw = rg, base, kw
            for k2 in tries:
                r2 = RIGS[name](actor, **k2)
                s2 = score(r2, t0, t1)
                if s2 < best_s:
                    best, best_s, best_kw = r2, s2, k2
                if s2 == 0:
                    break
            if best is not rg:
                st.shots[k] = (t0, t1, best)
                specs[k] = (name, best_kw, actor)
            print(f"camera {k} ({name}): {base} blocked samples -> {best_s} with {({a: round(b, 2) if isinstance(b, float) else b for a, b in best_kw.items() if a != 't_pass'})}", flush=True)

    def _grass(self):
        """Real grass where the scene's ground is meadow, around where the hero animal goes."""
        g = getattr(self.st, "grass", None)
        hero = getattr(self.st, "hero", None)
        if not g or hero is None:
            return
        P = np.array([hero.state(t)[0] for t in np.linspace(0, self.D, 25)])
        m = g.get("margin", 40.0)
        x0, x1 = P[:, 0].min() - m, P[:, 0].max() + m
        y0, y1 = P[:, 1].min() - m, P[:, 1].max() + m
        bx0, bx1, by0, by1 = g.get("bounds", (-1e9, 1e9, -1e9, 1e9))
        self.br.grass(max(x0, bx0), min(x1, bx1), max(y0, by0), min(y1, by1), avoid=g.get("avoid"),
                      density=g.get("density", 34.0))

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
                                 texture=cast.find(info["texture"]) if info.get("texture") else None,
                                 eyes=info.get("eyes"), coat=cast.COATS.get(pose.model.kind))
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
        if self.soft and getattr(self.st, "hero", None) is not None:
            hp = np.asarray(self.st.hero.state(t)[0], float) + (0, 0, self.st.hero.model.height * 0.6)
            self.br.focus(np.linalg.norm(hp - np.asarray(cam.pos, float)))
        img = self.br.render(path)
        fns = list(self.st.overlays)
        if k in self.st.cam_overlays:
            fns.append(self.st.cam_overlays[k])
        if fns:
            img = img.resize((OUT_W, OUT_H), Image.LANCZOS)
            img = overlay(img, cam, fns, t)
        return img.resize((OUT_W, OUT_H), Image.LANCZOS) if img.size != (OUT_W, OUT_H) else img

    def frame(self, t, path):
        img = self._frame(t, path)
        return self._label(img, t) if self.spec.get("label") else img

    LABEL_COLS = [(255, 138, 60), (70, 160, 240), (240, 90, 140), (90, 180, 80), (160, 110, 230), (240, 170, 30)]

    def _label(self, img, t):
        """The animal's name at the top, in big friendly letters: it fades in a moment after each camera angle
        starts, stays for a while, then fades away (no pops, no flashing)."""
        a = 0.0
        for t0, t1, _ in self.st.shots:
            on, off = t0 + 1.0, min(t1 - 0.5, t0 + 9.0)
            a = max(a, min(1.0, max(0.0, (t - on) / 0.8), max(0.0, (off - t) / 0.8)))
        if a <= 0.01:
            return img
        from PIL import ImageDraw, ImageFont, ImageFilter
        font = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Fredoka.ttf"), 128)
        try:
            font.set_variation_by_name("Bold")
        except Exception:  # noqa: BLE001
            pass
        text = self.spec["label"]
        col = self.LABEL_COLS[self.spec.get("index", 0) % len(self.LABEL_COLS)]
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        w = d.textlength(text, font=font)
        x, y = (img.size[0] - w) / 2, 52
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).text((x + 4, y + 8), text, font=font, fill=(0, 0, 0, 90), stroke_width=12, stroke_fill=(0, 0, 0, 90))
        layer = Image.alpha_composite(layer, shadow.filter(ImageFilter.GaussianBlur(8)))
        d = ImageDraw.Draw(layer)
        d.text((x, y), text, font=font, fill=(255, 255, 255, 255), stroke_width=12, stroke_fill=(*col, 255))
        if a < 1.0:
            al = layer.getchannel("A").point(lambda v: int(v * a))
            layer.putalpha(al)
        return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    def _frame(self, t, path):
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


def render_scene(spec, frames, out_dir, res=1280, samples=4, log=print, part=0, parts=1):
    """Render one scene, or one part of it (frames are split evenly; parts are joined with join_parts)."""
    from engine3 import sfx3
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    k = spec["index"]
    D = frames / FPS
    f0, f1 = frames * part // parts, frames * (part + 1) // parts
    t0 = time.time()
    R = Renderer4(spec, D, res=res, samples=samples, work=out_dir)
    log(f"scene {k} ({spec['script']}) part {part + 1}/{parts}: set up in {time.time() - t0:.0f}s, "
        f"{len(R.st.static)} scenery objects, {len(getattr(R.st, 'props', []))} props")
    mp4 = out_dir / (f"scene_{k:02d}.mp4" if parts == 1 else f"scene_{k:02d}_p{part}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                           str(mp4)], stdin=subprocess.PIPE)
    tmp = out_dir / f"_frame_{k:02d}.png"
    from flashguard import FlashGuard
    guard = FlashGuard()
    for i in range(f0, f1):
        t = i / FPS
        img = guard(R.frame(t, tmp))
        ff.stdin.write(np.asarray(img.convert("RGB"), np.uint8).tobytes())
        if i == frames // 2:
            img.resize((160, 90)).save(out_dir / f"key_{k:02d}.png")
        if i == int(min(frames - 1, 8 * FPS)):
            img.save(out_dir / f"thumb_{k:02d}.png")
        if (i - f0) % 48 == 0:
            el = time.time() - t0
            log(f"scene {k}: frame {i}/{frames} ({el / max(1, i - f0):.1f}s per frame, {el / 60:.0f} min so far)")
    ff.stdin.close()
    ff.wait()
    if part == 0:
        np.save(out_dir / f"sfx_{k:02d}.npy", sfx3.render_scene(R.st, D, spec["theme"]).astype(np.float32))
    log(f"scene {k}: done in {(time.time() - t0) / 60:.1f} min")
    tmp.unlink(missing_ok=True)
    return mp4


def join_parts(work):
    """Join scene_KK_p0.mp4, scene_KK_p1.mp4, ... into scene_KK.mp4 (same encoding: no re-encode)."""
    work = Path(work)
    groups = {}
    for p in sorted(work.glob("scene_*_p*.mp4")):
        kk, part = p.stem.split("_")[1], int(p.stem.split("_p")[-1])
        groups.setdefault(kk, []).append((part, p))
    for kk, lst in groups.items():
        lst.sort()
        if [i for i, _ in lst] != list(range(len(lst))):
            raise SystemExit(f"scene {kk}: missing parts {[i for i, _ in lst]}")
        listing = work / f"_parts_{kk}.txt"
        listing.write_text("".join(f"file '{p.resolve()}'\n" for _, p in lst))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
                        str(work / f"scene_{kk}.mp4")], check=True)
        listing.unlink()
        for _, p in lst:
            p.unlink()
        print(f"scene {kk}: joined {len(lst)} parts", flush=True)


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
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--parts", type=int, default=1)
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
    render_scene(spec, n, a.out, res=a.res, samples=a.samples, part=a.part, parts=a.parts)
