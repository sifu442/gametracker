import os
import time
from pathlib import Path

from core.constants import EMULATORS_FILE, COVERS_DIR, LOGOS_DIR, HEROES_DIR, SCRIPT_DIR, IS_WINDOWS, IS_LINUX
from utils.helpers import fix_path_str, canonicalize_path


def load_emulators(self):
    """Load emulator definitions from file"""
    self.emulators_data = self.load_json(EMULATORS_FILE, {})
    self.ensure_emulator_ids()
    changed = False

    def _looks_windows_binary(path_value):
        p = str(path_value or "").strip().lower()
        if not p:
            return False
        return p.endswith(".exe") or p.startswith("c:/") or p.startswith("d:/") or p.startswith("e:/")
    for emulator_id, emulator_data in self.emulators_data.items():
        if not isinstance(emulator_data, dict):
            continue
        launch_type = (emulator_data.get("launch_type") or "executable").strip().lower()
        if launch_type == "exe":
            launch_type = "executable"
        if not isinstance(emulator_data.get("exe_paths"), dict):
            exe_path = emulator_data.get("exe_path") or ""
            if exe_path:
                emulator_data["exe_paths"] = {launch_type: exe_path}
                changed = True
        exe_paths = emulator_data.get("exe_paths") or {}
        if emulator_data.get("exe_path_windows") in (None, "") and exe_paths.get("Windows"):
            emulator_data["exe_path_windows"] = exe_paths.get("Windows")
            changed = True
        if emulator_data.get("exe_path_linux") in (None, "") and exe_paths.get("Linux"):
            emulator_data["exe_path_linux"] = exe_paths.get("Linux")
            changed = True
        if emulator_data.get("launch_type_windows") in (None, "") and emulator_data.get("launch_type"):
            emulator_data["launch_type_windows"] = emulator_data.get("launch_type")
            changed = True
        if emulator_data.get("launch_type_linux") in (None, "") and emulator_data.get("launch_type"):
            emulator_data["launch_type_linux"] = emulator_data.get("launch_type")
            changed = True
        legacy_exe = emulator_data.get("exe_path") or ""
        if legacy_exe:
            if emulator_data.get("exe_path_windows") in (None, "") and _looks_windows_binary(legacy_exe):
                emulator_data["exe_path_windows"] = legacy_exe
                changed = True
            if emulator_data.get("exe_path_linux") in (None, "") and not _looks_windows_binary(legacy_exe):
                emulator_data["exe_path_linux"] = legacy_exe
                changed = True
    if not EMULATORS_FILE.exists():
        self.save_emulators()
    elif changed:
        self.save_emulators()
    return self.emulators_data


def ensure_emulator_ids(self):
    """Ensure every emulator entry has an id field matching its key."""
    changed = False
    for emulator_id, emulator_data in self.emulators_data.items():
        if not isinstance(emulator_data, dict):
            continue
        if emulator_data.get("id") != emulator_id:
            emulator_data["id"] = emulator_id
            changed = True
    if changed:
        self.save_emulators()


def save_emulators(self):
    """Save emulator definitions to file"""
    return self.save_json(EMULATORS_FILE, self.emulators_data)


def add_emulator(self, emulator_data):
    """Add a new emulator definition"""
    name = emulator_data.get("name", "").strip()
    if not name:
        return False, None, "Emulator name is required"
    emulator_id = emulator_data.get("id") or name.replace(" ", "_").lower()
    if emulator_id in self.emulators_data:
        return False, None, f"Emulator '{name}' already exists"
    emulator_data["id"] = emulator_id
    self.emulators_data[emulator_id] = emulator_data
    if self.save_emulators():
        return True, emulator_id, f"Added '{name}'"
    return False, None, "Failed to save emulators"


def update_emulator(self, emulator_id, updated_data):
    """Update emulator definition"""
    if emulator_id not in self.emulators_data:
        return False, None, "Emulator not found"
    old_data = self.emulators_data[emulator_id]
    new_entry = old_data.copy()
    new_entry.update(updated_data)
    self.emulators_data[emulator_id] = new_entry
    if self.save_emulators():
        return True, emulator_id, "Updated emulator"
    return False, None, "Failed to save emulators"


def remove_emulator(self, emulator_id):
    """Remove emulator definition"""
    if emulator_id not in self.emulators_data:
        return False, "Emulator not found"
    del self.emulators_data[emulator_id]
    if self.save_emulators():
        return True, "Removed emulator"
    return False, "Failed to save emulators"


def get_emulator(self, emulator_id):
    """Get emulator definition"""
    return self.emulators_data.get(emulator_id)


def get_all_emulators(self):
    """Get all emulators"""
    return self.emulators_data


def _resolve_emulator_base_dir(emulator):
    exe_path = ""
    if IS_WINDOWS and emulator.get("exe_path_windows"):
        exe_path = emulator.get("exe_path_windows")
    if IS_LINUX and emulator.get("exe_path_linux"):
        exe_path = emulator.get("exe_path_linux")
    exe_paths = emulator.get("exe_paths")
    if isinstance(exe_paths, dict):
        launch_type = (emulator.get("launch_type") or "executable").strip().lower()
        if IS_WINDOWS:
            launch_type = (emulator.get("launch_type_windows") or launch_type).strip().lower()
        if IS_LINUX:
            launch_type = (emulator.get("launch_type_linux") or launch_type).strip().lower()
        if launch_type == "exe":
            launch_type = "executable"
        if not exe_path:
            exe_path = exe_paths.get(launch_type, "")
        if not exe_path:
            for _, val in exe_paths.items():
                if val:
                    exe_path = val
                    break
    elif isinstance(exe_paths, str):
        exe_path = exe_paths
    if not exe_path:
        exe_path = emulator.get("exe_path") or ""
    if not exe_path:
        return None
    exe_path = Path(fix_path_str(exe_path))
    if not exe_path.is_absolute():
        exe_path = SCRIPT_DIR / exe_path
    return exe_path.parent


def _read_playtime_dat(base_dir):
    candidates = [
        base_dir / "inis" / "playtime.dat",
        base_dir / "ini" / "playtime.dat",
    ]
    playtime_file = None
    for candidate in candidates:
        if candidate.exists():
            playtime_file = candidate
            break
    if not playtime_file:
        return {}
    serial_seconds = {}
    try:
        with open(playtime_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 2:
                    continue
                serial = str(parts[0] or "").strip().upper()
                if not serial:
                    continue
                try:
                    serial_seconds[serial] = int(float(parts[1]))
                except Exception:
                    continue
    except Exception:
        return {}
    return serial_seconds


def sync_pcsx2_playtime_from_dat(self):
    """
    Copy PCSX2 playtime.dat values into library playtime on startup.
    Only increases stored playtime; never decreases.
    """
    changed = False
    updated_count = 0
    scanned_count = 0
    no_serial_count = 0
    no_dat_count = 0
    no_match_count = 0
    serial_map_by_emulator = {}

    for game_data in self.library_data.values():
        if not isinstance(game_data, dict):
            continue
        if not bool(game_data.get("is_emulated")):
            continue
        emulator_id = (game_data.get("emulator_id") or "").strip()
        serial = (game_data.get("serial") or "").strip().upper()
        if not emulator_id:
            continue

        emulator = self.emulators_data.get(emulator_id) or {}
        emulator_name = str(emulator.get("name") or "").lower()
        if "pcsx2" not in emulator_id.lower() and "pcsx2" not in emulator_name:
            continue
        scanned_count += 1
        if not serial:
            no_serial_count += 1
            continue

        if emulator_id not in serial_map_by_emulator:
            base_dir = _resolve_emulator_base_dir(emulator)
            serial_map_by_emulator[emulator_id] = _read_playtime_dat(base_dir) if base_dir else {}
            if not serial_map_by_emulator[emulator_id]:
                no_dat_count += 1

        serial_seconds = serial_map_by_emulator.get(emulator_id) or {}
        seconds = int(serial_seconds.get(serial, 0) or 0)
        if seconds <= 0:
            no_match_count += 1
            continue
        minutes = round(seconds / 60.0, 2)
        try:
            current_minutes = float(game_data.get("playtime", 0) or 0)
        except Exception:
            current_minutes = 0.0
        if minutes > current_minutes:
            game_data["playtime"] = minutes
            changed = True
            updated_count += 1

    if changed:
        self.save_library()
    return {
        "updated": updated_count,
        "scanned": scanned_count,
        "no_serial": no_serial_count,
        "no_dat": no_dat_count,
        "no_match": no_match_count,
    }


def scan_emulated_games(self):
    """
    Scan emulator ROM directories and add new emulated games.

    Returns:
        tuple: (added_count, skipped_count)
    """
    added = 0
    skipped = 0
    changed = False

    def _normalize_rom_path(path_value):
        return canonicalize_path(fix_path_str(str(path_value or "").strip()))

    def _entry_quality(entry):
        # Prefer keeping records with richer metadata/history.
        score = 0
        if (entry.get("cover") or "").strip():
            score += 2
        if (entry.get("logo") or "").strip():
            score += 2
        if (entry.get("hero") or "").strip():
            score += 2
        if (entry.get("serial") or "").strip():
            score += 1
        if (entry.get("notes") or "").strip():
            score += 1
        try:
            score += max(0, int(entry.get("playtime", 0) or 0))
        except Exception:
            pass
        return score

    # Deduplicate existing emulated entries by (emulator_id, rom_path).
    best_by_key = {}
    remove_ids = set()
    for game_id, game in list(self.library_data.items()):
        if not isinstance(game, dict):
            continue
        if not game.get("is_emulated"):
            continue
        emulator_id = (game.get("emulator_id") or "").strip()
        rom_path = _normalize_rom_path(game.get("rom_path"))
        if not emulator_id or not rom_path:
            continue
        key = (emulator_id, rom_path)
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = game_id
            continue
        current_game = self.library_data.get(current, {})
        if _entry_quality(game) > _entry_quality(current_game):
            remove_ids.add(current)
            best_by_key[key] = game_id
        else:
            remove_ids.add(game_id)

    for gid in remove_ids:
        if gid in self.library_data:
            del self.library_data[gid]
            changed = True

    # Build a set of existing (emulator_id, rom_path) for quick lookup.
    existing_keys = set()
    for game in self.library_data.values():
        if not isinstance(game, dict):
            continue
        if game.get("is_emulated") and game.get("rom_path") and game.get("emulator_id"):
            existing_keys.add(
                ((game.get("emulator_id") or "").strip(), _normalize_rom_path(game.get("rom_path")))
            )

    def _find_media_path(media_dir, base_name, suffix_tag):
        if not media_dir.exists():
            return ""
        pattern = f"{base_name}_{suffix_tag}.*"
        matches = list(media_dir.glob(pattern))
        if not matches:
            return ""
        try:
            return str(matches[0].relative_to(SCRIPT_DIR))
        except Exception:
            return str(matches[0])

    for emulator_id, emulator in self.emulators_data.items():
        rom_dirs = emulator.get("rom_dirs") or []
        extensions = emulator.get("rom_extensions") or []
        extensions = [ext.lower() for ext in extensions]

        for rom_dir in rom_dirs:
            rom_dir_path = Path(fix_path_str(rom_dir))
            if not rom_dir_path.exists():
                continue

            for root, _, files in os.walk(rom_dir_path):
                for fname in files:
                    fpath = Path(root) / fname
                    if extensions:
                        if fpath.suffix.lower() not in extensions:
                            continue

                    rom_path = _normalize_rom_path(str(fpath))
                    key = (emulator_id, rom_path)
                    if key in existing_keys:
                        skipped += 1
                        continue

                    title = fpath.stem.replace("_", " ").strip()
                    base_name = (title or fpath.stem).replace(" ", "_")
                    game_id = f"{emulator_id}_{fpath.stem}".replace(" ", "_").lower()
                    if game_id in self.library_data:
                        skipped += 1
                        continue

                    self.library_data[game_id] = {
                        "id": game_id,
                        "name": title or fpath.stem,
                        "genre": "",
                        "platform": (emulator.get("platforms") or ["Emulated"])[0],
                        "notes": "",
                        "playtime": 0,
                        "proton_path": None,
                        "added_date": time.time(),
                        "cover": _find_media_path(COVERS_DIR, base_name, "cover"),
                        "logo": _find_media_path(LOGOS_DIR, base_name, "logo"),
                        "hero": _find_media_path(HEROES_DIR, base_name, "hero"),
                        "is_emulated": True,
                        "emulator_id": emulator_id,
                        "rom_path": rom_path,
                        "process_name": fpath.stem,
                        "installed": True,
                    }
                    existing_keys.add(key)
                    added += 1
                    changed = True

    if changed:
        self.save_library()
    return added, skipped


def get_emulator_playtime_seconds(self, emulator_id, serial):
    def _stored_seconds_fallback():
        if not emulator_id or not serial:
            return 0
        for game_data in self.library_data.values():
            if not isinstance(game_data, dict):
                continue
            if not game_data.get("is_emulated"):
                continue
            if (game_data.get("emulator_id") or "") != emulator_id:
                continue
            if (game_data.get("serial") or "").upper() != serial.upper():
                continue
            try:
                mins = int(game_data.get("playtime", 0) or 0)
            except Exception:
                mins = 0
            return max(0, mins * 60)
        return 0

    def _persist_seconds_to_library(seconds):
        # Playtime in library JSON is treated as immutable metadata.
        # Runtime values should be read from tracker/state sources instead.
        return

    if not emulator_id or not serial:
        return 0
    emulator = self.emulators_data.get(emulator_id) or {}
    base_dir = _resolve_emulator_base_dir(emulator)
    if not base_dir:
        return _stored_seconds_fallback()
    serial_map = _read_playtime_dat(base_dir)
    try:
        seconds = int(serial_map.get(serial.upper(), 0) or 0)
        if seconds > 0:
            _persist_seconds_to_library(seconds)
            return seconds
    except Exception:
        return _stored_seconds_fallback()
    return _stored_seconds_fallback()
