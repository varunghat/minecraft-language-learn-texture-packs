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
import hashlib
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


def find_client_download(version_manifest_url: str) -> dict:
    """Returns Mojang's downloads.client dict: {"url", "sha1", "size"}."""
    data = fetch_json(version_manifest_url)
    return data["downloads"]["client"]


def sha1_of(path: Path) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path):
    print(f"Downloading {url}")
    try:
        urllib.request.urlretrieve(url, dest)
    except BaseException:
        # Interrupted (Ctrl-C, connection drop, ...) -- don't leave a partial
        # .jar sitting at `dest` for a future run to trip over.
        dest.unlink(missing_ok=True)
        raise


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
    client = find_client_download(version_manifest_url)

    jar_path = ROOT / "jar" / f"{args.version}-client.jar"
    jar_path.parent.mkdir(parents=True, exist_ok=True)
    download(client["url"], jar_path)

    expected_sha1 = client.get("sha1")
    if expected_sha1:
        actual_sha1 = sha1_of(jar_path)
        if actual_sha1 != expected_sha1:
            jar_path.unlink()
            raise SystemExit(
                f"Download verification failed: sha1 mismatch for {args.version}-client.jar "
                f"(expected {expected_sha1}, got {actual_sha1}).\n"
                f"The download was likely interrupted or corrupted -- run this again."
            )
        print(f"Verified sha1 {actual_sha1}")

    extract(jar_path, dest_dir, args.full)

    if args.keep_jar:
        print(f"Kept downloaded jar at {jar_path}")
    else:
        jar_path.unlink()

    print(f"Now run: python build_block_textures.py --version {args.version}")


if __name__ == "__main__":
    main()
