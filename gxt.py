"""Encode 1024x1024 BMFont atlas images as Vita BC3 GXT textures."""
from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image


def compact(value: int) -> int:
    value &= 0x55555555
    value = (value ^ (value >> 1)) & 0x33333333
    value = (value ^ (value >> 2)) & 0x0F0F0F0F
    value = (value ^ (value >> 4)) & 0x00FF00FF
    value = (value ^ (value >> 8)) & 0x0000FFFF
    return value


def swizzle_bc3(linear: bytes, width: int, height: int) -> bytes:
    blocks_w = max(1, (width + 3) // 4)
    blocks_h = max(1, (height + 3) // 4)
    if blocks_w != blocks_h or blocks_w & (blocks_w - 1):
        raise ValueError("Expected a square power-of-two atlas")
    if len(linear) != blocks_w * blocks_h * 16:
        raise ValueError("BC3 block count does not match dimensions")
    result = bytearray(len(linear))
    for index in range(blocks_w * blocks_h):
        x = compact(index >> 1)
        y = compact(index)
        source = (y * blocks_w + x) * 16
        result[index * 16 : index * 16 + 16] = linear[source : source + 16]
    return bytes(result)


def encode(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        if image.size != (1024, 1024):
            raise ValueError(f"Unexpected atlas dimensions: {source}")
        alpha = (
            image.getchannel("A")
            if image.mode in ("RGBA", "LA")
            else image.convert("L")
        )
        width, height = image.size

    pixels = bytearray()
    mip_count = 0
    while True:
        white = Image.new("L", alpha.size, 255)
        rgba = Image.merge("RGBA", (white, white, white, alpha))
        buffer = io.BytesIO()
        rgba.save(buffer, format="DDS", pixel_format="DXT5")
        encoded = buffer.getvalue()
        if encoded[:4] != b"DDS " or encoded[84:88] != b"DXT5":
            raise ValueError(f"DXT5 encoding failed: {source}")
        pixels.extend(swizzle_bc3(encoded[128:], alpha.width, alpha.height))
        mip_count += 1
        if alpha.size == (1, 1):
            break
        alpha = alpha.resize(
            (max(1, alpha.width // 2), max(1, alpha.height // 2)),
            Image.Resampling.BOX,
        )

    header = struct.pack("<8I", 0x00545847, 0x10000003, 1, 64, len(pixels), 0, 0, 0)
    texture = struct.pack(
        "<6IHHB3x",
        64,
        len(pixels),
        0xFFFFFFFF,
        0,
        0,
        0x87000000,
        width,
        height,
        mip_count,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(header + texture + pixels)

