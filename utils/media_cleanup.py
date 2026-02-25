#!/usr/bin/env python3
"""
Cleanup/report utility for media assets referenced by game_library.json.

- Removes zero-byte placeholders in covers/logos/heroes.
- Reports unresolved media references from the library.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_FILE = ROOT / "game_library.json"
MEDIA_DIRS = [ROOT / "covers", ROOT / "logos", ROOT / "heroes"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".ico"}


def fix_path_str(p: str) -> str:
    if not p:
        return p
    path = str(p).replace("\\", "/")
    if path.lower().startswith("d:/"):
        return "/media/SSD" + path[2:]
    return path


def normalize_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_").lower()
    return stem


def is_valid_media_file(path: Path) -> bool:
    try:
        return path.exists() and path.is_file() and path.stat().st_size > 0
    except Exception:
        return False


def find_media_by_name(filename: str) -> Path | None:
    for media_dir in MEDIA_DIRS:
        candidate = media_dir / filename
        if is_valid_media_file(candidate):
            return candidate

    wanted = normalize_stem(filename)
    if not wanted:
        return None

    for media_dir in MEDIA_DIRS:
        try:
            for entry in media_dir.iterdir():
                if not entry.is_file():
                    continue
                if entry.suffix.lower() not in IMAGE_EXTS:
                    continue
                if entry.stat().st_size <= 0:
                    continue
                stem = normalize_stem(entry.name)
                if stem == wanted or stem.startswith(wanted) or wanted.startswith(stem):
                    return entry
        except Exception:
            continue
    return None


def resolve_media_path(rel_path: str) -> Path | None:
    if not rel_path:
        return None

    media_path = Path(fix_path_str(rel_path))
    if is_valid_media_file(media_path):
        return media_path

    by_name = find_media_by_name(media_path.name)
    if by_name:
        return by_name

    if not media_path.is_absolute():
        candidate = ROOT / media_path
        if is_valid_media_file(candidate):
            return candidate
    return None


def cleanup_zero_byte_files(apply_changes: bool) -> list[Path]:
    removed_or_found: list[Path] = []
    for media_dir in MEDIA_DIRS:
        if not media_dir.exists():
            continue
        for entry in media_dir.iterdir():
            try:
                if entry.is_file() and entry.stat().st_size == 0:
                    removed_or_found.append(entry)
                    if apply_changes:
                        entry.unlink(missing_ok=True)
            except Exception:
                continue
    return removed_or_found


def unresolved_media_entries() -> list[tuple[str, str, str]]:
    if not LIBRARY_FILE.exists():
        return []
    data = json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
    unresolved: list[tuple[str, str, str]] = []
    for game_id, game in data.items():
        if not isinstance(game, dict):
            continue
        for key in ("cover", "logo", "hero"):
            value = str(game.get(key) or "").strip()
            if not value:
                continue
            if resolve_media_path(value) is None:
                unresolved.append((game_id, key, value))
    return unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup/report media references.")
    parser.add_argument("--apply", action="store_true", help="Delete zero-byte media placeholders.")
    args = parser.parse_args()

    zero_byte = cleanup_zero_byte_files(apply_changes=args.apply)
    unresolved = unresolved_media_entries()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[media-cleanup] Mode: {mode}")
    print(f"[media-cleanup] Zero-byte placeholders found: {len(zero_byte)}")
    for path in zero_byte:
        action = "removed" if args.apply else "would remove"
        print(f"  - {action}: {path}")

    print(f"[media-cleanup] Unresolved media references: {len(unresolved)}")
    for game_id, field, value in unresolved:
        print(f"  - {game_id} :: {field} -> {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
