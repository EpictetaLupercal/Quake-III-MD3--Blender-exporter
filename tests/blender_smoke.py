"""Run: blender --background --factory-startup --python tests/blender_smoke.py"""
import importlib.util
from pathlib import Path
import struct
import tempfile
import bpy

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("io_export_md3", root / "io_export_md3.py")
addon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(addon)
addon.register()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.object
cube.modifiers.new("Stable triangles", "TRIANGULATE")
material = bpy.data.materials.new("models/test/cube")
cube.data.materials.append(material)
cube.location.x = 0
cube.keyframe_insert(data_path="location", frame=1)
cube.location.x = 2
cube.keyframe_insert(data_path="location", frame=2)
bpy.ops.object.empty_add()
bpy.context.object.name = "tag_weapon"
cube.select_set(True)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 2
bpy.context.scene.frame_set(7, subframe=0.5)

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "cube.md3"
    addon.export_md3(bpy.context, str(path), animation=True)
    data = path.read_bytes()
    h = struct.unpack_from("<4si64s9i", data)
    assert h[0:2] == (b"IDP3", 15)
    assert h[4:8] == (2, 1, 1, 0), h
    assert h[8] == 108 and h[9] == 108 + 2 * 56
    assert h[10] == h[9] + 2 * 112 and h[11] == len(data)
    offset = h[10]
    s = struct.unpack_from("<4s64s10i", data, offset)
    assert s[3] == 2 and s[4] == 1 and s[6] == 12
    assert s[5] == 24 and offset + s[11] == len(data)
    assert s[8] == s[7] + 12 * s[6]
    assert s[9] == s[8] + 68 and s[10] == s[9] + 8 * s[5]
    assert s[11] == s[10] + 8 * s[5] * 2
    p1 = struct.unpack_from("<3hH", data, offset + s[10])
    p2 = struct.unpack_from("<3hH", data, offset + s[10] + 8 * s[5])
    assert p2[0] - p1[0] == 128
    assert data[h[9]:h[9] + 10] == b"tag_weapon"
    assert bpy.context.scene.frame_current == 7
    assert bpy.context.scene.frame_subframe == 0.5
    # Failure must restore timeline and preserve the previous output.
    try:
        addon.export_md3(bpy.context, str(path), scale=10000)
    except ValueError:
        pass
    else:
        raise AssertionError("Out-of-range coordinates accepted")
    assert path.read_bytes() == data
    assert bpy.context.scene.frame_current == 7
addon.unregister()
print("MD3_SMOKE_OK", bpy.app.version_string)
