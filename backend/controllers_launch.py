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
from PyQt6.QtCore import QTimer

from core.constants import COVERS_DIR, HEROES_DIR, IS_LINUX, IS_WINDOWS, LOGOS_DIR, SCRIPT_DIR
from threads.process_monitor import ProcessMonitor
from utils.emulator_launcher import EmulatorLauncher
from utils.game_launcher import GameLauncher
from utils.helpers import debug_log, fix_path_str, resolve_user_path, sanitized_subprocess_env, system_python_path_env

if TYPE_CHECKING:
    from backend.controllers import AppController


class LaunchControllerOps:
    """Encapsulates game launch and tracking lifecycle for AppController."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller
        self._steam_probe_timer = QTimer()
        self._steam_probe_timer.setInterval(250)
        self._steam_probe_timer.timeout.connect(self._probe_steam_game_process)
        self._steam_probe_game_id = ""
        self._steam_probe_target = ""
        self._steam_probe_targets = []
        self._steam_probe_source = ""
        self._steam_probe_install_path = ""
        self._steam_probe_app_id = ""
        self._steam_probe_recover_mode = False
        self._steam_probe_started_at = 0.0
        self._steam_probe_baseline_pids = set()
        self._steam_probe_deadline = 0.0
        self._prev_power_profile = ""
        self._power_profile_armed = False
        self._power_restore_timer = QTimer()
        self._power_restore_timer.setInterval(5000)
        self._power_restore_timer.timeout.connect(self._maybe_restore_linux_power_profile)
        self._pending_restore_process_name = ""
        debug_log("[debug] launch controller initialized")

    def _norm(self, value):
        return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

    def _norm_path(self, value):
        return str(value or "").strip().lower().replace("\\", "/")

    def _path_matches_install(self, install_path_l, exe, cmdline_list):
        install_path_l = self._norm_path(install_path_l).rstrip("/")
        if not install_path_l:
            return False
        exe_l = self._norm_path(exe)
        if exe_l and exe_l.startswith(install_path_l + "/"):
            return True
        for tok in (cmdline_list or []):
            t = self._norm_path(str(tok).strip().strip('"').strip("'"))
            if t.startswith(install_path_l + "/"):
                return True
        return False

    def _dbg(self, message):
        print(message, flush=True)
        debug_log(message)

    def _is_launcher_or_helper_process(self, proc_name, cmdline_l):
        pname = str(proc_name or "").strip().lower()
        if pname in (
            "steam",
            "steam.exe",
            "steamwebhelper",
            "steamwebhelper.exe",
            "heroic",
            "heroic.exe",
            "heroicgameslauncher",
            "legendary",
            "legendary.exe",
            "epicgameslauncher",
            "epicgameslauncher.exe",
            "epicwebhelper",
            "epicwebhelper.exe",
        ):
            return True
        return any(
            token in str(cmdline_l or "")
            for token in (
                "heroicgameslauncher",
                "com.heroicgameslauncher.hgl",
                "heroic://",
                "legendary launch",
                "steamwebhelper",
                "epicwebhelper",
                "epicgameslauncher",
            )
        )

    def _enable_linux_performance_profile(self):
        if not IS_LINUX or self._power_profile_armed:
            return
        powerprofilesctl = shutil.which("powerprofilesctl")
        if not powerprofilesctl:
            self._dbg("[power] powerprofilesctl not found")
            return
        prev = ""
        cmd_env = system_python_path_env()
        try:
            res = subprocess.run(
                [powerprofilesctl, "get"],
                capture_output=True,
                text=True,
                timeout=2,
                env=cmd_env,
            )
            if res.returncode == 0:
                prev = (res.stdout or "").strip()
            else:
                self._dbg(
                    f"[power] get failed rc={res.returncode} stderr={(res.stderr or '').strip()}",
                )
        except Exception:
            prev = ""
            self._dbg("[power] get raised exception")
        try:
            res = subprocess.run(
                [powerprofilesctl, "set", "performance"],
                capture_output=True,
                text=True,
                timeout=3,
                env=cmd_env,
            )
            if res.returncode == 0:
                self._prev_power_profile = prev
                self._power_profile_armed = True
                verify = subprocess.run(
                    [powerprofilesctl, "get"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env=cmd_env,
                )
                current = (verify.stdout or "").strip() if verify.returncode == 0 else "<unknown>"
                self._dbg(f"[power] set performance ok (prev='{prev}', current='{current}')")
            else:
                self._dbg(
                    f"[power] set performance failed rc={res.returncode} "
                    f"stdout={(res.stdout or '').strip()} stderr={(res.stderr or '').strip()}",
                )
        except Exception:
            self._dbg("[power] set performance raised exception")

    def _restore_linux_power_profile(self):
        if not IS_LINUX or not self._power_profile_armed:
            return
        powerprofilesctl = shutil.which("powerprofilesctl")
        if not powerprofilesctl:
            self._prev_power_profile = ""
            self._power_profile_armed = False
            return
        target = (self._prev_power_profile or "").strip().lower()
        cmd_env = system_python_path_env()
        try:
            if target and target != "performance":
                res = subprocess.run(
                    [powerprofilesctl, "set", target],
                    timeout=3,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=cmd_env,
                )
                if res.returncode == 0:
                    self._dbg(f"[power] restored profile '{target}'")
                else:
                    self._dbg(f"[power] restore failed rc={res.returncode} target='{target}'")
        except Exception:
            self._dbg("[power] restore raised exception")
        self._prev_power_profile = ""
        self._power_profile_armed = False
        self._pending_restore_process_name = ""
        self._power_restore_timer.stop()

    def _process_name_running(self, process_name):
        target = str(process_name or "").strip().lower()
        if not target:
            return False
        for proc in psutil.process_iter(["name", "exe", "cmdline"]):
            try:
                name = str(proc.info.get("name") or "").strip().lower()
                exe = str(proc.info.get("exe") or "").strip().lower()
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                if name == target:
                    return True
                if exe and Path(exe).stem.lower() == target:
                    return True
                if cmdline and (f"/{target}" in cmdline or f"\\{target}" in cmdline):
                    return True
            except Exception:
                continue
        return False

    def _maybe_restore_linux_power_profile(self):
        if not self._power_profile_armed:
            self._power_restore_timer.stop()
            self._pending_restore_process_name = ""
            return
        if self._pending_restore_process_name and self._process_name_running(self._pending_restore_process_name):
            return
        self._restore_linux_power_profile()

    def _probe_steam_game_process(self):
        c = self._c
        if not self._steam_probe_game_id:
            self._steam_probe_timer.stop()
            return
        if time.time() > self._steam_probe_deadline:
            self._dbg(
                f"[probe] timeout source={self._steam_probe_source} "
                f"targets={self._steam_probe_targets or [self._steam_probe_target]}",
            )
            # Fallback: if Steam launch probe failed, still mark last played.
            if self._steam_probe_source == "steam" and self._steam_probe_game_id:
                game_data = c._game_manager.get_game(self._steam_probe_game_id)
                if game_data:
                    last_ts = time.time()
                    try:
                        prev = float(game_data.get("last_played") or 0)
                    except Exception:
                        prev = 0
                    if last_ts > prev:
                        game_data["last_played"] = float(last_ts)
                        c._game_manager.save_library()
                        c.libraryChanged.emit()
            self._steam_probe_timer.stop()
            self._steam_probe_game_id = ""
            self._steam_probe_target = ""
            self._steam_probe_targets = []
            self._steam_probe_source = ""
            self._steam_probe_install_path = ""
            self._steam_probe_app_id = ""
            recover_mode = bool(self._steam_probe_recover_mode)
            self._steam_probe_recover_mode = False
            self._steam_probe_started_at = 0.0
            self._steam_probe_baseline_pids = set()
            self._steam_probe_deadline = 0.0
            if recover_mode and c._is_monitoring:
                c._stop_tracking()
            return

        raw_targets = self._steam_probe_targets or ([self._steam_probe_target] if self._steam_probe_target else [])
        targets = [self._norm(t) for t in raw_targets if str(t or "").strip()]
        install_path_l = self._norm_path(self._steam_probe_install_path)
        app_id = str(self._steam_probe_app_id or "").strip()
        best = None
        best_ct = 0.0
        fallback = None
        fallback_ct = 0.0
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "create_time"]):
            try:
                info = proc.info
                pid = int(info.get("pid") or 0)
                if pid <= 0 or pid == os.getpid():
                    continue
                pname = str(info.get("name") or "").lower()
                if self._is_launcher_or_helper_process(pname, ""):
                    continue
                exe = str(info.get("exe") or "")
                exe_name = Path(exe).name.lower() if exe else ""
                if self._is_launcher_or_helper_process(exe_name, ""):
                    continue
                cmdline_list = info.get("cmdline") or []
                cmdline = " ".join(cmdline_list)
                cmdline_l = cmdline.lower()
                if self._is_launcher_or_helper_process(pname, cmdline_l):
                    continue
                hay = " ".join(
                    [
                        str(info.get("name") or ""),
                        exe,
                        cmdline,
                    ]
                )
                hay_norm = self._norm(hay)
                if targets and any(t and t in hay_norm for t in targets):
                    ct = float(info.get("create_time") or 0.0)
                    if ct > best_ct:
                        best_ct = ct
                        best = (pid, ct)
                    continue

                # Fallback matching for Steam/Heroic entries where process_name is unreliable.
                if pid in self._steam_probe_baseline_pids:
                    continue
                ct = float(info.get("create_time") or 0.0)
                if ct < (self._steam_probe_started_at - 2.0):
                    continue
                candidate = False
                if self._path_matches_install(install_path_l, exe, cmdline_list):
                    candidate = True
                if not candidate and app_id and app_id in cmdline_l:
                    candidate = True
                if candidate and ct > fallback_ct:
                    fallback_ct = ct
                    fallback = (pid, ct)
            except Exception:
                continue

        winner = best if best and best[0] > 0 else fallback
        if winner and winner[0] > 0:
            self._steam_probe_timer.stop()
            gid = self._steam_probe_game_id
            source = self._steam_probe_source
            mode = "target" if winner == best else "fallback"
            self._dbg(f"[probe] matched {mode} pid={winner[0]} source={source}")
            self._steam_probe_game_id = ""
            self._steam_probe_target = ""
            self._steam_probe_targets = []
            self._steam_probe_source = ""
            self._steam_probe_install_path = ""
            self._steam_probe_app_id = ""
            self._steam_probe_recover_mode = False
            self._steam_probe_started_at = 0.0
            self._steam_probe_baseline_pids = set()
            self._steam_probe_deadline = 0.0
            # Ensure a stable tracking key for last-played updates.
            game_data = c._game_manager.get_game(gid) if gid else None
            if game_data is not None:
                process_name = str(game_data.get("process_name") or "").strip()
                if not process_name:
                    game_data["process_name"] = str(gid or "").strip()
            c._start_tracking(gid, winner[0], winner[1], None)

    def _find_runtime_pid_for_game(self, game_data):
        targets = [
            str(game_data.get("process_name") or "").strip(),
            str(game_data.get("legendary_app_name") or "").strip(),
            str(game_data.get("heroic_app_name") or "").strip(),
        ]
        norm_targets = [self._norm(t) for t in targets if t]
        install_path_l = self._norm_path(game_data.get("install_path"))
        steam_app_id = str(game_data.get("steam_app_id") or "").strip()
        source = str(game_data.get("source") or "").strip().lower()
        process_name = str(game_data.get("process_name") or "").strip().lower()

        best_pid = 0
        best_ct = 0.0
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "create_time"]):
            try:
                info = proc.info
                pid = int(info.get("pid") or 0)
                if pid <= 0 or pid == os.getpid():
                    continue
                pname = str(info.get("name") or "").lower()
                exe = str(info.get("exe") or "")
                cmdline_list = info.get("cmdline") or []
                cmdline = " ".join(cmdline_list)
                cmdline_l = cmdline.lower()
                if self._is_launcher_or_helper_process(pname, cmdline_l):
                    continue
                hay = f"{pname} {exe} {cmdline}"
                hay_norm = self._norm(hay)
                exe_stem = Path(exe).stem.lower() if exe else ""

                matched = False
                if self._path_matches_install(install_path_l, exe, cmdline_list):
                    matched = True
                elif process_name and (exe_stem == process_name or pname == process_name):
                    matched = True
                elif steam_app_id and steam_app_id in cmdline_l:
                    matched = True
                elif source == "steam" and norm_targets and any(t and t in hay_norm for t in norm_targets):
                    matched = True

                if not matched:
                    continue
                ct = float(info.get("create_time") or 0.0)
                if ct > best_ct:
                    best_ct = ct
                    best_pid = pid
            except Exception:
                continue
        return best_pid, best_ct

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
        c._pending_session_finalize = True
        c._is_monitoring = True
        self._enable_linux_performance_profile()
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

        game_data = c._game_manager.get_game(c._current_game_id) if c._current_game_id else None
        source = str((game_data or {}).get("source") or "").strip().lower()
        is_launcher_managed = source in ("steam", "epic") or bool(
            (game_data or {}).get("legendary_app_name") or (game_data or {}).get("heroic_app_name")
        )
        runtime_managed = bool(getattr(c, "_current_runtime_managed", False))
        runtime_tool = str(getattr(c, "_current_runtime_tool", "") or "").strip().lower()
        if game_data and is_launcher_managed:
            new_pid, new_start = self._find_runtime_pid_for_game(game_data)
            if new_pid and new_pid != int(c._current_pid or 0):
                self._dbg(f"[probe] reattach runtime pid={new_pid} source={source or 'launcher'}")
                if c._session_start:
                    elapsed = int(time.time() - c._session_start)
                    process_name = game_data.get("process_name", "")
                    if process_name and elapsed > 0:
                        current_total = c._game_manager.get_total_playtime(process_name)
                        c._game_manager.set_playtime(process_name, current_total + elapsed)
                c._start_tracking(c._current_game_id, new_pid, new_start or time.time(), None)
                return
            # Bootstrap process ended before main runtime was visible. Keep running state
            # and probe for the actual game process for a short recovery window.
            self._steam_probe_game_id = c._current_game_id
            self._steam_probe_target = str(game_data.get("process_name") or "").strip()
            self._steam_probe_targets = [
                str(game_data.get("process_name") or "").strip(),
                str(game_data.get("legendary_app_name") or "").strip(),
                str(game_data.get("heroic_app_name") or "").strip(),
                str(game_data.get("name") or "").strip(),
            ]
            self._steam_probe_targets = [t for t in self._steam_probe_targets if t]
            self._steam_probe_source = source or "launcher"
            self._steam_probe_install_path = str(game_data.get("install_path") or "")
            self._steam_probe_app_id = str(game_data.get("steam_app_id") or "")
            self._steam_probe_recover_mode = True
            self._steam_probe_started_at = time.time()
            self._steam_probe_baseline_pids = {p.pid for p in psutil.process_iter(["pid"])}
            self._steam_probe_deadline = time.time() + 5.0
            self._steam_probe_timer.start()
            return
        if game_data and runtime_managed and runtime_tool in ("wine", "proton"):
            new_pid, new_start = self._find_runtime_pid_for_game(game_data)
            if new_pid and new_pid != int(c._current_pid or 0):
                self._dbg(f"[probe] reattach runtime pid={new_pid} source=compat")
                if c._session_start:
                    elapsed = int(time.time() - c._session_start)
                    process_name = game_data.get("process_name", "")
                    if process_name and elapsed > 0:
                        current_total = c._game_manager.get_total_playtime(process_name)
                        c._game_manager.set_playtime(process_name, current_total + elapsed)
                c._start_tracking(c._current_game_id, new_pid, new_start or time.time(), None)
                return

        if c._session_start:
            elapsed = int(time.time() - c._session_start)
            if game_data:
                process_name = game_data.get("process_name", "")
                if process_name:
                    current_total = c._game_manager.get_total_playtime(process_name)
                    c._game_manager.set_playtime(process_name, current_total + elapsed)
                    last_ts = time.time()
                    c._game_manager.set_last_played(process_name, last_ts)
                    # Persist last played on the game entry for immediate UI updates.
                    try:
                        prev = float(game_data.get("last_played") or 0)
                    except Exception:
                        prev = 0
                    if last_ts > prev:
                        game_data["last_played"] = float(last_ts)
                        c._game_manager.save_library()
                        c.libraryChanged.emit()
        c._pending_session_finalize = False
        c._stop_tracking()

    def stop_tracking(self):
        c = self._c
        game_data = c._game_manager.get_game(c._current_game_id) if c._current_game_id else None
        process_name = str((game_data or {}).get("process_name") or "").strip().lower()
        if getattr(c, "_pending_session_finalize", False) and c._session_start:
            elapsed = int(time.time() - c._session_start)
            if game_data and process_name:
                if elapsed > 0:
                    current_total = c._game_manager.get_total_playtime(process_name)
                    c._game_manager.set_playtime(process_name, current_total + elapsed)
                last_ts = time.time()
                c._game_manager.set_last_played(process_name, last_ts)
                try:
                    prev = float(game_data.get("last_played") or 0)
                except Exception:
                    prev = 0
                if last_ts > prev:
                    game_data["last_played"] = float(last_ts)
                    c._game_manager.save_library()
                    c.libraryChanged.emit()
            c._pending_session_finalize = False
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
        if self._power_profile_armed and process_name and self._process_name_running(process_name):
            self._pending_restore_process_name = process_name
            self._power_restore_timer.start()
        else:
            self._restore_linux_power_profile()
        c.playbackChanged.emit()
        c.trackingChanged.emit()
        c._game_model.refresh()
        c.libraryChanged.emit()

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
            launch_cmd = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
            if IS_LINUX and launch_cmd and launch_cmd[0] != "game-performance":
                launch_cmd = ["game-performance"] + launch_cmd
            launch_env = sanitized_subprocess_env(env if env is not None else os.environ.copy())
            if IS_LINUX and launch_cmd and launch_cmd[0] == "game-performance":
                launch_env = system_python_path_env(launch_env)
            try:
                proc = subprocess.Popen(launch_cmd, env=launch_env)
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
            if not game_data.get("install_path"):
                install_path = c._game_manager.get_steam_install_path(app_id)
                if install_path:
                    game_data["install_path"] = install_path
                    c._game_manager.save_library()
            # Ensure a stable tracking key for Steam games.
            process_name = str(game_data.get("process_name") or "").strip()
            if not process_name:
                process_name = str(c._selected_game_id or "").strip()
                if process_name:
                    game_data["process_name"] = process_name
                    c._game_manager.save_library()
            # Do not track Steam launcher PID as game runtime; Steam process can stay alive.
            # Steam playtime is read from Steam userdata, not local PID runtime.
            baseline_pids = set()
            try:
                baseline_pids = {p.pid for p in psutil.process_iter(["pid"])}
                subprocess.Popen(cmd)
            except Exception:
                c.errorMessage.emit("Failed to launch Steam.")
                return
            # Mark last played immediately on launch to avoid missed tracking.
            last_ts = time.time()
            if process_name:
                c._game_manager.set_last_played(process_name, last_ts)
                c.trackingChanged.emit()
            try:
                prev = float(game_data.get("last_played") or 0)
            except Exception:
                prev = 0
            if last_ts > prev:
                game_data["last_played"] = float(last_ts)
                c._game_manager.save_library()
                c.libraryChanged.emit()
            # Probe for the actual game process by configured process_name.
            target = str(game_data.get("process_name") or "").strip()
            self._steam_probe_game_id = c._selected_game_id
            self._steam_probe_target = target
            self._steam_probe_targets = [target] if target else []
            self._steam_probe_source = "steam"
            self._steam_probe_install_path = str(game_data.get("install_path") or "")
            self._steam_probe_app_id = str(app_id)
            self._steam_probe_recover_mode = False
            self._steam_probe_started_at = time.time()
            self._steam_probe_baseline_pids = baseline_pids
            self._steam_probe_deadline = time.time() + 60.0
            self._steam_probe_timer.start()
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
            pid_l = str(product_id or "").strip().lower()
            launch_product = pid_l
            launch_patchline = "live"
            if "." in pid_l:
                parts = [p for p in pid_l.split(".") if p]
                if parts:
                    launch_product = parts[0]
                    if len(parts) > 1:
                        launch_patchline = parts[1]
            launch_cmd = [
                client_path,
                f"--launch-product={launch_product}",
                f"--launch-patchline={launch_patchline}",
            ]
            baseline_pids = set()
            try:
                baseline_pids = {p.pid for p in psutil.process_iter(["pid"])}
                launch_env = sanitized_subprocess_env(os.environ.copy())
                subprocess.Popen(launch_cmd, env=launch_env)
            except Exception:
                c.errorMessage.emit("Failed to launch Riot Client.")
                return
            last_ts = time.time()
            process_name = str(game_data.get("process_name") or "").strip()
            if process_name:
                c._game_manager.set_last_played(process_name, last_ts)
                c.trackingChanged.emit()
            try:
                prev = float(game_data.get("last_played") or 0)
            except Exception:
                prev = 0
            if last_ts > prev:
                game_data["last_played"] = float(last_ts)
                c._game_manager.save_library()
                c.libraryChanged.emit()
            self._steam_probe_game_id = c._selected_game_id
            self._steam_probe_target = process_name
            self._steam_probe_targets = [process_name] if process_name else []
            self._steam_probe_source = "riot"
            self._steam_probe_install_path = str(game_data.get("install_path") or "")
            self._steam_probe_app_id = str(product_id)
            self._steam_probe_recover_mode = False
            self._steam_probe_started_at = time.time()
            self._steam_probe_baseline_pids = baseline_pids
            self._steam_probe_deadline = time.time() + 60.0
            self._steam_probe_timer.start()
            return

        if game_data.get("source") == "epic" or game_data.get("legendary_app_name") or game_data.get("heroic_app_name"):
            app_name = game_data.get("heroic_app_name") or game_data.get("legendary_app_name")
            if not app_name:
                c.errorMessage.emit("Epic app id is missing.")
                return
            launcher_kind, cmd = c._game_manager.get_epic_launch_command(app_name)
            if not cmd:
                c.errorMessage.emit("Heroic/Legendary launcher not found.")
                return
            try:
                env = os.environ.copy()
                if launcher_kind == "legendary":
                    cfg_dir = c._game_manager.get_heroic_legendary_config_dir()
                    if cfg_dir:
                        env["LEGENDARY_CONFIG_PATH"] = str(cfg_dir)
                        env["LEGENDARY_CONFIG_DIR"] = str(cfg_dir)
                        env.setdefault("XDG_CONFIG_HOME", str(cfg_dir.parent.parent))
            except Exception:
                c.errorMessage.emit("Failed to prepare Epic launcher environment.")
                return
            # Heroic/Legendary launchers can exit before the real game process.
            # On Linux, probe for the actual game process instead of tracking launcher PID.
            launch_cmd = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
            if IS_LINUX and launch_cmd and launch_cmd[0] != "game-performance":
                launch_cmd = ["game-performance"] + launch_cmd
            launch_env = sanitized_subprocess_env(env if env is not None else os.environ.copy())
            if IS_LINUX and launch_cmd and launch_cmd[0] == "game-performance":
                launch_env = system_python_path_env(launch_env)
            baseline_pids = set()
            try:
                baseline_pids = {p.pid for p in psutil.process_iter(["pid"])}
                self._dbg(f"[epic] launcher={launcher_kind} cmd={launch_cmd}")
                subprocess.Popen(launch_cmd, env=launch_env)
            except Exception:
                c.errorMessage.emit("Failed to launch Epic game.")
                return
            target = str(game_data.get("process_name") or "").strip() or str(app_name).strip()
            if target:
                probe_targets = [target, str(app_name or "").strip(), str(game_data.get("name") or "").strip()]
                probe_targets = [t for t in probe_targets if t]
                self._steam_probe_game_id = c._selected_game_id
                self._steam_probe_target = target
                self._steam_probe_targets = probe_targets
                self._steam_probe_source = "epic"
                self._steam_probe_install_path = str(game_data.get("install_path") or "")
                self._steam_probe_app_id = ""
                self._steam_probe_recover_mode = False
                self._steam_probe_started_at = time.time()
                self._steam_probe_baseline_pids = baseline_pids
                self._steam_probe_deadline = time.time() + 90.0
                self._steam_probe_timer.start()
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
        env_vars = game_data.get("env_vars")
        if not env_vars:
            legacy = (game_data.get("wine_dll_overrides") or "").strip()
            if legacy:
                env_vars = f"WINEDLLOVERRIDES={legacy}"
        launch_options = (game_data.get("launch_options") or "").strip() or None
        proc, pid, start_time = GameLauncher.launch_game(
            exe_path,
            use_proton=bool(game_data.get("proton_path")),
            proton_path=game_data.get("proton_path"),
            compat_tool=game_data.get("compat_tool"),
            compat_path=game_data.get("wine_prefix"),
            env_vars=env_vars,
            launch_options=launch_options,
            wine_esync=game_data.get("wine_esync"),
            wine_fsync=game_data.get("wine_fsync"),
            proton_wayland=game_data.get("proton_wayland"),
            proton_discord_rich_presence=game_data.get("proton_discord_rich_presence"),
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

    def _build_shortcut_payload(self, game_data):
        c = self._c
        raw_name = (game_data.get("name") or "Game").strip()
        if IS_WINDOWS:
            name = re.sub(r"[<>:\"/\\|?*]+", "_", raw_name).strip(" .") or "Game"
        else:
            name = raw_name.replace("/", "_") or "Game"

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

        return name, cmd, target_hint, icon_path

    def _write_windows_shortcut(self, shortcut_path, cmd, target_hint, icon_path, name):
        target = str(cmd[0])
        args = " ".join([f'"{str(ca).replace(chr(34), chr(92) + chr(34))}"' for ca in cmd[1:]])
        work_dir = str(target_hint.parent) if target_hint.exists() else str(SCRIPT_DIR)

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

    def _write_linux_desktop_shortcut(self, shortcut_path, cmd, icon_path, name):
        exec_cmd = " ".join([f'"{x}"' for x in cmd])
        content = (
            "\n".join(
                [
                    "[Desktop Entry]",
                    "Type=Application",
                    f"Name={name}",
                    f"Exec={exec_cmd}",
                    f"Icon={str(icon_path)}" if icon_path else "",
                    "Categories=Game;",
                    "Terminal=false",
                ]
            )
            + "\n"
        )
        shortcut_path.write_text(content, encoding="utf-8")
        shortcut_path.chmod(0o755)

    def create_desktop_shortcut(self):
        c = self._c
        game_data = c._game_manager.get_game(c._selected_game_id) if c._selected_game_id else None
        if not game_data:
            return "No game selected."

        try:
            name, cmd, target_hint, icon_path = self._build_shortcut_payload(game_data)
            if IS_WINDOWS:
                desktop = Path(os.environ.get("USERPROFILE", "")) / "Desktop"
                desktop.mkdir(parents=True, exist_ok=True)
                shortcut_path = desktop / f"{name}.lnk"
            else:
                desktop = Path.home() / "Desktop"
                desktop.mkdir(parents=True, exist_ok=True)
                shortcut_path = desktop / f"{name}.desktop"
            if IS_WINDOWS:
                self._write_windows_shortcut(shortcut_path, cmd, target_hint, icon_path, name)
            else:
                self._write_linux_desktop_shortcut(shortcut_path, cmd, icon_path, name)
            return f"Created shortcut: {shortcut_path}"
        except Exception as e:
            return f"Failed to create shortcut: {e}"

    def create_start_menu_shortcut(self):
        c = self._c
        game_data = c._game_manager.get_game(c._selected_game_id) if c._selected_game_id else None
        if not game_data:
            return "No game selected."

        try:
            name, cmd, target_hint, icon_path = self._build_shortcut_payload(game_data)
            if IS_WINDOWS:
                start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
                start_menu.mkdir(parents=True, exist_ok=True)
                shortcut_path = start_menu / f"{name}.lnk"
                self._write_windows_shortcut(shortcut_path, cmd, target_hint, icon_path, name)
            else:
                start_menu = Path.home() / ".local" / "share" / "applications"
                start_menu.mkdir(parents=True, exist_ok=True)
                shortcut_path = start_menu / f"{name}.desktop"
                self._write_linux_desktop_shortcut(shortcut_path, cmd, icon_path, name)
            return f"Created start menu shortcut: {shortcut_path}"
        except Exception as e:
            return f"Failed to create start menu shortcut: {e}"
