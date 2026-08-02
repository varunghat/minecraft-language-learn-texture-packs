"""Stamp translated words onto vanilla block textures.

Reads the block -> texture allowlist produced by build_block_textures.py and
Mojang's own official lang file (jar/<VERSION>/assets/minecraft/lang/<LANGUAGE>.json,
keyed "block.minecraft.<id>"), then renders each labeled block texture
upscaled with the word centered on it. Using the game's own lang file gives
full, accurate coverage for free -- no hand-curated translation data to
maintain, and any non-block keys in the file (items, GUI text, banner
pattern names, ...) are simply never looked up.

Get a lang file for a language with fetch_lang.py before running this.

Blocks with no translation entry are skipped (and logged), not stamped with
a placeholder -- missing coverage should be obvious, not silently wrong.

Usage:
    python generate_pack.py --language de_de --version 1.21.4
    python generate_pack.py --language es_es --version 1.20.6
"""

import argparse
import json
import os
import textwrap
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm

SCALE = 8  # 16x16 source -> 128x128 output, nearest-neighbor (keeps pixel art crisp)

# Minecraft resource pack format per version (see the "Pack format" table on
# the Minecraft Wiki). Textures still load with a mismatched value, but the
# game shows an "incompatible" warning on the pack screen without it. Only
# entries we're actually sure of are listed; override with --pack-format for
# anything else.
KNOWN_PACK_FORMATS = {
    "1.21.4": 46,
}

ROOT = Path(__file__).parent

# Preference order; first candidate that exists on disk wins.
# - fonts/Monocraft.ttf: drop in Monocraft (github.com/IdreesInc/Monocraft), a
#   monospace font designed to match Minecraft's own typeface, for the closest
#   in-game look. Not bundled here (binary asset, needs a manual download).
# - Everything else is a monospace TTF that ships with Windows, so the pack
#   generates something reasonable with zero setup. All of them cover Latin
#   scripts including most accented/umlauted characters. They do NOT cover
#   CJK, Cyrillic, Arabic, etc. -- non-Latin languages need a different font
#   dropped into fonts/ (tracked as follow-up work, not done yet).
FONT_CANDIDATES = [
    str(ROOT / "fonts" / "Monocraft.ttf"),
    r"C:\Windows\Fonts\consolab.ttf",   # Consolas Bold
    r"C:\Windows\Fonts\consola.ttf",    # Consolas
    r"C:\Windows\Fonts\lucon.ttf",      # Lucida Console
    r"C:\Windows\Fonts\courbd.ttf",     # Courier New Bold
    r"C:\Windows\Fonts\cour.ttf",       # Courier New
    "/Library/Fonts/Andale Mono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]

# Text fitting: shrink the font until the word(s) fit within MAX_LINES lines,
# wrapping onto a second line before shrinking below MIN_FONT_SIZE. Below
# MIN_FONT_SIZE we keep shrinking in finer steps (rather than clipping) down
# to HARD_MIN_FONT_SIZE, which only exists to stop the loop on pathological input.
MAX_LINES = 2
MIN_FONT_SIZE = 10
HARD_MIN_FONT_SIZE = 6

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def load_font(size: int):
    if size in _font_cache:
        return _font_cache[size]
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            font = ImageFont.truetype(path, size)
            _font_cache[size] = font
            return font
    font = ImageFont.load_default(size=size)
    _font_cache[size] = font
    return font


def _measure(draw, font, lines, stroke_width):
    ascent, descent = font.getmetrics()
    line_height = (ascent + descent) * 1.15
    total_h = line_height * len(lines)
    max_line_w = max(draw.textlength(line, font=font) for line in lines) + stroke_width * 2
    return line_height, total_h, max_line_w


def _fit_text(draw: ImageDraw.ImageDraw, text: str, canvas_w: int, canvas_h: int):
    """Find the largest font size that fits `text` within MAX_LINES lines of
    canvas_w x canvas_h, wrapping onto a second line before shrinking below
    MIN_FONT_SIZE.

    Wrapping only ever breaks at a space (break_on_hyphens=False, and
    break_long_words=False on this pass) so a phrase like "Roter Sand" splits
    between whole words, never mid-word. Fit is checked by actually measuring
    each resulting line's pixel width -- not just estimating "chars per
    line" -- so a word that's a hair too wide (e.g. "Obsidian") is caught and
    the font shrinks further instead of silently overflowing.
    """
    font_size = max(MIN_FONT_SIZE, canvas_h // 5)

    while font_size > HARD_MIN_FONT_SIZE:
        font = load_font(font_size)
        stroke_width = max(1, font_size // 12)
        char_w = draw.textlength("M", font=font)
        max_chars = max(1, int((canvas_w * 0.9 - stroke_width * 2) / char_w))
        lines = textwrap.wrap(
            text, width=max_chars, break_long_words=False, break_on_hyphens=False
        ) or [text]

        line_height, total_h, max_line_w = _measure(draw, font, lines, stroke_width)
        fits = len(lines) <= MAX_LINES and total_h <= canvas_h * 0.9 and max_line_w <= canvas_w * 0.94
        if fits:
            return font, lines, stroke_width, line_height

        font_size -= 1 if font_size <= MIN_FONT_SIZE else 2

    # Absolute last resort: even a single word doesn't fit at HARD_MIN_FONT_SIZE
    # on its own line. Only now allow a mid-word character break.
    font = load_font(HARD_MIN_FONT_SIZE)
    stroke_width = max(1, HARD_MIN_FONT_SIZE // 12)
    char_w = draw.textlength("M", font=font)
    max_chars = max(1, int((canvas_w * 0.9 - stroke_width * 2) / char_w))
    lines = textwrap.wrap(
        text, width=max_chars, break_long_words=True, break_on_hyphens=False
    ) or [text]
    lines = lines[:MAX_LINES]
    line_height, _, _ = _measure(draw, font, lines, stroke_width)
    return font, lines, stroke_width, line_height


def stamp_text(img: Image.Image, text: str) -> Image.Image:
    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    font, lines, stroke_width, line_height = _fit_text(draw, text, w, h)

    y = (h - line_height * len(lines)) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        x = (w - (bbox[2] - bbox[0])) / 2 - bbox[0]
        draw.text(
            (x, y - bbox[1]), line, font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255),
        )
        y += line_height

    return img


def resolve_paths(version: str, language: str) -> dict:
    jar_assets = ROOT / "jar" / version / "assets" / "minecraft"
    pack_name = f"language-learn-{version}-{language}"
    pack_root = ROOT / "output" / pack_name
    return {
        "language": language,
        "jar_textures": jar_assets / "textures" / "block",
        "lang_path": jar_assets / "lang" / f"{language}.json",
        "manifest_path": ROOT / "data" / f"block_textures_{version}.json",
        "pack_name": pack_name,
        "pack_root": pack_root,
        "output_dir": pack_root / "assets" / "minecraft" / "textures" / "block",
        "zip_path": ROOT / "output" / f"{pack_name}.zip",
    }


def write_pack_mcmeta(pack_root: Path, language: str, pack_format: int):
    mcmeta = {
        "pack": {
            "pack_format": pack_format,
            "description": f"Block labels for language learning ({language})",
        }
    }
    (pack_root / "pack.mcmeta").write_text(
        json.dumps(mcmeta, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def write_pack_icon(pack_root: Path, output_dir: Path, icon_source_stem: str | None):
    """Use one already-stamped texture as the pack's icon (pack.png) so the
    icon itself previews the effect on the resource pack selection screen."""
    if icon_source_stem is None:
        return
    src = output_dir / f"{icon_source_stem}.png"
    if not src.is_file():
        return
    Image.open(src).convert("RGBA").save(pack_root / "pack.png")


def zip_pack(pack_root: Path, zip_path: Path):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in pack_root.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(pack_root))


def main():
    parser = argparse.ArgumentParser(description="Generate a labeled Minecraft resource pack for a given language.")
    parser.add_argument(
        "--language", required=True,
        help="Language code matching jar/<version>/assets/minecraft/lang/<language>.json. "
             "Use fetch_lang.py to pull one from your local Minecraft install.",
    )
    parser.add_argument(
        "--version", required=True,
        help="Minecraft version matching a jar/<version>/ folder and a "
             "data/block_textures_<version>.json manifest.",
    )
    parser.add_argument(
        "--pack-format", type=int, default=None,
        help="Override the resource pack format number written to pack.mcmeta "
             "(auto-picked from --version when known; required if not).",
    )
    args = parser.parse_args()
    paths = resolve_paths(args.version, args.language)

    pack_format = args.pack_format or KNOWN_PACK_FORMATS.get(args.version)
    if pack_format is None:
        raise SystemExit(
            f"Don't know the pack_format for version {args.version}. "
            f"Pass --pack-format explicitly (check the Minecraft Wiki's 'Pack format' table)."
        )

    if not paths["lang_path"].is_file():
        raise SystemExit(
            f"No lang file at {paths['lang_path']}.\n"
            f"Run: python fetch_lang.py --language {args.language} --version {args.version}"
        )
    if not paths["manifest_path"].is_file():
        raise SystemExit(
            f"No manifest at {paths['manifest_path']}.\n"
            f"Run: python build_block_textures.py --version {args.version}"
        )

    manifest = json.loads(paths["manifest_path"].read_text(encoding="utf-8"))
    blocks: dict[str, list[str]] = manifest["blocks"]
    lang: dict[str, str] = json.loads(paths["lang_path"].read_text(encoding="utf-8"))

    output_dir = paths["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    written: set[str] = set()
    skipped_no_translation: list[str] = []
    stamped = 0

    for block_id in tqdm(sorted(blocks)):
        word = lang.get(f"block.minecraft.{block_id}")
        if not word:
            skipped_no_translation.append(block_id)
            continue

        for stem in blocks[block_id]:
            if stem in written:
                # Some blocks intentionally share a texture (e.g. monster egg
                # blocks disguised as stone); first block to claim it wins.
                continue

            src_path = paths["jar_textures"] / f"{stem}.png"
            if not src_path.is_file():
                continue

            img = Image.open(src_path).convert("RGBA")
            img = img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)
            img = stamp_text(img, word)
            img.save(output_dir / f"{stem}.png")

            written.add(stem)
            stamped += 1

    labeled_blocks = len(blocks) - len(skipped_no_translation)
    print(f"\nStamped {stamped} textures for {labeled_blocks}/{len(blocks)} blocks.")
    if skipped_no_translation:
        preview = ", ".join(skipped_no_translation[:20])
        more = " ..." if len(skipped_no_translation) > 20 else ""
        print(f"No '{args.language}' translation, skipped: {preview}{more}")

    write_pack_mcmeta(paths["pack_root"], args.language, pack_format)
    icon_stem = "oak_planks" if "oak_planks" in written else next(iter(written), None)
    write_pack_icon(paths["pack_root"], output_dir, icon_stem)
    zip_pack(paths["pack_root"], paths["zip_path"])
    print(f"Wrote {paths['pack_root']} and {paths['zip_path']}")


if __name__ == "__main__":
    main()
