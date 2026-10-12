"""Build the selected PS Vita Korean rePatch from user-provided game files."""
from __future__ import annotations

import argparse
import re
import tempfile
import zipfile
from pathlib import Path

from convert import Psarc, convert_table
from gxt import encode
from pack_psarc import build_archive

ROOT = Path(__file__).resolve().parent
TITLE_ID = "PCSG01154"
FONT_SPACE_WIDTHS = {
    "korean_ubuntu.fnt": 7,
    "korean_ubuntu_m.fnt": 8,
    "korean_dwarven_axe_l.fnt": 12,
    "korean_dwarven_axe_m.fnt": 8,
    "korean_popup.fnt": 15,
}
BASE_FONTS = {
    "ubuntu_small": "korean_ubuntu.fnt",
    "ubuntu_medium": "korean_ubuntu_m.fnt",
    "dwarven_axe_medium": "korean_dwarven_axe_m.fnt",
    "dwarven_axe_large": "korean_dwarven_axe_l.fnt",
    "popup": "korean_popup.fnt",
    "ubuntu_xsmall": "korean_ubuntu.fnt",
}


def add_space(descriptor: bytes, advance: int) -> bytes:
    if re.search(rb"(?m)^char id=32 ", descriptor):
        raise ValueError("The source descriptor already has a space glyph")
    match = re.search(rb"(?m)^chars count=(\d+)(\r?\n)", descriptor)
    if match is None:
        raise ValueError("BMFont character count was not found")
    newline = match.group(2)
    glyph = (
        f"char id=32 x=1023 y=1023 width=1 height=1 "
        f"xoffset=0 yoffset=0 xadvance={advance} page=0 chnl=15"
    ).encode("ascii")
    replacement = (
        b"chars count="
        + str(int(match.group(1)) + 1).encode("ascii")
        + newline
        + glyph
        + newline
    )
    return descriptor[: match.start()] + replacement + descriptor[match.end() :]


def make_font_config(vita: Psarc, switch_root: Path) -> bytes:
    lines = vita.read("fonts/fonts.darkest").decode("utf-8").splitlines()
    found_fonts: set[str] = set()
    found_tutorial = False
    for index, line in enumerate(lines):
        if line.startswith("font:"):
            for font_id, filename in BASE_FONTS.items():
                if f'.id "{font_id}"' in line:
                    replaced, count = re.subn(
                        r'\.file "fonts/[^"]+\.fnt"',
                        f'.file "fonts/{filename}"',
                        line,
                        count=1,
                    )
                    if count != 1:
                        raise ValueError(f"Missing file reference for {font_id}")
                    lines[index] = replaced
                    found_fonts.add(font_id)
                    break
        elif line.startswith("font_ref:") and '.id "tutorial_popup_description"' in line:
            if '.font "ubuntu_small"' not in line:
                raise ValueError("Unexpected tutorial font reference")
            lines[index] = line.replace('.font "ubuntu_small"', '.font "ubuntu_medium"')
            found_tutorial = True
    if found_fonts != set(BASE_FONTS) or not found_tutorial:
        raise ValueError("Vita font configuration differs from the supported version")

    switch_config = (switch_root / "fonts" / "fonts.darkest").read_text(
        encoding="utf-8-sig"
    )
    overrides = [
        line.strip()
        for line in switch_config.splitlines()
        if '.language "koreana"' in line
        and line.startswith("font_language_override:")
    ]
    if len(overrides) != 6:
        raise ValueError("Expected six Korean font overrides in the Switch update")
    return ("\r\n".join(lines + [""] + overrides) + "\r\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vita", required=True, type=Path, help="Vita content.psarc")
    parser.add_argument(
        "--switch", required=True, type=Path, help="Unpacked Switch update romfs"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    vita_path = args.vita.resolve()
    switch_root = args.switch.resolve()
    output = args.output.resolve()
    if not vita_path.is_file():
        parser.error(f"Vita archive not found: {vita_path}")
    if not (switch_root / "localization" / "koreana.loc2").is_file():
        parser.error(f"Switch Korean update data not found: {switch_root}")
    output.mkdir(parents=True, exist_ok=True)
    work = ROOT / "build"
    work.mkdir(parents=True, exist_ok=True)

    vita = Psarc(vita_path)
    with tempfile.TemporaryDirectory(prefix="ddko-", dir=work) as temp:
        overlay = Path(temp) / "overlay"
        fonts = overlay / "fonts"
        fonts.mkdir(parents=True)
        jobs = [
            ("localization/english.loc", ["localization/koreana.loc2"]),
            (
                "localization/psv/english.loc",
                ["localization/nx/koreana.loc2", "localization/koreana.loc2"],
            ),
        ]
        for destination, sources in jobs:
            converted, total, counts = convert_table(vita, switch_root, destination, sources)
            target = overlay / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(converted)
            print(f"{destination}: {total} keys, {dict(counts)}", flush=True)

        (fonts / "fonts.darkest").write_bytes(make_font_config(vita, switch_root))
        for name, advance in FONT_SPACE_WIDTHS.items():
            source = switch_root / "fonts" / name
            descriptor = add_space(source.read_bytes(), advance)
            (fonts / name).write_bytes(descriptor)
            for atlas in re.findall(rb'^page id=\d+ file="([^"]+)"', descriptor, re.M):
                atlas_name = atlas.decode("ascii")
                encode(switch_root / "fonts" / atlas_name, fonts / atlas_name)

        archive = Path(temp) / "content.psarc"
        build_archive(vita_path, overlay, archive)
        package = output / f"DarkestDungeon_Korean_rePatch_{TITLE_ID}.zip"
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_STORED) as zipped:
            zipped.write(archive, f"rePatch/{TITLE_ID}/content.psarc")
            zipped.writestr(
                "README.txt",
                "Extract this ZIP to ux0:.\n",
            )
    print(f"Created: {package}", flush=True)


if __name__ == "__main__":
    main()

