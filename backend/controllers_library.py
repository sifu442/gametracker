"""
Library CRUD operations extracted from AppController.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from core.constants import COVERS_DIR, HEROES_DIR, IS_LINUX, IS_WINDOWS, LOGOS_DIR, SCRIPT_DIR
from utils.helpers import canonicalize_path, fix_path_str, sanitize_filename_component

if TYPE_CHECKING:
    from backend.controllers import AppController


class LibraryControllerOps:
    """Encapsulates game add/update/remove methods."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def _parse_date_to_timestamp(self, date_text):
        text = str(date_text or "").strip()
        if not text:
            return None
        try:
            dt = datetime.strptime(text, "%Y-%m-%d")
            return dt.timestamp()
        except Exception:
            return None

    def _default_linux_wine_prefix(self, game_name):
        safe_name = (game_name or "").strip() or "Game"
        return str(Path.home() / ".local" / "share" / "gametracker" / "default" / safe_name)

    def remove_selected(self):
        c = self._c
        if not c._selected_game_id:
            return
        success, message = c._game_manager.remove_game(c._selected_game_id)
        if not success:
            c.errorMessage.emit(message)
            return
        c._selected_game_id = ""
        c._game_model.refresh()
        c.libraryChanged.emit()

    def update_selected_basic(self, name, genre, platform, notes):
        c = self._c
        if not c._selected_game_id:
            return
        current = c._game_manager.get_game(c._selected_game_id)
        if not current:
            c.errorMessage.emit("Game not found.")
            return
        updated = current.copy()
        updated["name"] = name.strip()
        updated["genre"] = genre.strip()
        updated["platform"] = platform.strip()
        updated["notes"] = notes
        success, new_game_id, message = c._game_manager.update_game(c._selected_game_id, updated)
        if not success:
            c.errorMessage.emit(message)
            return
        if new_game_id and new_game_id != c._selected_game_id:
            c._selected_game_id = new_game_id
        c._game_model.refresh()
        c.libraryChanged.emit()

    def rename_game_media(self, new_entry, old_data, media_type, game_name):
        old_path = old_data.get(media_type)
        if old_path:
            old_file = Path(fix_path_str(old_path))
            if not old_file.is_absolute():
                old_file = SCRIPT_DIR / old_file
            if old_file.exists():
                new_name = f"{sanitize_filename_component(game_name)}_{media_type}{old_file.suffix}"
                new_path = old_file.parent / new_name
                try:
                    old_file.rename(new_path)
                    new_entry[media_type] = new_path.name
                except Exception:
                    new_entry[media_type] = str(old_file)

    def find_media_by_name(self, media_dir, game_name, media_type):
        if not media_dir.exists():
            return ""
        bases = [game_name.replace(" ", "_"), sanitize_filename_component(game_name)]
        matches = []
        for base in bases:
            if not base:
                continue
            pattern = f"{base}_{media_type}.*"
            matches = list(media_dir.glob(pattern))
            if matches:
                break
        if not matches:
            return ""
        try:
            return str(matches[0].relative_to(SCRIPT_DIR))
        except Exception:
            return str(matches[0])

    def add_game_full(
        self,
        name,
        genre,
        platform,
        playtime_minutes,
        notes,
        serial,
        exe_windows,
        exe_linux,
        install_location,
        wine_prefix,
        wine_dll_overrides,
        windows_only,
        installed,
        cover_path,
        logo_path,
        hero_path,
        compat_tool,
        proton_path,
        is_emulated,
        emulator_id,
        rom_path,
        links_json,
        first_played_date,
        last_played_date,
    ):
        c = self._c
        name = (name or "").strip()
        if not name:
            c.errorMessage.emit("Game name is required.")
            return
        is_emulated = bool(is_emulated)
        exe_windows = (exe_windows or "").strip()
        exe_linux = (exe_linux or "").strip()
        emulator_id = (emulator_id or "").strip()
        rom_path = canonicalize_path((rom_path or "").strip())
        if is_emulated and (not emulator_id or not rom_path):
            c.errorMessage.emit("Please set emulator and ROM path.")
            return

        compat_tool = (compat_tool or "").strip().lower()
        if compat_tool not in ("", "wine", "proton"):
            compat_tool = ""

        resolved_wine_prefix = canonicalize_path((wine_prefix or "").strip()) or None
        if IS_LINUX and not is_emulated and not resolved_wine_prefix:
            resolved_wine_prefix = canonicalize_path(self._default_linux_wine_prefix(name))

        game_data = {
            "name": name,
            "exe_paths": {
                "Windows": canonicalize_path(exe_windows),
                "Linux": canonicalize_path(exe_linux),
            },
            "install_location": canonicalize_path((install_location or "").strip()),
            "wine_prefix": resolved_wine_prefix,
            "wine_dll_overrides": (wine_dll_overrides or "").strip() or None,
            "windows_only": bool(windows_only),
            "installed": bool(installed),
            "genre": (genre or "").strip(),
            "platform": (platform or ("Windows" if IS_WINDOWS else "Linux")).strip(),
            "notes": notes or "",
            "serial": (serial or "").strip(),
            # Playtime is read-only in metadata flows; runtime trackers own this value.
            "playtime": 0,
            "compat_tool": compat_tool or None,
            "proton_path": canonicalize_path((proton_path or "").strip()) or None,
            "added_date": time.time(),
            "is_emulated": is_emulated,
            "links": c._normalize_links_json(links_json),
        }
        if is_emulated:
            game_data["emulator_id"] = emulator_id or None
            game_data["rom_path"] = rom_path or None
            game_data["ra_game_id"] = c._get_ra_id_by_rom_path(rom_path) if rom_path else None
        first_ts = self._parse_date_to_timestamp(first_played_date)
        last_ts = self._parse_date_to_timestamp(last_played_date)
        if first_ts:
            game_data["first_played"] = first_ts
        if last_ts:
            game_data["last_played"] = last_ts
        steam_app_id_from_link = c._extract_steam_app_id_from_links(game_data.get("links"))
        if steam_app_id_from_link:
            game_data["steam_app_id"] = steam_app_id_from_link

        platform_value = game_data.get("platform", "").strip()
        if platform_value:
            platforms = set(c._get_platforms_from_config())
            if platform_value not in platforms:
                platforms.add(platform_value)
                c._save_platforms_to_config(sorted(platforms, key=lambda v: v.lower()))

        process_name = name if is_emulated else (exe_windows if IS_WINDOWS else exe_linux)
        if process_name:
            game_data["process_name"] = Path(process_name).stem

        cover_path = (cover_path or "").strip()
        logo_path = (logo_path or "").strip()
        hero_path = (hero_path or "").strip()
        if cover_path:
            c._update_game_media(game_data, {}, cover_path, "cover", name, COVERS_DIR)
        if logo_path:
            c._update_game_media(game_data, {}, logo_path, "logo", name, LOGOS_DIR)
        if hero_path:
            c._update_game_media(game_data, {}, hero_path, "hero", name, HEROES_DIR)

        success, _, message = c._game_manager.add_game(game_data)
        if not success:
            c.errorMessage.emit(message)
            return
        if game_data.get("process_name") and (first_ts or last_ts):
            track = c._game_manager.tracking_data.get(game_data["process_name"], {})
            if first_ts:
                track["first_opened"] = first_ts
            if last_ts:
                track["last_session_end"] = last_ts
            c._game_manager.tracking_data[game_data["process_name"]] = track
            c._game_manager.save_tracking()
        c._game_model.refresh()
        c.libraryChanged.emit()

    def update_selected_full(
        self,
        name,
        genre,
        platform,
        playtime_minutes,
        notes,
        serial,
        exe_windows,
        exe_linux,
        install_location,
        wine_prefix,
        wine_dll_overrides,
        windows_only,
        installed,
        cover_path,
        logo_path,
        hero_path,
        compat_tool,
        proton_path,
        links_json,
        first_played_date,
        last_played_date,
    ):
        c = self._c
        if not c._selected_game_id:
            return
        old_data = c._game_manager.get_game(c._selected_game_id)
        if not old_data:
            c.errorMessage.emit("Game not found.")
            return

        new_name = (name or "").strip() or old_data.get("name", "")
        new_entry = old_data.copy()
        new_entry["name"] = new_name
        new_entry["genre"] = (genre or "").strip()
        new_entry["platform"] = (platform or "").strip()
        new_entry["notes"] = notes or ""
        new_entry["serial"] = (serial or "").strip()
        # Playtime is read-only in metadata flows; keep existing value.
        external_playtime = bool(old_data.get("is_emulated")) or (
            (old_data.get("source") or "").strip().lower() == "steam"
        )
        new_entry["playtime"] = int(old_data.get("playtime") or 0)
        new_entry["install_location"] = canonicalize_path((install_location or "").strip())
        resolved_wine_prefix = canonicalize_path((wine_prefix or "").strip()) or None
        if IS_LINUX and not old_data.get("is_emulated") and not resolved_wine_prefix:
            resolved_wine_prefix = canonicalize_path(self._default_linux_wine_prefix(new_name))
        new_entry["wine_prefix"] = resolved_wine_prefix
        new_entry["wine_dll_overrides"] = (wine_dll_overrides or "").strip() or None
        new_entry["windows_only"] = bool(windows_only)
        new_entry["installed"] = bool(installed)
        new_entry["links"] = c._normalize_links_json(links_json)
        steam_app_id_from_link = c._extract_steam_app_id_from_links(new_entry.get("links"))
        if steam_app_id_from_link:
            new_entry["steam_app_id"] = steam_app_id_from_link

        platform_value = new_entry.get("platform", "").strip()
        if platform_value:
            platforms = set(c._get_platforms_from_config())
            if platform_value not in platforms:
                platforms.add(platform_value)
                c._save_platforms_to_config(sorted(platforms, key=lambda v: v.lower()))

        compat_tool = (compat_tool or "").strip().lower()
        if compat_tool not in ("", "wine", "proton"):
            compat_tool = ""
        new_entry["compat_tool"] = compat_tool or None
        new_entry["proton_path"] = canonicalize_path((proton_path or "").strip()) or None
        first_ts = self._parse_date_to_timestamp(first_played_date)
        last_ts = self._parse_date_to_timestamp(last_played_date)
        if first_ts:
            new_entry["first_played"] = first_ts
        else:
            new_entry.pop("first_played", None)
        if last_ts:
            new_entry["last_played"] = last_ts
        else:
            new_entry.pop("last_played", None)

        if not bool(new_entry.get("is_emulated")):
            new_entry.pop("emulator_id", None)
            new_entry.pop("rom_path", None)
            new_entry.pop("ra_game_id", None)

        if not old_data.get("is_emulated"):
            new_entry["exe_paths"] = {
                "Windows": canonicalize_path((exe_windows or "").strip()),
                "Linux": canonicalize_path((exe_linux or "").strip()),
            }
            current_exe = new_entry["exe_paths"]["Windows"] if IS_WINDOWS else new_entry["exe_paths"]["Linux"]
            if current_exe:
                new_entry["process_name"] = Path(current_exe).stem
        else:
            new_entry.pop("exe_paths", None)

        process_name = new_entry.get("process_name")
        if process_name and (first_ts or last_ts):
            track = c._game_manager.tracking_data.get(process_name, {})
            if first_ts:
                track["first_opened"] = first_ts
            if last_ts:
                track["last_session_end"] = last_ts
            c._game_manager.tracking_data[process_name] = track
            c._game_manager.save_tracking()

        cover_path = (cover_path or "").strip()
        logo_path = (logo_path or "").strip()
        hero_path = (hero_path or "").strip()

        def _delete_old_media(rel_path, media_dir):
            try:
                old_rel = (rel_path or "").strip()
                if not old_rel:
                    return
                old_file = Path(fix_path_str(old_rel))
                if not old_file.is_absolute():
                    old_file = media_dir / old_file.name
                if old_file.exists():
                    old_file.unlink(missing_ok=True)
            except Exception:
                pass

        # Explicit clear from Media tab ("delete" button sets field to "").
        if cover_path == "":
            _delete_old_media(old_data.get("cover"), COVERS_DIR)
            new_entry["cover"] = ""
        elif cover_path and cover_path != old_data.get("cover"):
            c._update_game_media(new_entry, old_data, cover_path, "cover", new_name, COVERS_DIR)
        elif old_data.get("cover") and new_name != old_data.get("name"):
            c._rename_game_media(new_entry, old_data, "cover", new_name)

        if logo_path == "":
            _delete_old_media(old_data.get("logo"), LOGOS_DIR)
            new_entry["logo"] = ""
        elif logo_path and logo_path != old_data.get("logo"):
            c._update_game_media(new_entry, old_data, logo_path, "logo", new_name, LOGOS_DIR)
        elif old_data.get("logo") and new_name != old_data.get("name"):
            c._rename_game_media(new_entry, old_data, "logo", new_name)

        if hero_path == "":
            _delete_old_media(old_data.get("hero"), HEROES_DIR)
            new_entry["hero"] = ""
        elif hero_path and hero_path != old_data.get("hero"):
            c._update_game_media(new_entry, old_data, hero_path, "hero", new_name, HEROES_DIR)
        elif old_data.get("hero") and new_name != old_data.get("name"):
            c._rename_game_media(new_entry, old_data, "hero", new_name)

        success, new_game_id, message = c._game_manager.update_game(c._selected_game_id, new_entry)
        if not success:
            c.errorMessage.emit(message)
            return
        if new_game_id and new_game_id != c._selected_game_id:
            c._selected_game_id = new_game_id
        c._game_model.refresh()
        c.libraryChanged.emit()

    def update_selected_emulation(self, is_emulated, emulator_id, rom_path):
        c = self._c
        if not c._selected_game_id:
            return
        current = c._game_manager.get_game(c._selected_game_id)
        if not current:
            c.errorMessage.emit("Game not found.")
            return
        updated = current.copy()
        updated["is_emulated"] = bool(is_emulated)
        if updated["is_emulated"]:
            updated["emulator_id"] = (emulator_id or "").strip() or None
            updated["rom_path"] = canonicalize_path((rom_path or "").strip()) or None
            if updated.get("rom_path") and not updated.get("ra_game_id"):
                mapped = c._get_ra_id_by_rom_path(updated.get("rom_path"))
                if mapped:
                    updated["ra_game_id"] = mapped
            if not updated.get("process_name"):
                updated["process_name"] = c._selected_game_id
        else:
            updated.pop("emulator_id", None)
            updated.pop("rom_path", None)
            updated.pop("ra_game_id", None)

        candidates = [
            updated.get("name", ""),
            updated.get("process_name", ""),
            c._selected_game_id.replace("_", " "),
        ]
        if updated.get("rom_path"):
            candidates.append(Path(fix_path_str(updated["rom_path"])).stem.replace("_", " "))

        def _find_media(media_dir, media_type):
            for nm in candidates:
                if not nm:
                    continue
                base = nm.replace(" ", "_")
                matches = list(media_dir.glob(f"{base}_{media_type}.*"))
                if matches:
                    return matches[0].name
            return ""

        if not updated.get("cover"):
            updated["cover"] = _find_media(COVERS_DIR, "cover")
        if not updated.get("logo"):
            updated["logo"] = _find_media(LOGOS_DIR, "logo")
        if not updated.get("hero"):
            updated["hero"] = _find_media(HEROES_DIR, "hero")

        success, new_game_id, message = c._game_manager.update_game(c._selected_game_id, updated)
        if not success:
            c.errorMessage.emit(message)
            return
        if new_game_id and new_game_id != c._selected_game_id:
            c._selected_game_id = new_game_id
        c._game_model.refresh()
        c.libraryChanged.emit()

    def set_selected_hidden(self, hidden: bool):
        c = self._c
        if not c._selected_game_id:
            return
        current = c._game_manager.get_game(c._selected_game_id)
        if not current:
            c.errorMessage.emit("Game not found.")
            return
        updated = current.copy()
        updated["hidden"] = bool(hidden)
        success, new_game_id, message = c._game_manager.update_game(c._selected_game_id, updated)
        if not success:
            c.errorMessage.emit(message)
            return
        if new_game_id and new_game_id != c._selected_game_id:
            c._selected_game_id = new_game_id
        c._game_model.refresh()
        c.libraryChanged.emit()
