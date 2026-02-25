"""
RetroAchievements mapping and selection operations extracted from AppController.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.constants import CONFIG_FILE
from utils.helpers import canonicalize_path, save_json

if TYPE_CHECKING:
    from backend.controllers import AppController


class RaControllerOps:
    """Encapsulates RA id mapping and selected-game RA updates."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def load_ra_progress_cache_from_config(self):
        c = self._c
        raw = c._config.get("ra_progress_cache") or {}
        if not isinstance(raw, dict):
            return {}
        normalized = {}
        for key, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            game_key = str(key).strip()
            if not game_key:
                continue
            unlocked_list = entry.get("unlocked_list") or []
            if not isinstance(unlocked_list, list):
                unlocked_list = []
            normalized[game_key] = {
                "unlocked": int(entry.get("unlocked") or 0),
                "total": int(entry.get("total") or 0),
                "unlocked_list": unlocked_list,
                "ts": float(entry.get("ts") or 0),
            }
        return normalized

    def save_ra_progress_cache_to_config(self):
        c = self._c
        serializable = {}
        for key, entry in c._ra_progress_cache.items():
            if not isinstance(entry, dict):
                continue
            serializable[str(key)] = {
                "unlocked": int(entry.get("unlocked") or 0),
                "total": int(entry.get("total") or 0),
                "unlocked_list": entry.get("unlocked_list") or [],
                "ts": float(entry.get("ts") or 0),
            }
        c._config["ra_progress_cache"] = serializable
        save_json(CONFIG_FILE, c._config)

    def get_ra_id_by_rom_path(self, rom_path):
        c = self._c
        path = canonicalize_path((rom_path or "").strip())
        mapping = c._config.get("ra_game_ids") or {}
        if not isinstance(mapping, dict):
            return None
        value = None
        if path:
            value = mapping.get(path)
        if value is None and rom_path:
            value = mapping.get((rom_path or "").strip())
        try:
            value = int(value)
        except Exception:
            return None
        return value if value > 0 else None

    def get_ra_id_by_game_id(self, game_id):
        c = self._c
        if not game_id:
            return None
        mapping = c._config.get("ra_game_ids_by_game") or {}
        if not isinstance(mapping, dict):
            return None
        value = mapping.get(game_id)
        try:
            value = int(value)
        except Exception:
            return None
        return value if value > 0 else None

    def apply_ra_mapping_to_library(self):
        c = self._c
        changed = False
        all_games = c._game_manager.get_all_games() or {}
        for game_id, game_data in all_games.items():
            if not isinstance(game_data, dict):
                continue
            if not game_data.get("is_emulated"):
                continue
            if game_data.get("ra_game_id"):
                continue
            mapped = self.get_ra_id_by_game_id(game_id)
            if not mapped:
                rom_path = game_data.get("rom_path")
                if rom_path:
                    mapped = self.get_ra_id_by_rom_path(rom_path)
            if not mapped:
                continue
            updated = game_data.copy()
            updated["ra_game_id"] = mapped
            success, _, _ = c._game_manager.update_game(game_id, updated)
            if success:
                changed = True
        return changed

    def set_ra_id_by_rom_path(self, rom_path, ra_game_id):
        c = self._c
        path = canonicalize_path((rom_path or "").strip())
        if not path:
            return
        mapping = c._config.get("ra_game_ids") or {}
        if not isinstance(mapping, dict):
            mapping = {}
        if ra_game_id is None:
            mapping.pop(path, None)
        else:
            mapping[path] = int(ra_game_id)
        c._config["ra_game_ids"] = mapping
        save_json(CONFIG_FILE, c._config)

    def set_ra_id_by_game_id(self, game_id, ra_game_id):
        c = self._c
        if not game_id:
            return
        mapping = c._config.get("ra_game_ids_by_game") or {}
        if not isinstance(mapping, dict):
            mapping = {}
        if ra_game_id is None:
            mapping.pop(game_id, None)
        else:
            mapping[game_id] = int(ra_game_id)
        c._config["ra_game_ids_by_game"] = mapping
        save_json(CONFIG_FILE, c._config)

    def set_selected_ra_game_id(self, ra_game_id_text):
        c = self._c
        if not c._selected_game_id:
            c.errorMessage.emit("No game selected.")
            return
        game = c._game_manager.get_game(c._selected_game_id) or {}
        if not game.get("is_emulated"):
            c.errorMessage.emit("RetroAchievements ID can be set only for emulated games.")
            return

        value = (ra_game_id_text or "").strip()
        if value == "":
            ra_game_id = None
        else:
            try:
                ra_game_id = int(value)
            except Exception:
                c.errorMessage.emit("RetroAchievements ID must be a number.")
                return
            if ra_game_id <= 0:
                c.errorMessage.emit("RetroAchievements ID must be a positive number.")
                return

        updated = game.copy()
        updated["ra_game_id"] = ra_game_id
        success, new_game_id, message = c._game_manager.update_game(c._selected_game_id, updated)
        if not success:
            c.errorMessage.emit(message)
            return

        if new_game_id and new_game_id != c._selected_game_id:
            old_id = c._selected_game_id
            c._selected_game_id = new_game_id
            self.set_ra_id_by_game_id(old_id, None)
            self.set_ra_id_by_game_id(new_game_id, ra_game_id)
        else:
            self.set_ra_id_by_game_id(c._selected_game_id, ra_game_id)

        if game.get("rom_path"):
            self.set_ra_id_by_rom_path(game.get("rom_path"), ra_game_id)

        c._game_model.refresh()
        c.libraryChanged.emit()
        c._kick_ra_progress_update()
