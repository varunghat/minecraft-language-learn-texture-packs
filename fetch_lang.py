"""Pull an official Minecraft translation file out of a local .minecraft install.

Mojang's client jar only ships en_us.json -- every other language is
downloaded on demand by the launcher as a loose, content-addressed object,
once you've selected that language in-game at least once. Finding it by hand
means: open the version's client json to get the asset index id, open that
index to find the sha1 hash for "minecraft/lang/<language>.json", then look
up assets/objects/<hash[:2]>/<hash>. This script does that lookup for you.

Usage:
    python fetch_lang.py --language de_de --version 1.21.4
    python fetch_lang.py --language ja_jp --version 1.21.4 --minecraft-dir "D:/Games/.minecraft"
    python fetch_lang.py --language fr_fr --version 1.21.4 --asset-index 26   # skip version.json lookup

    # Modded launcher profile (OptiFine/Forge/Fabric/...) whose local
    # .minecraft/versions/<X>/ folder name isn't the plain version id:
    python fetch_lang.py --language fr_fr --version 1.21.8 --local-version-dir "OptiFine 1.21.8"

Prerequisite: in Minecraft, Options > Language > select the target language
at least once (even briefly) so the launcher actually downloads those assets.

Note: --version is the canonical id used for jar/<version>/ everywhere in
this repo (build_block_textures.py, fetch_jar.py, generate_pack.py all key
off it). It only needs to match a real local .minecraft/versions/ folder
name if you don't pass --local-version-dir or --asset-index.
"""

import argparse
import json
import shutil
from pathlib import Path

from mc_paths import default_minecraft_dir

ROOT = Path(__file__).parent


def find_asset_index_id(minecraft_dir: Path, local_version_dir: str) -> str:
    version_json = minecraft_dir / "versions" / local_version_dir / f"{local_version_dir}.json"
    if not version_json.is_file():
        available = sorted(p.name for p in (minecraft_dir / "versions").glob("*") if p.is_dir())
        raise SystemExit(
            f"Couldn't find {version_json}.\n"
            f"Installed version folders: {available or '(none found)'}\n"
            f"If your local folder name isn't the plain version id (e.g. a modded "
            f"launcher profile like 'OptiFine 1.21.8'), pass --local-version-dir to "
            f"match one of those exactly, keeping --version as the clean id. "
            f"Or pass --asset-index directly if you already know it."
        )
    data = json.loads(version_json.read_text(encoding="utf-8"))
    return data["assetIndex"]["id"]


def find_object_hash(minecraft_dir: Path, asset_index_id: str, asset_key: str) -> str:
    index_path = minecraft_dir / "assets" / "indexes" / f"{asset_index_id}.json"
    if not index_path.is_file():
        raise SystemExit(f"Asset index not found: {index_path}")
    data = json.loads(index_path.read_text(encoding="utf-8"))
    obj = data["objects"].get(asset_key)
    if obj is None:
        raise SystemExit(
            f"'{asset_key}' isn't in {index_path}.\n"
            f"Double check the language code (e.g. de_de, es_es, ja_jp)."
        )
    return obj["hash"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--language", required=True, help="Language code, e.g. de_de, es_es, fr_fr, ja_jp")
    parser.add_argument("--minecraft-dir", type=Path, default=None, help="Override .minecraft location (auto-detected per OS by default)")
    parser.add_argument(
        "--version", required=True,
        help="Canonical Minecraft version -- determines the jar/<version>/ folder "
             "the lang file gets copied into (must match what you pass to the rest "
             "of the toolchain), e.g. 1.21.4. Also used as the local "
             ".minecraft/versions/ folder name unless --local-version-dir is given.",
    )
    parser.add_argument(
        "--local-version-dir", default=None,
        help="Local .minecraft/versions/<X>/ folder name to read the asset index "
             "from, if it differs from --version (e.g. a modded launcher profile "
             "like 'OptiFine 1.21.8' when you want a clean --version of 1.21.8). "
             "Defaults to --version.",
    )
    parser.add_argument("--asset-index", default=None, help="Asset index id (e.g. 26) -- skips the version.json lookup if you already know it")
    args = parser.parse_args()

    minecraft_dir = args.minecraft_dir or default_minecraft_dir()
    if not minecraft_dir.is_dir():
        raise SystemExit(f"No Minecraft install found at {minecraft_dir}. Pass --minecraft-dir.")

    local_version_dir = args.local_version_dir or args.version
    asset_index_id = args.asset_index or find_asset_index_id(minecraft_dir, local_version_dir)
    asset_key = f"minecraft/lang/{args.language}.json"
    file_hash = find_object_hash(minecraft_dir, asset_index_id, asset_key)

    src = minecraft_dir / "assets" / "objects" / file_hash[:2] / file_hash
    if not src.is_file():
        raise SystemExit(
            f"Object {src} isn't on disk yet.\n"
            f"The launcher only downloads a language's assets after you've "
            f"selected it in-game at least once: Options > Language > "
            f"{args.language}, then rerun this script."
        )

    dest_dir = ROOT / "jar" / args.version / "assets" / "minecraft" / "lang"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{args.language}.json"
    shutil.copy2(src, dest)
    print(f"Copied {src}\n     -> {dest}")
    print(f"Now run: python generate_pack.py --language {args.language} --version {args.version}")


if __name__ == "__main__":
    main()
