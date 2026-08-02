"""Build an allowlist of (block id -> texture stems) from vanilla block models.

Walks blockstates/*.json (one file per real, placeable block id) to find every
model each block can render as, resolves each model's texture variables by
following its "parent" chain, and collects the concrete texture files that
actually appear as a visible block face. This avoids hand-maintained
include/exclude lists: blocks with no static face texture (chests, beds,
banners, item frames -- anything rendered via a block entity) simply resolve
to zero textures and are skipped automatically.

Output: data/block_textures_<version>.json, consumed by generate_pack.py.

Usage:
    python build_block_textures.py --version 1.21.4
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent


def paths_for(version: str) -> dict:
    assets = ROOT / "jar" / version / "assets" / "minecraft"
    return {
        "blockstates_dir": assets / "blockstates",
        "models_dir": assets / "models" / "block",
        "textures_dir": assets / "textures" / "block",
        "output_path": ROOT / "data" / f"block_textures_{version}.json",
    }


def normalize_ref(ref: str) -> str:
    """'minecraft:block/oak_log_horizontal' -> 'oak_log_horizontal'"""
    ref = ref.split(":", 1)[-1]
    if ref.startswith("block/"):
        ref = ref[len("block/"):]
    return ref


def load_model_textures(name: str, models_dir: Path, cache: dict) -> dict:
    """Return the merged texture-variable dict for a model, parent-first so
    the child's own definitions win over anything inherited."""
    if name in cache:
        return cache[name]

    path = models_dir / f"{name}.json"
    if not path.is_file():
        # Terminal/builtin parent (builtin/generated, builtin/entity, ...)
        # or a name we can't resolve -- treat as having no static textures.
        cache[name] = {}
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))

    textures = {}
    parent = data.get("parent")
    if parent:
        textures.update(load_model_textures(normalize_ref(parent), models_dir, cache))
    textures.update(data.get("textures", {}))

    cache[name] = textures
    return textures


def resolve_concrete_textures(textures: dict) -> set:
    """Follow '#variable' chains to concrete texture path strings.

    Skips the "particle" key: it's only used for break-particle effects, and
    for entity-rendered blocks with no real visible face (banners, beds,
    signs, ...) it's the *only* key defined -- pointing at a generic
    placeholder texture (usually oak_planks) rather than anything specific
    to that block. Including it would wrongly claim that shared texture for
    an unrelated block. For blocks that do have real faces, "particle" is
    always just an alias for one of them (e.g. cube_column.json sets
    "particle": "#side"), so skipping it loses no real coverage.
    """
    resolved = set()
    for key, value in textures.items():
        if key == "particle":
            continue
        seen = set()
        while isinstance(value, str) and value.startswith("#"):
            ref = value[1:]
            if ref in seen or ref not in textures:
                value = None
                break
            seen.add(ref)
            value = textures.get(ref)
        if isinstance(value, str) and not value.startswith("#"):
            resolved.add(value)
    return resolved


def concrete_to_stem(value: str) -> str | None:
    """'minecraft:block/oak_log_top' -> 'oak_log_top'; None if not a block/ texture."""
    v = value.split(":", 1)[-1]
    if v.startswith("block/"):
        return v[len("block/"):]
    return None


def collect_model_refs(blockstate: dict) -> set:
    refs = set()

    for variant in blockstate.get("variants", {}).values():
        entries = variant if isinstance(variant, list) else [variant]
        for entry in entries:
            if "model" in entry:
                refs.add(entry["model"])

    for part in blockstate.get("multipart", []):
        apply_val = part.get("apply")
        entries = apply_val if isinstance(apply_val, list) else [apply_val]
        for entry in entries:
            if entry and "model" in entry:
                refs.add(entry["model"])

    return refs


def main():
    parser = argparse.ArgumentParser(description="Build the block -> texture allowlist for a Minecraft version.")
    parser.add_argument(
        "--version", required=True,
        help="Minecraft version matching a jar/<version>/ folder, e.g. 1.21.4. "
             "Use fetch_jar.py to populate one.",
    )
    args = parser.parse_args()
    paths = paths_for(args.version)

    if not paths["blockstates_dir"].is_dir():
        raise SystemExit(
            f"No {paths['blockstates_dir']} found.\n"
            f"Run: python fetch_jar.py --version {args.version}"
        )

    cache: dict = {}
    result: dict[str, list[str]] = {}

    blockstate_files = sorted(paths["blockstates_dir"].glob("*.json"))
    for blockstate_file in blockstate_files:
        block_id = blockstate_file.stem
        blockstate = json.loads(blockstate_file.read_text(encoding="utf-8"))

        stems = set()
        for ref in collect_model_refs(blockstate):
            model_name = normalize_ref(ref)
            textures = load_model_textures(model_name, paths["models_dir"], cache)
            for concrete in resolve_concrete_textures(textures):
                stem = concrete_to_stem(concrete)
                if stem:
                    stems.add(stem)

        valid_stems = []
        for stem in sorted(stems):
            png_path = paths["textures_dir"] / f"{stem}.png"
            mcmeta_path = paths["textures_dir"] / f"{stem}.png.mcmeta"
            if not png_path.is_file():
                continue
            if mcmeta_path.is_file():
                # Animated strip (lava, water, fire, ...) -- leave untouched.
                continue
            valid_stems.append(stem)

        if valid_stems:
            result[block_id] = valid_stems

    output_path = paths["output_path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"version": args.version, "blocks": result}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    distinct_textures = {stem for stems in result.values() for stem in stems}
    print(f"Scanned {len(blockstate_files)} blockstates.")
    print(f"Blocks with a labelable texture: {len(result)}")
    print(f"Distinct texture files: {len(distinct_textures)}")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
