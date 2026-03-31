"""
Steam/SteamEmu refresh orchestration extracted from AppController.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

from ui.workers import SteamRefreshWorker, SteamEmuRefreshWorker

if TYPE_CHECKING:
    from backend.controllers import AppController


class SteamControllerOps:
    """Encapsulates Steam and SteamEmu background refresh/poll flows."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def log_steamemu(self, message):
        print(f"[SteamEmu] {message}", flush=True)

    def refresh_steam_achievements(self):
        c = self._c
        try:
            c._steam_service.update_api_key((c._config.get("steam_web_api_key") or "").strip())
            c._steam_service.update_lang((c._config.get("steam_lang") or "en").strip())
            worker = SteamRefreshWorker(c._steam_service)
            worker.signals.progress.connect(self.on_steam_worker_progress)
            worker.signals.game_loaded.connect(self.on_steam_worker_game_loaded)
            worker.signals.unlock_event.connect(self.on_steam_worker_unlock_event)
            worker.signals.error.connect(self.on_steam_worker_error)
            worker.signals.finished.connect(self.on_steam_worker_finished)
            c._steam_thread_pool.start(worker)
            return "Steam achievement refresh started."
        except Exception as exc:
            return f"Steam achievement refresh failed to start: {exc}"

    def on_steam_worker_progress(self, value):
        self._c.steamRefreshProgress.emit(int(value or 0))

    def on_steam_worker_game_loaded(self, payload):
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
        except Exception:
            data = {}
        try:
            from utils.helpers import debug_log
            debug_log(f"[steam] game_loaded payload_type={type(payload).__name__}")
        except Exception:
            pass
        self._c._achievements_ops.on_steam_worker_game_loaded(data)

    def on_steam_worker_unlock_event(self, payload):
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
        except Exception:
            data = {}
        try:
            from utils.helpers import debug_log
            debug_log(f"[steam] unlock_event payload_type={type(payload).__name__}")
        except Exception:
            pass
        self._c._achievements_ops.on_steam_worker_unlock_event(data)

    def on_steam_worker_error(self, message):
        self._c.errorMessage.emit(message)

    def on_steam_worker_finished(self):
        self._c.steamRefreshFinished.emit()

    def refresh_steamemu_achievements(self):
        c = self._c
        try:
            if c._steamemu_manual_refresh_running:
                return "SteamEmu achievement refresh is already running."

            c._steam_emu_service.update_api_key((c._config.get("steam_web_api_key") or "").strip())
            c._steam_emu_service.update_lang((c._config.get("steam_lang") or "en").strip())
            worker = SteamEmuRefreshWorker(c._steam_emu_service, changed_only=False)
            c._steamemu_manual_refresh_running = True
            c._steamemu_manual_games_loaded = 0
            c._steamemu_manual_unlock_events = 0
            c._steamemu_manual_started_at = time.time()
            self.log_steamemu("Manual refresh started.")
            worker.signals.progress.connect(self.on_steamemu_manual_progress)
            worker.signals.game_loaded.connect(self.on_steamemu_manual_game_loaded)
            worker.signals.unlock_event.connect(self.on_steamemu_manual_unlock_event)
            worker.signals.error.connect(self.on_steamemu_manual_error)
            worker.signals.finished.connect(self.on_steamemu_manual_finished)
            c._steam_thread_pool.start(worker)
            return "SteamEmu achievement refresh started."
        except Exception as exc:
            c._steamemu_manual_refresh_running = False
            self.log_steamemu(f"Manual refresh failed to start: {exc}")
            return f"SteamEmu achievement refresh failed to start: {exc}"

    def poll_steamemu_achievements(self):
        c = self._c
        if c._steamemu_watch_running or c._steamemu_manual_refresh_running:
            return
        c._steamemu_watch_running = True
        try:
            worker = SteamEmuRefreshWorker(c._steam_emu_service, changed_only=True)
            worker.signals.progress.connect(self.on_steamemu_worker_progress)
            worker.signals.game_loaded.connect(self.on_steamemu_worker_game_loaded)
            worker.signals.unlock_event.connect(self.on_steamemu_worker_unlock_event)
            worker.signals.error.connect(lambda _msg: None)
            worker.signals.finished.connect(self.on_steamemu_poll_finished)
            c._steam_thread_pool.start(worker)
        except Exception:
            c._steamemu_watch_running = False

    def on_steamemu_worker_progress(self, value):
        self._c.steamEmuRefreshProgress.emit(int(value or 0))

    def on_steamemu_worker_game_loaded(self, payload):
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
        except Exception:
            data = {}
        try:
            from utils.helpers import debug_log
            debug_log(f"[steamemu] game_loaded payload_type={type(payload).__name__}")
        except Exception:
            pass
        self._c._achievements_ops.on_steamemu_worker_game_loaded(data)

    def on_steamemu_worker_unlock_event(self, payload):
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
        except Exception:
            data = {}
        try:
            from utils.helpers import debug_log
            debug_log(f"[steamemu] unlock_event payload_type={type(payload).__name__}")
        except Exception:
            pass
        self._c._achievements_ops.on_steamemu_worker_unlock_event(data)

    def on_steamemu_worker_finished(self):
        self._c.steamEmuRefreshFinished.emit()

    def on_steamemu_poll_finished(self):
        self._c._steamemu_watch_running = False

    def on_steamemu_manual_progress(self, value):
        self.on_steamemu_worker_progress(value)
        self.log_steamemu(f"Manual refresh progress: {int(value or 0)}%")

    def on_steamemu_manual_game_loaded(self, payload):
        c = self._c
        c._steamemu_manual_games_loaded += 1
        self.on_steamemu_worker_game_loaded(payload)
        appid = str((payload or {}).get("appid") or "")
        game = str((payload or {}).get("game") or "")
        details = game or appid or "unknown"
        self.log_steamemu(f"Loaded: {details}")

    def on_steamemu_manual_unlock_event(self, payload):
        c = self._c
        c._steamemu_manual_unlock_events += 1
        self.on_steamemu_worker_unlock_event(payload)
        game = str((payload or {}).get("game") or "unknown")
        achievement = str((payload or {}).get("achievement") or "unknown")
        self.log_steamemu(f"Unlock event: {game} - {achievement}")

    def on_steamemu_manual_error(self, message):
        self.on_steam_worker_error(message)
        self.log_steamemu(f"Error: {message}")

    def on_steamemu_manual_finished(self):
        c = self._c
        elapsed = max(0.0, time.time() - float(c._steamemu_manual_started_at or 0.0))
        c._steamemu_manual_refresh_running = False
        self.on_steamemu_worker_finished()
        self.log_steamemu(
            f"Manual refresh finished in {elapsed:.1f}s "
            f"(games={c._steamemu_manual_games_loaded}, unlock_events={c._steamemu_manual_unlock_events})."
        )
