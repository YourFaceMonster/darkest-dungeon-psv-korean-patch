"""Build the selected PS Vita Korean rePatch from user-provided game files."""
from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

from convert import Psarc, convert_table
from gxt import decode_alpha, encode
from pack_psarc import build_archive

ROOT = Path(__file__).resolve().parent
TITLE_ID = "PCSG01154"
VERSION = "0.9.1"
FONT_SPACE_WIDTHS = {
    "korean_ubuntu.fnt": 7,
    "korean_ubuntu_m.fnt": 8,
    "korean_dwarven_axe_l.fnt": 12,
    "korean_dwarven_axe_m.fnt": 8,
    "korean_popup.fnt": 15,
}
VITA_FONT_DESCRIPTORS = {
    "korean_ubuntu.fnt": "ubuntu.fnt",
    "korean_ubuntu_m.fnt": "ubuntu_m.fnt",
    "korean_dwarven_axe_l.fnt": "dwarvenaxe-l.fnt",
    "korean_dwarven_axe_m.fnt": "dwarvenaxe-m.fnt",
    "korean_popup.fnt": "popup.fnt",
}
BASE_FONTS = {
    "ubuntu_small": "korean_ubuntu.fnt",
    "ubuntu_medium": "korean_ubuntu_m.fnt",
    "dwarven_axe_medium": "korean_dwarven_axe_m.fnt",
    "dwarven_axe_large": "korean_dwarven_axe_l.fnt",
    "popup": "korean_popup.fnt",
    "ubuntu_xsmall": "korean_ubuntu.fnt",
}


def fields(line: bytes) -> dict[bytes, int]:
    return {
        key: int(value)
        for key, value in re.findall(rb"(\w+)=(-?\d+)", line)
    }


def replace_field(line: bytes, key: bytes, value: int) -> bytes:
    updated, count = re.subn(
        rb"(?<!\w)" + key + rb"=-?\d+",
        key + b"=" + str(value).encode("ascii"),
        line,
        count=1,
    )
    if count != 1:
        raise ValueError(f"Missing BMFont field: {key.decode('ascii')}")
    return updated


def merge_vita_ascii(
    vita: Psarc, switch_root: Path, fonts: Path, name: str, space_width: int
) -> None:
    """Put Vita ASCII glyphs in unused space of a Korean atlas page."""
    source_lines = vita.read(
        "fonts/" + VITA_FONT_DESCRIPTORS[name]
    ).splitlines()
    source_glyphs = {
        fields(line)[b"id"]: line
        for line in source_lines
        if line.startswith(b"char id=")
    }
    source_pages = [
        re.search(rb'file="([^"]+)"', line).group(1).decode("ascii")
        for line in source_lines
        if line.startswith(b"page id=")
    ]
    if len(source_pages) != 1:
        raise ValueError(f"Expected one Vita atlas page for {name}")
    source_alpha = decode_alpha(vita.read("fonts/" + source_pages[0]))

    descriptor = (switch_root / "fonts" / name).read_bytes()
    lines = descriptor.splitlines(keepends=True)
    pages = [
        re.search(rb'file="([^"]+)"', line).group(1).decode("ascii")
        for line in lines
        if line.startswith(b"page id=")
    ]
    if not pages:
        raise ValueError(f"No Korean atlas pages for {name}")
    target_page = len(pages) - 1
    target_name = pages[target_page]
    target_glyphs = [
        fields(line)
        for line in lines
        if line.startswith(b"char id=")
    ]
    existing_ids = {glyph[b"id"] for glyph in target_glyphs}
    y = max(
        glyph[b"y"] + glyph[b"height"]
        for glyph in target_glyphs
        if glyph[b"page"] == target_page
    ) + 2
    x = 1
    row_height = 0
    newline = b"\r\n" if b"\r\n" in descriptor else b"\n"
    with Image.open(switch_root / "fonts" / target_name) as image:
        target_alpha = (
            image.getchannel("A")
            if "A" in image.getbands()
            else image.convert("L")
        )
    if target_alpha.size != (1024, 1024):
        raise ValueError(f"Unexpected Korean atlas dimensions for {name}")
    added = []
    for char_id in range(32, 127):
        if char_id in existing_ids:
            continue
        original = source_glyphs.get(char_id)
        if original is None:
            raise ValueError(f"Vita font {name} is missing ASCII {char_id}")
        glyph = fields(original)
        width, height = glyph[b"width"], glyph[b"height"]
        if x + width + 2 > 1024:
            x, y, row_height = 1, y + row_height, 0
        if y + height + 2 > 1024:
            raise ValueError(f"No atlas space for ASCII in {name}")
        crop = source_alpha.crop(
            (
                glyph[b"x"],
                glyph[b"y"],
                glyph[b"x"] + width,
                glyph[b"y"] + height,
            )
        )
        target_alpha.paste(crop, (x, y))
        updated = replace_field(original, b"x", x)
        updated = replace_field(updated, b"y", y)
        updated = replace_field(updated, b"page", target_page)
        if char_id == 32:
            updated = replace_field(updated, b"xadvance", space_width)
        added.append(updated.rstrip(b"\r\n") + newline)
        x += width + 2
        row_height = max(row_height, height + 2)

    count_index = next(
        i for i, line in enumerate(lines) if line.startswith(b"chars count=")
    )
    lines[count_index] = replace_field(
        lines[count_index], b"count", len(target_glyphs) + len(added)
    )
    # The game's BMFont lookup expects character IDs in ascending order.
    # Printable ASCII precedes every Korean extension glyph.
    if [glyph[b"id"] for glyph in target_glyphs] != sorted(existing_ids):
        raise ValueError(f"Korean BMFont glyphs are not sorted: {name}")
    insert_at = count_index + 1
    lines[insert_at:insert_at] = added
    (fonts / name).write_bytes(b"".join(lines))

    thin_popup = name == "korean_popup.fnt"
    for atlas_name in pages:
        destination = fonts / atlas_name
        if atlas_name == target_name:
            with tempfile.TemporaryDirectory(prefix="atlas-", dir=fonts) as temp:
                edited = Path(temp) / atlas_name
                if thin_popup:
                    target_alpha = target_alpha.filter(ImageFilter.MinFilter(5))
                target_alpha.save(edited)
                encode(edited, destination)
        elif thin_popup:
            # The Switch popup glyphs include a four-pixel solid outline in
            # the alpha bitmap. It closes counters after Vita downsamples it.
            with tempfile.TemporaryDirectory(prefix="atlas-", dir=fonts) as temp:
                edited = Path(temp) / atlas_name
                with Image.open(switch_root / "fonts" / atlas_name) as image:
                    image.getchannel("A").filter(ImageFilter.MinFilter(5)).save(edited)
                encode(edited, destination)
        else:
            encode(switch_root / "fonts" / atlas_name, destination)


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
    last_japanese = max(
        i for i, line in enumerate(lines)
        if line.startswith('font_language_override: .language "japanese"')
    )
    lines.insert(last_japanese + 1, "")
    return ("\r\n".join(lines + overrides) + "\r\n").encode("utf-8")


def make_combat_colours(vita: Psarc) -> bytes:
    """Give floating combat text a light fill and a dark, readable edge."""
    original = vita.read("colours/base.colours.darkest")
    pattern = re.compile(
        rb'(?m)^(colour:\s+\.id "(pop_text_[^"]+)"\s+\.rgba )([^\r\n]+)'
    )
    colours = {match.group(2).decode("ascii"): match.group(3) for match in pattern.finditer(original)}
    updates: dict[str, bytes] = {}

    # The Vita palette draws several status messages as black letters with
    # pale outlines. On the dark battle scene their interiors disappear.
    for name, colour in colours.items():
        if not name.startswith("pop_text_outline_") and colour == b"#000000":
            updates[name] = b"#fff1d6"
            outline = "pop_text_outline_" + name.removeprefix("pop_text_")
            if outline not in colours:
                raise ValueError(f"Missing combat text outline: {outline}")
            updates[outline] = b"#241710"

    # Damage numerals overlap a red blood effect. A pale red fill keeps their
    # meaning while making their shapes distinguishable from the effect.
    for name in ("damage", "bleed", "tagged", "riposte", "no_damage", "death_avoided"):
        fill = "pop_text_" + name
        outline = "pop_text_outline_" + name
        if fill not in colours or outline not in colours:
            raise ValueError(f"Missing combat text colour: {name}")
        updates[fill] = b"#ffc3a4"
        updates[outline] = b"#260c08"

    seen: set[str] = set()

    def replace(match: re.Match[bytes]) -> bytes:
        name = match.group(2).decode("ascii")
        if name not in updates:
            return match.group(0)
        seen.add(name)
        return match.group(1) + updates[name]

    edited = pattern.sub(replace, original)
    if seen != updates.keys():
        raise ValueError(f"Combat colours not found: {sorted(updates.keys() - seen)}")
    return edited


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
        colours = overlay / "colours" / "base.colours.darkest"
        colours.parent.mkdir(parents=True)
        colours.write_bytes(make_combat_colours(vita))
        for name, advance in FONT_SPACE_WIDTHS.items():
            merge_vita_ascii(vita, switch_root, fonts, name, advance)

        archive = output / f"v{VERSION}" / "rePatch" / TITLE_ID / "content.psarc"
        build_archive(vita_path, overlay, archive)
    print(f"Created: {archive}", flush=True)


if __name__ == "__main__":
    main()
