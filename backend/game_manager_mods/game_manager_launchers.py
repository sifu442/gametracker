import os
import shutil
import re
from pathlib import Path

from core.constants import IS_WINDOWS, IS_LINUX


def _find_heroic_executable():
    heroic_cmd = shutil.which("heroic")
    if heroic_cmd:
        return heroic_cmd
    if IS_WINDOWS:
        local_appdata = os.environ.get("LOCALAPPDATA")
        candidates = []
        if local_appdata:
            candidates.extend([
                Path(local_appdata) / "Programs" / "heroic" / "Heroic.exe",
                Path(local_appdata) / "Programs" / "Heroic" / "Heroic.exe",
                Path(local_appdata) / "Programs" / "heroic" / "heroic.exe",
                Path(local_appdata) / "Programs" / "Heroic" / "heroic.exe",
            ])
        candidates.extend([
            Path("C:/Program Files/Heroic/Heroic.exe"),
            Path("C:/Program Files/Heroic/heroic.exe"),
            Path("C:/Program Files (x86)/Heroic/Heroic.exe"),
            Path("C:/Program Files (x86)/Heroic/heroic.exe"),
        ])
        for c in candidates:
            if c.exists():
                return str(c)
    return ""


def get_legendary_launch_command(self, app_name):
    legendary_cmd = shutil.which("legendary")
    if not legendary_cmd:
        candidates = []
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            candidates.extend([
                Path(local_appdata) / "Programs" / "heroic" / "resources" / "app.asar.unpacked" / "build" / "bin" / "legendary.exe",
                Path(local_appdata) / "Programs" / "heroic" / "resources" / "app.asar.unpacked" / "build" / "legendary" / "legendary.exe",
            ])
        candidates.extend([
            Path("C:/Program Files/Heroic/resources/app.asar.unpacked/build/bin/x64/win32/legendary.exe"),
            Path("C:/Program Files/Heroic/resources/app.asar.unpacked/build/bin/legendary.exe"),
            Path("C:/Program Files/Heroic/resources/app.asar.unpacked/build/legendary/legendary.exe"),
        ])
        candidates.extend([
            Path.home() / "opt" / "Heroic" / "resources" / "app.asar.unpacked" / "build" / "bin" / "x64" / "linux" / "legendary",
            Path("/opt/Heroic/resources/app.asar.unpacked/build/bin/x64/linux/legendary"),
            Path.home() / ".var" / "app" / "com.heroicgameslauncher.hgl" / "config" / "heroic" / "tools" / "legendary" / "legendary",
        ])
        for candidate in candidates:
            if candidate.exists():
                legendary_cmd = str(candidate)
                break
    if not legendary_cmd:
        return None
    return [legendary_cmd, "launch", app_name]


def get_heroic_launch_command(self, app_name):
    if not app_name:
        return None
    app_name = str(app_name).strip()
    if not app_name:
        return None
    uri = f"heroic://launch/{app_name}"
    heroic_cmd = _find_heroic_executable()
    if IS_WINDOWS:
        if heroic_cmd:
            # Keep Heroic in background while starting the game.
            return [heroic_cmd, "--no-gui", "--uri", uri]
        # Fallback to URI handler; /min helps keep the launcher from popping foreground.
        return ["cmd", "/c", "start", "", "/min", uri]
    if IS_LINUX:
        if heroic_cmd:
            # Direct CLI launch is more reliable than xdg-open and keeps UI minimized.
            return [heroic_cmd, "--no-gui", "--uri", uri]
        flatpak_cmd = shutil.which("flatpak")
        if flatpak_cmd:
            return [
                flatpak_cmd,
                "run",
                "--command=heroic",
                "com.heroicgameslauncher.hgl",
                "--no-gui",
                "--uri",
                uri,
            ]
    opener = shutil.which("xdg-open")
    if opener:
        return [opener, uri]
    return None


def get_epic_launch_command(self, app_name):
    heroic_cmd = self.get_heroic_launch_command(app_name)
    if heroic_cmd:
        return "heroic", heroic_cmd
    legendary_cmd = self.get_legendary_launch_command(app_name)
    if legendary_cmd:
        return "legendary", legendary_cmd
    return "", None


def get_steam_launch_command(self, app_id):
    if not app_id:
        return None
    steam_cmd = shutil.which("steam")
    if not steam_cmd and IS_WINDOWS:
        for root in self._get_steam_root_candidates():
            candidate = root / "steam.exe"
            if candidate.exists():
                steam_cmd = str(candidate)
                break
    if not steam_cmd:
        return None
    # Launch Steam games with lightweight client UI flags.
    return [
        steam_cmd,
        "-nochatui",
        "-nofriendsui",
        "-silent",
        "-applaunch",
        str(app_id),
    ]


def get_steam_playtime_minutes(self, app_id):
    if not app_id:
        return 0
    app_id = str(app_id)
    for root in self._get_steam_root_candidates():
        userdata_root = root / "userdata"
        if not userdata_root.exists():
            continue
        for user_dir in userdata_root.iterdir():
            if not user_dir.is_dir():
                continue
            cfg = user_dir / "config" / "localconfig.vdf"
            if not cfg.exists():
                continue
            try:
                text = cfg.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            m = re.search(
                rf'"{re.escape(app_id)}"\s*\{{[^}}]*?"Playtime"\s*"(\d+)"',
                text,
                re.S,
            )
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    return 0
    return 0
