"""Generate deterministic PWA PNG icons with Python's standard library."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "public" / "icons"

INK = (16, 37, 43, 255)
MINT = (47, 198, 170, 255)
SIGNAL = (255, 122, 77, 255)


def inside_rounded_rect(x: int, y: int, left: int, top: int, right: int, bottom: int, radius: int) -> bool:
    if left + radius <= x < right - radius or top + radius <= y < bottom - radius:
        return left <= x < right and top <= y < bottom
    cx = left + radius if x < left + radius else right - radius - 1
    cy = top + radius if y < top + radius else bottom - radius - 1
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2


def icon_pixels(size: int, safe: bool) -> bytes:
    pixels = bytearray(INK * (size * size))
    inset = round(size * (0.22 if safe else 0.14))
    left = top = inset
    right = bottom = size - inset
    radius = round(size * 0.12)

    for y in range(top, bottom):
        for x in range(left, right):
            bubble = inside_rounded_rect(x, y, left, top, right, bottom, radius)
            tail = left + radius <= x < left + round(size * .27) and bottom <= y < bottom + round(size * .08)
            if bubble or (tail and x - (left + radius) <= bottom + round(size * .08) - y):
                offset = (y * size + x) * 4
                pixels[offset:offset + 4] = bytes(MINT)

    bar_width = max(3, round(size * .055))
    gap = round(size * .055)
    base_y = round(size * .64)
    start_x = round(size * .34)
    heights = [round(size * .14), round(size * .23), round(size * .32)]
    for index, height in enumerate(heights):
        bar_left = start_x + index * (bar_width + gap)
        for y in range(base_y - height, base_y):
            for x in range(bar_left, bar_left + bar_width):
                offset = (y * size + x) * 4
                pixels[offset:offset + 4] = bytes(INK)

    dot_x, dot_y, dot_radius = round(size * .67), round(size * .34), round(size * .055)
    for y in range(dot_y - dot_radius, dot_y + dot_radius + 1):
        for x in range(dot_x - dot_radius, dot_x + dot_radius + 1):
            if (x - dot_x) ** 2 + (y - dot_y) ** 2 <= dot_radius ** 2:
                offset = (y * size + x) * 4
                pixels[offset:offset + 4] = bytes(SIGNAL)
    return bytes(pixels)


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def write_png(path: Path, size: int, safe: bool = False) -> None:
    pixels = icon_pixels(size, safe)
    stride = size * 4
    scanlines = b"".join(b"\x00" + pixels[row * stride:(row + 1) * stride] for row in range(size))
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(scanlines, 9))
    png += png_chunk(b"IEND", b"")
    path.write_bytes(png)


if __name__ == "__main__":
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for filename, size, safe in (
        ("pwa-192.png", 192, False),
        ("pwa-512.png", 512, False),
        ("pwa-maskable-512.png", 512, True),
        ("apple-touch-icon-180.png", 180, True),
    ):
        write_png(ICON_DIR / filename, size, safe)
        print(f"generated {filename}")
