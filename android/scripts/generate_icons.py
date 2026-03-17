#!/usr/bin/env python3
"""
generate_icons.py — Generate PNG launcher icons for all Android mipmap densities
and Play Store assets from the vector drawable design.

Icon design (mirrors ic_launcher_foreground.xml + ic_launcher_background.xml):
  Background : solid #1565C0 (Material Deep Blue 800)
  Foreground : white cross centred on a 108×108 dp adaptive-icon canvas
               Vertical bar   : x=50–58, y=24–84
               Horizontal bar : x=30–78, y=44–52

Usage:
    python3 scripts/generate_icons.py

Outputs are written relative to the script's parent directory
(i.e. android/app/src/main/res/mipmap-* and android/play_store_assets/).
"""

from __future__ import annotations

import math
import os
import struct
import zlib
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
BG_COLOR = (0x15, 0x65, 0xC0, 0xFF)  # #1565C0 opaque
FG_COLOR = (0xFF, 0xFF, 0xFF, 0xFF)  # white opaque

# ---------------------------------------------------------------------------
# Adaptive-icon canvas (vector viewport in dp)
# ---------------------------------------------------------------------------
CANVAS_DP = 108  # vector viewport is 108 × 108

# Cross geometry in vector coordinate space (0–108)
# These numbers come directly from ic_launcher_foreground.xml
CROSS_V = (50, 24, 58, 84)   # (x1, y1, x2, y2) vertical bar
CROSS_H = (30, 44, 78, 52)   # horizontal bar

# ---------------------------------------------------------------------------
# Mipmap density specs
# ---------------------------------------------------------------------------
class DensitySpec(NamedTuple):
    name: str        # folder suffix, e.g. "mdpi"
    icon_px: int     # launcher icon size in pixels
    round: bool = True  # also produce ic_launcher_round.png


DENSITIES: list[DensitySpec] = [
    DensitySpec("mdpi",    48),
    DensitySpec("hdpi",    72),
    DensitySpec("xhdpi",   96),
    DensitySpec("xxhdpi",  144),
    DensitySpec("xxxhdpi", 192),
]

# ---------------------------------------------------------------------------
# Minimal pure-stdlib PNG writer
# ---------------------------------------------------------------------------

def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    c = chunk_type + data
    return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)


def _encode_png(width: int, height: int, pixels: list[tuple[int, int, int, int]]) -> bytes:
    """Encode RGBA pixel list to PNG bytes (RGBA, 8-bit)."""
    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)
    # IDAT — filter byte 0 (None) before each row
    raw_rows = bytearray()
    for y in range(height):
        raw_rows.append(0)  # filter type None
        for x in range(width):
            r, g, b, a = pixels[y * width + x]
            raw_rows.extend([r, g, b, a])
    compressed = zlib.compress(bytes(raw_rows), level=9)
    idat = _png_chunk(b"IDAT", compressed)
    iend = _png_chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# ---------------------------------------------------------------------------
# Icon renderer
# ---------------------------------------------------------------------------

def _scale(value: float, size: int) -> float:
    """Map a coordinate from the 108-dp viewport to a pixel canvas of `size`."""
    return value * size / CANVAS_DP


def _render_icon(size: int, *, circle_clip: bool = False) -> list[tuple[int, int, int, int]]:
    """
    Render a `size x size` RGBA pixel buffer of the launcher icon.

    If circle_clip=True, pixels outside the inscribed circle are transparent
    (used for the round icon variant).
    """
    pixels: list[tuple[int, int, int, int]] = []

    # Pre-compute cross rectangles in pixel space
    vx1 = _scale(CROSS_V[0], size)
    vy1 = _scale(CROSS_V[1], size)
    vx2 = _scale(CROSS_V[2], size)
    vy2 = _scale(CROSS_V[3], size)

    hx1 = _scale(CROSS_H[0], size)
    hy1 = _scale(CROSS_H[1], size)
    hx2 = _scale(CROSS_H[2], size)
    hy2 = _scale(CROSS_H[3], size)

    cx = size / 2.0
    cy = size / 2.0
    r  = size / 2.0

    for y in range(size):
        for x in range(size):
            # Circle mask
            if circle_clip:
                dx = x + 0.5 - cx
                dy = y + 0.5 - cy
                if math.sqrt(dx * dx + dy * dy) > r:
                    pixels.append((0, 0, 0, 0))
                    continue

            # Foreground cross (white)
            px = x + 0.5
            py = y + 0.5
            if (vx1 <= px <= vx2 and vy1 <= py <= vy2) or \
               (hx1 <= px <= hx2 and hy1 <= py <= hy2):
                pixels.append(FG_COLOR)
            else:
                pixels.append(BG_COLOR)

    return pixels


def _write_png(path: Path, width: int, height: int,
               pixels: list[tuple[int, int, int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_encode_png(width, height, pixels))
    print(f"  wrote {path}  ({width}×{height})")


# ---------------------------------------------------------------------------
# Feature graphic renderer  (1024 × 500)
# ---------------------------------------------------------------------------

def _render_feature_graphic(width: int = 1024, height: int = 500) -> tuple[list[tuple[int, int, int, int]], int, int]:
    """
    Create a simple branded feature graphic:
    - Deep-blue background
    - Centred icon (≈40 % of height)
    - Gradient-style darker strip at the bottom third
    """
    icon_size = int(height * 0.40)  # ~200 px icon
    icon_pixels = _render_icon(icon_size, circle_clip=True)

    # Canvas background
    pixels: list[tuple[int, int, int, int]] = [BG_COLOR] * (width * height)

    # Slightly darker bottom band (decorative)
    dark = (0x0D, 0x47, 0xA1, 0xFF)  # #0D47A1 — Blue 900
    band_start_y = height * 2 // 3
    for y in range(band_start_y, height):
        # blend: lerp from BG_COLOR → dark over the band
        t = (y - band_start_y) / (height - band_start_y)
        blended = tuple(
            int(BG_COLOR[i] + t * (dark[i] - BG_COLOR[i])) for i in range(4)
        )
        for x in range(width):
            pixels[y * width + x] = blended  # type: ignore[assignment]

    # Stamp the icon centred on canvas
    icon_x0 = (width  - icon_size) // 2
    icon_y0 = (height - icon_size) // 2 - int(height * 0.04)  # slight upward nudge

    for iy in range(icon_size):
        for ix in range(icon_size):
            r, g, b, a = icon_pixels[iy * icon_size + ix]
            if a == 0:
                continue
            cx = icon_x0 + ix
            cy = icon_y0 + iy
            if 0 <= cx < width and 0 <= cy < height:
                # Alpha-composite over background
                bg = pixels[cy * width + cx]
                alpha = a / 255.0
                blended_px = (
                    int(r * alpha + bg[0] * (1 - alpha)),
                    int(g * alpha + bg[1] * (1 - alpha)),
                    int(b * alpha + bg[2] * (1 - alpha)),
                    255,
                )
                pixels[cy * width + cx] = blended_px  # type: ignore[assignment]

    return pixels, width, height


# ---------------------------------------------------------------------------
# Play-store 512 × 512 icon
# ---------------------------------------------------------------------------

def _render_store_icon(size: int = 512) -> list[tuple[int, int, int, int]]:
    """
    Play Store requires a 512×512 RGBA PNG with no transparency.
    We render a square icon (no circle clip) to keep it simple and let the
    Play Store apply its own mask.
    """
    return _render_icon(size, circle_clip=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    script_dir = Path(__file__).resolve().parent          # android/scripts/
    res_dir    = script_dir.parent / "app" / "src" / "main" / "res"
    assets_dir = script_dir.parent / "play_store_assets"

    print("=== Generating mipmap PNG icons ===")
    for spec in DENSITIES:
        folder = res_dir / f"mipmap-{spec.name}"

        # Square launcher icon
        px = _render_icon(spec.icon_px)
        _write_png(folder / "ic_launcher.png", spec.icon_px, spec.icon_px, px)

        # Round launcher icon
        px_round = _render_icon(spec.icon_px, circle_clip=True)
        _write_png(folder / "ic_launcher_round.png", spec.icon_px, spec.icon_px, px_round)

    print("\n=== Generating Play Store assets ===")
    # 512×512 app icon
    store_px = _render_store_icon(512)
    _write_png(assets_dir / "ic_launcher_store_512.png", 512, 512, store_px)

    # 1024×500 feature graphic
    fg_pixels, fg_w, fg_h = _render_feature_graphic(1024, 500)
    _write_png(assets_dir / "feature_graphic_1024x500.png", fg_w, fg_h, fg_pixels)

    print("\nDone! ✓")
    print(f"  Mipmap PNGs  → {res_dir}/mipmap-{{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}}/")
    print(f"  Store assets → {assets_dir}/")
    print()
    print("Next steps for Play Store screenshots:")
    print("  1. Run the app on a device/emulator (pixel_6 or similar 1080×2400 profile)")
    print("  2. Take screenshots via Android Studio Device Manager → Screenshot button")
    print("  3. Place 1080×1920 (or 9:16) PNGs in android/play_store_assets/screenshots/")


if __name__ == "__main__":
    main()
