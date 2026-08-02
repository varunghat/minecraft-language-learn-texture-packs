"""Download and extract a Minecraft client jar's assets.

Uses Mojang's public version manifest -- the same endpoints the vanilla
launcher itself uses -- to find and download a given version's client jar,
then extracts assets/minecraft/ (blockstates, models, textures, lang, ...)
into jar/<version>/assets/minecraft/, matching the layout
build_block_textures.py, fetch_lang.py, and generate_pack.py all expect.

Usage:
    python fetch_jar.py --version 1.21.4
    python fetch_jar.py --version 1.20.6 --full   # keep .class files etc too
"""

import argparse
import json
import urllib.request
import zipfile
from pathlib import Path

VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

ROOT = Path(__file__).parent


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_version_manifest_url(version: str) -> str:
    manifest = fetch_json(VERSION_MANIFEST_URL)
    for entry in manifest["versions"]:
        if entry["id"] == version:
            return entry["url"]
    recent = ", ".join(v["id"] for v in manifest["versions"][:15])
    raise SystemExit(
        f"Version '{version}' not found in Mojang's version manifest.\n"
        f"Most recent versions: {recent}, ..."
    )


def find_client_jar_url(version_manifest_url: str) -> str:
    data = fetch_json(version_manifest_url)
    return data["downloads"]["client"]["url"]


def download(url: str, dest: Path):
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, dest)


def extract(jar_path: Path, dest_dir: Path, full: bool):
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(jar_path) as zf:
        members = zf.namelist()
        if not full:
            members = [m for m in members if m.startswith("assets/")]
        for member in members:
            zf.extract(member, dest_dir)
    print(f"Extracted {'everything' if full else 'assets/ only'} -> {dest_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True, help="Minecraft version id, e.g. 1.21.4 (must match Mojang's version manifest exactly)")
    parser.add_argument(
        "--full", action="store_true",
        help="Extract the entire jar (.class files, META-INF, data/, ...) instead of "
             "just assets/ (default: assets/ only -- that's all this project reads)",
    )
    parser.add_argument("--keep-jar", action="store_true", help="Don't delete the downloaded .jar after extracting")
    args = parser.parse_args()

    dest_dir = ROOT / "jar" / args.version
    if dest_dir.exists() and any(dest_dir.iterdir()):
        raise SystemExit(f"{dest_dir} already exists and isn't empty. Remove it first if you want to re-fetch.")

    version_manifest_url = find_version_manifest_url(args.version)
    client_jar_url = find_client_jar_url(version_manifest_url)

    jar_path = ROOT / "jar" / f"{args.version}-client.jar"
    jar_path.parent.mkdir(parents=True, exist_ok=True)
    download(client_jar_url, jar_path)

    extract(jar_path, dest_dir, args.full)

    if args.keep_jar:
        print(f"Kept downloaded jar at {jar_path}")
    else:
        jar_path.unlink()

    print(f"Now run: python build_block_textures.py --version {args.version}")


if __name__ == "__main__":
    main()
