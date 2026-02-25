"""
Launch/tracking operations extracted from AppController.
"""

from __future__ import annotations

import os
import re
import base64
import subprocess
import sys
import time
import signal
import shutil
import psutil
from pathlib import Path
from typing import TYPE_CHECKING

from core.constants import COVERS_DIR, HEROES_DIR, IS_LINUX, IS_WINDOWS, LOGOS_DIR, SCRIPT_DIR
from threads.process_monitor import ProcessMonitor
from utils.emulator_launcher import EmulatorLauncher
from utils.game_launcher import GameLauncher
from utils.helpers import fix_path_str, resolve_user_path

if TYPE_CHECKING:
    from backend.controllers import AppController


class LaunchControllerOps:
    """Encapsulates game launch and tracking lifecycle for AppController."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def get_exe_path_for_platform(self, game_data):
        exe_paths = game_data.get("exe_paths", {})
        if isinstance(exe_paths, str):
            return fix_path_str(exe_paths)
        if IS_WINDOWS:
            return fix_path_str(exe_paths.get("Windows", ""))
        if IS_LINUX:
            return fix_path_str(exe_paths.get("Linux", ""))
        return ""

    def normalize_launch_type(self, launch_type):
        launch_type = (launch_type or "executable").strip().lower()
        if launch_type == "exe":
            return "executable"
        return launch_type

    def _looks_windows_binary(self, path_value):
        p = str(path_value or "").strip().lower()
        if not p:
            return False
        return p.endswith(".exe") or p.startswith("c:/") or p.startswith("d:/") or p.startswith("e:/")

    def get_emulator_exec_path(self, emulator, launch_type):
        if IS_WINDOWS and emulator.get("exe_path_windows"):
            return emulator.get("exe_path_windows")
        if IS_LINUX and emulator.get("exe_path_linux"):
            return emulator.get("exe_path_linux")
        exe_paths = emulator.get("exe_paths")
        if isinstance(exe_paths, dict):
            direct = exe_paths.get(launch_type, "")
            if direct and not (IS_LINUX and self._looks_windows_binary(direct)):
                return direct
            for _, val in exe_paths.items():
                if not val:
                    continue
                if IS_LINUX and self._looks_windows_binary(val):
                    continue
                return val
            if IS_LINUX:
                return ""
        elif isinstance(exe_paths, str) and exe_paths:
            if IS_LINUX and self._looks_windows_binary(exe_paths):
                return ""
            return exe_paths
        fallback = emulator.get("exe_path") or ""
        if IS_LINUX and self._looks_windows_binary(fallback):
            return ""
        return fallback

    def start_tracking(self, game_id, pid, start_time, proc=None):
        c = self._c
        c._current_game_id = game_id
        c._current_pid = pid
        c._current_proc = proc
        c._session_start = time.time()
        c._is_monitoring = True
        c.playbackChanged.emit()

        c._monitor_thread = ProcessMonitor(pid, start_time)
        c._monitor_thread.game_ended.connect(c._on_game_ended)
        c._monitor_thread.start()
        c._auto_save_timer.start(30000)

    def _cleanup_linux_runtime(self):
        c = self._c
        if not IS_LINUX:
            return
        if not getattr(c, "_current_runtime_managed", False):
            return
        runtime_tool = str(getattr(c, "_current_runtime_tool", "") or "").strip().lower()
        runtime_prefix = str(getattr(c, "_current_runtime_prefix", "") or "").strip()
        runtime_proton_path = str(getattr(c, "_current_runtime_proton_path", "") or "").strip()
        runtime_exe_name = str(getattr(c, "_current_runtime_exe_name", "") or "").strip().lower()
        runtime_game_name = str(getattr(c, "_current_runtime_game_name", "") or "").strip().lower()
        runtime_started_at = float(getattr(c, "_current_runtime_started_at", 0.0) or 0.0)
        pid = int(c._current_pid or 0)
        if pid <= 0:
            if runtime_tool in ("wine", "proton"):
                self._shutdown_wineserver(runtime_prefix, runtime_proton_path)
                self._kill_runtime_processes_by_context(
                    runtime_prefix,
                    runtime_proton_path,
                    runtime_exe_name,
                    runtime_game_name,
                    runtime_started_at,
                )
            return
        try:
            os.killpg(pid, signal.SIGTERM)
            time.sleep(0.2)
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass
        except Exception as err:
            print(f"Runtime cleanup warning: {err}", flush=True)
        if runtime_tool in ("wine", "proton"):
            self._shutdown_wineserver(runtime_prefix, runtime_proton_path)
            self._kill_runtime_processes_by_context(
                runtime_prefix,
                runtime_proton_path,
                runtime_exe_name,
                runtime_game_name,
                runtime_started_at,
            )

    def _reap_child_zombies(self):
        # Collect any exited child processes to avoid lingering <defunct> entries.
        while True:
            try:
                pid, _status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    break
            except ChildProcessError:
                break
            except Exception:
                break

    def _shutdown_wineserver(self, prefix_path, proton_path):
        env = os.environ.copy()
        if prefix_path:
            env["WINEPREFIX"] = prefix_path

        candidates = []
        if proton_path:
            p = Path(proton_path)
            candidates.extend(
                [
                    p / "files" / "bin" / "wineserver",
                    p / "bin" / "wineserver",
                    p / "wineserver",
                ]
            )
        sys_ws = shutil.which("wineserver")
        if sys_ws:
            candidates.append(Path(sys_ws))

        seen = set()
        commands = []
        for c in candidates:
            s = str(c)
            if s in seen:
                continue
            seen.add(s)
            if Path(s).exists():
                commands.append(s)
        if not commands and sys_ws:
            commands.append(sys_ws)

        for ws in commands:
            try:
                subprocess.run([ws, "-k"], env=env, timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                continue
        for ws in commands:
            try:
                subprocess.run([ws, "-w"], env=env, timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                continue

    def _kill_runtime_processes_by_context(self, prefix_path, proton_path, exe_name, game_name, started_at):
        # Fallback cleanup for containerized launches (umu/pressure-vessel) that may
        # outlive the initial launcher process group.
        prefix_norm = str(prefix_path or "").strip()
        proton_norm = str(proton_path or "").strip()
        if not prefix_norm and not proton_norm and not exe_name and not game_name and started_at <= 0:
            return

        tokens = (
            "wineserver",
            "wine64",
            "wine",
            "proton",
            "umu-run",
            "pressure-vessel",
            "steam-runtime-launch-client",
        )
        pids = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if not cmdline:
                    continue
                lower_cmd = cmdline.lower()
                if not any(t in lower_cmd for t in tokens):
                    continue
                match = False
                if prefix_norm and prefix_norm in cmdline:
                    match = True
                if proton_norm and proton_norm in cmdline:
                    match = True
                if exe_name and exe_name in lower_cmd:
                    match = True
                if game_name and game_name in lower_cmd:
                    match = True
                if not match and started_at > 0:
                    try:
                        if float(proc.create_time()) >= (started_at - 2.0):
                            match = True
                    except Exception:
                        pass
                if not match:
                    continue
                pids.append(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                continue
        time.sleep(0.2)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                continue

    def auto_save(self):
        c = self._c
        self._reap_child_zombies()
        if c._is_monitoring and c._session_start:
            elapsed = int(time.time() - c._session_start)
            game_data = c._game_manager.get_game(c._current_game_id)
            if not game_data:
                return
            process_name = game_data.get("process_name", "")
            if process_name:
                current_total = c._game_manager.get_total_playtime(process_name)
                c._game_manager.set_playtime(process_name, current_total + elapsed)
                c._session_start = time.time()
            c.trackingChanged.emit()

    def on_game_ended(self):
        c = self._c
        if not c._is_monitoring:
            return
        if c._session_start:
            elapsed = int(time.time() - c._session_start)
            game_data = c._game_manager.get_game(c._current_game_id)
            if game_data:
                process_name = game_data.get("process_name", "")
                if process_name:
                    current_total = c._game_manager.get_total_playtime(process_name)
                    c._game_manager.set_playtime(process_name, current_total + elapsed)
                    c._game_manager.set_last_played(process_name, time.time())
        c._stop_tracking()

    def stop_tracking(self):
        c = self._c
        c._is_monitoring = False
        if c._monitor_thread:
            c._monitor_thread.stop()
            c._monitor_thread.wait()
            c._monitor_thread = None
        c._auto_save_timer.stop()
        self._cleanup_linux_runtime()
        self._reap_child_zombies()
        current_proc = getattr(c, "_current_proc", None)
        if current_proc is not None:
            try:
                current_proc.wait(timeout=0.5)
            except Exception:
                pass
        self._reap_child_zombies()
        c._current_game_id = None
        c._current_pid = None
        c._current_proc = None
        c._current_runtime_managed = False
        c._current_runtime_tool = ""
        c._current_runtime_prefix = ""
        c._current_runtime_proton_path = ""
        c._current_runtime_exe_name = ""
        c._current_runtime_game_name = ""
        c._current_runtime_started_at = 0.0
        c._session_start = None
        c.playbackChanged.emit()
        c.trackingChanged.emit()

    def play_selected(self):
        c = self._c
        c._current_runtime_managed = False
        c._current_runtime_tool = ""
        c._current_runtime_prefix = ""
        c._current_runtime_proton_path = ""
        c._current_proc = None
        c._current_runtime_exe_name = ""
        c._current_runtime_game_name = ""
        c._current_runtime_started_at = 0.0
        if not c._selected_game_id:
            return
        if c._is_monitoring:
            c.errorMessage.emit("A game is already running. Stop it first.")
            return
        game_data = c._game_manager.get_game(c._selected_game_id)
        if not game_data:
            c.errorMessage.emit("Game not found.")
            return

        def _launch_subprocess_and_track(cmd, fail_message, env=None):
            try:
                proc = subprocess.Popen(cmd, env=env)
            except Exception:
                c.errorMessage.emit(fail_message)
                return False
            pid = proc.pid
            start_time = time.time()
            c._start_tracking(c._selected_game_id, pid, start_time, proc)
            return True

        # Route through Steam only for actual Steam-source entries.
        # Non-Steam games may still have steam_app_id for achievements metadata.
        if game_data.get("source") == "steam":
            app_id = game_data.get("steam_app_id")
            if not app_id:
                c.errorMessage.emit("Steam app id is missing.")
                return
            cmd = c._game_manager.get_steam_launch_command(app_id)
            if not cmd:
                c.errorMessage.emit("Steam client not found.")
                return
            _launch_subprocess_and_track(cmd, "Failed to launch Steam.")
            return

        if game_data.get("source") == "riot" or game_data.get("riot_product_id"):
            product_id = game_data.get("riot_product_id")
            if not product_id:
                c.errorMessage.emit("Riot product id is missing.")
                return
            override_path = c._config.get("riot_client_path", "")
            client_path = (
                override_path
                if override_path and os.path.exists(override_path)
                else c._game_manager._get_riot_client_path()
            )
            if not client_path:
                c.errorMessage.emit("Riot Client not found.")
                return
            _launch_subprocess_and_track(
                [client_path, f"--launch-product={product_id}", "--launch-patchline=live"],
                "Failed to launch Riot Client.",
            )
            return

        if game_data.get("source") == "epic" or game_data.get("legendary_app_name"):
            app_name = game_data.get("legendary_app_name")
            if not app_name:
                c.errorMessage.emit("Epic app id is missing.")
                return
            cmd = c._game_manager.get_legendary_launch_command(app_name)
            if not cmd:
                c.errorMessage.emit("Legendary CLI not found in PATH.")
                return
            try:
                env = os.environ.copy()
                cfg_dir = c._game_manager.get_heroic_legendary_config_dir()
                if cfg_dir:
                    env["LEGENDARY_CONFIG_PATH"] = str(cfg_dir)
                    env["LEGENDARY_CONFIG_DIR"] = str(cfg_dir)
                    env.setdefault("XDG_CONFIG_HOME", str(cfg_dir.parent.parent))
            except Exception:
                c.errorMessage.emit("Failed to launch Legendary.")
                return
            _launch_subprocess_and_track(cmd, "Failed to launch Legendary.", env=env)
            return

        if game_data.get("is_emulated"):
            emulator_id = game_data.get("emulator_id")
            rom_path = game_data.get("rom_path")
            if not emulator_id or not rom_path:
                c.errorMessage.emit("Emulator or ROM is not configured.")
                return
            emulator = c._game_manager.get_emulator(emulator_id)
            if not emulator:
                c.errorMessage.emit("Emulator not found.")
                return
            launch_type = c._normalize_launch_type(emulator.get("launch_type") or "executable")
            if IS_WINDOWS:
                launch_type = c._normalize_launch_type(emulator.get("launch_type_windows") or launch_type)
            if IS_LINUX:
                launch_type = c._normalize_launch_type(emulator.get("launch_type_linux") or launch_type)
            emulator_path = c._get_emulator_exec_path(emulator, launch_type)
            args_template = emulator.get("args_template")
            flatpak_id = emulator.get("flatpak_id")
            if launch_type == "flatpak":
                if not flatpak_id:
                    c.errorMessage.emit("Flatpak app ID is missing.")
                    return
            elif not emulator_path:
                c.errorMessage.emit("Emulator executable/AppImage path is missing.")
                return
            proc, pid, start_time = EmulatorLauncher.launch_emulator(
                launch_type,
                emulator_path,
                rom_path,
                args_template=args_template,
                flatpak_id=flatpak_id,
            )
            if not pid:
                c.errorMessage.emit("Failed to launch emulator.")
                return
            if not game_data.get("process_name"):
                game_data["process_name"] = c._selected_game_id
            c._start_tracking(c._selected_game_id, pid, start_time, proc)
            return

        exe_path = c._get_exe_path_for_platform(game_data)
        if not exe_path:
            c.errorMessage.emit("No executable configured for this platform.")
            return
        proc, pid, start_time = GameLauncher.launch_game(
            exe_path,
            use_proton=bool(game_data.get("proton_path")),
            proton_path=game_data.get("proton_path"),
            compat_tool=game_data.get("compat_tool"),
            compat_path=game_data.get("wine_prefix"),
            wine_dll_overrides=game_data.get("wine_dll_overrides"),
            steam_app_id=game_data.get("steam_app_id"),
            game_name=game_data.get("name"),
        )
        if not pid:
            c.errorMessage.emit("Failed to launch game.")
            return
        compat_tool = str(game_data.get("compat_tool") or "").strip().lower()
        c._current_runtime_managed = IS_LINUX and (
            compat_tool in ("wine", "proton") or bool(game_data.get("proton_path"))
        )
        if c._current_runtime_managed:
            c._current_runtime_tool = compat_tool or ("proton" if game_data.get("proton_path") else "")
            c._current_runtime_prefix = resolve_user_path(str(game_data.get("wine_prefix") or "").strip())
            c._current_runtime_proton_path = str(game_data.get("proton_path") or "").strip()
            c._current_runtime_exe_name = Path(str(exe_path)).name.lower()
            c._current_runtime_game_name = str(game_data.get("name") or "").strip().lower()
            c._current_runtime_started_at = float(start_time or time.time())
        c._start_tracking(c._selected_game_id, pid, start_time, proc)

    def launch_game_by_id(self, game_id):
        c = self._c
        game_id = (game_id or "").strip()
        if not game_id:
            return "Game ID is empty."
        if not c._game_manager.get_game(game_id):
            return f"Game not found: {game_id}"
        c.select_game(game_id)
        c.play_selected()
        return f"Launch requested for {game_id}"

    def create_desktop_shortcut(self):
        c = self._c
        game_data = c._game_manager.get_game(c._selected_game_id) if c._selected_game_id else None
        if not game_data:
            return "No game selected."

        raw_name = (game_data.get("name") or "Game").strip()
        if IS_WINDOWS:
            name = re.sub(r"[<>:\"/\\|?*]+", "_", raw_name).strip(" .") or "Game"
        else:
            name = raw_name.replace("/", "_") or "Game"
        if IS_WINDOWS:
            desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
            desktop.mkdir(parents=True, exist_ok=True)
            shortcut_path = desktop / f"{name}.lnk"
        else:
            desktop = Path.home() / "Desktop"
            desktop.mkdir(parents=True, exist_ok=True)
            shortcut_path = desktop / f"{name}.desktop"

        encoded_game_id = base64.urlsafe_b64encode(c._selected_game_id.encode("utf-8")).decode("ascii")
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--launch-game-id-b64", encoded_game_id, "--start-minimized"]
            target_hint = Path(sys.executable)
        else:
            cmd = [sys.executable, str(SCRIPT_DIR / "main.py"), "--launch-game-id-b64", encoded_game_id, "--start-minimized"]
            target_hint = Path(sys.executable)

        def _resolve_media_file(rel_path):
            if not rel_path:
                return None
            media_path = Path(fix_path_str(rel_path))
            if not media_path.is_absolute():
                if media_path.name == str(media_path):
                    for media_dir in (LOGOS_DIR, COVERS_DIR, HEROES_DIR):
                        candidate = media_dir / media_path.name
                        if candidate.exists():
                            media_path = candidate
                            break
                    else:
                        media_path = SCRIPT_DIR / media_path
                else:
                    media_path = SCRIPT_DIR / media_path
            return media_path if media_path.exists() else None

        icon_path = (
            _resolve_media_file(game_data.get("logo"))
            or _resolve_media_file(game_data.get("cover"))
            or _resolve_media_file(game_data.get("hero"))
        )

        def _windows_shortcut_icon_source(path_obj, game_name):
            if not path_obj:
                return ""
            try:
                p = Path(path_obj)
                if p.suffix.lower() in (".ico", ".exe", ".dll"):
                    return str(p)
                cache_dir = SCRIPT_DIR / "shortcut_icons"
                cache_dir.mkdir(parents=True, exist_ok=True)
                ico_name = f"{game_name.replace(' ', '_')}.ico"
                ico_path = cache_dir / ico_name
                from PIL import Image
                with Image.open(p) as im:
                    im.save(ico_path, format="ICO")
                return str(ico_path)
            except Exception:
                return ""

        try:
            if IS_WINDOWS:
                target = str(cmd[0])
                args = " ".join([f'"{str(ca).replace(chr(34), chr(92) + chr(34))}"' for ca in cmd[1:]])
                work_dir = str(target_hint.parent) if target_hint.exists() else str(SCRIPT_DIR)
                icon_loc = _windows_shortcut_icon_source(icon_path, name)

                def _ps_escape(value):
                    return str(value).replace("'", "''")

                shortcut_ps = _ps_escape(shortcut_path)
                target_ps = _ps_escape(target)
                args_ps = _ps_escape(args)
                work_dir_ps = _ps_escape(work_dir)
                icon_ps = _ps_escape(icon_loc) if icon_loc else ""

                ps_script = (
                    "$W=New-Object -ComObject WScript.Shell;"
                    f"$S=$W.CreateShortcut('{shortcut_ps}');"
                    f"$S.TargetPath='{target_ps}';"
                    f"$S.Arguments='{args_ps}';"
                    f"$S.WorkingDirectory='{work_dir_ps}';"
                    + (f"$S.IconLocation='{icon_ps},0';" if icon_ps else "")
                    + "$S.Save();"
                )
                subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=True,
                )
            else:
                exec_cmd = " ".join([f'"{x}"' for x in cmd])
                content = (
                    "\n".join(
                        [
                            "[Desktop Entry]",
                            "Type=Application",
                            f"Name={name}",
                            f"Exec={exec_cmd}",
                            f"Icon={str(icon_path)}" if icon_path else "",
                            "Terminal=false",
                        ]
                    )
                    + "\n"
                )
                shortcut_path.write_text(content, encoding="utf-8")
                shortcut_path.chmod(0o755)
            return f"Created shortcut: {shortcut_path}"
        except Exception as e:
            return f"Failed to create shortcut: {e}"
