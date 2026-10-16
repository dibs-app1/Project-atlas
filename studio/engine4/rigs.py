"""Artist-made animated models (glTF, CC0) inside the engine-4 Blender scene.

Each model file is imported once into a hidden library; every animal on screen is a copy of it (its
own armature, sharing the mesh data). Every frame the animal's pose is evaluated from its clips
(walk, idle, eat, run...) at its own clip time, and clips blend smoothly into each other, so an animal
can walk, slow down and start grazing without popping. Walk/run clips play at a speed matched to how
fast the animal moves, so its feet do not slide.
"""
import math
import re

import bpy  # noqa: I001
import numpy as np
from mathutils import Matrix, Quaternion, Vector

LIB = {}          # path -> dict(arm, meshes, clips, size)
BAD_CLIPS = re.compile(r"death|dead|die|dying|attack|hit|bite|kill|punch|wound|shoot|scream|guard|legs-up|t pose", re.I)


def _fcurves(action):
    if hasattr(action, "layers") and len(action.layers):
        out = []
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    cb = strip.channelbag(slot)
                    if cb is not None:
                        out.extend(cb.fcurves)
        return out
    return list(getattr(action, "fcurves", []))


class Clip:
    def __init__(self, action):
        self.name = action.name
        self.f0, self.f1 = action.frame_range[0], action.frame_range[1]
        self.length = max(1.0, self.f1 - self.f0)
        chans = {}
        for fc in _fcurves(action):
            m = re.match(r'pose\.bones\["(.+)"\]\.(\w+)', fc.data_path)
            if not m:
                continue
            chans.setdefault((m.group(1), m.group(2)), []).append((fc.array_index, fc))
        self.chans = chans

    def sample(self, frame):
        f = self.f0 + (frame % self.length)
        out = {}
        for (bone, prop), lst in self.chans.items():
            n = 4 if prop == "rotation_quaternion" else 3
            v = [1.0, 0, 0, 0] if prop == "rotation_quaternion" else ([1.0] * 3 if prop == "scale" else [0.0] * 3)
            for i, fc in lst:
                if i < n:
                    v[i] = fc.evaluate(f)
            out[(bone, prop)] = v
        return out


def load(path):
    """Import a glTF file once; return its library entry."""
    if path in LIB:
        return LIB[path]
    before = set(bpy.data.objects)
    acts_before = set(bpy.data.actions)
    if str(path).lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=False)
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if o.type not in ("MESH", "ARMATURE", "EMPTY")]:     # files can carry their own camera/lights
        bpy.data.objects.remove(o)
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    arm = next((o for o in new if o.type == "ARMATURE"), None)
    meshes = [o for o in new if o.type == "MESH"]
    clips = {}
    for a in bpy.data.actions:
        if a not in acts_before and not BAD_CLIPS.search(a.name):
            clips[a.name] = Clip(a)
    for o in new:            # the library copy stays hidden
        o.hide_render = True
        if o.animation_data:
            o.animation_data.action = None
    # size in the model's own frame (after the importer's Y-up -> Z-up conversion)
    pts = []
    for o in meshes:
        M = o.matrix_world
        pts += [M @ Vector(c) for c in o.bound_box]
    P = np.array([tuple(p) for p in pts]) if pts else np.zeros((1, 3))
    lo, hi = P.min(axis=0), P.max(axis=0)
    # which way does it face? the head bone (or the front of the mesh) points forward
    fwd = None
    if arm is not None:
        hb = [b for b in arm.data.bones if re.search(r"head|neck|nose|jaw", b.name, re.I)]
        if hb:
            hp = arm.matrix_world @ hb[0].head_local
            c = (lo + hi) / 2
            v = np.array([hp[0] - c[0], hp[1] - c[1]])
            if np.linalg.norm(v) > 1e-6:
                fwd = math.atan2(v[1], v[0])
    LIB[path] = dict(arm=arm, meshes=meshes, clips=clips, lo=lo, hi=hi, new=new, fwd=fwd)
    return LIB[path]


WORDS = {"grey": (150, 150, 156), "gray": (150, 150, 156), "white": (246, 244, 238), "pink": (240, 160, 170),
         "black": (40, 38, 42), "brown": (130, 86, 56), "lightyellow": (246, 228, 160), "yellow": (250, 210, 60),
         "orange": (240, 140, 50), "red": (210, 60, 50), "blue": (70, 120, 210), "green": (90, 160, 80), "beak": (250, 190, 60),
         "claws": (230, 180, 60), "head": (246, 244, 238), "wings": (110, 76, 50)}

# models whose files carry no colours: the colours per material, in order of how much of the body uses it
PALETTES = {
    "Dog": [(196, 146, 92)], "Wolf": [(150, 150, 160)], "Chick": [(250, 220, 90), (250, 150, 40)],
    "bird": [(90, 140, 220), (250, 190, 70)], "Whale": [(80, 100, 140), (210, 216, 226)],
    "Red Fox": [(230, 120, 50), (246, 240, 230)], "Cat": None, "Eagle": None, "Piranha": None,
}


def _srgb(c):
    return tuple((x / 255) ** 2.2 for x in c) + (1.0,)


def clean_materials(meshes, palette=None, force=False):
    """Rebuild imported materials as simple, sturdy ones: the material's own colour or texture, times the mesh's
    vertex colours when it has them (many low-poly models are painted with vertex colours)."""
    done = {}
    for o in meshes:
        # rank this mesh's materials by how many faces use them (for palettes given by size)
        cnt = {}
        for poly in o.data.polygons:
            cnt[poly.material_index] = cnt.get(poly.material_index, 0) + 1
        rank = {mi: r for r, (mi, _) in enumerate(sorted(cnt.items(), key=lambda kv: -kv[1]))}
        has_col = len(o.data.color_attributes) > 0
        cname = o.data.color_attributes[0].name if has_col else None
        for i, slot in enumerate(o.material_slots):
            m = slot.material
            if m is None:
                continue
            key = (m.name, cname, rank.get(i), id(palette))
            if key in done:
                slot.material = done[key]
                continue
            base, img = (0.8, 0.8, 0.8, 1.0), None
            if m.node_tree:
                b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if b is not None:
                    base = tuple(b.inputs["Base Color"].default_value)
                    if b.inputs["Base Color"].links:
                        src = b.inputs["Base Color"].links[0].from_node
                        if src.type == "TEX_IMAGE":
                            img = src.image
            else:
                base = tuple(m.diffuse_color)
            plain = all(abs(x - 0.8) < 0.01 for x in base[:3])        # the exporter's default grey: no colour stored
            if force and palette and rank.get(i, 99) < len(palette):
                base, img = _srgb(palette[rank[i]]), None
            elif plain and img is None:
                word = re.sub(r"[^a-z]", "", m.name.lower())
                if palette and rank.get(i, 99) < len(palette):
                    base = _srgb(palette[rank[i]])
                elif word in WORDS:
                    base = _srgb(WORDS[word])
            nm = bpy.data.materials.new(m.name + "_clean")
            nt = nm.node_tree
            if nt is None:
                nm.use_nodes = True
                nt = nm.node_tree
            bsdf = nt.nodes.get("Principled BSDF")
            bsdf.inputs["Roughness"].default_value = 0.75
            col = None
            if img is not None and o.data.uv_layers:
                tex = nt.nodes.new("ShaderNodeTexImage")
                tex.image = img
                col = tex.outputs["Color"]
            if cname and img is None:
                at = nt.nodes.new("ShaderNodeAttribute")
                at.attribute_name = cname
                mul = nt.nodes.new("ShaderNodeMix")
                mul.data_type = "RGBA"
                mul.blend_type = "MULTIPLY"
                mul.inputs["Factor"].default_value = 1.0
                mul.inputs["A"].default_value = base
                nt.links.new(at.outputs["Color"], mul.inputs["B"])
                col = mul.outputs["Result"]
            if col is not None:
                nt.links.new(col, bsdf.inputs["Base Color"])
            else:
                bsdf.inputs["Base Color"].default_value = base
            done[key] = nm
            slot.material = nm


def relink_images(path):
    """Textures of appended .blend/.fbx files often point to the artist's own folders: find them next to the file."""
    import os
    base = os.path.dirname(str(path))
    root = os.path.dirname(base)
    for img in bpy.data.images:
        if img.source != "FILE" or img.packed_file is not None:
            continue
        fp = bpy.path.abspath(img.filepath)
        if fp and os.path.exists(fp):
            continue
        name = os.path.basename(fp.replace("\\", "/"))
        for d in (base, root):
            hit = None
            for dirpath, _, files in os.walk(d):
                if name in files:
                    hit = os.path.join(dirpath, name)
                    break
            if hit:
                img.filepath = hit
                img.reload()
                break


def find_clip(clips, *names):
    """First clip whose name contains one of the names (case-insensitive)."""
    for n in names:
        for k, c in clips.items():
            if n.lower() in k.lower():
                return c
    return None


class Instance:
    """One animal on screen: its own import of the model file (correct hierarchy, materials and clips)."""

    def __init__(self, path, length, yaw_fix=None, collection=None, palette=None):
        sc = bpy.context.scene
        col = collection or sc.collection
        before = set(bpy.data.objects)
        acts_before = set(bpy.data.actions)
        low = str(path).lower()
        if low.endswith(".fbx"):
            bpy.ops.import_scene.fbx(filepath=str(path))
        elif low.endswith(".blend"):
            with bpy.data.libraries.load(str(path), link=False) as (src, dst):
                dst.objects = list(src.objects)
                dst.actions = list(src.actions)
            for o in dst.objects:
                if o is not None:
                    col.objects.link(o)
        else:
            bpy.ops.import_scene.gltf(filepath=str(path))
        new = [o for o in bpy.data.objects if o not in before]
        for o in [o for o in new if o.type not in ("MESH", "ARMATURE", "EMPTY")]:
            bpy.data.objects.remove(o)
        new = [o for o in bpy.data.objects if o not in before]
        arms = [o for o in new if o.type == "ARMATURE"]
        if arms:      # keep the rig and what it moves; drop ground planes, props and helper objects
            def driven(o):
                return o.type == "ARMATURE" or (o.type == "MESH" and (o.parent in arms or any(
                    m.type == "ARMATURE" and m.object in arms for m in o.modifiers)))
            for o in [o for o in new if not driven(o) and o.type != "EMPTY"]:
                bpy.data.objects.remove(o)
        else:         # a single mesh: keep the biggest one
            ms = sorted([o for o in new if o.type == "MESH"], key=lambda o: -len(o.data.polygons))
            for o in ms[1:]:
                if len(o.data.polygons) < len(ms[0].data.polygons) * 0.3 or o.name.lower().startswith(("plane", "ground")):
                    bpy.data.objects.remove(o)
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            if o.type == "MESH":
                for ps in list(o.modifiers):
                    if ps.type == "PARTICLE_SYSTEM":      # fur etc.: too heavy for a CPU renderer
                        o.modifiers.remove(ps)
            o.hide_render = False
            o.hide_viewport = False
        bpy.context.view_layer.update()
        relink_images(path)
        self.arm = next((o for o in new if o.type == "ARMATURE"), None)
        self.meshes = [o for o in new if o.type == "MESH"]
        stem = re.sub(r"\.(fbx|glb|gltf)$", "", str(path).split("/")[-1], flags=re.I)
        clean_materials(self.meshes, palette or PALETTES.get(stem), force=palette is not None)
        self.clips = {a.name.split("|")[-1]: Clip(a) for a in bpy.data.actions
                      if a not in acts_before and not BAD_CLIPS.search(a.name)}
        for o in new:
            if o.animation_data:
                o.animation_data.action = None
        pts = []
        for o in self.meshes:
            pts += [tuple(o.matrix_world @ Vector(c)) for c in o.bound_box]
        P = np.array(pts) if pts else np.zeros((1, 3))
        lo, hi = P.min(axis=0), P.max(axis=0)
        ext = hi - lo
        self.lo, self.hi = lo, hi
        self.scale = length / max(1e-6, max(ext[0], ext[1]))
        self.height = ext[2] * self.scale
        fwd = None
        if self.arm is not None:
            hb = [b for b in self.arm.data.bones if re.search(r"head|neck|nose|jaw|beak", b.name, re.I)]
            if hb:
                hp = self.arm.matrix_world @ hb[0].head_local
                c = (lo + hi) / 2
                v = np.array([hp[0] - c[0], hp[1] - c[1]])
                if np.linalg.norm(v) > 1e-6 * max(ext):
                    fwd = math.atan2(v[1], v[0])
        self.fwd = fwd
        if yaw_fix is None:
            if fwd is not None:
                yaw_fix = -fwd
            else:     # no head bone: models lying along y face -y (glTF/FBX convention), along x face +x
                yaw_fix = math.pi / 2 if ext[1] > ext[0] else 0.0
        self.yaw_fix = yaw_fix
        self.center = (lo + hi) / 2
        self.root = bpy.data.objects.new("animal", None)
        col.objects.link(self.root)
        for o in new:
            if o.parent is None:
                o.parent = self.root
                o.matrix_parent_inverse = Matrix.Identity(4)
        self.lib = dict(lo=lo, hi=hi, fwd=fwd)

    def place(self, pos, yaw, pitch=0.0, roll=0.0):
        from engine3.r3d import ypr
        # the model's footprint centre and its feet go to `pos`
        Rm = np.asarray(ypr(yaw, pitch, roll)) @ np.asarray(ypr(self.yaw_fix)) * self.scale
        lo = self.lib["lo"]
        anchor = np.array([self.center[0], self.center[1], lo[2]])
        M = np.eye(4)
        M[:3, :3] = Rm
        M[:3, 3] = np.asarray(pos, float) - Rm @ anchor
        self.root.matrix_world = Matrix(M.tolist())

    def pose(self, mix):
        """mix: [(Clip, frame, weight)]. Blend the clips and pose the armature."""
        if self.arm is None or not mix:
            return
        tot = sum(w for _, _, w in mix) or 1.0
        acc = {}
        for clip, frame, w in mix:
            w /= tot
            for key, v in clip.sample(frame).items():
                a = acc.get(key)
                if a is None:
                    acc[key] = [w * x for x in v]
                else:
                    if key[1] == "rotation_quaternion" and sum(x * y for x, y in zip(a, v)) < 0:
                        v = [-x for x in v]
                    acc[key] = [x + w * y for x, y in zip(a, v)]
        pbs = self.arm.pose.bones
        for (bone, prop), v in acc.items():
            pb = pbs.get(bone)
            if pb is None:
                continue
            if prop == "rotation_quaternion":
                q = Quaternion(v)
                q.normalize()
                pb.rotation_quaternion = q
            elif prop == "location":
                pb.location = v
            elif prop == "scale":
                pb.scale = v
            elif prop == "rotation_euler":
                pb.rotation_euler = v

    def hide(self, h=True):
        for o in self.meshes:
            o.hide_render = h


class Gait:
    """Chooses and blends clips: idle (or a mood such as eating/pecking/sitting) when still, walk, then run.
    Walk and run play at a rate matched to the ground speed, so feet do not slide. Changes blend over ~0.4 s."""

    def __init__(self, inst, walk_speed=1.2, run_speed=4.0, eat=True):
        c = inst.clips
        self.inst = inst
        anyc = next(iter(c.values()), None)
        self.clips = c
        self.walk = find_clip(c, "Walk", "Waddle", "Swim", "Flying", "Fly", "Running") or anyc
        self.run = find_clip(c, "Gallop", "Run", "Trot") or self.walk
        self.idle = find_clip(c, "Idle", "Stand", "Basic", "Sitting", "idle") or self.walk
        self.walk_speed, self.run_speed = max(0.05, walk_speed), run_speed
        self.phase = 0.0
        self.t_prev = None
        self.fps = 24.0
        self.w = np.array([1.0, 0.0, 0.0])        # smoothed weights: still, walk, run
        self.mood_clip = None

    def update(self, t, v, mood=None):
        first = self.t_prev is None
        dt = 0.0 if first else max(0.0, t - self.t_prev)
        self.t_prev = t
        if v < 0.05:
            target = np.array([1.0, 0.0, 0.0])
        elif v < self.walk_speed * 1.6 or self.run is self.walk:
            k = min(1.0, v / max(0.05, self.walk_speed * 0.3))
            target = np.array([1 - k, k, 0.0])
        else:
            k = min(1.0, (v - self.walk_speed * 1.6) / max(0.1, self.run_speed - self.walk_speed * 1.6))
            target = np.array([0.0, 1 - k, k])
        a = 1.0 if first else 1.0 - math.exp(-dt / 0.35)
        self.w = self.w + (target - self.w) * a
        still = self.idle
        if mood:
            mc = find_clip(self.clips, *mood.split("|"))
            if mc is not None:
                still = mc
        rate = v / self.walk_speed
        self.phase += dt * self.fps * max(0.0, rate)
        mix = []
        if self.w[0] > 0.01:
            mix.append((still, t * self.fps, self.w[0]))
        if self.w[1] > 0.01:
            mix.append((self.walk, self.phase, self.w[1]))
        if self.w[2] > 0.01:
            mix.append((self.run, self.phase * (self.run.length / max(1.0, self.walk.length)), self.w[2]))
        self.inst.pose(mix)
