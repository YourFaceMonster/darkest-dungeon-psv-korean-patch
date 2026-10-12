"""Build Vita-format Korean localization files from the Switch update.

The inputs are read only. Output is written to this script's ``converted`` folder.
"""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import zlib
from collections import Counter
from pathlib import Path


DEFAULT_VITA = Path("input/content.psarc")
DEFAULT_SWITCH = Path("input/switch_romfs")
OUTPUT = Path("build/converted")


def u32(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


class Psarc:
    def __init__(self, path: Path):
        self.data = path.read_bytes()
        data = self.data
        if data[:4] != b"PSAR" or data[8:12] != b"zlib":
            raise ValueError("Unsupported PSARC header")
        self.toc_end = int.from_bytes(data[12:16], "big")
        self.entry_size = int.from_bytes(data[16:20], "big")
        self.entry_count = int.from_bytes(data[20:24], "big")
        self.block_size = int.from_bytes(data[24:28], "big")
        if self.entry_size != 30 or self.block_size != 65536:
            raise ValueError("Unexpected PSARC entry or block size")
        self.block_lengths = data[32 + self.entry_count * self.entry_size : self.toc_end]
        self.names = self._read_entry(0).decode("utf-8").splitlines()
        if len(self.names) + 1 != self.entry_count:
            raise ValueError("PSARC manifest and entry table disagree")
        self.index = {name: i + 1 for i, name in enumerate(self.names)}

    def _read_entry(self, index: int) -> bytes:
        data = self.data
        start = 32 + index * self.entry_size
        entry = data[start : start + self.entry_size]
        block_index = int.from_bytes(entry[16:20], "big")
        expected_size = int.from_bytes(entry[20:25], "big")
        pos = int.from_bytes(entry[25:30], "big")
        result = bytearray()
        for i in range((expected_size + self.block_size - 1) // self.block_size):
            at = (block_index + i) * 2
            compressed_size = int.from_bytes(self.block_lengths[at : at + 2], "big")
            if compressed_size == 0:
                compressed_size = self.block_size
            block = data[pos : pos + compressed_size]
            pos += compressed_size
            try:
                result.extend(zlib.decompress(block))
            except zlib.error:
                result.extend(block)
        if len(result) != expected_size:
            raise ValueError(f"PSARC entry {index}: size mismatch")
        return bytes(result)

    def read(self, name: str) -> bytes:
        return self._read_entry(self.index[name])


def read_segments(data: bytes, index_start: int, text_start: int):
    if (text_start - index_start) % 12:
        raise ValueError("Invalid segment table")
    result = []
    for pos in range(index_start, text_start, 12):
        offset, length, flag = struct.unpack_from("<III", data, pos)
        end = text_start + offset + length
        if end > len(data):
            raise ValueError("String segment outside file")
        result.append((data[text_start + offset : end], flag))
    return result


def read_loc(data: bytes):
    key_end, text_index_end = struct.unpack_from("<II", data)
    if key_end < 4104 or (key_end - 4104) % 12:
        raise ValueError("Invalid .loc key table")
    segments = read_segments(data, key_end, text_index_end)
    keys = []
    for pos in range(4104, key_end, 12):
        key, count, first = struct.unpack_from("<III", data, pos)
        if first + count > len(segments):
            raise ValueError("Invalid .loc segment range")
        keys.append((key, segments[first : first + count]))
    return data[8:4104], keys


def read_loc2(data: bytes):
    key_end, mapping_end, text_index_end = struct.unpack_from("<III", data)
    if key_end < 4108 or (key_end - 4108) % 12 or (mapping_end - key_end) % 8:
        raise ValueError("Invalid .loc2 table layout")
    segments = read_segments(data, mapping_end, text_index_end)
    mappings = [
        struct.unpack_from("<II", data, pos)
        for pos in range(key_end, mapping_end, 8)
    ]
    result = {}
    for pos in range(4108, key_end, 12):
        key, mapping_index, mapping_count = struct.unpack_from("<III", data, pos)
        if mapping_count != 1 or mapping_index >= len(mappings):
            raise ValueError("Unsupported .loc2 string mapping")
        first, count = mappings[mapping_index]
        if first + count > len(segments):
            raise ValueError("Invalid .loc2 segment range")
        result[key] = segments[first : first + count]
    return result


def build_loc(buckets: bytes, entries):
    if len(buckets) != 4096:
        raise ValueError("Invalid bucket table")
    key_end = 8 + len(buckets) + len(entries) * 12
    key_table = bytearray()
    segment_table = bytearray()
    text = bytearray()
    segment_index = 0
    for key, segments in entries:
        key_table.extend(struct.pack("<III", key, len(segments), segment_index))
        segment_index += len(segments)
        for raw, flag in segments:
            segment_table.extend(struct.pack("<III", len(text), len(raw), flag))
            text.extend(raw)
    text_start = key_end + len(segment_table)
    return b"".join(
        [struct.pack("<II", key_end, text_start), buckets, key_table, segment_table, text]
    )


def convert_table(vita: Psarc, switch_root: Path, vita_name: str, sources: list[str]):
    buckets, original = read_loc(vita.read(vita_name))
    source_tables = [read_loc2((switch_root / source).read_bytes()) for source in sources]
    entries = []
    counts = Counter()
    for key, english_segments in original:
        for source, table in zip(sources, source_tables):
            if key in table:
                entries.append((key, table[key]))
                counts[source] += 1
                break
        else:
            entries.append((key, english_segments))
            counts["english_fallback"] += 1
    return build_loc(buckets, entries), len(original), counts


def copy_fonts(vita: Psarc, switch_root: Path, output: Path):
    old = vita.read("fonts/fonts.darkest")
    updated = (switch_root / "fonts" / "fonts.darkest").read_bytes()
    lines = [
        line.strip()
        for line in updated.splitlines()
        if b'.language "koreana"' in line
    ]
    if len(lines) != 6:
        raise ValueError("Expected six Korean font overrides")
    font_names = {
        name.decode("ascii")
        for line in lines
        for name in re.findall(rb'\.file "fonts/([^"]+\.fnt)"', line)
    }
    font_output = output / "fonts"
    font_output.mkdir(parents=True, exist_ok=True)
    english_lines = [line.replace(b'.language "koreana"', b'.language "english"') for line in lines]
    (font_output / "fonts.darkest").write_bytes(
        old.rstrip(b"\r\n") + b"\r\n" + b"\r\n".join(lines + english_lines) + b"\r\n"
    )
    copied = 0
    for name in sorted(font_names):
        source = switch_root / "fonts" / name
        shutil.copyfile(source, font_output / name)
        data = source.read_bytes()
        for atlas in re.findall(rb'^page id=\d+ file="([^"]+)"', data, re.M):
            atlas_name = atlas.decode("ascii")
            shutil.copyfile(switch_root / "fonts" / atlas_name, font_output / atlas_name)
            copied += 1
    return len(font_names), copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vita", type=Path, default=DEFAULT_VITA)
    parser.add_argument("--switch", type=Path, default=DEFAULT_SWITCH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    vita = Psarc(args.vita)
    jobs = [
        (
            "localization/koreana.loc",
            ["localization/koreana.loc2"],
        ),
        (
            "localization/psv/koreana.loc",
            [
                "localization/nx/koreana.loc2",
                "localization/koreana.loc2",
            ],
        ),
    ]
    for vita_name, sources in jobs:
        english_name = vita_name.replace("koreana.loc", "english.loc")
        converted, total, counts = convert_table(vita, args.switch, english_name, sources)
        destination = output.joinpath(*vita_name.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(converted)
        english_destination = output.joinpath(*english_name.split("/"))
        english_destination.write_bytes(converted)
        print(f"{vita_name}: {total} keys, {len(converted)} bytes, {dict(counts)}")
    fonts, atlases = copy_fonts(vita, args.switch, output)
    print(f"fonts: {fonts} descriptors and {atlases} atlas pages")
    print(f"output: {output}")


if __name__ == "__main__":
    main()

