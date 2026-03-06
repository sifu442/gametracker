"""
Game data management - handles library and tracking data.
Thin wrapper delegating to modular helpers.
"""
import json
from core.constants import LIBRARY_FILE, TRACKING_FILE, EMULATORS_FILE, DB_FILE
from backend.game_manager_mods import media as gm_media
from backend.game_manager_mods import emulators as gm_emulators
from backend.game_manager_mods import sources as gm_sources
from backend.game_manager_mods import launchers as gm_launchers
from backend.game_manager_mods import library as gm_library
from backend.sqlite_store import SQLiteStore


class GameManager:
    """Manages game library and playtime tracking data"""

    def __init__(self):
        self.library_data = {}
        self.tracking_data = {}
        self.emulators_data = {}
        self.last_error = ""
        self._sqlite = SQLiteStore(DB_FILE)
        self.load_library()
        self.load_tracking()
        self.load_emulators()
        sync_stats = self.sync_pcsx2_playtime_from_dat() or {}
        print(
            "[PCSX2] startup playtime sync "
            f"updated={int(sync_stats.get('updated', 0))} "
            f"scanned={int(sync_stats.get('scanned', 0))} "
            f"no_serial={int(sync_stats.get('no_serial', 0))} "
            f"no_dat={int(sync_stats.get('no_dat', 0))} "
            f"no_match={int(sync_stats.get('no_match', 0))}",
            flush=True,
        )
        self.migrate_cover_paths()

    def _dataset_key(self, filepath):
        try:
            f = filepath.resolve()
        except Exception:
            f = filepath
        if f == LIBRARY_FILE:
            return "library"
        if f == TRACKING_FILE:
            return "tracking"
        if f == EMULATORS_FILE:
            return "emulators"
        return None

    def load_json(self, filepath, default=None):
        """Load JSON file with error handling"""
        if default is None:
            default = {}
        dataset_key = self._dataset_key(filepath)
        if dataset_key:
            payload = self._sqlite.read_dataset(dataset_key, None)
            if payload is not None:
                return payload
            # One-time migration from legacy JSON files.
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    self._sqlite.write_dataset(dataset_key, payload)
                    return payload
                except Exception as e:
                    print(f"Error loading {filepath}: {e}")
                    return default
            return default
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
                return default
        return default

    def save_json(self, filepath, data):
        """Save JSON file with error handling"""
        dataset_key = self._dataset_key(filepath)
        if dataset_key:
            ok = self._sqlite.write_dataset(dataset_key, data)
            if ok:
                self.last_error = ""
                return True
            self.last_error = f"Error saving dataset '{dataset_key}' to sqlite"
            return False
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self.last_error = ""
            return True
        except Exception as e:
            self.last_error = f"Error saving {filepath}: {e}"
            print(self.last_error)
            return False

    def load_library(self):
        """Load game library from file"""
        self.library_data = self.load_json(LIBRARY_FILE, {})
        self.ensure_game_ids()
        return self.library_data

    def save_library(self):
        """Save game library to file"""
        return self.save_json(LIBRARY_FILE, self.library_data)

    def load_tracking(self):
        """Load playtime tracking data from file"""
        self.tracking_data = self.load_json(TRACKING_FILE, {})
        return self.tracking_data

    def save_tracking(self):
        """Save playtime tracking data to file"""
        return self.save_json(TRACKING_FILE, self.tracking_data)


# Bind modular implementations to keep public API stable.
GameManager._find_media_by_name = gm_media._find_media_by_name
GameManager._find_media_by_candidates = gm_media._find_media_by_candidates

GameManager.load_emulators = gm_emulators.load_emulators
GameManager.ensure_emulator_ids = gm_emulators.ensure_emulator_ids
GameManager.save_emulators = gm_emulators.save_emulators
GameManager.add_emulator = gm_emulators.add_emulator
GameManager.update_emulator = gm_emulators.update_emulator
GameManager.remove_emulator = gm_emulators.remove_emulator
GameManager.get_emulator = gm_emulators.get_emulator
GameManager.get_all_emulators = gm_emulators.get_all_emulators
GameManager.scan_emulated_games = gm_emulators.scan_emulated_games
GameManager.get_emulator_playtime_seconds = gm_emulators.get_emulator_playtime_seconds
GameManager.sync_pcsx2_playtime_from_dat = gm_emulators.sync_pcsx2_playtime_from_dat

GameManager._get_heroic_installed_path = gm_sources._get_heroic_installed_path
GameManager.get_heroic_legendary_config_dir = gm_sources.get_heroic_legendary_config_dir
GameManager._parse_heroic_installed = gm_sources._parse_heroic_installed
GameManager.scan_heroic_legendary = gm_sources.scan_heroic_legendary
GameManager._get_steam_root_candidates = gm_sources._get_steam_root_candidates
GameManager._parse_vdf_paths = gm_sources._parse_vdf_paths
GameManager._parse_vdf_field = gm_sources._parse_vdf_field
GameManager.scan_steam_games = gm_sources.scan_steam_games
GameManager._get_riot_programdata_root = gm_sources._get_riot_programdata_root
GameManager._get_riot_client_path = gm_sources._get_riot_client_path
GameManager.scan_riot_games = gm_sources.scan_riot_games

GameManager.get_legendary_launch_command = gm_launchers.get_legendary_launch_command
GameManager.get_steam_launch_command = gm_launchers.get_steam_launch_command
GameManager.get_steam_playtime_minutes = gm_launchers.get_steam_playtime_minutes

GameManager.ensure_game_ids = gm_library.ensure_game_ids
GameManager.migrate_cover_paths = gm_library.migrate_cover_paths
GameManager.add_game = gm_library.add_game
GameManager.remove_game = gm_library.remove_game
GameManager.update_game = gm_library.update_game
GameManager.get_game = gm_library.get_game
GameManager.get_all_games = gm_library.get_all_games
GameManager.get_total_playtime = gm_library.get_total_playtime
GameManager.update_playtime = gm_library.update_playtime
GameManager.set_playtime = gm_library.set_playtime
GameManager.set_last_played = gm_library.set_last_played
GameManager.get_library_stats = gm_library.get_library_stats
