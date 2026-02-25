from __future__ import annotations

import configparser
import os
import re
from dataclasses import dataclass
from pathlib import Path
from utils.helpers import fix_path_str

@dataclass(slots=True)
class EmuAchievementFile:
    """Discovered emulator achievement state file."""

    appid: str
    path: Path
    source_root: Path

ACH_FILES = {
    "achievements.ini",
    "achievements.json",
    "achiev.ini",
    "stats.ini",
    "achievements.bin",
    "achieve.dat",
    "stats.bin",
    "user_stats.ini",
}

CFG_FILES = {
    "ali213.ini",
    "valve.ini",
    "hlm.ini",
    "ds.ini",
    "steam_api.ini",
    "steamconfig.ini",
    "tenoke.ini",
    "universelan.ini",
}


def _env_path(var: str) -> Path | None:
    val = os.environ.get(var)
    if not val:
        return None
    p = Path(val)
    return p if p.exists() else None


def default_roots(extra_roots: list[str] | None = None) -> list[Path]:
    """Return default roots mirroring Achievement Watcher style locations."""

    roots: list[Path] = []
    public = _env_path("PUBLIC")
    appdata = _env_path("APPDATA")
    programdata = _env_path("PROGRAMDATA")
    local = _env_path("LOCALAPPDATA")
    user = _env_path("USERPROFILE")

    if public:
        roots += [
            public / "Documents" / "Steam" / "CODEX",
            public / "Documents" / "Steam" / "RUNE",
            public / "Documents" / "OnlineFix",
            public / "Documents" / "EMPRESS",
        ]
    if appdata:
        roots += [
            appdata / "Steam" / "CODEX",
            appdata / "Goldberg SteamEmu Saves",
            appdata / "GSE Saves",
            appdata / "EMPRESS",
            appdata / "SmartSteamEmu",
        ]
        for p in (appdata / "NemirtingasEpicEmu").glob("*/*"):
            roots.append(p)
        for p in (appdata / "NemirtingasGalaxyEmu").glob("*/*"):
            roots.append(p)
    if programdata:
        roots.append(programdata / "Steam")
    if local:
        roots += [
            local / "SKIDROW",
            local / "anadius" / "LSX emu" / "achievement_watcher",
        ]
    if user:
        roots.append(user / "Documents" / "SKIDROW")

    if extra_roots:
        for raw in extra_roots:
            if not raw:
                continue
            try:
                expanded = Path(raw).expanduser()
                roots.append(expanded)
                translated = fix_path_str(str(expanded))
                if translated and translated != str(expanded):
                    roots.append(Path(translated).expanduser())
            except Exception:
                continue

    seen = set()
    out = []
    for r in roots:
        if r.exists():
            key = str(r.resolve())
            if key not in seen:
                seen.add(key)
                out.append(r)
    return out


def _extract_appid_from_path(path: Path) -> str | None:
    parts = [p for p in path.parts]
    for token in reversed(parts):
        if token.isdigit():
            return token
    # EMPRESS special: remote/<appid>
    for idx, token in enumerate(parts[:-1]):
        if token.lower() == "remote" and parts[idx + 1].isdigit():
            return parts[idx + 1]
    return None


def _extract_appid_from_ini(path: Path) -> str | None:
    try:
        cp = configparser.ConfigParser()
        cp.read(path, encoding="utf-8", errors="ignore")
        for section in cp.sections():
            for key, value in cp.items(section):
                if key.lower() in ("appid", "steamappid", "app_id"):
                    val = str(value).strip().strip('"').strip("'")
                    if val.isdigit():
                        return val
    except Exception:
        pass
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = re.search(
        r"(?:appid|steamappid|app_id)\s*=\s*([0-9]{3,})", text, flags=re.IGNORECASE
    )
    return m.group(1) if m else None


def discover_files(extra_roots: list[str] | None = None) -> list[EmuAchievementFile]:
    """Discover local achievement files and infer appids."""

    results: list[EmuAchievementFile] = []
    for root in default_roots(extra_roots):
        ini_appid_map: dict[Path, str] = {}
        try:
            for cfg in root.rglob("*"):
                if not cfg.is_file():
                    continue
                if cfg.name.lower() in CFG_FILES:
                    appid = _extract_appid_from_ini(cfg)
                    if appid:
                        ini_appid_map[cfg.parent] = appid
        except Exception:
            pass

        try:
            for f in root.rglob("*"):
                if not f.is_file():
                    continue
                if f.name.lower() not in ACH_FILES:
                    continue
                appid = _extract_appid_from_path(f)
                if not appid:
                    # Walk up for config-derived appid
                    for parent in [f.parent, *f.parents]:
                        if parent in ini_appid_map:
                            appid = ini_appid_map[parent]
                            break
                if not appid:
                    continue
                results.append(
                    EmuAchievementFile(appid=appid, path=f, source_root=root)
                )
        except Exception:
            continue

    # Deduplicate by (appid,file)
    dedup: dict[tuple[str, str], EmuAchievementFile] = {}
    for row in results:
        dedup[(row.appid, str(row.path).lower())] = row
    return list(dedup.values())