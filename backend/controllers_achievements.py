"""
Achievements-related controller operations extracted from AppController.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import threading
import time
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from PyQt6.QtCore import QTimer
from PyQt6.QtCore import QUrl

from core.constants import IS_LINUX, IS_WINDOWS, SCRIPT_DIR
from steam.models import UnlockEvent
from utils.helpers import fix_path_str, load_json
from utils.retroachievements import get_unlocked_achievements

if TYPE_CHECKING:
    from backend.controllers import AppController


class AchievementsControllerOps:
    """Encapsulates achievement fetching/merge/progress logic for AppController."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def _normalize_icon_url(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        low = raw.lower()
        if low.startswith("http://") or low.startswith("https://") or low.startswith("file://"):
            return raw
        p = Path(fix_path_str(raw))
        if p.exists():
            try:
                return QUrl.fromLocalFile(str(p.resolve())).toString()
            except Exception:
                return raw
        if len(raw) > 2 and raw[1] == ":":
            try:
                return QUrl.fromLocalFile(str(Path(fix_path_str(raw)))).toString()
            except Exception:
                return raw
        return raw

    def _resolve_progress_provider(self, game: dict, serial: str, ra_game_id):
        """
        Resolve the achievements provider and identifier for the selected game.
        """
        source = (game.get("source") or "").strip().lower()
        is_steam = source == "steam"
        is_epic = source == "epic" or bool(game.get("legendary_app_name"))
        is_emulated = bool(game.get("is_emulated"))
        emu_name = str(game.get("emulator_id") or "").lower()
        steam_app_id = str(game.get("steam_app_id") or "").strip()

        is_rpcs3 = is_emulated and "rpcs3" in emu_name and bool(serial)
        is_shadps4 = is_emulated and "shadps4" in emu_name and bool(serial)

        if is_rpcs3:
            return "rpcs3", serial
        if is_shadps4:
            return "shadps4", serial
        if is_emulated and ra_game_id:
            return "ra", str(ra_game_id)
        # SteamEmu is for non-emulated, non-Steam-source titles with a Steam app id.
        if steam_app_id and not is_steam and not is_emulated:
            return "steamemu", steam_app_id
        if is_steam and steam_app_id:
            return "steam", steam_app_id
        if is_epic and game.get("legendary_app_name"):
            return "epic", str(game.get("legendary_app_name"))
        return "", ""

    def get_steam_achievements(self, app_id):
        c = self._c
        app_id = str(app_id or "").strip()
        if not app_id:
            return [], 0

        cached = c._steam_merged_by_appid.get(app_id)
        if isinstance(cached, dict):
            rows = cached.get("achievements") or []
            total = int(cached.get("total") or len(rows))
            unlocked_list = []
            for row in rows:
                if not isinstance(row, dict) or not bool(row.get("achieved")):
                    continue
                unlocked_list.append(
                    {
                        "id": str(row.get("name") or ""),
                        "title": row.get("display_name") or row.get("name") or "",
                        "description": row.get("description") or "",
                        "earned": c._format_unix_utc(row.get("unlock_time") or 0),
                        "points": 0,
                        "icon": self._normalize_icon_url(row.get("icon") or ""),
                    }
                )
            return unlocked_list, total

        api_key = (c._config.get("steam_web_api_key") or "").strip()
        if not api_key:
            return [], 0
        steam_id = c._get_steam_id64()
        if not steam_id:
            return [], 0

        schema_map = {}
        try:
            schema_resp = requests.get(
                "https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/",
                params={"key": api_key, "appid": app_id, "l": "english"},
                timeout=20,
            )
            schema_data = schema_resp.json() if schema_resp.ok else {}
            ach_defs = (
                (((schema_data or {}).get("game") or {}).get("availableGameStats") or {})
            ).get("achievements") or []
            if isinstance(ach_defs, list):
                for ach in ach_defs:
                    if not isinstance(ach, dict):
                        continue
                    api_name = (ach.get("name") or "").strip()
                    if api_name:
                        schema_map[api_name] = ach
        except Exception:
            schema_map = {}

        try:
            player_resp = requests.get(
                "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/",
                params={
                    "key": api_key,
                    "steamid": steam_id,
                    "appid": app_id,
                    "l": "english",
                },
                timeout=20,
            )
            player_data = player_resp.json() if player_resp.ok else {}
            playerstats = (player_data or {}).get("playerstats") or {}
            achievements = playerstats.get("achievements") or []
            if not isinstance(achievements, list):
                return [], 0
            total = len(achievements)
            unlocked_list = []
            for ach in achievements:
                if not isinstance(ach, dict):
                    continue
                if int(ach.get("achieved") or 0) != 1:
                    continue
                api_name = (ach.get("apiname") or "").strip()
                unlock_time = int(ach.get("unlocktime") or 0)
                meta = schema_map.get(api_name) or {}
                unlocked_list.append(
                    {
                        "id": api_name,
                        "title": meta.get("displayName") or api_name,
                        "description": meta.get("description") or "",
                        "earned": c._format_unix_utc(unlock_time),
                        "points": 0,
                        "icon": self._normalize_icon_url(meta.get("icon") or ""),
                    }
                )
            unlocked_list.sort(key=lambda x: x.get("earned") or "")
            return unlocked_list, total
        except Exception:
            return [], 0

    def get_steamemu_achievements(self, app_id):
        c = self._c
        app_id = str(app_id or "").strip()
        if not app_id:
            return [], 0

        cached = c._steam_merged_by_appid.get(app_id)
        if isinstance(cached, dict):
            rows = cached.get("achievements") or []
            total = int(cached.get("total") or len(rows))
            unlocked_list = []
            for row in rows:
                if not isinstance(row, dict) or not bool(row.get("achieved")):
                    continue
                unlock_ts = int(row.get("unlock_time") or 0)
                unlocked_list.append(
                    {
                        "id": str(row.get("name") or ""),
                        "title": row.get("display_name") or row.get("name") or "",
                        "description": row.get("description") or "",
                        "earned": c._format_unix_utc(unlock_ts),
                        "points": 0,
                        "icon": self._normalize_icon_url(row.get("icon") or ""),
                        "_unlock_ts": unlock_ts,
                    }
                )
            unlocked_list.sort(key=lambda x: int(x.get("_unlock_ts") or 0), reverse=True)
            for item in unlocked_list:
                item.pop("_unlock_ts", None)
            return unlocked_list, total

        state_payload = load_json(
            SCRIPT_DIR / "cache" / "user" / "emu" / f"{app_id}.json", {}
        )
        state_map = state_payload.get("state") if isinstance(state_payload, dict) else {}
        if not isinstance(state_map, dict):
            state_map = {}

        lang = (c._config.get("steam_lang") or "en").strip() or "en"
        schema_payload = load_json(
            SCRIPT_DIR / "cache" / "schema" / lang / f"{app_id}.json", {}
        )
        if not schema_payload:
            schema_payload = load_json(
                SCRIPT_DIR / "cache" / "schema" / "en" / f"{app_id}.json", {}
            )
        schema_rows = schema_payload.get("achievements") if isinstance(schema_payload, dict) else []
        if not isinstance(schema_rows, list):
            schema_rows = []

        meta_by_name = {}
        for row in schema_rows:
            if not isinstance(row, dict):
                continue
            ach_name = str(row.get("name") or "").strip()
            if not ach_name:
                continue
            meta_by_name[ach_name] = row

        total = len(meta_by_name) if meta_by_name else len(state_map)
        unlocked_list = []
        for ach_name, state in state_map.items():
            if not isinstance(state, dict) or not bool(state.get("achieved")):
                continue
            unlock_ts = int(state.get("unlock_time") or 0)
            meta = meta_by_name.get(str(ach_name), {})
            unlocked_list.append(
                {
                    "id": str(ach_name),
                    "title": meta.get("display_name") or meta.get("name") or str(ach_name),
                    "description": meta.get("description") or "",
                    "earned": c._format_unix_utc(unlock_ts),
                    "points": 0,
                    "icon": self._normalize_icon_url(meta.get("icon") or ""),
                    "_unlock_ts": unlock_ts,
                }
            )
        unlocked_list.sort(key=lambda x: int(x.get("_unlock_ts") or 0), reverse=True)
        for item in unlocked_list:
            item.pop("_unlock_ts", None)

        if not state_map:
            now = time.time()
            if (
                (now - float(c._steamemu_cache_refresh_requested_at or 0.0)) > 10.0
                and not c._steamemu_manual_refresh_running
            ):
                c._steamemu_cache_refresh_requested_at = now
                try:
                    c.refresh_steamemu_achievements()
                except Exception:
                    pass

        return unlocked_list, total

    def extract_epic_achievements_from_payload(self, payload):
        c = self._c
        if not isinstance(payload, dict):
            return [], 0
        candidates = [
            payload.get("achievements"),
            payload.get("player_achievements"),
            payload.get("items"),
        ]
        data_obj = payload.get("data")
        if isinstance(data_obj, dict):
            candidates.append(data_obj.get("achievements"))
            candidates.append(data_obj.get("items"))

        items = None
        for cand in candidates:
            if isinstance(cand, list):
                items = cand
                break
        if not isinstance(items, list):
            return [], 0

        unlocked_list = []
        total = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            total += 1
            progress = item.get("progress")
            unlocked = (
                bool(item.get("unlocked"))
                or bool(item.get("achieved"))
                or bool(item.get("isUnlocked"))
                or bool(item.get("unlockTime"))
            )
            if not unlocked:
                try:
                    unlocked = float(progress or 0) >= 100.0
                except Exception:
                    unlocked = False
            if not unlocked:
                continue
            unlock_time = item.get("unlockTime") or item.get("unlockedAt") or item.get("dateUnlocked")
            earned = str(unlock_time or "")
            if isinstance(unlock_time, (int, float)):
                earned = c._format_unix_utc(unlock_time)
            unlocked_list.append(
                {
                    "id": str(item.get("id") or item.get("name") or ""),
                    "title": item.get("displayName")
                    or item.get("title")
                    or item.get("name")
                    or "Achievement",
                    "description": item.get("description") or "",
                    "earned": earned,
                    "points": int(item.get("xp") or item.get("points") or 0),
                    "icon": self._normalize_icon_url(
                        item.get("icon")
                        or item.get("iconUrl")
                        or item.get("unlockedIcon")
                        or ""
                    ),
                }
            )
        unlocked_list.sort(key=lambda x: x.get("earned") or "")
        return unlocked_list, total

    def get_epic_achievements(self, app_name):
        c = self._c
        app_name = (app_name or "").strip()
        if not app_name:
            return [], 0

        launch_cmd = c._game_manager.get_legendary_launch_command(app_name)
        if not launch_cmd:
            return [], 0
        legendary_cmd = launch_cmd[0]

        env = os.environ.copy()
        cfg_dir = c._game_manager.get_heroic_legendary_config_dir()
        if cfg_dir:
            env["LEGENDARY_CONFIG_PATH"] = str(cfg_dir)
            env["LEGENDARY_CONFIG_DIR"] = str(cfg_dir)

        command_variants = [
            [legendary_cmd, "list-achievements", app_name, "--json"],
            [legendary_cmd, "achievements", app_name, "--json"],
            [legendary_cmd, "status", app_name, "--json"],
        ]
        for cmd in command_variants:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                )
                if proc.returncode != 0:
                    continue
                payload = json.loads(proc.stdout or "{}")
                unlocked_list, total = self.extract_epic_achievements_from_payload(payload)
                if total > 0:
                    return unlocked_list, total
            except Exception:
                continue
        return [], 0

    def get_rpcs3_achievements(self, emulator_id, serial):
        c = self._c
        emulator_id = (emulator_id or "").strip()
        serial = (serial or "").strip().upper()
        if not emulator_id or not serial:
            return [], 0

        emulator = c._game_manager.get_emulator(emulator_id) or {}
        exe_path = ""
        if IS_WINDOWS and emulator.get("exe_path_windows"):
            exe_path = emulator.get("exe_path_windows")
        if IS_LINUX and emulator.get("exe_path_linux"):
            exe_path = emulator.get("exe_path_linux")
        if not exe_path:
            exe_paths = emulator.get("exe_paths")
            if isinstance(exe_paths, dict):
                launch_type = ((emulator.get("launch_type") or "executable").strip().lower())
                if IS_WINDOWS:
                    launch_type = ((emulator.get("launch_type_windows") or launch_type).strip().lower())
                if IS_LINUX:
                    launch_type = ((emulator.get("launch_type_linux") or launch_type).strip().lower())
                if launch_type == "exe":
                    launch_type = "executable"
                exe_path = exe_paths.get(launch_type) or ""
                if not exe_path:
                    for _, val in exe_paths.items():
                        if val:
                            exe_path = val
                            break
        if not exe_path:
            exe_path = emulator.get("exe_path") or ""
        if not exe_path:
            return [], 0

        exe_file = Path(fix_path_str(exe_path))
        if not exe_file.is_absolute():
            exe_file = SCRIPT_DIR / exe_file
        base_dir = exe_file.parent
        db_candidates = [
            base_dir / "dev_hdd0" / "home" / "00000001" / "trophy" / "db" / "trophy.db",
            base_dir / "dev_hdd0" / "home" / "00000001" / "trophy" / "trophy.db",
            Path(os.environ.get("APPDATA", "")) / "RPCS3" / "dev_hdd0" / "home" / "00000001" / "trophy" / "db" / "trophy.db",
            Path(os.environ.get("APPDATA", "")) / "RPCS3" / "dev_hdd0" / "home" / "00000001" / "trophy" / "trophy.db",
            Path.home() / ".config" / "rpcs3" / "dev_hdd0" / "home" / "00000001" / "trophy" / "db" / "trophy.db",
            Path.home() / ".config" / "rpcs3" / "dev_hdd0" / "home" / "00000001" / "trophy" / "trophy.db",
        ]
        db_path = None
        for candidate in db_candidates:
            if candidate.exists():
                db_path = candidate
                break

        def _normalize_unlocked(val):
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return val > 0
            s = str(val or "").strip().lower()
            if s in ("1", "true", "yes", "y", "unlocked", "earned"):
                return True
            try:
                return float(s) > 0
            except Exception:
                return False

        def _to_earned_str(val):
            if val is None:
                return ""
            if isinstance(val, (int, float)):
                return c._format_unix_utc(val)
            s = str(val).strip()
            if not s:
                return ""
            if s.isdigit():
                return c._format_unix_utc(int(s))
            return s

        if db_path:
            best_unlocked = []
            best_total = 0
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                tables = [
                    r["name"]
                    for r in cur.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                ]

                for table in tables:
                    try:
                        cols = [
                            r["name"]
                            for r in cur.execute(f'PRAGMA table_info("{table}")').fetchall()
                        ]
                    except Exception:
                        continue
                    if not cols:
                        continue
                    lower_cols = {cc.lower(): cc for cc in cols}
                    title_cols = [
                        lower_cols[k]
                        for k in ("title_id", "titleid", "serial", "game_id", "npwr")
                        if k in lower_cols
                    ]
                    unlocked_col = next(
                        (
                            lower_cols[k]
                            for k in (
                                "unlocked",
                                "earned",
                                "is_unlocked",
                                "unlock_state",
                                "unlock_time",
                                "timestamp",
                            )
                            if k in lower_cols
                        ),
                        None,
                    )
                    name_col = next(
                        (lower_cols[k] for k in ("name", "title", "trophy_name") if k in lower_cols),
                        None,
                    )
                    desc_col = next(
                        (
                            lower_cols[k]
                            for k in ("description", "desc", "detail", "trophy_description")
                            if k in lower_cols
                        ),
                        None,
                    )
                    points_col = next(
                        (lower_cols[k] for k in ("points", "xp", "value") if k in lower_cols),
                        None,
                    )
                    time_col = next(
                        (
                            lower_cols[k]
                            for k in ("unlock_time", "timestamp", "earned_at", "time_unlocked")
                            if k in lower_cols
                        ),
                        None,
                    )
                    id_col = next(
                        (lower_cols[k] for k in ("id", "trophy_id", "achievement_id") if k in lower_cols),
                        None,
                    )
                    if not (name_col or unlocked_col):
                        continue

                    rows = cur.execute(f'SELECT * FROM "{table}"').fetchall()
                    if not rows:
                        continue

                    filtered = []
                    for row in rows:
                        matches_serial = False
                        for tc in title_cols:
                            v = str(row[tc] or "").upper()
                            if serial in v:
                                matches_serial = True
                                break
                        if title_cols and not matches_serial:
                            continue
                        filtered.append(row)
                    if not filtered:
                        continue

                    total = len(filtered)
                    unlocked_list = []
                    for row in filtered:
                        unlocked_val = row[unlocked_col] if unlocked_col else 0
                        if not _normalize_unlocked(unlocked_val):
                            continue
                        trophy_id = str(row[id_col]) if id_col and row[id_col] is not None else ""
                        title = str(row[name_col] or "Trophy") if name_col else "Trophy"
                        desc = str(row[desc_col] or "") if desc_col else ""
                        points = 0
                        if points_col:
                            try:
                                points = int(row[points_col] or 0)
                            except Exception:
                                points = 0
                        earned_raw = row[time_col] if time_col else unlocked_val
                        unlocked_list.append(
                            {
                                "id": trophy_id,
                                "title": title,
                                "description": desc,
                                "earned": _to_earned_str(earned_raw),
                                "points": points,
                                "icon": "",
                            }
                        )
                    if total > best_total:
                        best_total = total
                        best_unlocked = unlocked_list

                conn.close()
                if best_total > 0:
                    return best_unlocked, best_total
            except Exception:
                pass

        trophy_root_candidates = [
            base_dir / "dev_hdd0" / "home" / "00000001" / "trophy",
            Path(os.environ.get("APPDATA", "")) / "RPCS3" / "dev_hdd0" / "home" / "00000001" / "trophy",
            Path.home() / ".config" / "rpcs3" / "dev_hdd0" / "home" / "00000001" / "trophy",
        ]
        trophy_root = next((p for p in trophy_root_candidates if p.exists()), None)
        if not trophy_root:
            return [], 0

        game = c._game_manager.get_game(c._selected_game_id) or {}
        rom_path = Path(fix_path_str(game.get("rom_path") or ""))
        npwr_id = ""
        try:
            for parent in [rom_path] + list(rom_path.parents):
                tropdir = parent / "PS3_GAME" / "TROPDIR"
                if tropdir.exists():
                    subdirs = [d for d in tropdir.iterdir() if d.is_dir() and d.name.upper().startswith("NPWR")]
                    if subdirs:
                        npwr_id = subdirs[0].name.upper()
                        break
        except Exception:
            npwr_id = ""

        trophy_dir = None
        if npwr_id:
            candidate = trophy_root / npwr_id
            if candidate.exists():
                trophy_dir = candidate
        if not trophy_dir:
            serial_token = serial.replace("-", "").replace("_", "")
            for d in trophy_root.iterdir():
                if not d.is_dir():
                    continue
                conf = d / "TROPCONF.SFM"
                if not conf.exists():
                    continue
                txt = conf.read_text(encoding="utf-8", errors="ignore").upper()
                if serial_token and serial_token in txt.replace("-", "").replace("_", ""):
                    trophy_dir = d
                    break
        if not trophy_dir:
            return [], 0

        conf_path = trophy_dir / "TROPCONF.SFM"
        usr_path = trophy_dir / "TROPUSR.DAT"
        if not conf_path.exists():
            return [], 0

        try:
            root = ET.fromstring(conf_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return [], 0

        trophies = []
        for t in root.findall(".//trophy"):
            tid = (t.attrib.get("id") or "").strip()
            name = (t.findtext("name") or "Trophy").strip()
            detail = (t.findtext("detail") or "").strip()
            icon = trophy_dir / f"TROP{tid.zfill(3)}.PNG"
            trophies.append(
                {
                    "id": tid,
                    "title": name,
                    "description": detail,
                    "earned": "",
                    "points": 0,
                    "icon": QUrl.fromLocalFile(str(icon)).toString() if icon.exists() else "",
                }
            )
        total = len(trophies)
        if total == 0:
            return [], 0

        unlocked_ids = set()
        if usr_path.exists():
            try:
                b = usr_path.read_bytes()
                hits = []
                for o in range(0, len(b) - 8, 4):
                    if int.from_bytes(b[o : o + 4], "big") == 6 and int.from_bytes(
                        b[o + 4 : o + 8], "big"
                    ) == 96:
                        hits.append(o)

                if len(hits) >= 2:
                    entry_base = hits[1]
                    stride = 0x70
                    for i in range(total):
                        o = entry_base + i * stride
                        if o + 24 > len(b):
                            break
                        trophy_index = int.from_bytes(b[o + 8 : o + 12], "big")
                        unlocked_flag = int.from_bytes(b[o + 20 : o + 24], "big")
                        if unlocked_flag > 0:
                            unlocked_ids.add(str(trophy_index).zfill(3))
                else:
                    base = 0xD0
                    stride = 0x60
                    for i in range(total):
                        o = base + i * stride
                        if o + 0x20 > len(b):
                            break
                        state = b[o + 0x18 : o + 0x60]
                        if any(v != 0 for v in state):
                            unlocked_ids.add(str(i).zfill(3))
            except Exception:
                pass

        unlocked_list = [t for t in trophies if t["id"].zfill(3) in unlocked_ids]
        return unlocked_list, total

    def get_shadps4_achievements(self, emulator_id, game_id, rom_path=""):
        c = self._c
        emulator_id = (emulator_id or "").strip()
        game_id = (game_id or "").strip().upper()
        game_id_norm = re.sub(r"[^A-Z0-9]", "", game_id)
        if not emulator_id:
            return [], 0

        emulator = c._game_manager.get_emulator(emulator_id) or {}
        exe_path = ""
        if IS_WINDOWS and emulator.get("exe_path_windows"):
            exe_path = emulator.get("exe_path_windows")
        if IS_LINUX and emulator.get("exe_path_linux"):
            exe_path = emulator.get("exe_path_linux")
        if not exe_path:
            exe_paths = emulator.get("exe_paths")
            if isinstance(exe_paths, dict):
                launch_type = ((emulator.get("launch_type") or "executable").strip().lower())
                if IS_WINDOWS:
                    launch_type = ((emulator.get("launch_type_windows") or launch_type).strip().lower())
                if IS_LINUX:
                    launch_type = ((emulator.get("launch_type_linux") or launch_type).strip().lower())
                if launch_type == "exe":
                    launch_type = "executable"
                exe_path = exe_paths.get(launch_type) or ""
                if not exe_path:
                    for _, val in exe_paths.items():
                        if val:
                            exe_path = val
                            break
        if not exe_path:
            exe_path = emulator.get("exe_path") or ""
        if not exe_path:
            return [], 0

        exe_file = Path(fix_path_str(exe_path))
        if not exe_file.is_absolute():
            exe_file = SCRIPT_DIR / exe_file
        base_dir = exe_file.parent

        # Infer game id if missing (e.g. CUSAxxxxx) from rom path.
        if not game_id:
            rp = str(rom_path or "")
            m = re.search(r"([A-Z]{4}\d{5})", rp.upper())
            if m:
                game_id = m.group(1)
                game_id_norm = re.sub(r"[^A-Z0-9]", "", game_id)

        roots = []
        # shadPS4 portable builds often keep `user/game_data` at a parent of the exe dir.
        for parent in [base_dir] + list(base_dir.parents)[:5]:
            roots.append(parent / "user" / "game_data")
        roots.extend(
            [
                Path(os.environ.get("APPDATA", "")) / "shadPS4" / "user" / "game_data",
                Path.home() / ".config" / "shadPS4" / "user" / "game_data",
                Path.home() / ".config" / "shadps4" / "user" / "game_data",
            ]
        )

        trophy_dir = None
        for root in roots:
            if not root.exists():
                continue
            if game_id:
                candidate = root / game_id / "TrophyFiles"
                if candidate.exists():
                    trophy_dir = candidate
                    break
                if game_id_norm and game_id_norm != game_id:
                    candidate2 = root / game_id_norm / "TrophyFiles"
                    if candidate2.exists():
                        trophy_dir = candidate2
                        break
            try:
                for gd in root.iterdir():
                    if not gd.is_dir():
                        continue
                    tf = gd / "TrophyFiles"
                    if not tf.exists():
                        continue
                    if game_id:
                        gd_norm = re.sub(r"[^A-Z0-9]", "", gd.name.upper())
                        if game_id in gd.name.upper() or (
                            game_id_norm and game_id_norm in gd_norm
                        ):
                            trophy_dir = tf
                            break
                    else:
                        trophy_dir = tf
                        break
                if trophy_dir:
                    break
            except Exception:
                continue

        if not trophy_dir:
            return [], 0

        # Read trophy metadata from common candidates.
        conf_paths = []
        for pat in ("**/TROPCONF.SFM", "**/tropconf.sfm", "**/TROP.SFM", "**/trop.sfm", "**/*.xml"):
            conf_paths.extend(trophy_dir.glob(pat))
        # deterministic order: trophy00, trophy01, ...
        conf_paths = sorted(
            list({p.resolve(): p for p in conf_paths}.values()),
            key=lambda p: str(p).lower(),
        )
        if not conf_paths:
            return [], 0

        def _format_ps4_timestamp(raw_ts: str) -> str:
            """
            Convert shadPS4 trophy timestamp to UI string.
            Falls back to empty string if format is unknown.
            """
            try:
                s = str(raw_ts or "").strip()
                if not s or s == "0":
                    return ""
                v = int(s)
                # AW/SuccessStory-compatible conversion:
                # PS4 epoch is 2008-01-01 UTC and values are in microseconds.
                base = datetime(2008, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
                dt = base + timedelta(milliseconds=(v // 1000))
                # Some dumps appear offset by +2007 years.
                if dt.year > 2100:
                    try:
                        dt = dt.replace(year=dt.year - 2007)
                    except Exception:
                        pass
                return dt.astimezone().strftime("%Y-%m-%d %H:%M")
            except Exception:
                return ""

        def _parse_unlocked_ids(usr_path: Path, total_hint: int):
            unlocked = set()
            try:
                b = usr_path.read_bytes()
                hits = []
                for o in range(0, len(b) - 8, 4):
                    if int.from_bytes(b[o : o + 4], "big") == 6 and int.from_bytes(
                        b[o + 4 : o + 8], "big"
                    ) == 96:
                        hits.append(o)
                if len(hits) >= 2:
                    entry_base = hits[1]
                    stride = 0x70
                    for i in range(total_hint):
                        o = entry_base + i * stride
                        if o + 24 > len(b):
                            break
                        trophy_index = int.from_bytes(b[o + 8 : o + 12], "big")
                        unlocked_flag = int.from_bytes(b[o + 20 : o + 24], "big")
                        if unlocked_flag > 0:
                            unlocked.add(str(trophy_index).zfill(3))
                else:
                    base = 0xD0
                    stride = 0x60
                    for i in range(total_hint):
                        o = base + i * stride
                        if o + 0x20 > len(b):
                            break
                        state = b[o + 0x18 : o + 0x60]
                        if any(v != 0 for v in state):
                            unlocked.add(str(i).zfill(3))
            except Exception:
                pass
            return unlocked

        trophies = []
        unlocked_ids_global = set()
        seen_ids = set()
        for conf_path in conf_paths:
            try:
                root = ET.fromstring(conf_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            conf_dir = conf_path.parent
            local_trophies = []
            xml_unlocked_ids = set()
            for t in [x for x in root.iter() if x.tag.lower().endswith("trophy")]:
                tid = (t.attrib.get("id") or "").strip()
                if not tid:
                    continue
                ztid = tid.zfill(3)
                if ztid in seen_ids:
                    continue
                seen_ids.add(ztid)
                name = "Trophy"
                detail = ""
                for child in list(t):
                    tag = child.tag.lower()
                    if tag.endswith("name") and (child.text or "").strip():
                        name = (child.text or "").strip()
                    if tag.endswith("detail") and (child.text or "").strip():
                        detail = (child.text or "").strip()
                unlock_state_attr = str(t.attrib.get("unlockstate") or "").strip().lower()
                timestamp_attr = str(t.attrib.get("timestamp") or "").strip()
                unlocked_from_xml = (
                    unlock_state_attr in {"1", "true", "yes", "unlocked", "earned"}
                    or (timestamp_attr not in {"", "0"})
                )
                if unlocked_from_xml:
                    xml_unlocked_ids.add(ztid)
                icon_candidates = [
                    conf_dir / f"TROP{ztid}.PNG",
                    conf_dir / f"TROP{ztid}.png",
                    conf_dir.parent / "Icons" / f"TROP{ztid}.PNG",
                    conf_dir.parent / "Icons" / f"TROP{ztid}.png",
                    conf_dir.parent / f"TROP{ztid}.PNG",
                    conf_dir.parent / f"TROP{ztid}.png",
                ]
                icon = next((p for p in icon_candidates if p.exists()), conf_dir / f"TROP{ztid}.PNG")
                if not icon.exists():
                    # Search both Xml subtree and its sibling folders (not only Xml).
                    hits = list(conf_dir.parent.rglob(f"TROP{ztid}.*"))
                    if hits:
                        icon = hits[0]
                local_trophies.append(
                    {
                        "id": tid,
                        "title": name,
                        "description": detail,
                        "earned": _format_ps4_timestamp(timestamp_attr) if unlocked_from_xml else "",
                        "points": 0,
                        "icon": QUrl.fromLocalFile(str(icon)).toString() if icon.exists() else "",
                    }
                )
            if not local_trophies:
                continue
            trophies.extend(local_trophies)
            unlocked_ids_global.update(xml_unlocked_ids)

            usr_candidates = [
                conf_dir / "TROPUSR.DAT",
                conf_dir / "tropusr.dat",
                conf_dir.parent / "TROPUSR.DAT",
                conf_dir.parent / "tropusr.dat",
            ]
            usr_path = next((p for p in usr_candidates if p.exists()), None)
            if usr_path:
                unlocked_ids_global.update(_parse_unlocked_ids(usr_path, len(local_trophies)))

        total = len(trophies)
        if total == 0:
            return [], 0
        unlocked_list = [t for t in trophies if t["id"].zfill(3) in unlocked_ids_global]
        return unlocked_list, total

    def kick_ra_progress_update(self):
        c = self._c
        game = c._game_manager.get_game(c._selected_game_id) if c._selected_game_id else None
        if not game:
            c._set_ra_progress(0, 0, None, [])
            return

        is_ra = bool(game.get("is_emulated"))
        serial = (game.get("serial") or "").strip().upper()
        emu_name = str(game.get("emulator_id") or "").lower()
        if not serial and is_ra and ("rpcs3" in emu_name or "shadps4" in emu_name):
            rom_path = str(game.get("rom_path") or "")
            m = re.search(r"([A-Z]{4}[-_]?\d{5})", rom_path.upper())
            if m:
                serial = m.group(1).replace("_", "-")
                updated = game.copy()
                updated["serial"] = serial
                c._game_manager.update_game(c._selected_game_id, updated)
                c._game_model.refresh()
                c.libraryChanged.emit()
        ra_game_id = game.get("ra_game_id") if is_ra else None

        if is_ra and not ra_game_id:
            mapped = c._get_ra_id_by_game_id(c._selected_game_id)
            if not mapped and game.get("rom_path"):
                mapped = c._get_ra_id_by_rom_path(game.get("rom_path"))
            if mapped:
                ra_game_id = mapped
                updated = game.copy()
                updated["ra_game_id"] = mapped
                c._game_manager.update_game(c._selected_game_id, updated)
                c._game_model.refresh()
                c.libraryChanged.emit()

        provider, provider_id = self._resolve_progress_provider(game, serial, ra_game_id)

        if not provider_id:
            c._set_ra_progress(0, 0, None, [])
            return

        cache_key = f"{provider}:{provider_id}"
        cached = c._ra_progress_cache.get(cache_key)
        if not cached and provider == "ra":
            cached = c._ra_progress_cache.get(provider_id)
        # shadPS4 parser behavior changed; avoid serving stale cached full trophy lists.
        if provider == "shadps4":
            c._ra_progress_cache.pop(cache_key, None)
            cached = None
        if cached:
            c._set_ra_progress(
                cached.get("unlocked", 0),
                cached.get("total", 0),
                cache_key,
                cached.get("unlocked_list", []),
            )
            if time.time() - cached.get("ts", 0) < 300:
                return

        def worker():
            unlocked_list = []
            total = 0
            unlocked_count = 0
            try:
                if provider == "ra":
                    username = (c._config.get("ra_username") or "").strip()
                    api_key = (c._config.get("ra_api_key") or "").strip()
                    if username and api_key:
                        unlocked_list, total = get_unlocked_achievements(username, api_key, provider_id)
                        unlocked_count = len(unlocked_list)
                elif provider == "rpcs3":
                    unlocked_list, total = self.get_rpcs3_achievements(
                        game.get("emulator_id"),
                        provider_id,
                    )
                    unlocked_count = len(unlocked_list)
                elif provider == "shadps4":
                    unlocked_list, total = self.get_shadps4_achievements(
                        game.get("emulator_id"),
                        provider_id,
                        game.get("rom_path"),
                    )
                    unlocked_count = len(unlocked_list)
                elif provider == "steamemu":
                    unlocked_list, total = self.get_steamemu_achievements(provider_id)
                    unlocked_count = len(unlocked_list)
                elif provider == "steam":
                    unlocked_list, total = self.get_steam_achievements(provider_id)
                    unlocked_count = len(unlocked_list)
                elif provider == "epic":
                    unlocked_list, total = self.get_epic_achievements(provider_id)
                    unlocked_count = len(unlocked_list)
            except Exception:
                unlocked_list, total = [], 0
                unlocked_count = 0
            c.raProgressLoaded.emit(unlocked_count, total, cache_key, unlocked_list)

        threading.Thread(target=worker, daemon=True).start()

    def on_ra_progress_loaded(self, unlocked, total, game_id, unlocked_list):
        c = self._c
        cache_key = str(game_id)
        c._ra_progress_cache[cache_key] = {
            "unlocked": int(unlocked or 0),
            "total": int(total or 0),
            "unlocked_list": unlocked_list or [],
            "ts": time.time(),
        }
        c._save_ra_progress_cache_to_config()
        c._set_ra_progress(unlocked, total, game_id, unlocked_list or [])

    def set_ra_progress(self, unlocked, total, game_id, unlocked_list=None):
        c = self._c
        c._ra_unlocked = int(unlocked or 0)
        c._ra_total = int(total or 0)
        c._ra_progress_game_id = game_id
        if unlocked_list is not None:
            normalized_list = []
            for item in (unlocked_list or []):
                if isinstance(item, dict):
                    row = dict(item)
                    row["icon"] = self._normalize_icon_url(row.get("icon") or "")
                    normalized_list.append(row)
                else:
                    normalized_list.append(item)
            try:
                c._ra_unlocked_list = sorted(
                    normalized_list,
                    key=c._achievement_sort_key_desc,
                    reverse=True,
                )
            except Exception:
                c._ra_unlocked_list = normalized_list
        c.raProgressChanged.emit()

    def on_steam_worker_game_loaded(self, payload):
        c = self._c
        try:
            try:
                from utils.helpers import debug_log
                debug_log(f"[steam] on_steam_worker_game_loaded payload_type={type(payload).__name__}")
            except Exception:
                pass
            appid = str((payload or {}).get("appid") or "")
            if appid:
                c._steam_merged_by_appid[appid] = payload
            try:
                c.steamGameLoaded.emit(json.dumps(payload))
            except Exception:
                c.steamGameLoaded.emit("{}")
        except Exception:
            pass

    def on_steam_worker_unlock_event(self, payload):
        c = self._c
        try:
            from utils.helpers import debug_log
            debug_log(f"[steam] on_steam_worker_unlock_event payload_type={type(payload).__name__}")
        except Exception:
            pass
        try:
            c.steamUnlockEvent.emit(json.dumps(payload))
        except Exception:
            c.steamUnlockEvent.emit("{}")
        try:
            if c._steam_popup_manager and payload:
                event = UnlockEvent(
                    appid=str(payload.get("appid") or ""),
                    game=str(payload.get("game") or ""),
                    achievement=str(payload.get("achievement") or ""),
                    description=str(payload.get("description") or ""),
                    unlock_time=int(payload.get("unlock_time") or 0),
                    icon_path=str(payload.get("icon_path") or ""),
                )
                c._steam_popup_manager.enqueue(event)
        except Exception:
            pass

    def on_steamemu_worker_game_loaded(self, payload):
        c = self._c
        try:
            try:
                from utils.helpers import debug_log
                debug_log(f"[steamemu] on_steamemu_worker_game_loaded payload_type={type(payload).__name__}")
            except Exception:
                pass
            appid = str((payload or {}).get("appid") or "")
            if appid:
                c._steam_merged_by_appid[appid] = payload
            try:
                c.steamEmuGameLoaded.emit(json.dumps(payload))
            except Exception:
                c.steamEmuGameLoaded.emit("{}")
        except Exception:
            pass

    def on_steamemu_worker_unlock_event(self, payload):
        c = self._c
        try:
            from utils.helpers import debug_log
            debug_log(f"[steamemu] on_steamemu_worker_unlock_event payload_type={type(payload).__name__}")
        except Exception:
            pass
        try:
            c.steamEmuUnlockEvent.emit(json.dumps(payload))
        except Exception:
            c.steamEmuUnlockEvent.emit("{}")
        self.on_steam_worker_unlock_event(payload)

    def emit_test_notification(self):
        c = self._c
        if not c._steam_popup_manager:
            return "Popup manager is not initialized."
        event = UnlockEvent(
            appid="2717880",
            game="Test Game",
            achievement="Test Achievement",
            description="Notification pipeline check.",
            unlock_time=int(time.time()),
            icon_path=str(SCRIPT_DIR / "ui" / "assets" / "placeholder_achievement.png"),
        )
        QTimer.singleShot(20000, lambda ev=event: c._steam_popup_manager.enqueue(ev))
        return "Test notification will appear in 20 seconds."
