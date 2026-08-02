"""Install a generated resource pack into Minecraft's resourcepacks folder.

Copies (or moves) output/language-learn-<version>-<language>.zip, built by
generate_pack.py, into <.minecraft>/resourcepacks/ so it shows up in
Minecraft's resource pack list without you having to find and drag the file
yourself. Both --version and --language are required (no default) so this
always installs one specific build, not whichever version happened to be
generated last.

Usage:
    python install_pack.py --language de_de --version 1.21.4
    python install_pack.py --language ja_jp --version 1.21.4 --minecraft-dir "D:/Games/.minecraft"
    python install_pack.py --language de_de --version 1.21.4 --move   # remove the zip from output/ after copying

    # Modded launcher instance (MultiMC/Prism/CurseForge/...) that keeps
    # resource packs outside the shared .minecraft folder:
    python install_pack.py --language fr_fr --version 1.21.8 --resourcepacks-dir "D:/Instances/MyModpack/resourcepacks"
"""

import argparse
import shutil
from pathlib import Path

from mc_paths import default_minecraft_dir

ROOT = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--language", required=True, help="Language code matching output/language-learn-<version>-<language>.zip")
    parser.add_argument("--version", required=True, help="Minecraft version matching output/language-learn-<version>-<language>.zip")
    parser.add_argument("--minecraft-dir", type=Path, default=None, help="Override .minecraft location (auto-detected per OS by default)")
    parser.add_argument(
        "--resourcepacks-dir", type=Path, default=None,
        help="Install straight into this folder instead of <.minecraft>/resourcepacks/ "
             "-- use this for modded launcher instances (MultiMC/Prism/CurseForge) "
             "that keep resource packs outside the shared .minecraft folder. "
             "Overrides --minecraft-dir.",
    )
    parser.add_argument("--move", action="store_true", help="Remove the zip from output/ after copying, instead of leaving it in place")
    args = parser.parse_args()

    pack_name = f"language-learn-{args.version}-{args.language}"
    src = ROOT / "output" / f"{pack_name}.zip"
    if not src.is_file():
        raise SystemExit(
            f"No {src}.\n"
            f"Run: python generate_pack.py --language {args.language} --version {args.version}"
        )

    if args.resourcepacks_dir:
        resourcepacks_dir = args.resourcepacks_dir
    else:
        resourcepacks_dir = (args.minecraft_dir or default_minecraft_dir()) / "resourcepacks"
    resourcepacks_dir.mkdir(parents=True, exist_ok=True)

    dest = resourcepacks_dir / src.name
    if args.move:
        shutil.move(str(src), str(dest))
        print(f"Moved {src}\n   -> {dest}")
    else:
        shutil.copy2(src, dest)
        print(f"Copied {src}\n   -> {dest}")

    print("In Minecraft: Options > Resource Packs, then enable it from the list.")


if __name__ == "__main__":
    main()
