"""Package the converted Korean files into a separate Vita PSARC archive."""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from convert import DEFAULT_VITA, OUTPUT, Psarc


@dataclass
class Entry:
    digest: bytes
    size: int
    block_lengths: list[int]
    packed: bytes | memoryview


def pack_bytes(raw: bytes, block_size: int) -> tuple[list[int], bytes]:
    lengths = []
    packed = bytearray()
    for start in range(0, len(raw), block_size):
        block = raw[start : start + block_size]
        compressed = zlib.compress(block, 9)
        if len(compressed) < len(block) and len(compressed) <= 65535:
            lengths.append(len(compressed))
            packed.extend(compressed)
        else:
            lengths.append(0 if len(block) == 65536 else len(block))
            packed.extend(block)
    return lengths, bytes(packed)


def original_entries(archive: Psarc) -> list[Entry]:
    data = archive.data
    starts = []
    descriptors = []
    for i in range(archive.entry_count):
        at = 32 + i * archive.entry_size
        descriptor = data[at : at + archive.entry_size]
        descriptors.append(descriptor)
        starts.append(int.from_bytes(descriptor[25:30], "big"))
    starts.append(len(data))
    entries = []
    for i, descriptor in enumerate(descriptors):
        size = int.from_bytes(descriptor[20:25], "big")
        first_block = int.from_bytes(descriptor[16:20], "big")
        count = max(1, (size + archive.block_size - 1) // archive.block_size)
        lengths = [
            int.from_bytes(
                archive.block_lengths[(first_block + j) * 2 : (first_block + j + 1) * 2],
                "big",
            )
            for j in range(count)
        ]
        entries.append(
            Entry(
                descriptor[:16],
                size,
                lengths,
                memoryview(data)[starts[i] : starts[i + 1]],
            )
        )
    return entries


def build_archive(vita_path: Path, converted: Path, destination: Path):
    archive = Psarc(vita_path)
    names = list(archive.names)
    replacements = {
        path.relative_to(converted).as_posix(): path.read_bytes()
        for path in converted.rglob("*")
        if path.is_file() and path.suffix.lower() in {".loc", ".darkest", ".fnt", ".tga"}
    }
    existing = set(names)
    added_names = sorted(set(replacements) - existing)
    names.extend(added_names)
    manifest = "\n".join(names).encode("utf-8")
    entries = original_entries(archive)
    manifest_lengths, manifest_packed = pack_bytes(manifest, archive.block_size)
    entries[0] = Entry(b"\0" * 16, len(manifest), manifest_lengths, manifest_packed)

    for i, name in enumerate(names, 1):
        if name not in replacements:
            continue
        raw = replacements[name]
        lengths, packed = pack_bytes(raw, archive.block_size)
        digest = entries[i].digest if i < len(entries) else hashlib.md5(name.encode("utf-8")).digest()
        changed = Entry(digest, len(raw), lengths, packed)
        if i < len(entries):
            entries[i] = changed
        else:
            entries.append(changed)

    block_count = sum(len(entry.block_lengths) for entry in entries)
    toc_length = 32 + len(entries) * 30 + block_count * 2
    header = bytearray(archive.data[:32])
    header[12:16] = toc_length.to_bytes(4, "big")
    header[20:24] = len(entries).to_bytes(4, "big")
    offset = toc_length
    block_index = 0
    toc = bytearray()
    block_table = bytearray()
    for entry in entries:
        toc.extend(entry.digest)
        toc.extend(block_index.to_bytes(4, "big"))
        toc.extend(entry.size.to_bytes(5, "big"))
        toc.extend(offset.to_bytes(5, "big"))
        block_index += len(entry.block_lengths)
        offset += len(entry.packed)
        for length in entry.block_lengths:
            block_table.extend(struct.pack(">H", length))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file:
        file.write(header)
        file.write(toc)
        file.write(block_table)
        for entry in entries:
            file.write(entry.packed)
    print(f"archive: {destination}")
    print(f"files: {len(entries) - 1}, newly added: {len(added_names)}")
    print(f"size: {destination.stat().st_size:,} bytes")


