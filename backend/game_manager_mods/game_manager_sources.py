import os
import time
from pathlib import Path

from core.constants import IS_WINDOWS, IS_LINUX
from utils.helpers import fix_path_str, canonicalize_path


def _get_heroic_installed_path(self):
    """Locate Heroic Legendary installed.json across platforms."""
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "heroic" / "legendaryConfig" / "legendary" / "installed.json")
    candidates.append(Path.home() / ".config" / "heroic" / "legendaryConfig" / "legendary" / "installed.json")
    for path in candidates:
        if path.exists():
            return path
    return None


def get_heroic_legendary_config_dir(self):
    """Locate Heroic's bundled Legendary config directory."""
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "heroic" / "legendaryConfig" / "legendary")
    candidates.append(Path.home() / ".config" / "heroic" / "legendaryConfig" / "legendary")
    for path in candidates:
        if path.exists():
            return path
    return None


def _parse_heroic_installed(self, data):
    """Normalize Heroic Legendary installed.json into a list of entries."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "installed" in data and isinstance(data["installed"], (list, dict)):
            data = data["installed"]
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            entries = []
            for key, value in data.items():
                if isinstance(value, dict):
                    value = dict(value)
                    value.setdefault("app_name", key)
                    entries.append(value)
            return entries
    return []


def scan_heroic_legendary(self):
    """
    Scan Heroic Legendary installed.json and add/update Epic games.

    Returns:
        tuple: (added_count, updated_count, skipped_count)
    """
    path = self._get_heroic_installed_path()
    if not path:
        return 0, 0, 0
    data = self.load_json(path, [])
    entries = self._parse_heroic_installed(data)
    if not entries:
        return 0, 0, 0

    added = 0
    updated = 0
    skipped = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("is_dlc") is True:
            skipped += 1
            continue

        app_name = entry.get("app_name") or entry.get("appName") or entry.get("app_name")
        if not app_name:
            skipped += 1
            continue

        name = entry.get("title") or entry.get("name") or entry.get("gameTitle") or app_name
        install_path = entry.get("install_path") or entry.get("installPath") or entry.get("install") or ""
        install_path = canonicalize_path(fix_path_str(install_path)) if install_path else install_path
        exe_hint = (
            entry.get("executable")
            or entry.get("launchExecutable")
            or entry.get("launch_executable")
            or entry.get("exe")
            or ""
        )
        exe_hint = str(exe_hint or "").strip()
        process_name_hint = Path(exe_hint).stem.strip() if exe_hint else ""
        if not process_name_hint:
            process_name_hint = name or app_name

        existing_id = None
        for game_id, game_data in self.library_data.items():
            if game_data.get("legendary_app_name") == app_name or game_data.get("heroic_app_name") == app_name:
                existing_id = game_id
                break
        if not existing_id:
            # Fallback match for legacy/manual entries to avoid creating duplicates
            # that appear as "playtime reset to 0".
            for game_id, game_data in self.library_data.items():
                if not isinstance(game_data, dict):
                    continue
                source = str(game_data.get("source") or "").strip().lower()
                if source not in ("epic", "heroic"):
                    continue
                if install_path and str(game_data.get("install_path") or "").strip() == install_path:
                    existing_id = game_id
                    break
                if (str(game_data.get("name") or "").strip().lower() == str(name).strip().lower()):
                    existing_id = game_id
                    break
        if existing_id:
            existing = self.library_data.get(existing_id)
            changed = False
            if existing.get("name") != name:
                existing["name"] = name
                changed = True
            if existing.get("install_path") != install_path and install_path:
                existing["install_path"] = install_path
                changed = True
            if existing.get("legendary_app_name") != app_name:
                existing["legendary_app_name"] = app_name
                changed = True
            if existing.get("heroic_app_name") != app_name:
                existing["heroic_app_name"] = app_name
                changed = True
            if existing.get("source") != "epic":
                existing["source"] = "epic"
                changed = True
            old_process_name = str(existing.get("process_name") or "").strip()
            if process_name_hint and (
                not old_process_name
                or old_process_name == str(existing.get("name") or "").strip()
                or old_process_name == str(app_name).strip()
            ):
                if old_process_name != process_name_hint:
                    existing["process_name"] = process_name_hint
                    changed = True
            if existing.get("installed") is not True:
                existing["installed"] = True
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue

        game_id = f"epic_{app_name}".replace(" ", "_").lower()
        if game_id in self.library_data and isinstance(self.library_data.get(game_id), dict):
            # Merge into existing key instead of skipping, preserving playtime/history.
            existing = self.library_data.get(game_id)
            changed = False
            if existing.get("name") != name:
                existing["name"] = name
                changed = True
            if install_path and existing.get("install_path") != install_path:
                existing["install_path"] = install_path
                changed = True
            if existing.get("legendary_app_name") != app_name:
                existing["legendary_app_name"] = app_name
                changed = True
            if existing.get("heroic_app_name") != app_name:
                existing["heroic_app_name"] = app_name
                changed = True
            if existing.get("source") != "epic":
                existing["source"] = "epic"
                changed = True
            if existing.get("installed") is not True:
                existing["installed"] = True
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue

        self.library_data[game_id] = {
            "id": game_id,
            "name": name,
            "genre": "",
            "platform": "Epic Games",
            "notes": "",
            "playtime": 0,
            "proton_path": None,
            "added_date": time.time(),
            "cover": "",
            "logo": "",
            "hero": "",
            "is_emulated": False,
            "legendary_app_name": app_name,
            "heroic_app_name": app_name,
            "install_path": install_path,
            "process_name": process_name_hint,
            "source": "epic",
            "installed": True,
        }
        added += 1

    if added or updated:
        self.save_library()
    return added, updated, skipped


def _get_steam_root_candidates(self):
    candidates = []
    if IS_WINDOWS:
        for root in (
            Path("C:/Program Files (x86)/Steam"),
            Path("C:/Program Files/Steam"),
            Path("D:/Steam"),
        ):
            candidates.append(root)
    else:
        candidates.append(Path.home() / ".steam" / "steam")
        candidates.append(Path.home() / ".local" / "share" / "Steam")
        candidates.append(Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam")
    return candidates


def _parse_vdf_paths(self, text):
    paths = []
    for line in text.splitlines():
        if '"path"' in line:
            try:
                path = line.split('"path"')[1].strip().strip('"')
                if path:
                    paths.append(path)
            except Exception:
                continue
    return paths


def _parse_vdf_field(self, text, key):
    for line in text.splitlines():
        if line.strip().startswith(f'"{key}"'):
            parts = line.strip().split('"')
            if len(parts) >= 4:
                return parts[3]
    return None


def scan_steam_games(self):
    """
    Scan Steam libraries for installed games.

    Returns:
        tuple: (added_count, updated_count, skipped_count)
    """
    added = 0
    updated = 0
    skipped = 0

    # Cleanup legacy Steam IDs (e.g. "apex_legends" + "steam_1172470").
    def _dedupe_steam_entries():
        groups = {}
        for game_id, game_data in self.library_data.items():
            if not isinstance(game_data, dict):
                continue
            app_id = str(game_data.get("steam_app_id") or "").strip()
            if not app_id:
                continue
            if (game_data.get("source") or "").strip().lower() not in ("", "steam"):
                continue
            groups.setdefault(app_id, []).append(game_id)

        changed_local = False
        for app_id, ids in groups.items():
            if len(ids) <= 1:
                continue

            preferred_id = f"steam_{app_id}"
            keep_id = preferred_id if preferred_id in ids else ids[0]
            keep = self.library_data.get(keep_id, {})
            if not isinstance(keep, dict):
                keep = {}

            for game_id in ids:
                if game_id == keep_id:
                    continue
                other = self.library_data.get(game_id) or {}
                if not isinstance(other, dict):
                    continue

                # Preserve richer metadata when present.
                for key in ("cover", "logo", "hero", "install_path", "genre", "notes", "platform"):
                    if not keep.get(key) and other.get(key):
                        keep[key] = other.get(key)
                try:
                    keep["playtime"] = max(int(keep.get("playtime") or 0), int(other.get("playtime") or 0))
                except Exception:
                    pass
                try:
                    keep["added_date"] = min(float(keep.get("added_date") or time.time()), float(other.get("added_date") or time.time()))
                except Exception:
                    pass
                del self.library_data[game_id]
                changed_local = True

            keep["steam_app_id"] = app_id
            keep["source"] = "steam"
            keep["id"] = keep_id
            self.library_data[keep_id] = keep

            # Normalize key to steam_{appid} when available.
            if keep_id != preferred_id and preferred_id not in self.library_data:
                self.library_data[preferred_id] = self.library_data.pop(keep_id)
                self.library_data[preferred_id]["id"] = preferred_id
                changed_local = True

        return changed_local

    if _dedupe_steam_entries():
        self.save_library()

    library_paths = []
    for root in self._get_steam_root_candidates():
        if not root.exists():
            continue
        library_paths.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            try:
                text = vdf.read_text(encoding="utf-8", errors="ignore")
                for path in self._parse_vdf_paths(text):
                    library_paths.append(Path(fix_path_str(path)))
            except Exception:
                pass

    seen_apps = set()
    for root in library_paths:
        steamapps = root / "steamapps"
        if not steamapps.exists():
            continue
        for appmanifest in steamapps.glob("appmanifest_*.acf"):
            try:
                text = appmanifest.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            app_id = self._parse_vdf_field(text, "appid")
            if not app_id or app_id in seen_apps:
                continue
            seen_apps.add(app_id)
            name = self._parse_vdf_field(text, "name") or f"Steam {app_id}"
            installdir = self._parse_vdf_field(text, "installdir")
            install_path = ""
            if installdir:
                install_path = canonicalize_path(fix_path_str(str(steamapps / "common" / installdir)))

            existing_id = f"steam_{app_id}"
            existing = self.library_data.get(existing_id)
            if not existing:
                # Backward compatibility with legacy keys.
                for gid, gdata in self.library_data.items():
                    if not isinstance(gdata, dict):
                        continue
                    if str(gdata.get("steam_app_id") or "").strip() == str(app_id):
                        existing = gdata
                        existing_id = gid
                        break
            if existing:
                changed = False
                if existing.get("name") != name:
                    existing["name"] = name
                    changed = True
                if install_path and existing.get("install_path") != install_path:
                    existing["install_path"] = install_path
                    changed = True
                if existing.get("installed") is not True:
                    existing["installed"] = True
                    changed = True
                if changed:
                    updated += 1
                else:
                    skipped += 1
                continue

            self.library_data[existing_id] = {
                "id": existing_id,
                "name": name,
                "genre": "",
                "platform": "Steam",
                "notes": "",
                "playtime": 0,
                "proton_path": None,
                "added_date": time.time(),
                "cover": "",
                "logo": "",
                "hero": "",
                "is_emulated": False,
                "steam_app_id": app_id,
                "install_path": install_path,
                "process_name": name,
                "source": "steam",
                "installed": True,
            }
            added += 1

    if added or updated:
        self.save_library()
    return added, updated, skipped


def get_steam_install_path(self, app_id):
    """Return install path for a Steam appid by scanning appmanifest files."""
    if not app_id:
        return ""
    app_id = str(app_id).strip()
    if not app_id:
        return ""
    library_paths = []
    for root in self._get_steam_root_candidates():
        if not root.exists():
            continue
        library_paths.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            try:
                text = vdf.read_text(encoding="utf-8", errors="ignore")
                for path in self._parse_vdf_paths(text):
                    library_paths.append(Path(fix_path_str(path)))
            except Exception:
                pass
    for root in library_paths:
        steamapps = root / "steamapps"
        if not steamapps.exists():
            continue
        appmanifest = steamapps / f"appmanifest_{app_id}.acf"
        if not appmanifest.exists():
            continue
        try:
            text = appmanifest.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        installdir = self._parse_vdf_field(text, "installdir")
        if not installdir:
            continue
        install_path = canonicalize_path(fix_path_str(str(steamapps / "common" / installdir)))
        if install_path:
            return install_path
    return ""


def _get_riot_programdata_root(self):
    if IS_WINDOWS:
        return Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Riot Games"
    return None


def _get_riot_client_path(self):
    config_path = Path(os.environ.get("APPDATA", "")) / "Riot Games" / "RiotClientInstalls.json"
    if config_path.exists():
        data = self.load_json(config_path, {})
        path = data.get("rc_default")
        if path:
            return path
    return ""


def scan_riot_games(self):
    """
    Scan Riot installs (Windows only) via ProgramData metadata.

    Returns:
        tuple: (added_count, updated_count, skipped_count)
    """
    if not IS_WINDOWS:
        return 0, 0, 0
    root = self._get_riot_programdata_root()
    if not root or not root.exists():
        return 0, 0, 0

    added = 0
    updated = 0
    skipped = 0

    installs_file = root / "RiotClientInstalls.json"
    data = self.load_json(installs_file, {})
    if not isinstance(data, dict):
        data = {}

    # Non-game keys that can appear in RiotClientInstalls.json
    non_game_keys = {"associated_client", "patchlines", "riot client", "riot_client"}

    # Prune previously imported non-game Riot entries.
    removed = 0
    for gid in list(self.library_data.keys()):
        g = self.library_data.get(gid)
        if not isinstance(g, dict):
            continue
        if (g.get("source") or "").lower() != "riot":
            continue
        rid = str(g.get("riot_product_id") or "").strip().lower()
        if (not rid) or (rid in non_game_keys) or (".live" not in rid):
            del self.library_data[gid]
            removed += 1

    def _parse_yaml_scalar(path_obj, key):
        try:
            with open(path_obj, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith(f"{key}:"):
                        continue
                    value = line.split(":", 1)[1].strip().strip('"').strip("'")
                    return value
        except Exception:
            return ""
        return ""

    riot_entries = []
    for product_id, meta in data.items():
        pid = str(product_id or "").strip()
        pid_l = pid.lower()
        if not pid or pid_l in non_game_keys:
            continue
        if not isinstance(meta, dict):
            continue

        # Skip internal/metadata-only entries
        if any(k in meta for k in ("associated_client", "patchlines")):
            continue

        # Product IDs must look like actual launchable products (e.g. valorant.live)
        if ".live" not in pid_l:
            continue
        riot_entries.append((pid, meta))

    # Fallback path for current Riot layout where installs.json has no per-game entries.
    if not riot_entries:
        associated_client = data.get("associated_client") if isinstance(data.get("associated_client"), dict) else {}
        meta_root = root / "Metadata"
        if meta_root.exists():
            display_names = {
                "valorant.live": "VALORANT",
                "league_of_legends.live": "League of Legends",
                "bacon.live": "League of Legends",
                "lion.live": "Teamfight Tactics",
            }
            for entry_dir in meta_root.iterdir():
                if not entry_dir.is_dir():
                    continue
                pid = str(entry_dir.name or "").strip()
                pid_l = pid.lower()
                if not pid or pid_l in non_game_keys or ".live" not in pid_l:
                    continue

                meta = {}
                yaml_path = entry_dir / f"{pid}.product_settings.yaml"
                if yaml_path.exists():
                    install_full = _parse_yaml_scalar(yaml_path, "product_install_full_path")
                    install_root = _parse_yaml_scalar(yaml_path, "product_install_root")
                    if install_full:
                        meta["install_path"] = install_full
                    elif install_root:
                        meta["install_path"] = install_root

                if not meta.get("install_path"):
                    token = pid_l.split(".", 1)[0]
                    for install_key in associated_client.keys():
                        key_path = str(install_key or "")
                        if token and token in key_path.lower():
                            meta["install_path"] = key_path
                            break

                if not meta.get("install_path"):
                    continue
                meta["product_name"] = display_names.get(pid_l, pid.replace(".live", "").replace("_", " ").title())
                riot_entries.append((pid, meta))

    for product_id, meta in riot_entries:
        pid = str(product_id or "").strip()
        pid_l = pid.lower()

        name = meta.get("product_name") or pid
        install_path = (
            meta.get("install_path")
            or meta.get("installLocation")
            or meta.get("product_install_full_path")
            or meta.get("product_install_root")
        )
        # If we can't resolve install location at all, treat as non-install metadata.
        if not install_path:
            skipped += 1
            continue
        install_path = canonicalize_path(fix_path_str(install_path)) if install_path else install_path
        existing_id = pid.replace(" ", "_").lower()
        existing = self.library_data.get(existing_id)
        if not existing:
            # Fallback match for legacy/manual Riot entries.
            for game_id, game_data in self.library_data.items():
                if not isinstance(game_data, dict):
                    continue
                source = str(game_data.get("source") or "").strip().lower()
                if source != "riot":
                    continue
                if str(game_data.get("riot_product_id") or "").strip() == pid:
                    existing = game_data
                    existing_id = game_id
                    break
                if install_path and str(game_data.get("install_path") or "").strip() == install_path:
                    existing = game_data
                    existing_id = game_id
                    break
        if existing:
            changed = False
            if existing.get("name") != name:
                existing["name"] = name
                changed = True
            if install_path and existing.get("install_path") != install_path:
                existing["install_path"] = install_path
                changed = True
            if existing.get("riot_product_id") != pid:
                existing["riot_product_id"] = pid
                changed = True
            if existing.get("source") != "riot":
                existing["source"] = "riot"
                changed = True
            if existing.get("installed") is not True:
                existing["installed"] = True
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue

        self.library_data[existing_id] = {
            "id": existing_id,
            "name": name,
            "genre": "",
            "platform": "Riot Games",
            "notes": "",
            "playtime": 0,
            "proton_path": None,
            "added_date": time.time(),
            "cover": "",
            "logo": "",
            "hero": "",
            "is_emulated": False,
            "riot_product_id": pid,
            "install_path": install_path,
            "process_name": name,
            "source": "riot",
            "installed": True,
        }
        added += 1

    if added or updated:
        self.save_library()
    elif removed:
        self.save_library()
    return added, updated + removed, skipped
