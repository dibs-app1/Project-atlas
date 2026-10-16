"""Engine 4: the engine-3 world (models, scenery, actors, camera angles) rendered by Blender's EEVEE.

Blender gives what the software renderer could not: smooth rounded bodies (welded vertices + smooth
normals, with crisp edges kept where faces meet at an angle), soft real shadows, ambient occlusion,
a physically based sky with a real sun, and gentle surface detail on the ground. It runs headless
(the `bpy` package, CPU only through Mesa), so it works on an ordinary CI runner.

Every frame: the stage's objects (static scenery once, moving models every frame) are synced into
Blender as linked instances, the shot's camera is set, EEVEE renders, and the 2D extras (smoke, dust,
snow, bubbles, dashboards) are drawn on top with the same projection as before.
"""
import math

import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh
import numpy as np
from PIL import Image, ImageDraw

from engine3 import r3d as R3

W, H = R3.W, R3.H

# sky (sun elevation) and light per time of day: sun strength, sky strength, exposure, tint
LOOKS = {
    "morning": (3.2, 0.9, 0.05, (1.0, 0.92, 0.82)),
    "day": (3.8, 1.0, 0.0, (1.0, 0.98, 0.94)),
    "golden": (3.0, 0.8, 0.15, (1.0, 0.82, 0.62)),
    "dusk": (1.6, 0.7, 0.5, (1.0, 0.72, 0.6)),
    "night": (0.25, 0.08, 1.4, (0.7, 0.78, 1.0)),
    "snow": (2.2, 1.2, -0.7, (0.96, 0.97, 1.0)),
    "overcast": (1.6, 1.3, -0.45, (0.95, 0.96, 1.0)),
    "underwater": (2.6, 0.0, 0.3, (0.8, 0.95, 1.0)),
}


def _mat(name, kind):
    m = bpy.data.materials.new(name)
    nt = m.node_tree if m.node_tree else None
    if nt is None:
        m.use_nodes = True
        nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    attr = nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    attr.attribute_type = "GEOMETRY"
    col = attr.outputs["Color"]
    if kind == "ground":        # soft variation so big ground areas don't look flat
        tex = nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 0.6
        tex.inputs["Detail"].default_value = 8.0
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        ramp = nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value = 0.3
        ramp.inputs["From Max"].default_value = 0.7
        ramp.inputs["To Min"].default_value = 0.72
        ramp.inputs["To Max"].default_value = 1.15
        links.new(tex.outputs["Fac"], ramp.inputs["Value"])
        cmb = nodes.new("ShaderNodeCombineColor")
        for k in ("Red", "Green", "Blue"):
            links.new(ramp.outputs["Result"], cmb.inputs[k])
        links.new(col, mix.inputs["A"])
        links.new(cmb.outputs["Color"], mix.inputs["B"])
        col = mix.outputs["Result"]
    links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = {"ground": 0.95, "water": 0.22, "glossy": 0.35}.get(kind, 0.7)
    if kind == "water":
        bsdf.inputs["Specular IOR Level"].default_value = 0.3
    if kind == "emit":
        links.new(col, bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 2.0
    return m


def add_fog(mat, color, dist):
    """Blend a material towards the haze colour with distance from the camera (air haze, or murky water)."""
    if mat is None or not mat.node_tree or mat.get("fogged"):
        return
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out is None or not out.inputs["Surface"].links:
        return
    src = out.inputs["Surface"].links[0].from_socket
    cam = nt.nodes.new("ShaderNodeCameraData")
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MULTIPLY"
    k.inputs[1].default_value = -1.0 / dist
    nt.links.new(cam.outputs["View Distance"], k.inputs[0])
    e = nt.nodes.new("ShaderNodeMath")
    e.operation = "EXPONENT"
    nt.links.new(k.outputs[0], e.inputs[0])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(e.outputs[0], inv.inputs[1])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*[(c / 255) ** 2.2 for c in color], 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(inv.outputs[0], mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    mat["fogged"] = True


class Bridge:
    def __init__(self, time="day", sun_dir=(-0.35, 0.45, -0.82), res=(W, H), samples=4, underwater=None, fog=None, sky_cols=None,
                 hdri=None, hdri_strength=1.0, hdri_rot=0.0):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        PROPS.clear()          # a fresh Blender scene: forget models imported into the previous one
        self.sc = sc = bpy.context.scene
        sc.render.engine = "BLENDER_EEVEE"
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.compression = 0
        sc.render.film_transparent = False
        sc.eevee.taa_render_samples = samples
        sc.eevee.use_shadows = True
        sc.eevee.shadow_ray_count = 1
        sc.eevee.shadow_step_count = 4
        sc.eevee.use_raytracing = False
        sc.eevee.use_fast_gi = False
        sc.view_settings.view_transform = "Standard"     # true-to-colour (bright, friendly), not filmic grey
        sc.view_settings.look = "None"
        sun_s, sky_s, expo, tint = LOOKS.get(time, LOOKS["day"])
        sc.view_settings.exposure = expo
        self.mats = {k: _mat(k, k) for k in ("plain", "ground", "water", "emit", "glossy")}
        # sky and sun
        w = bpy.data.worlds.new("sky")
        sc.world = w
        nt = w.node_tree
        bg = nt.nodes.get("Background")
        d = -np.asarray(sun_dir, float)
        d /= np.linalg.norm(d)
        elev = math.asin(max(0.05, d[2]))
        # sky: a gradient from the horizon colour to the zenith colour by view direction (the world is lit by it)
        top, hz = sky_cols if sky_cols else ((66, 132, 214), (196, 220, 238))
        if underwater:
            top, hz = underwater
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        cr = ramp.color_ramp
        cr.elements[0].position, cr.elements[1].position = 0.0, 0.55
        lin = lambda c: tuple(((x / 255) ** 2.2) for x in c) + (1.0,)
        cr.elements[0].color, cr.elements[1].color = lin(hz), lin(top)
        nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = sky_s
        self.sky_cols = (top, hz)
        self.hdri = hdri
        if hdri and not underwater:       # a real photographed sky: its sun lights the scene and casts the shadows
            env = nt.nodes.new("ShaderNodeTexEnvironment")
            env.image = bpy.data.images.load(str(hdri))
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Rotation"].default_value[2] = hdri_rot
            nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
            nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
            nt.links.new(env.outputs["Color"], bg.inputs["Color"])
            bg.inputs["Strength"].default_value = hdri_strength
            w.sun_threshold = 2.0
            w.sun_angle = math.radians(3.0)
            w.use_sun_shadow = True
        sun = bpy.data.lights.new("sun", "SUN")
        sun.energy = sun_s if not (hdri and not underwater) else 0.0
        sun.color = tint
        sun.angle = math.radians(2.5)
        so = bpy.data.objects.new("sun", sun)
        sc.collection.objects.link(so)
        so.rotation_euler = self._dir_to_euler(sun_dir)
        # camera
        cd = bpy.data.cameras.new("cam")
        cd.sensor_fit = "HORIZONTAL"
        cd.clip_start, cd.clip_end = 0.15, 9000
        self.cam = bpy.data.objects.new("cam", cd)
        sc.collection.objects.link(self.cam)
        sc.camera = self.cam
        self.fog = fog            # (colour, distance) or None
        if fog:
            for m in self.mats.values():
                add_fog(m, *fog)
        self.pool = {}       # id(mesh) -> list of bpy objects using that mesh
        self.static_ids = set()
        self.used = {}
        self.static_done = False

    @staticmethod
    def _dir_to_euler(direction):
        d = np.asarray(direction, float)
        d /= np.linalg.norm(d)
        # a sun lamp shines down its local -Z: build a rotation that maps -Z onto d
        z = -d
        x = np.cross((0, 0, 1.0), z)
        if np.linalg.norm(x) < 1e-6:
            x = np.array([1.0, 0, 0])
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        from mathutils import Matrix
        return Matrix(np.stack([x, y, z], axis=1).tolist()).to_euler()

    # -------------------------------------------------------------- meshes
    def _bmesh(self, mesh, layer, smooth_angle=52.0):
        V = np.asarray(mesh.v, float)
        me = bpy.data.meshes.new("m")
        if not len(mesh.f):
            return me
        bm = bmesh.new()
        verts = [bm.verts.new(p) for p in V]
        bm.verts.ensure_lookup_table()
        ci = bm.faces.layers.int.new("ci")
        for k, f in enumerate(mesh.f):
            try:
                face = bm.faces.new([verts[i] for i in f])
            except ValueError:          # duplicate face
                continue
            face[ci] = k
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        thr = math.radians(smooth_angle)
        for e in bm.edges:
            if len(e.link_faces) == 2:
                e.smooth = e.calc_face_angle(0.0) < thr
            else:
                e.smooth = False
        for f in bm.faces:
            f.smooth = layer != 0
        bm.to_mesh(me)
        bm.free()
        nf = len(me.polygons)
        idx = np.zeros(nf, np.int32)
        if "ci" in me.attributes:
            me.attributes["ci"].data.foreach_get("value", idx)
        C = np.asarray(mesh.c, float)[idx] / 255.0
        FL = np.asarray(mesh.fl, int)[idx]
        loop_poly = np.zeros(len(me.loops), np.int32)
        starts = np.zeros(nf, np.int32)
        totals = np.zeros(nf, np.int32)
        me.polygons.foreach_get("loop_start", starts)
        me.polygons.foreach_get("loop_total", totals)
        loop_poly = np.repeat(np.arange(nf), totals)
        rgba = np.ones((len(me.loops), 4), np.float32)
        rgba[:, :3] = C[loop_poly]
        attr = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
        # byte colours are stored in sRGB, so pass sRGB values via color_srgb
        attr.data.foreach_set("color_srgb", rgba.ravel())
        mi = np.where((FL & 1) > 0, 1, 0).astype(np.int32)
        me.polygons.foreach_set("material_index", mi)
        if "ci" in me.attributes:
            me.attributes.remove(me.attributes["ci"])
        return me

    def _kind(self, obj):
        if getattr(obj, "name", "") == "water":
            return "water"
        return "ground" if obj.layer == 0 else "plain"

    def _new_obj(self, src, me=None):
        if me is None:
            me = self._bmesh(src.mesh, src.layer)
            me.materials.append(self.mats[self._kind(src)])
            me.materials.append(self.mats["emit"])
        ob = bpy.data.objects.new("o", me)
        self.sc.collection.objects.link(ob)
        if src.layer == 1 and id(src.mesh) not in self.static_ids and len(src.mesh.f) < 6000:
            sub = ob.modifiers.new("smooth", "SUBSURF")      # rounded, natural bodies
            sub.levels = sub.render_levels = 2
            sub.boundary_smooth = "PRESERVE_CORNERS"
        ob.visible_shadow = bool(src.shadow) and src.layer != 0
        return ob

    @staticmethod
    def _matrix(pos, Rm, z_off=0.0):
        M = np.eye(4)
        M[:3, :3] = Rm
        M[:3, 3] = np.asarray(pos, float) + (0, 0, z_off)
        return M

    def sync(self, objs, frame_key):
        """Place every object of this frame. Meshes seen before are reused (moving models just move)."""
        count = {}
        for o in objs:
            k = id(o.mesh)
            n = count.get(k, 0)
            count[k] = n + 1
            lst = self.pool.setdefault(k, [])
            if n >= len(lst):
                lst.append(self._new_obj(o) if not lst else self._new_obj(o, lst[0].data))
                self.used[k] = o.mesh          # keep the mesh alive so its id is not reused
            ob = lst[n]
            z_off = o.order * 0.015 if o.layer == 0 else 0.0     # ground layers stacked a little apart (no flicker)
            ob.matrix_world = _mtx(self._matrix(o.pos, o.R, z_off))
            ob.hide_render = False
        for k, lst in list(self.pool.items()):
            n = count.get(k, 0)
            for ob in lst[n:]:
                ob.hide_render = True

    def drop_unused(self, keep):
        """Delete objects whose mesh is not in `keep` (one-frame meshes such as wakes and ripples)."""
        for k in list(self.pool):
            if k not in keep:
                for ob in self.pool[k]:
                    me = ob.data
                    bpy.data.objects.remove(ob)
                    if me.users == 0:
                        bpy.data.meshes.remove(me)
                del self.pool[k]
                self.used.pop(k, None)

    def fog_all(self):
        """Apply the haze to every material (call after importing models)."""
        if self.fog:
            for m in bpy.data.materials:
                add_fog(m, *self.fog)

    def prop(self, path, pos, yaw=0.0, scale=1.0, name="prop", shadow=True, size=None):
        """Place an artist-made scenery model (tree, rock, flowers, barn...) as a light-weight instance."""
        col = PROPS.get(str(path))
        if col is None:
            col = bpy.data.collections.new("lib_" + str(len(PROPS)))
            before = set(bpy.data.objects)
            if str(path).lower().endswith(".fbx"):
                bpy.ops.import_scene.fbx(filepath=str(path))
            else:
                bpy.ops.import_scene.gltf(filepath=str(path))
            new = [o for o in set(bpy.data.objects) - before]
            for o in [o for o in new if o.type not in ("MESH", "EMPTY")]:
                bpy.data.objects.remove(o)
            new = [o for o in set(bpy.data.objects) - before]
            from engine4.rigs import clean_materials
            clean_materials([o for o in new if o.type == "MESH"])
            bpy.context.view_layer.update()
            # sit the model on the ground at its footprint centre
            pts = [o.matrix_world @ __import__("mathutils").Vector(c) for o in new if o.type == "MESH" for c in o.bound_box]
            if pts:
                zmin = min(p[2] for p in pts)
                cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
                cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
                col.instance_offset = (cx, cy, zmin)
                col["w"] = max(p[0] for p in pts) - min(p[0] for p in pts)
                col["d"] = max(p[1] for p in pts) - min(p[1] for p in pts)
                col["h"] = max(p[2] for p in pts) - zmin
            for o in new:
                for c in list(o.users_collection):
                    c.objects.unlink(o)
                col.objects.link(o)
            PROPS[str(path)] = col
        e = bpy.data.objects.new(name, None)
        e.instance_type = "COLLECTION"
        e.instance_collection = col
        e.location = tuple(float(x) for x in pos)
        e.rotation_euler = (0, 0, yaw)
        if size is not None and "h" in col:      # normalise to a real-world size, then vary by `scale`
            axis, metres = size
            native = col["h"] if axis == "h" else max(col["w"], col["d"])
            scale = scale * metres / max(1e-6, native)
        e.scale = (scale, scale, scale)
        e.visible_shadow = shadow
        self.sc.collection.objects.link(e)
        return e

    def camera(self, cam):
        B = cam.B                       # rows: right, up, forward
        M = np.eye(4)
        M[:3, 0], M[:3, 1], M[:3, 2] = B[0], B[1], -B[2]
        M[:3, 3] = cam.pos
        self.cam.matrix_world = _mtx(M)
        self.cam.data.angle = math.radians(cam.fov)

    def render(self, path):
        self.sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return Image.open(path).convert("RGB")


PROPS = {}


def _mtx(M):
    from mathutils import Matrix
    return Matrix(M.tolist())


def overlay(img, cam, fns, t):
    """Draw engine-3 2D extras on a Blender frame (they expect the supersampled canvas)."""
    if not fns:
        return img
    big = img.resize((W * R3.SS, H * R3.SS), Image.BILINEAR)
    d = ImageDraw.Draw(big, "RGBA")
    for fn in fns:
        fn(big, d, cam, t)
    return big.reduce(R3.SS)
