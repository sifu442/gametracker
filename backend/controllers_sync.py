"""
Library synchronization operations extracted from AppController.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.controllers import AppController


class SyncControllerOps:
    """Encapsulates reload and multi-source library update flows."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def reload(self):
        c = self._c
        c._game_manager.load_library()
        c._game_manager.load_tracking()
        c._game_manager.load_emulators()
        c._apply_ra_mapping_to_library()
        c._game_model.refresh()
        c.libraryChanged.emit()
        c._kick_ra_progress_update()
        c.trackingChanged.emit()
        c.emulatorsChanged.emit()

    def update_library_from_emulators(self):
        c = self._c
        added, skipped = c._game_manager.scan_emulated_games()
        epic_added, epic_updated, epic_skipped = c._game_manager.scan_heroic_legendary()
        riot_added, riot_updated, riot_skipped = c._game_manager.scan_riot_games()
        steam_added, steam_updated, steam_skipped = c._game_manager.scan_steam_games()

        c._apply_ra_mapping_to_library()
        c._game_model.refresh()
        c.libraryChanged.emit()
        c._kick_ra_progress_update()

        return (
            f"Added {added} emulated games, skipped {skipped}. "
            f"Epic: {epic_added} added, {epic_updated} updated, {epic_skipped} skipped. "
            f"Riot: {riot_added} added, {riot_updated} updated, {riot_skipped} skipped. "
            f"Steam: {steam_added} added, {steam_updated} updated, {steam_skipped} skipped."
        )
