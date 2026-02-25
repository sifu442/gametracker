from __future__ import annotations

import os
import re
from pathlib import Path

from steam.models import SteamCandidate


_STATS_RE = re.compile(r"^UserGameStats_(\d+)_(\d+)\.bin$", re.IGNORECASE)


def _steam_path_windows_registry() -> Path | None:
    """Resolve Steam path from Windows registry."""

    try:
        import winreg  # type: ignore
    except Exception:
        return None

    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]
    for root, key, name in keys:
        try:
            with winreg.OpenKey(root, key) as handle:
                val, _ = winreg.QueryValueEx(handle, name)
                p = Path(str(val))
                if p.exists():
                    return p
        except Exception:
            continue
    return None


def find_steam_root() -> Path | None:
    """Find Steam installation root."""

    if os.name == "nt":
        reg = _steam_path_windows_registry()
        if reg:
            return reg
        for p in (
            Path(r"C:\Program Files (x86)\Steam"),
            Path(r"C:\Program Files\Steam"),
            Path(r"D:\Steam"),
        ):
            if p.exists():
                return p
    else:
        for p in (
            Path.home() / ".steam" / "steam",
            Path.home() / ".local" / "share" / "Steam",
            Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
        ):
            if p.exists():
                return p
    return None


def discover_candidates(steam_root: Path) -> list[SteamCandidate]:
    """Enumerate app/user candidates from local Steam stats files."""

    stats_dir = steam_root / "appcache" / "stats"
    if not stats_dir.exists():
        return []

    out: list[SteamCandidate] = []
    for file in stats_dir.glob("UserGameStats_*_*.bin"):
        m = _STATS_RE.match(file.name)
        if not m:
            continue
        out.append(SteamCandidate(appid=m.group(2), steam_user=m.group(1), stats_file=file))
    return out

