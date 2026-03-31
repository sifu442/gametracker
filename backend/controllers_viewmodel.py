"""
Selected-game view model helpers extracted from AppController.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QUrl

from core.constants import COVERS_DIR, HEROES_DIR, IS_LINUX, LOGOS_DIR, SCRIPT_DIR
from utils.helpers import fix_path_str

if TYPE_CHECKING:
    from backend.controllers import AppController


class ViewModelControllerOps:
    """Encapsulates selected-game property calculations for QML bindings."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def selected_game(self):
        c = self._c
        if not c._selected_game_id:
            return {}
        return c._game_manager.get_game(c._selected_game_id) or {}

    def selected_game_str(self, key: str) -> str:
        game = self.selected_game()
        return game.get(key, "") if game else ""

    def selected_game_bool(self, key: str, default=False) -> bool:
        game = self.selected_game()
        if not game:
            return bool(default)
        return bool(game.get(key, default))

    def _split_csv(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            items = value
        else:
            items = str(value).split(",")
        out = []
        seen = set()
        for item in items:
            name = str(item or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
        return out

    def collect_unique_list(self, field_name: str):
        data = self._c._game_manager.get_all_games() or {}
        items = {}
        for _, game in data.items():
            if not isinstance(game, dict):
                continue
            values = self._split_csv(game.get(field_name))
            for value in values:
                items[value.lower()] = value
        return sorted(items.values(), key=lambda v: v.lower())

    def selected_links_json(self) -> str:
        game = self.selected_game() or {}
        links = game.get("links", [])
        if isinstance(links, list):
            safe = []
            for item in links:
                if not isinstance(item, dict):
                    continue
                link_type = str(item.get("type", "")).strip()
                url = str(item.get("url", "")).strip()
                if not link_type and not url:
                    continue
                safe.append({"type": link_type, "url": url})
            return json.dumps(safe)
        return "[]"

    def selected_exe_for(self, platform_key: str) -> str:
        game = self.selected_game()
        exe_paths = game.get("exe_paths", {}) if game else {}
        if isinstance(exe_paths, str):
            return exe_paths
        return exe_paths.get(platform_key, "")

    def infer_installed(self, game) -> bool:
        if not isinstance(game, dict):
            return False
        if "installed" in game:
            return bool(game.get("installed"))
        if game.get("is_emulated"):
            return bool(game.get("rom_path"))
        if game.get("install_path") or game.get("install_location"):
            return True
        exe_paths = game.get("exe_paths")
        if isinstance(exe_paths, dict):
            return any(bool(p) for p in exe_paths.values())
        if isinstance(exe_paths, str):
            return bool(exe_paths)
        return False

    def platform_options(self):
        c = self._c
        platforms = c._get_platforms_from_config()
        if not platforms:
            values = set()
            for _, game in (c._game_manager.get_all_games() or {}).items():
                if not isinstance(game, dict):
                    continue
                value = (game.get("platform") or "").strip()
                if value:
                    values.add(value)
            platforms = sorted(values, key=lambda v: v.lower())
        return platforms

    def selected_playtime_minutes(self) -> int:
        c = self._c
        game = self.selected_game()
        if not game:
            return 0
        if game.get("is_emulated") and game.get("serial"):
            secs = c._game_manager.get_emulator_playtime_seconds(
                game.get("emulator_id"),
                game.get("serial"),
            )
            if secs:
                return int(secs / 60)
        if game.get("source") == "steam":
            return int(c._game_manager.get_steam_playtime_minutes(game.get("steam_app_id")))
        process_name = str(game.get("process_name") or "").strip()
        if process_name:
            tracked_seconds = int(c._game_manager.get_total_playtime(process_name) or 0)
            if tracked_seconds > 0:
                return int(tracked_seconds // 60)
        return int(game.get("playtime", 0))

    def selected_playtime_seconds(self) -> int:
        c = self._c
        game = self.selected_game()
        if game and game.get("is_emulated") and game.get("serial"):
            return int(
                c._game_manager.get_emulator_playtime_seconds(
                    game.get("emulator_id"),
                    game.get("serial"),
                )
            )
        if game and game.get("source") == "steam":
            minutes = c._game_manager.get_steam_playtime_minutes(game.get("steam_app_id"))
            return int(minutes * 60)
        process_name = self.selected_game_str("process_name")
        tracked = 0
        if process_name:
            tracked = int(c._game_manager.get_total_playtime(process_name) or 0)
        if tracked > 0:
            return tracked
        # Fallback to persisted library field (stored in minutes).
        try:
            return int(float(game.get("playtime") or 0) * 60)
        except Exception:
            return 0

    def selected_compat_tool(self) -> str:
        game = self.selected_game()
        if not game:
            return ""
        compat_tool = (game.get("compat_tool") or "").strip().lower()
        if compat_tool:
            return compat_tool
        proton_path = (game.get("proton_path") or "").strip()
        if not proton_path:
            return ""
        path_obj = Path(proton_path)
        if (path_obj / "proton").exists():
            return "proton"
        if (path_obj / "bin" / "wine").exists() or (path_obj / "wine").exists():
            return "wine"
        return "proton"

    def available_compat_options(self):
        if not IS_LINUX:
            return []
        options = [
            {"label": "Native (No Wine/Proton)", "tool": "", "path": ""},
            {"label": "Wine (System)", "tool": "wine", "path": ""},
        ]
        proton_paths = []
        home = Path.home()
        roots = [
            home / ".steam" / "steam" / "steamapps" / "common",
            home / ".local" / "share" / "Steam" / "steamapps" / "common",
            home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam" / "steamapps" / "common",
            Path("/usr/share/steam/compatibilitytools.d"),
            home / ".config" / "heroic" / "tools" / "proton",
        ]
        for root in roots:
            if not root.exists():
                continue
            try:
                for entry in root.iterdir():
                    if entry.is_dir() and (entry / "proton").exists():
                        proton_paths.append(str(entry))
            except Exception:
                continue

        heroic_wine_dir = home / ".config" / "heroic" / "tools" / "wine"
        wine_paths = []
        if heroic_wine_dir.exists():
            try:
                for entry in heroic_wine_dir.iterdir():
                    if entry.is_dir() and ((entry / "bin" / "wine").exists() or (entry / "wine").exists()):
                        wine_paths.append(str(entry))
            except Exception:
                pass
            if (heroic_wine_dir / "bin" / "wine").exists() or (heroic_wine_dir / "wine").exists():
                wine_paths.append(str(heroic_wine_dir))

        for path in sorted(set(wine_paths), key=lambda p: Path(p).name.lower()):
            options.append({"label": f"Wine ({Path(path).name})", "tool": "wine", "path": path})
        seen = set()
        for path in sorted(proton_paths, key=lambda p: Path(p).name.lower()):
            if path in seen:
                continue
            seen.add(path)
            options.append({"label": f"Proton ({Path(path).name})", "tool": "proton", "path": path})
        return options

    def selected_last_played_text(self) -> str:
        game = self.selected_game()
        if not game:
            return "Never"
        process_name = str(game.get("process_name") or "").strip()
        tracking = self._c._game_manager.tracking_data
        last_ts = 0.0
        if process_name:
            last_ts = tracking.get(process_name, {}).get("last_session_end") or 0
            if not last_ts:
                last_ts = tracking.get(process_name.lower(), {}).get("last_session_end") or 0
        try:
            last_ts = float(last_ts or 0)
        except Exception:
            last_ts = 0.0
        if last_ts <= 0:
            try:
                last_ts = float(game.get("last_played") or 0)
            except Exception:
                last_ts = 0.0
        if not last_ts:
            return "Never"
        try:
            last_dt = datetime.fromtimestamp(last_ts)
            delta = datetime.now() - last_dt
            seconds = max(0, int(delta.total_seconds()))
            if seconds < 60:
                return "Just now"
            if seconds < 3600:
                return f"{seconds // 60}m ago"
            if seconds < 86400:
                return f"{seconds // 3600}h ago"
            return f"{seconds // 86400}d ago"
        except Exception:
            return "Unknown"

    def _format_date_yyyy_mm_dd(self, ts_value) -> str:
        try:
            ts = float(ts_value or 0)
            if ts <= 0:
                return ""
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            return ""

    def selected_first_played_date(self) -> str:
        game = self.selected_game()
        if not game:
            return ""
        process_name = str(game.get("process_name") or "").strip()
        if process_name:
            first_ts = self._c._game_manager.tracking_data.get(process_name, {}).get("first_opened")
            if first_ts:
                return self._format_date_yyyy_mm_dd(first_ts)
        return self._format_date_yyyy_mm_dd(game.get("first_played"))

    def selected_last_played_date(self) -> str:
        game = self.selected_game()
        if not game:
            return ""
        process_name = str(game.get("process_name") or "").strip()
        if process_name:
            tracking = self._c._game_manager.tracking_data
            last_ts = tracking.get(process_name, {}).get("last_session_end") or 0
            if not last_ts:
                last_ts = tracking.get(process_name.lower(), {}).get("last_session_end") or 0
            try:
                last_ts = float(last_ts or 0)
            except Exception:
                last_ts = 0.0
            if last_ts > 0:
                return self._format_date_yyyy_mm_dd(last_ts)
        return self._format_date_yyyy_mm_dd(game.get("last_played"))

    def resolve_media_url(self, rel_path):
        if not rel_path:
            return ""
        media_path = self._resolve_media_path(rel_path)
        if not media_path:
            return ""
        return QUrl.fromLocalFile(str(media_path)).toString()

    def _is_valid_media_file(self, path: Path) -> bool:
        try:
            return path.exists() and path.is_file() and path.stat().st_size > 0
        except Exception:
            return False

    def _media_lookup_dirs(self):
        return (COVERS_DIR, LOGOS_DIR, HEROES_DIR)

    def _normalize_media_stem(self, name: str) -> str:
        stem = Path(name).stem
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
        stem = re.sub(r"_+", "_", stem).strip("_").lower()
        return stem

    def _find_media_by_name(self, filename: str):
        # 1) Exact basename match in known media dirs.
        for media_dir in self._media_lookup_dirs():
            candidate = media_dir / filename
            if self._is_valid_media_file(candidate):
                return candidate

        # 2) Fuzzy stem match (handles ':' and extension drift).
        wanted = self._normalize_media_stem(filename)
        if not wanted:
            return None
        image_ext = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".ico"}
        for media_dir in self._media_lookup_dirs():
            try:
                for entry in media_dir.iterdir():
                    if not entry.is_file():
                        continue
                    if entry.suffix.lower() not in image_ext:
                        continue
                    if entry.stat().st_size <= 0:
                        continue
                    stem = self._normalize_media_stem(entry.name)
                    if stem == wanted or stem.startswith(wanted) or wanted.startswith(stem):
                        return entry
            except Exception:
                continue
        return None

    def _resolve_media_path(self, rel_path):
        media_path = Path(fix_path_str(rel_path))
        if self._is_valid_media_file(media_path):
            return media_path

        # If absolute/relative path is broken, retry using basename lookup in media dirs.
        by_name = self._find_media_by_name(media_path.name)
        if by_name:
            return by_name

        if not media_path.is_absolute():
            candidate = SCRIPT_DIR / media_path
            if self._is_valid_media_file(candidate):
                return candidate
        return None
