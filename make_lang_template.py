"""Generate a fill-in-the-blanks lang.json for a language Mojang doesn't
ship a translation for (or as a starting point to hand-edit an existing one).

Writes one "block.minecraft.<id>": "" entry per block in
data/block_textures_<version>.json (built by build_block_textures.py) to
jar/<version>/assets/minecraft/lang/<language>.json -- the exact same place
fetch_lang.py would put a real one, so generate_pack.py can't tell the
difference and needs no changes to use it.

Usage:
    # A made-up code for a language Minecraft doesn't support:
    python make_lang_template.py --version 1.21.4 --language tlh_aa

    # Starting point for hand-fixing an existing language's translations,
    # pre-filled with the English text so you can see what you're editing:
    python make_lang_template.py --version 1.21.4 --language de_de --prefill-english --force
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--version", required=True,
        help="Minecraft version matching a jar/<version>/ folder and a "
             "data/block_textures_<version>.json manifest.",
    )
    parser.add_argument(
        "--language", required=True,
        help="Language code to create a template for -- an existing Minecraft "
             "code you want to hand-edit, or a made-up one for an unsupported language.",
    )
    parser.add_argument(
        "--prefill-english", action="store_true",
        help="Fill each entry with its English text from en_us.json as a "
             "starting reference, instead of leaving the value blank.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite the lang file if one already exists at that path.",
    )
    args = parser.parse_args()

    manifest_path = ROOT / "data" / f"block_textures_{args.version}.json"
    if not manifest_path.is_file():
        raise SystemExit(
            f"No {manifest_path}.\nRun: python build_block_textures.py --version {args.version}"
        )
    blocks: dict[str, list[str]] = json.loads(manifest_path.read_text(encoding="utf-8"))["blocks"]

    en_us = {}
    if args.prefill_english:
        en_us_path = ROOT / "jar" / args.version / "assets" / "minecraft" / "lang" / "en_us.json"
        if not en_us_path.is_file():
            raise SystemExit(f"--prefill-english needs {en_us_path}, which doesn't exist.")
        en_us = json.loads(en_us_path.read_text(encoding="utf-8"))

    dest = ROOT / "jar" / args.version / "assets" / "minecraft" / "lang" / f"{args.language}.json"
    if dest.is_file() and not args.force:
        raise SystemExit(f"{dest} already exists. Pass --force to overwrite it.")

    template = {}
    for block_id in sorted(blocks):
        key = f"block.minecraft.{block_id}"
        template[key] = en_us.get(key, "") if args.prefill_english else ""

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(template, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {len(template)} entries to {dest}")
    print("Fill in each value, then run:")
    print(f"  python generate_pack.py --language {args.language} --version {args.version}")


if __name__ == "__main__":
    main()
