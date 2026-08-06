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
    python generate_pack.py --language ja_jp --version 1.21.4 --font fonts/NotoSansJP-VariableFont_wght.ttf
    python generate_pack.py --language ja_jp --version 1.21.4 --font fonts/NotoSansJP-VariableFont_wght.ttf --transliterate
"""

import argparse
import json
import os
import textwrap
import zipfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont
from tqdm import tqdm

from transliteration import MissingTransliterationDependency, get_transliterator

SCALE = 8  # 16x16 source -> 128x128 output, nearest-neighbor (keeps pixel art crisp)

# Approximate Minecraft plains-biome grass green, used to tint the pack icon
# base texture (see render_pack_icon). grass_block_top.png is deliberately a
# flat, mostly-gray texture in the jar -- Minecraft tints it per-biome at
# render time using colormap/grass.png, which pack.png doesn't go through
# (it's just a GUI image), so left untinted it'd look washed-out/gray rather
# than the green players expect. This is a fixed approximation, not a real
# biome colormap lookup -- fine for a static icon.
GRASS_TINT = (124, 189, 107)

# English names for a handful of common Minecraft language codes, used only
# for the pack.png icon label. Not exhaustive -- a code that isn't listed
# here just falls back to showing its raw code (e.g. "xx_xx") rather than
# guessing wrong. This is the ONE piece of icon text that has to be
# hardcoded: unlike the native name (see render_pack_icon), Minecraft's own
# lang files don't contain "the English name of this language" anywhere.
ENGLISH_LANGUAGE_NAMES = {
    "en_us": "English", "de_de": "German", "fr_fr": "French",
    "es_es": "Spanish", "es_mx": "Spanish (Mexico)", "it_it": "Italian",
    "pt_br": "Portuguese (Brazil)", "pt_pt": "Portuguese", "ru_ru": "Russian",
    "ja_jp": "Japanese", "ko_kr": "Korean", "zh_cn": "Chinese (Simplified)",
    "zh_tw": "Chinese (Traditional)", "nl_nl": "Dutch", "pl_pl": "Polish",
    "sv_se": "Swedish", "tr_tr": "Turkish", "uk_ua": "Ukrainian",
    "cs_cz": "Czech", "da_dk": "Danish", "fi_fi": "Finnish",
    "nb_no": "Norwegian", "hu_hu": "Hungarian", "el_gr": "Greek",
    "he_il": "Hebrew", "ar_sa": "Arabic", "hi_in": "Hindi", "th_th": "Thai",
    "vi_vn": "Vietnamese", "id_id": "Indonesian", "ro_ro": "Romanian",
    "bg_bg": "Bulgarian", "hr_hr": "Croatian", "sk_sk": "Slovak",
    "lt_lt": "Lithuanian", "lv_lv": "Latvian", "et_ee": "Estonian",
    "sl_si": "Slovenian",
}

ROOT = Path(__file__).parent
PACK_FORMATS_PATH = ROOT / "data" / "pack_formats.json"


def _version_tuple(version: str) -> tuple[int, ...]:
    """'1.21.4' -> (1, 21, 4, 0, 0); pads so ranges with a different number
    of version components (e.g. "1.19" vs "1.19.2", or "26.1" vs "1.21.11")
    still compare correctly as plain tuples."""
    parts = tuple(int(p) for p in version.split("."))
    return parts + (0,) * (5 - len(parts))


def find_pack_format(version: str, formats_path: Path = PACK_FORMATS_PATH) -> int | None:
    """Looks up `version` in data/pack_formats.json (scraped from the
    Minecraft Wiki's "Pack format" page), matching it against each
    [min, max] range. Returns None if no range covers it -- the caller
    should ask for --pack-format explicitly rather than guessing."""
    if not formats_path.is_file():
        return None
    data = json.loads(formats_path.read_text(encoding="utf-8"))
    v = _version_tuple(version)
    for entry in data["resource_pack_formats"]:
        if _version_tuple(entry["min"]) <= v <= _version_tuple(entry["max"]):
            return entry["format"]
    return None

# Default preference order; first candidate that exists on disk wins. --font
# on the CLI is inserted at the front of this list at runtime, so it always
# takes priority when given (see main()).
# - fonts/Monocraft.ttf: drop in Monocraft (github.com/IdreesInc/Monocraft), a
#   monospace font designed to match Minecraft's own typeface, for the closest
#   in-game look. Not bundled here (binary asset, needs a manual download).
# - Everything else is a monospace TTF that ships with Windows, so the pack
#   generates something reasonable with zero setup. All of them cover Latin
#   scripts including most accented/umlauted characters. They do NOT cover
#   CJK, Cyrillic, Kannada, Arabic, etc. -- for those, pass --font pointing at
#   a font that does (see fonts/README.md for where to get one).
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


def stamp_lines(img: Image.Image, lines: list[str]) -> Image.Image:
    """Draw each string in `lines` as its own centered row, evenly spaced.

    Used for --transliterate (word on one row, its romanization on the
    next) where the line split is already decided by the caller, unlike
    stamp_text's word-wrapping of a single phrase. Reuses the same
    shrink-to-fit-width helpers as the pack.png icon label (_fit_single_line/
    _draw_centered_line), since both are "fit N independent lines," not "wrap
    one string."
    """
    w, h = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    row_h = h / len(lines)
    max_font_size = int(row_h * 0.7)
    for i, line in enumerate(lines):
        _draw_centered_line(draw, line, w, row_h * (i + 0.5), max_font_size)
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


def _fit_single_line(draw, text: str, max_width: float, max_font_size: int, min_font_size: int = 8):
    """Like _fit_text, but for one independent line with no wrapping --
    just shrinks until it fits max_width."""
    font_size = max_font_size
    while font_size > min_font_size:
        font = load_font(font_size)
        stroke_width = max(1, font_size // 12)
        width = draw.textlength(text, font=font) + stroke_width * 2
        if width <= max_width:
            return font, stroke_width
        font_size -= 1
    return load_font(min_font_size), max(1, min_font_size // 12)


def _draw_centered_line(draw, text: str, canvas_w: int, y_center: float, max_font_size: int):
    font, stroke_width = _fit_single_line(draw, text, canvas_w * 0.92, max_font_size)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    x = (canvas_w - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = y_center - (bbox[3] - bbox[1]) / 2 - bbox[1]
    draw.text(
        (x, y), text, font=font,
        fill=(255, 255, 255, 255),
        stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255),
    )


def render_pack_icon(jar_textures: Path, language: str, lang: dict, size: int = 128) -> Image.Image:
    """A tinted grass-block-top texture labeled with the language's English
    name, plus its native name (from the lang file's own "language.name"
    key) as a second line when available and different from the English one.
    """
    base_path = jar_textures / "grass_block_top.png"
    img = Image.open(base_path).convert("RGBA").resize((size, size), Image.NEAREST)
    tint = Image.new("RGBA", img.size, (*GRASS_TINT, 255))
    img = ImageChops.multiply(img, tint)

    draw = ImageDraw.Draw(img, "RGBA")
    english_name = ENGLISH_LANGUAGE_NAMES.get(language, language)
    native_name = lang.get("language.name")

    lines = [english_name]
    if native_name and native_name.lower() != english_name.lower():
        lines.append(native_name)

    if len(lines) == 1:
        _draw_centered_line(draw, lines[0], size, size / 2, size // 5)
    else:
        _draw_centered_line(draw, lines[0], size, size * 0.34, size // 6)
        _draw_centered_line(draw, lines[1], size, size * 0.66, size // 6)

    return img


def write_pack_icon(pack_root: Path, jar_textures: Path, language: str, lang: dict):
    render_pack_icon(jar_textures, language, lang).save(pack_root / "pack.png")


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
    parser.add_argument(
        "--font", type=Path, default=None,
        help="Path to a specific .ttf/.otf font to stamp text with, overriding "
             "auto-detection. Required for non-Latin scripts (CJK, Cyrillic, "
             "Kannada, Arabic, ...) -- the default candidates are Latin-only "
             "and auto-detection can't guess which script you need. See "
             "fonts/README.md for where to get an open-source font per script.",
    )
    parser.add_argument(
        "--transliterate", action="store_true",
        help="Also stamp a romanization under the word, for languages that "
             "have one: pinyin (zh_cn/zh_tw), romaji (ja_jp), Revised "
             "Romanization (ko_kr). Needs extra dependencies -- see "
             "pyproject.toml's [project.optional-dependencies], e.g. "
             "`pip install -e \".[ja]\"`. A no-op (word only, no error) for "
             "any other language.",
    )
    args = parser.parse_args()
    paths = resolve_paths(args.version, args.language)

    if args.font:
        if not args.font.is_file():
            raise SystemExit(f"--font {args.font} not found.")
        FONT_CANDIDATES.insert(0, str(args.font))

    transliterator = None
    if args.transliterate:
        transliterator = get_transliterator(args.language)
        if transliterator is None:
            print(f"No transliterator available for '{args.language}' -- stamping words only.")

    pack_format = args.pack_format or find_pack_format(args.version)
    if pack_format is None:
        raise SystemExit(
            f"No pack_format entry covers version {args.version} in {PACK_FORMATS_PATH}.\n"
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

            translit = None
            if transliterator:
                try:
                    translit = transliterator(word)
                except MissingTransliterationDependency as e:
                    raise SystemExit(str(e))

            if translit and translit.strip().lower() != word.strip().lower():
                img = stamp_lines(img, [word, translit])
            else:
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
    write_pack_icon(paths["pack_root"], paths["jar_textures"], args.language, lang)
    zip_pack(paths["pack_root"], paths["zip_path"])
    print(f"Wrote {paths['pack_root']} and {paths['zip_path']}")


if __name__ == "__main__":
    main()
