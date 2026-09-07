"""Wrap the original Herdr PNG in an ICO container without changing its pixels."""
from pathlib import Path
import struct

root = Path(__file__).resolve().parent.parent
png = (root / "assets/herdr.png").read_bytes()
width, height = struct.unpack(">II", png[16:24])
if not 1 <= width <= 256 or not 1 <= height <= 256:
    raise ValueError("Use a PNG icon between 1 and 256 pixels")
icon = struct.pack("<HHH", 0, 1, 1)
icon += struct.pack("<BBBBHHII", width % 256, height % 256, 0, 0, 1, 32, len(png), 22)
output = root / "build/herdr.ico"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_bytes(icon + png)
