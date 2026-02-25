"""
Cross-platform game launching utility
"""
import subprocess
import psutil
import os
import shutil
import re
from pathlib import Path
from core.constants import IS_WINDOWS, IS_LINUX, DEFAULT_PROTON_PATH
from utils.helpers import resolve_user_path


class GameLauncher:
    """Handles launching games across different platforms"""

    @staticmethod
    def _detect_steam_client_install_path():
        """Best-effort Steam client location for Proton environment."""
        home = Path.home()
        candidates = [
            home / ".steam" / "steam",
            home / ".local" / "share" / "Steam",
            home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return str(candidates[1])

    @staticmethod
    def _safe_path_token(value):
        token = "".join(ch if (ch.isalnum() or ch in ("-", "_", ".")) else "_" for ch in str(value or ""))
        return token.strip("_") or "Game"

    @staticmethod
    def _default_compat_prefix(game_name):
        safe_name = GameLauncher._safe_path_token(game_name)
        return Path.home() / ".local" / "share" / "gametracker" / "Prefixes" / safe_name

    @staticmethod
    def _detect_wine_resolution():
        # Prefer current desktop resolution; fallback to a safe default.
        try:
            out = subprocess.check_output(["xrandr", "--current"], text=True, stderr=subprocess.DEVNULL)
            m = re.search(r"current\s+(\d+)\s+x\s+(\d+)", out or "")
            if m:
                return f"{m.group(1)}x{m.group(2)}"
        except Exception:
            pass
        return "2560x1440"
    
    @staticmethod
    def launch_game(
        exe_path,
        use_proton=False,
        proton_path=None,
        compat_tool=None,
        compat_path=None,
        wine_dll_overrides=None,
        steam_app_id=None,
        game_name=None,
    ):
        """
        Launch a game executable
        
        Args:
            exe_path: Path to game executable
            use_proton: Whether to use Proton (Linux only)
            proton_path: Custom Proton path (optional)
            compat_tool: Explicit compat tool ('proton' or 'wine')
            compat_path: Prefix/compat data directory
            wine_dll_overrides: WINEDLLOVERRIDES value
            steam_app_id: Optional Steam app id for Steam-like Proton env
            game_name: Optional game name for default compat prefix path
            
        Returns:
            tuple: (process_object, pid, start_time) or (None, None, None) on failure
        """
        exe_path = Path(exe_path)
        
        if not exe_path.exists():
            return None, None, None
        
        try:
            if IS_WINDOWS:
                # Windows: Direct execution
                proc = subprocess.Popen([str(exe_path)], shell=True, cwd=str(exe_path.parent))
                pid = proc.pid
                start_time = psutil.Process(pid).create_time()
                return proc, pid, start_time
                
            elif IS_LINUX:
                tool = (compat_tool or "").strip().lower()
                prefix_path = Path(resolve_user_path(compat_path)).expanduser() if compat_path else None
                dll_overrides = (wine_dll_overrides or "").strip()
                app_id = str(steam_app_id or "").strip()
                if not prefix_path and tool in ("wine", "proton"):
                    prefix_path = GameLauncher._default_compat_prefix(game_name or exe_path.stem)
                if prefix_path:
                    # Ensure compat folder exists before launch.
                    try:
                        prefix_path.mkdir(parents=True, exist_ok=True)
                    except PermissionError:
                        # Fallback to a user-writable path when configured prefix is not writable.
                        fallback = GameLauncher._default_compat_prefix(game_name or exe_path.stem)
                        fallback.mkdir(parents=True, exist_ok=True)
                        print(
                            f"Compat path not writable: {prefix_path}. "
                            f"Using fallback: {fallback}",
                            flush=True,
                        )
                        prefix_path = fallback
                    except OSError as err:
                        print(f"Failed to prepare compat path {prefix_path}: {err}", flush=True)
                        return None, None, None

                if (use_proton or tool == "proton") and proton_path:
                    # Linux with Proton
                    proton_bin = Path(proton_path) / "proton"
                    if proton_bin.exists():
                        env = os.environ.copy()
                        # Avoid inheriting potentially conflicting system wine env vars.
                        for key in ("WINEPREFIX", "WINE", "WINELOADER", "WINESERVER"):
                            env.pop(key, None)
                        # Avoid mixed 32/64-bit GStreamer plugin paths from host env.
                        for key in (
                            "GST_PLUGIN_PATH",
                            "GST_PLUGIN_PATH_1_0",
                            "GST_PLUGIN_SYSTEM_PATH",
                            "GST_PLUGIN_SYSTEM_PATH_1_0",
                        ):
                            env.pop(key, None)
                        if prefix_path:
                            env["STEAM_COMPAT_DATA_PATH"] = str(prefix_path)
                            shader_path = prefix_path / "shadercache"
                            shader_path.mkdir(parents=True, exist_ok=True)
                            env.setdefault("STEAM_COMPAT_SHADER_PATH", str(shader_path))
                        if dll_overrides:
                            env["WINEDLLOVERRIDES"] = dll_overrides
                        env.setdefault(
                            "STEAM_COMPAT_CLIENT_INSTALL_PATH",
                            GameLauncher._detect_steam_client_install_path(),
                        )
                        env.setdefault("STEAM_COMPAT_INSTALL_PATH", str(exe_path.parent))
                        env.setdefault("STEAM_COMPAT_TOOL_PATHS", str(Path(proton_path)))
                        if app_id.isdigit():
                            env.setdefault("SteamAppId", app_id)
                            env.setdefault("SteamGameId", app_id)
                            env.setdefault("STEAM_COMPAT_APP_ID", app_id)

                        # Use umu-run by default when available.
                        # Allow explicit opt-out with GAMETRACKER_DISABLE_UMU=1.
                        disable_umu = str(os.environ.get("GAMETRACKER_DISABLE_UMU", "")).strip().lower() in (
                            "1",
                            "true",
                            "yes",
                            "on",
                        )
                        umu_run = shutil.which("umu-run") if not disable_umu else None
                        if umu_run:
                            umu_env = env.copy()
                            umu_env["PROTONPATH"] = str(Path(proton_path))
                            if prefix_path:
                                # umu expects a Wine-style prefix path.
                                umu_env["WINEPREFIX"] = str(prefix_path)
                            umu_env.setdefault("GAMEID", app_id if app_id.isdigit() else f"gametracker-{exe_path.stem}")
                            try:
                                proc = subprocess.Popen(
                                    [umu_run, str(exe_path)],
                                    env=umu_env,
                                    cwd=str(exe_path.parent),
                                    start_new_session=True,
                                )
                                pid = proc.pid
                                start_time = psutil.Process(pid).create_time()
                                return proc, pid, start_time
                            except Exception as err:
                                print(f"umu-run launch failed, falling back to proton: {err}", flush=True)

                        cmd = [str(proton_bin), "waitforexitandrun", str(exe_path)]
                        steam_run = shutil.which("steam-run")
                        if steam_run:
                            cmd = [steam_run] + cmd
                        proc = subprocess.Popen(
                            cmd,
                            env=env,
                            cwd=str(exe_path.parent),
                            start_new_session=True,
                        )
                        pid = proc.pid
                        start_time = psutil.Process(pid).create_time()
                        return proc, pid, start_time

                if tool == "wine":
                    wine_candidates = []
                    if proton_path:
                        wine_candidates.extend([
                            Path(proton_path) / "bin" / "wine",
                            Path(proton_path) / "files" / "bin" / "wine",
                            Path(proton_path) / "wine",
                        ])
                    system_wine = ["wine", "wine64"]
                    wine_bin = None
                    for candidate in wine_candidates:
                        if candidate.exists():
                            wine_bin = str(candidate)
                            break
                    wine_res = GameLauncher._detect_wine_resolution()
                    base_wine = wine_bin if wine_bin else system_wine[0]
                    cmd = [base_wine, "explorer", f"/desktop=Game,{wine_res}", str(exe_path)]
                    steam_run = shutil.which("steam-run")
                    if steam_run:
                        cmd = [steam_run] + cmd
                    env = os.environ.copy()
                    if prefix_path:
                        env["WINEPREFIX"] = str(prefix_path)
                    if dll_overrides:
                        env["WINEDLLOVERRIDES"] = dll_overrides
                    if app_id.isdigit():
                        env.setdefault("SteamAppId", app_id)
                        env.setdefault("SteamGameId", app_id)
                        env.setdefault("STEAM_COMPAT_APP_ID", app_id)
                    for key in (
                        "GST_PLUGIN_PATH",
                        "GST_PLUGIN_PATH_1_0",
                        "GST_PLUGIN_SYSTEM_PATH",
                        "GST_PLUGIN_SYSTEM_PATH_1_0",
                    ):
                        env.pop(key, None)
                    try:
                        proc = subprocess.Popen(
                            cmd,
                            env=env,
                            cwd=str(exe_path.parent),
                            start_new_session=True,
                        )
                        pid = proc.pid
                        start_time = psutil.Process(pid).create_time()
                        return proc, pid, start_time
                    except FileNotFoundError:
                        if wine_bin:
                            return None, None, None
                        try:
                            fallback_cmd = [
                                system_wine[1],
                                "explorer",
                                f"/desktop=Game,{wine_res}",
                                str(exe_path),
                            ]
                            if steam_run:
                                fallback_cmd = [steam_run] + fallback_cmd
                            proc = subprocess.Popen(
                                fallback_cmd,
                                env=env,
                                cwd=str(exe_path.parent),
                                start_new_session=True,
                            )
                            pid = proc.pid
                            start_time = psutil.Process(pid).create_time()
                            return proc, pid, start_time
                        except Exception:
                            return None, None, None
                else:
                    # Native Linux execution
                    proc = subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
                    pid = proc.pid
                    start_time = psutil.Process(pid).create_time()
                    return proc, pid, start_time
                    
        except Exception as e:
            print(f"Failed to launch game: {e}")
            return None, None, None
        
        return None, None, None
