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
SOFT = False      # the soft look: welded, rounded bodies with a soft sheen, and big friendly eyes
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


def round_bodies(meshes):
    """Low-poly exports keep every face's corners apart (hard facets). Weld them, drop the hard-edge marks and
    custom normals, and add a subdivision after the rig: the same animal, but with rounded, natural forms."""
    import bmesh
    for o in meshes:
        me = o.data
        if me.users > 1:
            o.data = me = me.copy()
        bm = bmesh.new()
        bm.from_mesh(me)
        size = max(o.dimensions) / max(1e-6, max(o.scale)) if max(o.dimensions) else 1.0
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=max(1e-5, size * 2e-4))
        for e in bm.edges:
            e.smooth = True
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
        bm.free()
        for name in ("sharp_edge", "sharp_face", "custom_normal"):
            if name in me.attributes:
                me.attributes.remove(me.attributes[name])
        if getattr(me, "has_custom_normals", False):
            try:
                with bpy.context.temp_override(object=o, active_object=o):
                    bpy.ops.mesh.customdata_custom_splitnormals_clear()
            except RuntimeError:
                pass
        if len(me.polygons) < 20000 and not any(m.type == "SUBSURF" for m in o.modifiers):
            s = o.modifiers.new("round", "SUBSURF")
            s.levels = s.render_levels = 2
        for sl in o.material_slots:
            m = sl.material
            b = m.node_tree.nodes.get("Principled BSDF") if m and m.node_tree else None
            if b is not None and not m.get("eye"):
                b.inputs["Roughness"].default_value = 0.85
                b.inputs["Sheen Weight"].default_value = 0.35       # a soft, velvety fur/feather edge
                b.inputs["Sheen Roughness"].default_value = 0.6


def _eye_mat(name, rgb, rough, coat=0.0):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        if m.node_tree is None:
            m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (*rgb, 1.0)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Coat Weight"].default_value = coat
        m["eye"] = True
    return m


def give_eyes(inst, spec=None):
    """Big, friendly, glossy eyes on both sides of the head, riding on the head bone.

    spec: None (find the head and add eyes), {"own": True} (the model's eyes are fine), {"recolor": "Eyes"}
    (the model has eye meshes that came out grey: make them glossy black), or tuning such as
    {"size": 1.2, "back": 0.4, "down": 0.35, "out": 0.0}."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    spec = spec or {}
    inst.eye_pts = []
    black = _eye_mat("eye_black", (0.008, 0.008, 0.01), 0.06, coat=1.0)
    white = _eye_mat("eye_white", (0.92, 0.91, 0.88), 0.25)
    if spec.get("own"):
        return
    if spec.get("recolor"):
        for o in inst.meshes:
            if o.name.lower().startswith(spec["recolor"].lower()):
                for sl in o.material_slots:
                    sl.material = black
        if not spec.get("add"):
            return
    if not inst.meshes:
        return
    arm = inst.arm
    if arm is not None:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    V, F = [], []
    for o in inst.meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        base = len(V)
        V += [tuple(o.matrix_world @ v.co) for v in me.vertices]
        F += [tuple(base + i for i in p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
    if arm is not None:
        arm.data.pose_position = "POSE"
    P = np.array(V)
    fwd = inst.fwd if inst.fwd is not None else (-inst.yaw_fix)
    f = np.array([math.cos(fwd), math.sin(fwd), 0.0])
    side = np.array([-f[1], f[0], 0.0])
    a, z, s = P @ f, P[:, 2], P @ side
    L, Hh = a.max() - a.min(), z.max() - z.min()
    # the head: the front of the animal, above its knees
    head = (a > a.max() - spec.get("head", 0.26) * L) & (z > z.min() + 0.4 * Hh)
    if spec.get("top"):          # tall birds: the head is the top of the body, not its front (the breast)
        head = (z > z.max() - spec["top"] * Hh) & (a > (a.max() + a.min()) / 2 - 0.1 * L)
    if head.sum() < 8:
        head = a > a.max() - 0.3 * L
    ha, hz, hs = a[head], z[head], s[head]
    hl, hh = ha.max() - ha.min(), hz.max() - hz.min()
    ea = ha.max() - spec.get("back", 0.42) * hl
    ez = hz.max() - spec.get("down", 0.36) * hh
    mid = (hs.max() + hs.min()) / 2
    r = spec.get("size", 1.0) * 0.15 * min(hl, hh)
    tree = BVHTree.FromPolygons(V, F)
    bones = list(arm.data.bones) if arm is not None else []
    for sgn in (1, -1):
        start = f * ea + side * mid + np.array([0, 0, ez])
        hit = tree.ray_cast(Vector(start + side * sgn * 10 * L), Vector(-side * sgn))
        if hit[0] is None:
            continue
        p = np.array(hit[0]) - side * sgn * r * (0.35 - spec.get("out", 0.0))
        inst.eye_pts.append((p.copy(), r))
        for nm, mat, rad, push, fw in (("eye_w", white, r, 0.0, 0.0), ("eye_p", black, r * 0.66, r * 0.42, r * 0.12)):
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=rad)
            me = bpy.data.meshes.new(nm)
            bm.to_mesh(me)
            bm.free()
            for poly in me.polygons:
                poly.use_smooth = True
            me.materials.append(mat)
            e = bpy.data.objects.new(nm, me)
            for c in inst.meshes[0].users_collection:
                c.objects.link(e)
            M = np.eye(4)
            M[:3, 0], M[:3, 1], M[:3, 2] = f, side * sgn, (0, 0, 1)
            M[:3, :3] = M[:3, :3] @ np.diag([1.0, 0.62, 1.0])           # a little flattened against the head
            M[:3, 3] = p + side * sgn * push + f * fw
            want = Matrix(M.tolist())
            if bones:
                def seg_d(b):
                    h, t = arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local
                    ab = np.array(t - h)
                    u = np.clip(np.dot(p - np.array(h), ab) / max(1e-9, ab @ ab), 0, 1)
                    return np.linalg.norm(p - (np.array(h) + u * ab))
                near = min(bones, key=seg_d)
                named = [b for b in bones if re.search(r"head", b.name, re.I)]
                b = named[0] if named and seg_d(named[0]) < 1.6 * seg_d(near) + 1e-6 else near
                e.parent, e.parent_type, e.parent_bone = arm, "BONE", b.name
            else:
                e.parent = inst.meshes[0]
            bpy.context.view_layer.update()
            e.matrix_world = want
            inst.meshes.append(e)


# ------------------------------------------------------------------ fur, hair, wool and feathers

def _card(shape):
    """One strand, hair, feather or wool curl, 1 unit long along +Z from its root; 't' runs 0 (root) to 1 (tip)."""
    import bmesh
    key = "coat_" + shape
    if key in bpy.data.meshes:
        return bpy.data.meshes[key]
    bm = bmesh.new()
    T = []
    if shape == "wool":
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.5)
        for v in bm.verts:
            v.co.z += 0.3
        T = [min(1.0, max(0.0, v.co.z)) for v in bm.verts]
    else:
        segs = {"fur": 3, "hair": 5, "feather": 4}[shape]
        rows = []
        for i in range(segs + 1):
            u = i / segs
            if shape == "feather":
                w = 0.32 * math.sin(math.pi * (0.12 + 0.82 * u)) + 0.02
                y = -0.12 * u * u
                row = [bm.verts.new((-w, y + 0.03, u)), bm.verts.new((0, y + 0.07, u)), bm.verts.new((w, y + 0.03, u))]
            else:
                w = (0.22 if shape == "fur" else 0.08) * (1 - u) + 0.01
                y = (-0.25 if shape == "fur" else -0.15) * u * u
                row = [bm.verts.new((-w, y, u)), bm.verts.new((w, y, u))]
            rows.append(row)
            T += [u] * len(row)
        for a, b in zip(rows, rows[1:]):
            for j in range(len(a) - 1):
                bm.faces.new([a[j], a[j + 1], b[j + 1], b[j]])
    me = bpy.data.meshes.new(key)
    bm.to_mesh(me)
    bm.free()
    at = me.attributes.new("t", "FLOAT", "POINT")
    at.data.foreach_set("value", T)
    for p in me.polygons:
        p.use_smooth = True
    return me


def _slot_color(m):
    if m is None or not m.node_tree:
        return (0.6, 0.6, 0.6, 1.0)
    for n in m.node_tree.nodes:
        if n.type == "MIX" and getattr(n, "blend_type", "") == "MULTIPLY" and not n.inputs["A"].links:
            return tuple(n.inputs["A"].default_value)
    b = m.node_tree.nodes.get("Principled BSDF")
    return tuple(b.inputs["Base Color"].default_value) if b else (0.6, 0.6, 0.6, 1.0)


def _coat_mat(color, shape):
    m = bpy.data.materials.new("coat_" + shape)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = "t"
    mr = nt.nodes.new("ShaderNodeMapRange")          # darker at the root, lighter at the tip
    mr.inputs["To Min"].default_value = 0.74 if shape != "wool" else 0.82
    mr.inputs["To Max"].default_value = 1.1
    nt.links.new(at.outputs["Fac"], mr.inputs["Value"])
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    mr2 = nt.nodes.new("ShaderNodeMapRange")         # every strand a little different
    mr2.inputs["To Min"].default_value = 0.9
    mr2.inputs["To Max"].default_value = 1.08
    nt.links.new(oi.outputs["Random"], mr2.inputs["Value"])
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    nt.links.new(mr.outputs["Result"], k.inputs[0])
    nt.links.new(mr2.outputs["Result"], k.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    mix.inputs["A"].default_value = color
    cmb = nt.nodes.new("ShaderNodeCombineColor")
    for ch in ("Red", "Green", "Blue"):
        nt.links.new(k.outputs[0], cmb.inputs[ch])
    nt.links.new(cmb.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7 if shape != "feather" else 0.55
    b.inputs["Sheen Weight"].default_value = 0.4
    m.use_backface_culling = False
    return m


def _sock(node, name, kind, out=False):
    socks = node.outputs if out else node.inputs
    return next(s for s in socks if s.name == name and s.type == kind and s.enabled)


def add_coat(inst, layers):
    """Grow fur, hair, wool or feathers on the animal. The coat is laid out on the animal's resting body (so it
    never flickers as the body moves) and then pinned to the moving body: each strand rides its spot of skin and
    leans the way that animal's coat lies (backwards and down), around the eyes it stays clear."""
    fwd = inst.fwd if inst.fwd is not None else -inst.yaw_fix
    f = np.array([math.cos(fwd), math.sin(fwd), 0.0])
    zlo, zhi = inst.lo[2], inst.hi[2]
    for o in [m for m in inst.meshes if m.type == "MESH" and not m.name.startswith("eye_")]:
        if not any(md.type == "ARMATURE" for md in o.modifiers):
            continue
        Mw = np.array(o.matrix_world)
        Minv = np.linalg.inv(Mw)
        osc = float(np.mean(np.linalg.norm(Mw[:3, :3], axis=0)))
        k = inst.scale * osc                      # local units -> metres
        cnt = {}
        for poly in o.data.polygons:
            cnt[poly.material_index] = cnt.get(poly.material_index, 0) + 1
        rank = [mi for mi, _ in sorted(cnt.items(), key=lambda kv: -kv[1])]
        # 1) before the rig moves it: remember where every point of the body rests
        g0 = bpy.data.node_groups.new("rest", "GeometryNodeTree")
        g0.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        g0.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        a, b = g0.nodes.new("NodeGroupInput"), g0.nodes.new("NodeGroupOutput")
        st = g0.nodes.new("GeometryNodeStoreNamedAttribute")
        st.data_type, st.domain = "FLOAT_VECTOR", "POINT"
        st.inputs["Name"].default_value = "rest"
        pos = g0.nodes.new("GeometryNodeInputPosition")
        g0.links.new(a.outputs[0], st.inputs["Geometry"])
        g0.links.new(pos.outputs[0], _sock(st, "Value", "VECTOR"))
        g0.links.new(st.outputs[0], b.inputs[0])
        m0 = o.modifiers.new("rest", "NODES")
        m0.node_group = g0
        o.modifiers.move(len(o.modifiers) - 1, 0)
        # 2) after the rig and the rounding: grow the coat
        ng = bpy.data.node_groups.new("coat", "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        N, L = ng.nodes, ng.links
        gi, go = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
        join = N.new("GeometryNodeJoinGeometry")
        L.new(gi.outputs[0], join.inputs[0])
        # the moving body's positions and normals, kept as attributes; then lay the body back to rest
        sp = N.new("GeometryNodeStoreNamedAttribute")
        sp.data_type, sp.domain = "FLOAT_VECTOR", "POINT"
        sp.inputs["Name"].default_value = "dpos"
        L.new(gi.outputs[0], sp.inputs["Geometry"])
        L.new(N.new("GeometryNodeInputPosition").outputs[0], _sock(sp, "Value", "VECTOR"))
        sn = N.new("GeometryNodeStoreNamedAttribute")
        sn.data_type, sn.domain = "FLOAT_VECTOR", "FACE"
        sn.inputs["Name"].default_value = "dnorm"
        L.new(sp.outputs[0], sn.inputs["Geometry"])
        L.new(N.new("GeometryNodeInputNormal").outputs[0], _sock(sn, "Value", "VECTOR"))
        rest = N.new("GeometryNodeInputNamedAttribute")
        rest.data_type = "FLOAT_VECTOR"
        rest.inputs["Name"].default_value = "rest"
        setr = N.new("GeometryNodeSetPosition")
        L.new(sn.outputs[0], setr.inputs["Geometry"])
        L.new(_sock(rest, "Attribute", "VECTOR", out=True), setr.inputs["Position"])
        made = 0
        for li, lay in enumerate(layers):
            for r_ in lay.get("slots", [0]):
                if r_ >= len(rank):
                    continue
                mi = rank[r_]
                slot_mat = o.material_slots[mi].material if mi < len(o.material_slots) else None
                color = tuple(lay["color"]) + (1.0,) if lay.get("color") else _slot_color(slot_mat)
                shape = lay["shape"]
                card = bpy.data.objects.new("card", _card(shape))
                card.data = card.data.copy()
                card.data.materials.clear()
                card.data.materials.append(_coat_mat(color, shape))
                card.hide_render = True
                for c in o.users_collection:
                    c.objects.link(card)
                # this material's faces only
                sep = N.new("GeometryNodeSeparateGeometry")
                sep.domain = "FACE"
                cmp = N.new("FunctionNodeCompare")
                cmp.data_type, cmp.operation = "INT", "EQUAL"
                L.new(N.new("GeometryNodeInputMaterialIndex").outputs[0], _sock(cmp, "A", "INT"))
                _sock(cmp, "B", "INT").default_value = mi
                L.new(setr.outputs[0], sep.inputs["Geometry"])
                L.new(cmp.outputs[0], sep.inputs["Selection"])
                dist = N.new("GeometryNodeDistributePointsOnFaces")
                dist.inputs["Density"].default_value = lay["density"] * k * k
                dist.inputs["Seed"].default_value = 7 + li * 13 + r_
                L.new(sep.outputs["Selection"], dist.inputs["Mesh"])
                cur = dist.outputs["Points"]
                # keep clear of the eyes and (for manes and tails) of the hooves
                kill = None
                posn = N.new("GeometryNodeInputPosition")
                for p, r in getattr(inst, "eye_pts", []):
                    pl = (Minv @ np.array([*p, 1.0]))[:3]
                    vd = N.new("ShaderNodeVectorMath")
                    vd.operation = "DISTANCE"
                    L.new(posn.outputs[0], vd.inputs[0])
                    vd.inputs[1].default_value = tuple(pl)
                    lt = N.new("ShaderNodeMath")
                    lt.operation = "LESS_THAN"
                    L.new(_sock(vd, "Value", "VALUE", out=True), lt.inputs[0])
                    lt.inputs[1].default_value = 2.0 * r / osc
                    if kill is None:
                        kill = lt.outputs[0]
                    else:
                        mx = N.new("ShaderNodeMath")
                        mx.operation = "MAXIMUM"
                        L.new(kill, mx.inputs[0])
                        L.new(lt.outputs[0], mx.inputs[1])
                        kill = mx.outputs[0]
                if lay.get("zmin"):
                    row = Mw[2, :3]
                    thr = zlo + lay["zmin"] * (zhi - zlo) - Mw[2, 3]
                    dz = N.new("ShaderNodeVectorMath")
                    dz.operation = "DOT_PRODUCT"
                    L.new(posn.outputs[0], dz.inputs[0])
                    dz.inputs[1].default_value = tuple(row)
                    lt = N.new("ShaderNodeMath")
                    lt.operation = "LESS_THAN"
                    L.new(_sock(dz, "Value", "VALUE", out=True), lt.inputs[0])
                    lt.inputs[1].default_value = thr
                    if kill is None:
                        kill = lt.outputs[0]
                    else:
                        mx = N.new("ShaderNodeMath")
                        mx.operation = "MAXIMUM"
                        L.new(kill, mx.inputs[0])
                        L.new(lt.outputs[0], mx.inputs[1])
                        kill = mx.outputs[0]
                if lay.get("front_cut"):        # keep the muzzle bare (manes stop at the forehead)
                    corners = np.array([[x, y, z] for x in (inst.lo[0], inst.hi[0]) for y in (inst.lo[1], inst.hi[1])
                                        for z in (inst.lo[2], inst.hi[2])])
                    amax, amin = (corners @ f).max(), (corners @ f).min()
                    row = f @ Mw[:3, :3]
                    thr = amax - lay["front_cut"] * (amax - amin) - f @ Mw[:3, 3]
                    da = N.new("ShaderNodeVectorMath")
                    da.operation = "DOT_PRODUCT"
                    L.new(posn.outputs[0], da.inputs[0])
                    da.inputs[1].default_value = tuple(row)
                    gt = N.new("ShaderNodeMath")
                    gt.operation = "GREATER_THAN"
                    L.new(_sock(da, "Value", "VALUE", out=True), gt.inputs[0])
                    gt.inputs[1].default_value = thr
                    if kill is None:
                        kill = gt.outputs[0]
                    else:
                        mx = N.new("ShaderNodeMath")
                        mx.operation = "MAXIMUM"
                        L.new(kill, mx.inputs[0])
                        L.new(gt.outputs[0], mx.inputs[1])
                        kill = mx.outputs[0]
                if kill is not None:
                    dl = N.new("GeometryNodeDeleteGeometry")
                    dl.domain = "POINT"
                    L.new(cur, dl.inputs["Geometry"])
                    L.new(kill, dl.inputs["Selection"])
                    cur = dl.outputs[0]
                # pin each point to the moving body
                dpos = N.new("GeometryNodeInputNamedAttribute")
                dpos.data_type = "FLOAT_VECTOR"
                dpos.inputs["Name"].default_value = "dpos"
                setp = N.new("GeometryNodeSetPosition")
                L.new(cur, setp.inputs["Geometry"])
                L.new(_sock(dpos, "Attribute", "VECTOR", out=True), setp.inputs["Position"])
                # lean: from the skin's normal towards "back and down" along the skin
                dn = N.new("GeometryNodeInputNamedAttribute")
                dn.data_type = "FLOAT_VECTOR"
                dn.inputs["Name"].default_value = "dnorm"
                nrm = N.new("ShaderNodeVectorMath")
                nrm.operation = "NORMALIZE"
                L.new(_sock(dn, "Attribute", "VECTOR", out=True), nrm.inputs[0])
                droop = lay.get("droop", 0.4)
                vw = -f * (1 - droop) + np.array([0, 0, -1.0]) * droop
                vl = Minv[:3, :3] @ vw
                vl /= np.linalg.norm(vl) + 1e-9
                dot = N.new("ShaderNodeVectorMath")
                dot.operation = "DOT_PRODUCT"
                L.new(nrm.outputs[0], dot.inputs[0])
                dot.inputs[1].default_value = tuple(vl)
                sc1 = N.new("ShaderNodeVectorMath")
                sc1.operation = "SCALE"
                L.new(nrm.outputs[0], sc1.inputs[0])
                L.new(_sock(dot, "Value", "VALUE", out=True), _sock(sc1, "Scale", "VALUE"))
                tan = N.new("ShaderNodeVectorMath")
                tan.operation = "SUBTRACT"
                tan.inputs[0].default_value = tuple(vl)
                L.new(sc1.outputs[0], tan.inputs[1])
                tn = N.new("ShaderNodeVectorMath")
                tn.operation = "NORMALIZE"
                L.new(tan.outputs[0], tn.inputs[0])
                tilt = math.radians(lay.get("tilt", 65))
                a1 = N.new("ShaderNodeVectorMath")
                a1.operation = "SCALE"
                L.new(nrm.outputs[0], a1.inputs[0])
                _sock(a1, "Scale", "VALUE").default_value = math.cos(tilt)
                a2 = N.new("ShaderNodeVectorMath")
                a2.operation = "SCALE"
                L.new(tn.outputs[0], a2.inputs[0])
                _sock(a2, "Scale", "VALUE").default_value = math.sin(tilt)
                dsum = N.new("ShaderNodeVectorMath")
                dsum.operation = "ADD"
                L.new(a1.outputs[0], dsum.inputs[0])
                L.new(a2.outputs[0], dsum.inputs[1])
                al = N.new("FunctionNodeAlignRotationToVector")
                al.axis = "Z"
                L.new(dsum.outputs[0], al.inputs["Vector"])
                al2 = N.new("FunctionNodeAlignRotationToVector")      # lie flat against the skin
                al2.axis, al2.pivot_axis = "Y", "Z"
                L.new(al.outputs[0], al2.inputs["Rotation"])
                L.new(nrm.outputs[0], al2.inputs["Vector"])
                rs = N.new("FunctionNodeRandomValue")
                rs.data_type = "FLOAT"
                _sock(rs, "Min", "VALUE").default_value = lay["len"] / k * 0.7
                _sock(rs, "Max", "VALUE").default_value = lay["len"] / k * 1.3
                _sock(rs, "Seed", "INT").default_value = li + 3
                oi = N.new("GeometryNodeObjectInfo")
                oi.inputs["Object"].default_value = card
                sw = N.new("GeometryNodeScaleInstances")
                inst_n = N.new("GeometryNodeInstanceOnPoints")
                L.new(setp.outputs[0], inst_n.inputs["Points"])
                L.new(oi.outputs["Geometry"], inst_n.inputs["Instance"])
                L.new(al2.outputs[0], inst_n.inputs["Rotation"])
                L.new(_sock(rs, "Value", "VALUE", out=True), inst_n.inputs["Scale"])
                # widen the cards (the card is drawn for length 1; width is set per coat)
                L.new(inst_n.outputs[0], sw.inputs["Instances"])
                wid = lay.get("wid", 1.0)
                sw.inputs["Scale"].default_value = (wid, wid if shape == "wool" else 1.0, 1.0)
                sw.inputs["Local Space"].default_value = True
                L.new(sw.outputs[0], join.inputs[0])
                made += 1
        L.new(join.outputs[0], go.inputs[0])
        if made:
            mod = o.modifiers.new("coat", "NODES")
            mod.node_group = ng


class Instance:
    """One animal on screen: its own import of the model file (correct hierarchy, materials and clips)."""

    def __init__(self, path, length, yaw_fix=None, collection=None, palette=None, texture=None, eyes=None, coat=None):
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
            new = [o for o in bpy.data.objects if o not in before]
            skinned = [o for o in new if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
            if skinned:      # an unrigged copy riding along (e.g. a sculpt kept by the artist) would hide the animal
                for o in [o for o in bpy.data.objects if o not in before and o.type == "MESH" and o not in skinned
                          and o.parent_type != "BONE"]:
                    bpy.data.objects.remove(o)
        else:         # a single mesh: keep the biggest one
            ms = sorted([o for o in new if o.type == "MESH"], key=lambda o: -len(o.data.polygons))
            for o in ms[1:]:
                if len(o.data.polygons) < len(ms[0].data.polygons) * 0.3 or o.name.lower().startswith(("plane", "ground")):
                    bpy.data.objects.remove(o)
        new = [o for o in bpy.data.objects if o not in before]
        for o in list(new):
            if o.type == "MESH":
                for ps in list(o.modifiers):
                    if ps.type == "PARTICLE_SYSTEM":      # fur etc.: too heavy for a CPU renderer
                        o.modifiers.remove(ps)
        new = [o for o in bpy.data.objects if o not in before]
        bpy.context.view_layer.update()
        relink_images(path)
        self.arm = next((o for o in new if o.type == "ARMATURE"), None)
        self.meshes = [o for o in new if o.type == "MESH"]
        stem = re.sub(r"\.(fbx|glb|gltf)$", "", str(path).split("/")[-1], flags=re.I)
        clean_materials(self.meshes, palette or PALETTES.get(stem), force=palette is not None)
        if texture:        # old files whose texture is not wired into the material: paint it on through the UVs
            img = bpy.data.images.load(str(texture), check_existing=True)
            nm = bpy.data.materials.new("tex_" + stem)
            nt = nm.node_tree if nm.node_tree else None
            if nt is None:
                nm.use_nodes = True
                nt = nm.node_tree
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = img
            b = nt.nodes.get("Principled BSDF")
            b.inputs["Roughness"].default_value = 0.75
            nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
            for o in self.meshes:
                if o.data.uv_layers:
                    for sl in o.material_slots:
                        sl.material = nm
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
        if SOFT:
            round_bodies(self.meshes)
            give_eyes(self, eyes)
            if coat:
                add_coat(self, coat)

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
        acc, wsum = {}, {}
        for clip, frame, w in mix:
            w /= tot
            for key, v in clip.sample(frame).items():
                a = acc.get(key)
                wsum[key] = wsum.get(key, 0.0) + w
                if a is None:
                    acc[key] = [w * x for x in v]
                else:
                    if key[1] == "rotation_quaternion" and sum(x * y for x, y in zip(a, v)) < 0:
                        v = [-x for x in v]
                    acc[key] = [x + w * y for x, y in zip(a, v)]
        # a channel that only some of the clips animate: the others hold the bone at rest (not at zero, which
        # would shrink the bone away while one clip fades into another)
        rest = {"rotation_quaternion": [1.0, 0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0], "location": [0.0, 0.0, 0.0],
                "rotation_euler": [0.0, 0.0, 0.0]}
        for key, ws in wsum.items():
            if ws < 0.999 and key[1] in rest:
                acc[key] = [x + (1.0 - ws) * r for x, r in zip(acc[key], rest[key[1]])]
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
