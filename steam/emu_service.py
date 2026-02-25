from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from steam.cache import CacheStore
from steam.emu_discovery import EmuAchievementFile, discover_files
from steam.image_fetcher import prefetch_game_icons, resolve_icon_path
from steam.emu_state import load_local_state
from steam.logging import get_logger, slog
from steam.models import MergedGame, UnlockEvent
from steam.normalize import merge_schema_state
from steam.schema import SteamSchemaLoader


class SteamEmuAchievementsService:
    """SteamEmu achievement scanner/merger/diff service."""

    def __init__(self, cache_base: Path, api_key: str = "", lang: str = "en") -> None:
        self.cache = CacheStore(cache_base)
        self.cache.ensure_dirs()
        self.api_key = (api_key or "").strip()
        self.lang = (lang or "en").strip()
        self.logger = get_logger("steam.emu")
        self.schema_loader = SteamSchemaLoader(self.cache, self.logger)
        self._locks: dict[str, Lock] = {}
        self._guard = Lock()
        self._file_mtimes: dict[str, float] = {}
        self._extra_roots: list[str] = []
        self._icons_prefetched: set[str] = set()

    def update_api_key(self, api_key: str) -> None:
        """Update API key."""
        self.api_key = (api_key or "").strip()

    def update_lang(self, lang: str) -> None:
        """Update language."""
        self.lang = (lang or "en").strip()

    def set_extra_roots(self, roots: list[str] | None) -> None:
        """Set additional scan roots provided by user settings."""
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in (roots or []):
            val = str(raw or "").strip()
            if not val:
                continue
            key = val.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(val)
        self._extra_roots = normalized

    def _lock_for(self, key: str) -> Lock:
        with self._guard:
            if key not in self._locks:
                self._locks[key] = Lock()
            return self._locks[key]

    def _state_cache_path(self, appid: str) -> Path:
        return self.cache.user_state_path("emu", appid)

    def _load_prev_state(self, appid: str) -> dict:
        payload = self.cache.read_json(self._state_cache_path(appid)) or {}
        return payload.get("state") if isinstance(payload.get("state"), dict) else {}

    def _save_state(self, appid: str, state: dict) -> None:
        self.cache.write_json(
            self._state_cache_path(appid),
            {"appid": appid, "source": "emu", "fetched_at": int(time.time()), "state": state},
        )

    @staticmethod
    def _unlock_diff(
        appid: str, game_name: str, previous: dict, current: dict, titles: dict, descs: dict, icons: dict | None = None
    ) -> list[UnlockEvent]:
        events: list[UnlockEvent] = []
        for key, cur in current.items():
            prev = previous.get(key, {})
            prev_ach = bool(prev.get("achieved", False))
            cur_ach = bool(cur.get("achieved", False))
            if (not prev_ach) and cur_ach:
                events.append(
                    UnlockEvent(
                        appid=appid,
                        game=game_name,
                        achievement=titles.get(key, key),
                        description=descs.get(key, ""),
                        unlock_time=int(cur.get("unlock_time", 0) or 0),
                        icon_path=((icons or {}).get(key) or ""),
                    )
                )
        events.sort(key=lambda e: e.unlock_time)
        return events

    def refresh_one(self, row: EmuAchievementFile) -> tuple[MergedGame, list[UnlockEvent]] | None:
        """Refresh a single discovered local achievement file."""
        lock = self._lock_for(row.appid)
        with lock:
            schema = self.schema_loader.load(
                appid=row.appid,
                lang=self.lang,
                api_key=self.api_key,
                steam64=None,
            )
            schema_names = [a.name for a in schema.achievements]
            local_state = load_local_state(row.path, schema_names)
            if not local_state and not schema.achievements:
                return None

            merged_rows, unlocked, total = merge_schema_state(schema, local_state)
            refs: list[str] = []
            for m in merged_rows:
                if m.icon:
                    refs.append(m.icon)
                if m.icongray:
                    refs.append(m.icongray)
            do_network_prefetch = row.appid not in self._icons_prefetched
            prefetched = (
                prefetch_game_icons(row.appid, refs, self.cache.base_dir, max_workers=4)
                if do_network_prefetch
                else {}
            )
            for m in merged_rows:
                icon_local = prefetched.get(m.icon) or resolve_icon_path(
                    row.appid,
                    m.icon,
                    self.cache.base_dir,
                    fetch_if_missing=do_network_prefetch,
                )
                gray_local = prefetched.get(m.icongray) or resolve_icon_path(
                    row.appid,
                    m.icongray,
                    self.cache.base_dir,
                    fetch_if_missing=do_network_prefetch,
                )
                m.icon = str(icon_local) if icon_local else m.icon
                m.icongray = str(gray_local) if gray_local else m.icongray
            if do_network_prefetch:
                self._icons_prefetched.add(row.appid)
            game = MergedGame(
                appid=row.appid,
                name=schema.name or f"SteamEmu {row.appid}",
                img=schema.img,
                achievements=merged_rows,
                unlocked=unlocked,
                total=total,
            )

            prev = self._load_prev_state(row.appid)
            cur = {m.name: {"achieved": m.achieved, "unlock_time": m.unlock_time} for m in merged_rows}
            titles = {m.name: m.display_name for m in merged_rows}
            descs = {m.name: m.description for m in merged_rows}
            icons = {m.name: str(m.icon or "") for m in merged_rows}
            events = self._unlock_diff(row.appid, game.name, prev, cur, titles, descs, icons)
            self._save_state(row.appid, cur)

            slog(
                self.logger,
                20,
                "emu_refresh_ok",
                appid=row.appid,
                file=str(row.path),
                unlocked=unlocked,
                total=total,
                new_unlocks=len(events),
            )
            return game, events

    def refresh_all(self, progress_cb=None) -> list[tuple[MergedGame, list[UnlockEvent]]]:
        """Refresh all discovered emulator achievement files."""
        files = discover_files(self._extra_roots)
        results: list[tuple[MergedGame, list[UnlockEvent]]] = []
        if not files:
            return results
        total = len(files)
        for idx, row in enumerate(files, 1):
            if progress_cb:
                progress_cb(int(((idx - 1) / total) * 100))
            out = self.refresh_one(row)
            if out:
                results.append(out)
        if progress_cb:
            progress_cb(100)
        return results

    def prime_watch_index(self) -> None:
        """Index current discovered files without emitting unlock events."""
        for row in discover_files(self._extra_roots):
            try:
                self._file_mtimes[str(row.path).lower()] = row.path.stat().st_mtime
            except Exception:
                continue

    def refresh_changed(self, progress_cb=None) -> list[tuple[MergedGame, list[UnlockEvent]]]:
        """Refresh only files whose mtime changed since last poll."""
        files = discover_files(self._extra_roots)
        changed: list[EmuAchievementFile] = []
        for row in files:
            key = str(row.path).lower()
            try:
                mtime = row.path.stat().st_mtime
            except Exception:
                continue
            prev = self._file_mtimes.get(key)
            self._file_mtimes[key] = mtime
            if prev is None:
                # First sighting is baseline; no popup storm.
                continue
            if mtime > prev:
                changed.append(row)

        if not changed:
            return []

        results: list[tuple[MergedGame, list[UnlockEvent]]] = []
        total = len(changed)
        for idx, row in enumerate(changed, 1):
            if progress_cb:
                progress_cb(int(((idx - 1) / total) * 100))
            out = self.refresh_one(row)
            if out:
                results.append(out)
        if progress_cb:
            progress_cb(100)
        return results
