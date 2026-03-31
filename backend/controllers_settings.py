"""
Settings and emulator CRUD operations extracted from AppController.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.constants import CONFIG_FILE, IS_LINUX, IS_WINDOWS
from utils.helpers import save_json

if TYPE_CHECKING:
    from backend.controllers import AppController


class SettingsControllerOps:
    """Encapsulates settings + emulator management methods."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def set_riot_client_path(self, path):
        c = self._c
        path = (path or "").strip()
        if path == c._config.get("riot_client_path", ""):
            return
        c._config["riot_client_path"] = path
        save_json(CONFIG_FILE, c._config)
        c.riotClientPathChanged.emit()

    def set_steam_api_settings(self, api_key, steam_id64):
        c = self._c
        api_key = (api_key or "").strip()
        steam_id64 = (steam_id64 or "").strip()
        if steam_id64 and not steam_id64.isdigit():
            c.errorMessage.emit("Steam ID64 must be numeric.")
            return

        changed = False
        if api_key != c._config.get("steam_web_api_key", ""):
            c._config["steam_web_api_key"] = api_key
            changed = True
        if steam_id64 != c._config.get("steam_id64", ""):
            c._config["steam_id64"] = steam_id64
            changed = True

        if changed:
            save_json(CONFIG_FILE, c._config)
            c._steam_service.update_api_key(c._config.get("steam_web_api_key", ""))
            c._steam_emu_service.update_api_key(c._config.get("steam_web_api_key", ""))
            c.steamApiSettingsChanged.emit()


    def persist_steam_emu_custom_roots(self, roots):
        c = self._c
        seen = set()
        cleaned = []
        for raw in roots or []:
            val = str(raw or "").strip()
            if not val:
                continue
            key = val.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(val)
        c._config["steam_emu_custom_roots"] = cleaned
        save_json(CONFIG_FILE, c._config)
        c._steam_emu_service.set_extra_roots(cleaned)
        c._steam_emu_service.prime_watch_index()
        c.steamEmuRootsChanged.emit()

    def add_steam_emu_custom_root(self, path):
        c = self._c
        value = (path or "").strip()
        if not value:
            return "Path is empty."
        roots = c._config.get("steam_emu_custom_roots") or []
        if not isinstance(roots, list):
            roots = []
        if value.lower() in [str(r).strip().lower() for r in roots]:
            return "Path already exists."
        roots.append(value)
        self.persist_steam_emu_custom_roots(roots)
        return f"Added SteamEmu location: {value}"

    def remove_steam_emu_custom_root(self, path):
        c = self._c
        value = (path or "").strip().lower()
        roots = c._config.get("steam_emu_custom_roots") or []
        if not isinstance(roots, list):
            roots = []
        filtered = [str(r).strip() for r in roots if str(r).strip().lower() != value]
        if len(filtered) == len(roots):
            return "Path not found."
        self.persist_steam_emu_custom_roots(filtered)
        return "Removed SteamEmu location."

    def add_emulator(
        self,
        name,
        launch_type,
        exe_path,
        args_template,
        platforms,
        rom_extensions,
        rom_dirs,
        flatpak_id,
    ):
        c = self._c

        def _split_csv(value):
            if isinstance(value, list):
                return value
            if not value:
                return []
            return [v.strip() for v in str(value).split(",") if v.strip()]

        launch_type = c._normalize_launch_type(launch_type)
        exe_paths = {launch_type: (exe_path or "").strip()}
        emulator_data = {
            "name": (name or "").strip(),
            "launch_type": launch_type,
            "exe_paths": exe_paths,
            "exe_path": (exe_path or "").strip(),
            "args_template": (args_template or "").strip(),
            "platforms": _split_csv(platforms),
            "rom_extensions": _split_csv(rom_extensions),
            "rom_dirs": _split_csv(rom_dirs),
            "flatpak_id": (flatpak_id or "").strip(),
            "launch_type_windows": launch_type if IS_WINDOWS else "",
            "launch_type_linux": launch_type if IS_LINUX else "",
            "exe_path_windows": (exe_path or "").strip() if IS_WINDOWS else "",
            "exe_path_linux": (exe_path or "").strip() if IS_LINUX else "",
        }
        if launch_type == "flatpak" and not emulator_data["flatpak_id"]:
            c.errorMessage.emit("Flatpak app ID is required.")
            return
        if launch_type != "flatpak" and not emulator_data["exe_paths"].get(launch_type):
            c.errorMessage.emit("Emulator executable/AppImage path is required.")
            return
        success, _, message = c._game_manager.add_emulator(emulator_data)
        if not success:
            c.errorMessage.emit(message)
            return
        c.emulatorsChanged.emit()

    def update_emulator_fields(
        self,
        emulator_id,
        name,
        launch_type,
        exe_path,
        args_template,
        platforms,
        rom_extensions,
        rom_dirs,
        flatpak_id,
    ):
        c = self._c

        def _split_csv(value):
            if isinstance(value, list):
                return value
            if not value:
                return []
            return [v.strip() for v in str(value).split(",") if v.strip()]

        launch_type = c._normalize_launch_type(launch_type)
        emulator = c._game_manager.get_emulator(emulator_id) or {}
        exe_paths = emulator.get("exe_paths") if isinstance(emulator.get("exe_paths"), dict) else {}
        exe_paths = exe_paths.copy() if isinstance(exe_paths, dict) else {}
        exe_paths[launch_type] = (exe_path or "").strip()
        updates = {
            "name": (name or "").strip(),
            "launch_type": launch_type,
            "exe_paths": exe_paths,
            "exe_path": (exe_path or "").strip(),
            "args_template": (args_template or "").strip(),
            "platforms": _split_csv(platforms),
            "rom_extensions": _split_csv(rom_extensions),
            "rom_dirs": _split_csv(rom_dirs),
            "flatpak_id": (flatpak_id or "").strip(),
        }
        if IS_WINDOWS:
            updates["launch_type_windows"] = launch_type
            updates["exe_path_windows"] = (exe_path or "").strip()
        if IS_LINUX:
            updates["launch_type_linux"] = launch_type
            updates["exe_path_linux"] = (exe_path or "").strip()
        if launch_type != "flatpak" and not updates["exe_paths"].get(launch_type):
            c.errorMessage.emit("Emulator executable/AppImage path is required.")
            return
        success, _, message = c._game_manager.update_emulator(emulator_id, updates)
        if not success:
            c.errorMessage.emit(message)
            return
        c.emulatorsChanged.emit()

    def remove_emulator(self, emulator_id):
        c = self._c
        success, message = c._game_manager.remove_emulator(emulator_id)
        if not success:
            c.errorMessage.emit(message)
            return
        c.emulatorsChanged.emit()
