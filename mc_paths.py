"""Shared helper for locating the local .minecraft install."""

import os
import platform
from pathlib import Path


def default_minecraft_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise SystemExit("%APPDATA% isn't set; pass --minecraft-dir explicitly.")
        return Path(appdata) / ".minecraft"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "minecraft"
    return Path.home() / ".minecraft"  # Linux and everything else
