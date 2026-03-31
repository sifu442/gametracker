from __future__ import annotations

from dataclasses import asdict
import json

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from steam.models import SteamCandidate
from utils.helpers import debug_log
from steam.service import SteamAchievementsService
from steam.emu_service import SteamEmuAchievementsService


class SteamWorkerSignals(QObject):
    """Signals for steam background refresh worker."""

    progress = pyqtSignal(int)
    game_loaded = pyqtSignal(str)
    unlock_event = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class SteamRefreshWorker(QRunnable):
    """QRunnable that refreshes steam achievements off the UI thread."""

    def __init__(self, service: SteamAchievementsService, candidate: SteamCandidate | None = None) -> None:
        super().__init__()
        self.service = service
        self.candidate = candidate
        self.signals = SteamWorkerSignals()

    @pyqtSlot()
    def run(self) -> None:
        """Run worker and emit progress/result signals."""

        try:
            if self.candidate is not None:
                game, events = self.service.refresh_candidate(
                    self.candidate,
                    progress_cb=lambda x: self.signals.progress.emit(int(x)),
                )
                payload = json.dumps(asdict(game))
                debug_log(f"[steam-worker] game_loaded type=str size={len(payload)}")
                self.signals.game_loaded.emit(payload)
                for ev in events:
                    ev_payload = json.dumps(asdict(ev))
                    debug_log(f"[steam-worker] unlock_event type=str size={len(ev_payload)}")
                    self.signals.unlock_event.emit(ev_payload)
            else:
                rows = self.service.refresh_all(progress_cb=lambda x: self.signals.progress.emit(int(x)))
                for game, events in rows:
                    payload = json.dumps(asdict(game))
                    debug_log(f"[steam-worker] game_loaded type=str size={len(payload)}")
                    self.signals.game_loaded.emit(payload)
                    for ev in events:
                        ev_payload = json.dumps(asdict(ev))
                        debug_log(f"[steam-worker] unlock_event type=str size={len(ev_payload)}")
                        self.signals.unlock_event.emit(ev_payload)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class SteamEmuRefreshWorker(QRunnable):
    """QRunnable that refreshes SteamEmu achievements off UI thread."""

    def __init__(self, service: SteamEmuAchievementsService, changed_only: bool = False) -> None:
        super().__init__()
        self.service = service
        self.changed_only = changed_only
        self.signals = SteamWorkerSignals()

    @pyqtSlot()
    def run(self) -> None:
        """Run worker and emit progress/result signals."""

        try:
            if self.changed_only:
                rows = self.service.refresh_changed(progress_cb=lambda x: self.signals.progress.emit(int(x)))
            else:
                rows = self.service.refresh_all(progress_cb=lambda x: self.signals.progress.emit(int(x)))
            for game, events in rows:
                payload = json.dumps(asdict(game))
                debug_log(f"[steamemu-worker] game_loaded type=str size={len(payload)}")
                self.signals.game_loaded.emit(payload)
                for ev in events:
                    ev_payload = json.dumps(asdict(ev))
                    debug_log(f"[steamemu-worker] unlock_event type=str size={len(ev_payload)}")
                    self.signals.unlock_event.emit(ev_payload)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()
