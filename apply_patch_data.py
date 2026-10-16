"""Build the PS Vita rePatch archive from the small v0.9.1 source bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from pack_psarc import build_archive

ROOT = Path(__file__).resolve().parent
VERSION = "0.9.1"
TITLE_ID = "PCSG01154"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vita", required=True, type=Path, help="Original Vita content.psarc")
    parser.add_argument(
        "--source", type=Path, default=ROOT / f"patch_sources_v{VERSION}.tar",
        help="Downloaded source bundle",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "dist" / f"v{VERSION}" / "rePatch" / TITLE_ID / "content.psarc",
        help="Directly installable rePatch content.psarc",
    )
    args = parser.parse_args()
    vita_path = args.vita.resolve()
    source_path = args.source.resolve()
    output_path = args.output.resolve()
    if not vita_path.is_file():
        parser.error(f"Vita archive not found: {vita_path}")
    if not source_path.is_file():
        parser.error(f"Source bundle not found: {source_path}")

    with tarfile.open(source_path, "r:") as source:
        members = {member.name: member for member in source.getmembers()}
        if len(members) != len(source.getmembers()) or "manifest.json" not in members:
            raise ValueError("Invalid or duplicate source bundle entries")
        manifest_file = source.extractfile(members["manifest.json"])
        if manifest_file is None:
            raise ValueError("Source bundle manifest is not a file")
        manifest = json.load(manifest_file)
        if manifest.get("version") != VERSION or manifest.get("title_id") != TITLE_ID:
            raise ValueError("Source bundle is for a different patch version")
        if sha256_file(vita_path) != manifest.get("base_psarc_sha256"):
            raise ValueError("Vita content.psarc differs from the supported original")

        files = manifest["files"]
        expected = {"manifest.json"} | {f"overlay/{name}" for name in files}
        if set(members) != expected:
            raise ValueError("Source bundle file list differs from its manifest")
        with tempfile.TemporaryDirectory(prefix="ddko-source-") as temp:
            overlay = Path(temp) / "overlay"
            for name, record in files.items():
                path = PurePosixPath(name)
                parts = path.parts
                if path.is_absolute() or "\\" in name or ":" in name or not parts or any(
                    part in ("", ".", "..") for part in parts
                ):
                    raise ValueError(f"Unsafe source bundle path: {name}")
                member = members[f"overlay/{name}"]
                if not member.isfile():
                    raise ValueError(f"Source bundle entry is not a file: {name}")
                payload_file = source.extractfile(member)
                if payload_file is None:
                    raise ValueError(f"Missing source data: {name}")
                payload = payload_file.read()
                if len(payload) != record["size"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
                    raise ValueError(f"Source data checksum mismatch: {name}")
                target = overlay.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            build_archive(vita_path, overlay, output_path)
    print(f"Created: {output_path}")


if __name__ == "__main__":
    main()
