"""Binary writer checks without a Blender installation."""
import ast
import math
from pathlib import Path
import struct
import unittest

source = Path(__file__).resolve().parents[1] / "io_export_md3.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
names = {"cstr", "pack_normal", "pack_vertex", "surface_bytes"}
tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
namespace = {"math": math, "struct": struct}
exec(compile(tree, str(source), "exec"), namespace)


class Normal(tuple):
    def normalized(self):
        magnitude = math.sqrt(sum(v * v for v in self))
        return tuple(v / magnitude for v in self)


class BinaryTests(unittest.TestCase):
    def test_normals(self):
        for normal in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 0, -1), (-1, 2, -3)]:
            original = Normal(normal).normalized()
            packed = namespace["pack_normal"](Normal(normal))
            latitude = (packed >> 8) * 2 * math.pi / 255
            longitude = (packed & 255) * 2 * math.pi / 255
            decoded = (math.cos(latitude) * math.sin(longitude),
                       math.sin(latitude) * math.sin(longitude), math.cos(longitude))
            self.assertGreater(sum(a * b for a, b in zip(original, decoded)), 0.999)

    def test_coordinates_and_limits(self):
        pack = namespace["pack_vertex"]
        normal = Normal((0, 0, 1))
        data = pack((-512, 511.984375, 1.5), normal)
        self.assertEqual(struct.unpack("<3hH", data)[:3], (-32768, 32767, 96))
        for value in (512, -513, math.nan, math.inf):
            with self.assertRaises(ValueError):
                pack((value, 0, 0), normal)

    def test_surface_layout(self):
        surface = dict(name="mesh", shader="models/test", loops=[0, 1, 2],
                       triangles=[(2, 1, 0)], uv=[(0, 1), (1, 1), (0, 0)],
                       frames=[bytes(24), bytes(24)])
        data = namespace["surface_bytes"](surface, 2)
        h = struct.unpack_from("<4s64s10i", data)
        self.assertEqual(h[2:], (0, 2, 1, 3, 1, 108, 120, 188, 212, 260))
        self.assertEqual(len(data), 260)
        self.assertEqual(struct.unpack_from("<3i", data, 108), (2, 1, 0))
        self.assertEqual(struct.unpack_from("<2f", data, 188), (0, 1))

    def test_names(self):
        for value in ("x" * 64, "a\0b", "é"):
            with self.assertRaises(ValueError):
                namespace["cstr"](value, 64)


if __name__ == "__main__":
    unittest.main()
