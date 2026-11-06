"""Blender 5.0 MD3 exporter. SPDX-License-Identifier: MIT."""

import math
import os
import struct
import tempfile

import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

bl_info = {
    "name": "Quake III MD3 Exporter",
    "author": "MD3 Exporter contributors",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "File > Export > Quake III (.md3)",
    "description": "Export meshes, vertex animation and tag empties to MD3",
    "category": "Import-Export",
}


def cstr(value, size):
    """Reject ambiguous or silently truncated Quake names."""
    data = value.encode("ascii")
    if len(data) >= size or b"\0" in data:
        raise ValueError(f"Name must contain at most {size - 1} ASCII bytes: {value}")
    return data.ljust(size, b"\0")


def pack_normal(normal):
    x, y, z = normal.normalized()
    if not all(math.isfinite(v) for v in (x, y, z)):
        raise ValueError("Non-finite normal")
    latitude = round(math.atan2(y, x) * 255 / (2 * math.pi)) & 255
    longitude = round(math.acos(max(-1, min(1, z))) * 255 / (2 * math.pi)) & 255
    return (latitude << 8) | longitude


def pack_vertex(position, normal):
    if not all(math.isfinite(v) for v in position):
        raise ValueError("Non-finite vertex")
    xyz = [round(v * 64) for v in position]
    if any(v < -32768 or v > 32767 for v in xyz):
        raise ValueError("Vertex outside MD3 range [-512, 511.984375]; reduce Scale")
    return struct.pack("<3hH", *xyz, pack_normal(normal))


def surface_bytes(surface, frame_count):
    triangles = b"".join(struct.pack("<3i", *t) for t in surface["triangles"])
    shaders = struct.pack("<64si", cstr(surface["shader"], 64), 0)
    uv = b"".join(struct.pack("<2f", *st) for st in surface["uv"])
    vertices = b"".join(surface["frames"])
    ot = 108
    os = ot + len(triangles)
    ou = os + len(shaders)
    ov = ou + len(uv)
    header = struct.pack(
        "<4s64s10i", b"IDP3", cstr(surface["name"], 64), 0,
        frame_count, 1, len(surface["loops"]), len(surface["triangles"]),
        ot, os, ou, ov, ov + len(vertices),
    )
    return header + triangles + shaders + uv + vertices


def mesh_signature(mesh):
    return (
        len(mesh.vertices),
        tuple((tuple(t.vertices), tuple(t.loops), t.material_index)
              for t in mesh.loop_triangles),
        tuple(tuple(item.vector) for item in mesh.uv_layers.active.uv),
    )


def make_surfaces(obj, mesh, mirrored):
    surfaces = []
    materials = sorted({t.material_index for t in mesh.loop_triangles})
    for material_index in materials:
        triangles = [t for t in mesh.loop_triangles if t.material_index == material_index]
        material = mesh.materials[material_index] if material_index < len(mesh.materials) else None
        shader = str(material.get("md3_shader", material.name)) if material else ""
        shader = shader.replace("\\", "/")
        cstr(shader, 64)
        # At most 999 vertices: vanilla Q3 rejects surfaces with >=1000.
        for start in range(0, len(triangles), 333):
            loops, indices, output = [], {}, []
            for triangle in triangles[start:start + 333]:
                face = []
                for loop in triangle.loops:
                    if loop not in indices:
                        indices[loop] = len(loops)
                        loops.append(loop)
                    face.append(indices[loop])
                # MD3 uses clockwise front faces; reflected transforms reverse them.
                output.append(tuple(face if mirrored else reversed(face)))
            name = f"{obj.name}_{material_index}_{start // 333}"
            cstr(name, 64)
            uv = [tuple(mesh.uv_layers.active.uv[i].vector) for i in loops]
            surfaces.append(dict(name=name, shader=shader, loops=loops,
                                 triangles=output, uv=[(u, 1 - v) for u, v in uv], frames=[]))
    return surfaces


def export_md3(context, filepath, selected=True, animation=False, scale=1.0):
    scene = context.scene
    objects = sorted(context.selected_objects if selected else scene.objects, key=lambda o: o.name)
    meshes = [o for o in objects if o.type == "MESH"]
    tags = [o for o in objects if o.type == "EMPTY" and o.name.startswith("tag_")]
    if not meshes:
        raise ValueError("Select at least one mesh")
    if len(tags) > 16:
        raise ValueError("MD3 supports at most 16 tags")
    frames = list(range(scene.frame_start, scene.frame_end + 1)) if animation else [scene.frame_current]
    if not 1 <= len(frames) <= 1024:
        raise ValueError("MD3 requires 1 to 1024 frames")
    original_frame, original_subframe = scene.frame_current, scene.frame_subframe
    states, surfaces, frame_data, tag_data = {}, [], [], []
    try:
        for frame_number in frames:
            scene.frame_set(frame_number)
            graph = context.evaluated_depsgraph_get()
            positions = []
            for obj in meshes:
                evaluated = obj.evaluated_get(graph)
                mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
                try:
                    mesh.calc_loop_triangles()
                    if not mesh.uv_layers.active:
                        raise ValueError(f"{obj.name}: an active UV map is required")
                    matrix = evaluated.matrix_world
                    determinant = matrix.to_3x3().determinant()
                    if abs(determinant) < 1e-12:
                        raise ValueError(f"{obj.name}: singular transform")
                    mirrored = determinant < 0
                    signature = mesh_signature(mesh)
                    if obj.name not in states:
                        parts = make_surfaces(obj, mesh, mirrored)
                        states[obj.name] = (signature, mirrored, parts)
                        surfaces.extend(parts)
                        if len(surfaces) > 32:
                            raise ValueError("More than 32 MD3 surfaces; simplify or export separate models")
                    old_signature, old_mirrored, parts = states[obj.name]
                    if signature != old_signature or mirrored != old_mirrored:
                        raise ValueError(f"{obj.name}: topology, UVs or reflection changes during animation")
                    normal_matrix = matrix.to_3x3().inverted().transposed()
                    for part in parts:
                        data = []
                        for loop in part["loops"]:
                            position = (matrix @ mesh.vertices[mesh.loops[loop].vertex_index].co) * scale
                            normal = normal_matrix @ mesh.corner_normals[loop].vector
                            data.append(pack_vertex(position, normal))
                            # Bounds include the actual quantized positions stored in MD3.
                            positions.append(tuple(round(v * 64) / 64 for v in position))
                        part["frames"].append(b"".join(data))
                finally:
                    evaluated.to_mesh_clear()
            if not positions:
                raise ValueError("No triangles to export")
            lower = [min(p[i] for p in positions) for i in range(3)]
            upper = [max(p[i] for p in positions) for i in range(3)]
            radius = max(math.sqrt(sum(v * v for v in p)) for p in positions)
            frame_data.append(struct.pack("<10f16s", *lower, *upper, 0, 0, 0,
                                          radius, cstr(f"frame_{frame_number}", 16)))
            for tag in tags:
                matrix = tag.evaluated_get(graph).matrix_world
                axes = [matrix.to_3x3().col[i].normalized() for i in range(3)]
                if (matrix.to_3x3().determinant() <= 1e-12 or
                        any(abs(axes[i].dot(axes[j])) > 1e-4 for i in range(3) for j in range(i))):
                    raise ValueError(f"{tag.name}: tags require non-reflected, non-sheared axes")
                tag_data.append(struct.pack("<64s12f", cstr(tag.name, 64),
                                            *(matrix.translation * scale),
                                            *(v for axis in axes for v in axis)))
    finally:
        scene.frame_set(original_frame, subframe=original_subframe)
    frame_blob, tag_blob = b"".join(frame_data), b"".join(tag_data)
    surface_blob = b"".join(surface_bytes(s, len(frames)) for s in surfaces)
    ot = 108 + len(frame_blob)
    osurf = ot + len(tag_blob)
    header = struct.pack("<4si64s9i", b"IDP3", 15, cstr(os.path.basename(filepath), 64),
                         0, len(frames), len(tags), len(surfaces), 0,
                         108, ot, osurf, osurf + len(surface_blob))
    # Never replace an existing model with a partially written file.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(os.path.abspath(filepath)), delete=False) as stream:
            temporary = stream.name
            stream.write(header + frame_blob + tag_blob + surface_blob)
        os.replace(temporary, filepath)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


class EXPORT_SCENE_OT_md3(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.md3"
    bl_label = "Export Quake III MD3"
    filename_ext = ".md3"
    filter_glob: StringProperty(default="*.md3", options={"HIDDEN"})
    selected: BoolProperty(name="Selected objects only", default=True)
    animation: BoolProperty(name="Export scene frame range", default=False)
    scale: FloatProperty(name="Scale", default=1.0, min=0.000001)

    def execute(self, context):
        if context.mode != "OBJECT":
            self.report({"ERROR"}, "Switch to Object Mode before exporting")
            return {"CANCELLED"}
        try:
            export_md3(context, self.filepath, self.selected, self.animation, self.scale)
        except (ValueError, OSError, RuntimeError, OverflowError, struct.error) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, "MD3 exported")
        return {"FINISHED"}


def menu_export(self, context):
    self.layout.operator(EXPORT_SCENE_OT_md3.bl_idname, text="Quake III Arena (.md3)")


def register():
    bpy.utils.register_class(EXPORT_SCENE_OT_md3)
    bpy.types.TOPBAR_MT_file_export.append(menu_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_export)
    bpy.utils.unregister_class(EXPORT_SCENE_OT_md3)


if __name__ == "__main__":
    register()
