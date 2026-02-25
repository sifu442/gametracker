import time
from pathlib import Path

from utils.helpers import fix_path_str, canonicalize_path


def ensure_game_ids(self):
    """Ensure every game entry has an id field matching its key."""
    changed = False
    for game_id, game_data in self.library_data.items():
        if not isinstance(game_data, dict):
            continue
        if game_data.get("id") != game_id:
            game_data["id"] = game_id
            changed = True
    if changed:
        self.save_library()


def migrate_cover_paths(self):
    """
    Migrate to new exe_paths format (per-platform) and convert cover paths to relative
    """
    changed = False

    for game_id, game_data in self.library_data.items():
        # Migrate exe_path to exe_paths (platform-specific)
        if 'exe_path' in game_data and 'exe_paths' not in game_data:
            old_exe_path = game_data.get('exe_path')
            if old_exe_path:
                # Try to detect which platform this path belongs to
                if old_exe_path.startswith(('C:\\', 'D:\\', 'E:\\')) or 'Windows' in old_exe_path:
                    exe_paths = {'Windows': old_exe_path, 'Linux': ''}
                else:
                    exe_paths = {'Windows': '', 'Linux': old_exe_path}
                game_data['exe_paths'] = exe_paths
                del game_data['exe_path']
                changed = True

        # Migrate media paths to filename-only
        for key in ("cover", "logo", "hero"):
            media_path = game_data.get(key)
            if not media_path:
                continue
            media_file = Path(fix_path_str(media_path))
            # Store just the filename if path-like
            if media_file.name != str(media_path):
                self.library_data[game_id][key] = media_file.name
                changed = True

        # Normalize stored paths across OS (D:/ <-> /media/SSD)
        for key in ("rom_path", "install_path", "proton_path"):
            if key in game_data and game_data.get(key):
                new_path = canonicalize_path(fix_path_str(game_data.get(key)))
                if new_path != game_data.get(key):
                    game_data[key] = new_path
                    changed = True

        exe_paths = game_data.get("exe_paths")
        if isinstance(exe_paths, dict):
            for plat_key, plat_path in exe_paths.items():
                if plat_path:
                    new_path = canonicalize_path(fix_path_str(plat_path))
                    if new_path != plat_path:
                        exe_paths[plat_key] = new_path
                        changed = True

        # Emulation-only fields should not persist for native games.
        if not bool(game_data.get("is_emulated")):
            for key in ("emulator_id", "rom_path", "ra_game_id"):
                if key in game_data:
                    game_data.pop(key, None)
                    changed = True

    if changed:
        self.save_library()


def add_game(self, game_data):
    """
    Add a new game to the library

    Args:
        game_data: Dictionary containing game information

    Returns:
        tuple: (success: bool, game_id: str, message: str)
    """
    name = game_data.get('name', '').strip()
    if not name:
        return False, None, "Game name is required"

    game_id = name.replace(' ', '_').lower()

    if game_id in self.library_data:
        return False, None, f"Game '{name}' already exists in library"

    game_data["id"] = game_id
    self.library_data[game_id] = game_data

    if self.save_library():
        return True, game_id, f"Added '{name}' to library"
    else:
        return False, None, "Failed to save library"


def remove_game(self, game_id):
    """
    Remove a game from the library

    Args:
        game_id: ID of the game to remove

    Returns:
        tuple: (success: bool, message: str)
    """
    if game_id not in self.library_data:
        return False, "Game not found"

    del self.library_data[game_id]

    if self.save_library():
        return True, "Game removed"
    else:
        return False, "Failed to save library"


def update_game(self, game_id, updated_data):
    """
    Update an existing game

    Args:
        game_id: ID of the game to update
        updated_data: Dictionary containing updated game information

    Returns:
        tuple: (success: bool, new_game_id: str, message: str)
    """
    if game_id not in self.library_data:
        return False, None, "Game not found"

    old_data = self.library_data[game_id]
    new_entry = old_data.copy()
    new_entry.update(updated_data)

    new_name = new_entry.get('name', '').strip()
    if not new_name:
        return False, None, "Game name is required"

    new_id = new_name.replace(' ', '_').lower()
    if new_id != game_id and new_id in self.library_data:
        return False, None, f"Game '{new_name}' already exists"

    if new_id != game_id:
        del self.library_data[game_id]
        self.library_data[new_id] = new_entry
    else:
        self.library_data[game_id] = new_entry

    if self.save_library():
        return True, new_id, f"Updated '{new_name}'"
    else:
        if self.last_error:
            return False, None, self.last_error
        return False, None, "Failed to save library"


def get_game(self, game_id):
    """Get game data by ID"""
    return self.library_data.get(game_id)


def get_all_games(self):
    """Get all games in library"""
    return self.library_data


def get_total_playtime(self, process_name):
    """
    Get total playtime for a process

    Args:
        process_name: Name of the process

    Returns:
        int: Total playtime in seconds
    """
    if process_name in self.tracking_data:
        return self.tracking_data[process_name].get('total_runtime', 0)
    return 0


def update_playtime(self, process_name, seconds):
    if not process_name:
        return
    try:
        seconds = int(seconds)
    except Exception:
        return

    if process_name not in self.tracking_data:
        self.tracking_data[process_name] = {
            "total_runtime": 0,
            "last_session_start": 0,
            "last_session_end": 0,
        }
    self.tracking_data[process_name]["total_runtime"] = max(
        0, int(self.tracking_data[process_name].get("total_runtime", 0)) + seconds
    )

    self.save_tracking()


def set_playtime(self, process_name, seconds):
    if not process_name:
        return
    try:
        seconds = int(seconds)
    except Exception:
        return
    if process_name not in self.tracking_data:
        self.tracking_data[process_name] = {
            "total_runtime": 0,
            "last_session_start": 0,
            "last_session_end": 0,
        }
    self.tracking_data[process_name]["total_runtime"] = max(0, seconds)
    self.save_tracking()


def set_last_played(self, process_name, timestamp=None):
    if not process_name:
        return
    if process_name not in self.tracking_data:
        self.tracking_data[process_name] = {
            "total_runtime": 0,
            "last_session_start": 0,
            "last_session_end": 0,
        }
    if timestamp is None:
        timestamp = time.time()
    self.tracking_data[process_name]["last_session_end"] = timestamp
    self.save_tracking()


def get_library_stats(self):
    stats = {
        "total_games": len(self.library_data),
        "emulated_games": len([g for g in self.library_data.values() if g.get("is_emulated")]),
        "total_playtime": 0,
        "total_sessions": 0,
    }
    for process_name, data in self.tracking_data.items():
        stats["total_playtime"] += int(data.get("total_runtime", 0))
        if data.get("last_session_start") and data.get("last_session_end"):
            stats["total_sessions"] += 1
    return stats
