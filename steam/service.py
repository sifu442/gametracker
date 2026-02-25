from __future__ import annotations

from dataclasses import asdict
from threading import Lock
from pathlib import Path

from steam.cache import CacheStore
from steam.discovery import discover_candidates, find_steam_root
from steam.image_fetcher import prefetch_game_icons, resolve_icon_path
from steam.logging import get_logger, slog
from steam.models import MergedGame, SteamCandidate, UnlockEvent
from steam.normalize import merge_schema_state
from steam.schema import SteamSchemaLoader
from steam.state import SteamStateLoader


class SteamAchievementsService:
    """Orchestrate Steam discovery, fetch, merge and diff."""

    def __init__(self, cache_base: Path, api_key: str = "", lang: str = "en") -> None:
        self.cache = CacheStore(cache_base)
        self.cache.ensure_dirs()
        self.api_key = (api_key or "").strip()
        self.lang = (lang or "en").strip()
        self.logger = get_logger("steam.service")
        self.schema_loader = SteamSchemaLoader(self.cache, self.logger)
        self.state_loader = SteamStateLoader(self.cache, self.logger)
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def update_api_key(self, api_key: str) -> None:
        """Update API key at runtime."""

        self.api_key = (api_key or "").strip()

    def update_lang(self, lang: str) -> None:
        """Update language at runtime."""

        self.lang = (lang or "en").strip()

    @staticmethod
    def _steam64(steam_user: str) -> str:
        v = int(steam_user)
        return str(v if v > 76561197960265728 else (76561197960265728 + v))

    def _lock_for(self, key: str) -> Lock:
        with self._locks_guard:
            if key not in self._locks:
                self._locks[key] = Lock()
            return self._locks[key]

    def discover(self) -> list[SteamCandidate]:
        """Discover local candidate pairs from Steam cache."""

        root = find_steam_root()
        if not root:
            return []
        return discover_candidates(root)

    def _unlock_diff(
        self,
        appid: str,
        game_name: str,
        previous: dict,
        current: dict,
        title_map: dict[str, str],
        desc_map: dict[str, str],
        icon_map: dict[str, str] | None = None,
    ) -> list[UnlockEvent]:
        events: list[UnlockEvent] = []
        for key, cur in current.items():
            prev = previous.get(key)
            prev_achieved = bool(getattr(prev, "achieved", False))
            cur_achieved = bool(getattr(cur, "achieved", False))
            if (not prev_achieved) and cur_achieved:
                events.append(
                    UnlockEvent(
                        appid=appid,
                        game=game_name,
                        achievement=title_map.get(key, key),
                        description=desc_map.get(key, ""),
                        unlock_time=int(getattr(cur, "unlock_time", 0)),
                        icon_path=((icon_map or {}).get(key) or ""),
                    )
                )
        events.sort(key=lambda x: x.unlock_time)
        return events

    def refresh_candidate(self, candidate: SteamCandidate, progress_cb=None) -> tuple[MergedGame, list[UnlockEvent]]:
        """Refresh one candidate and return merged game + unlock diff events."""

        lock = self._lock_for(f"{candidate.steam_user}:{candidate.appid}")
        with lock:
            if progress_cb:
                progress_cb(5)
            steam64 = self._steam64(candidate.steam_user)
            schema = self.schema_loader.load(
                appid=candidate.appid,
                lang=self.lang,
                api_key=self.api_key,
                steam64=steam64,
            )
            if progress_cb:
                progress_cb(35)

            current_state, previous_state = self.state_loader.load(
                appid=candidate.appid,
                steam_user=candidate.steam_user,
                steam64=steam64,
                stats_file=candidate.stats_file,
                api_key=self.api_key,
            )
            if progress_cb:
                progress_cb(70)

            rows, unlocked, total = merge_schema_state(schema, current_state)

            for slot in ("header", "background", "portrait", "icon"):
                ref = schema.img.get(slot, "")
                local = resolve_icon_path(candidate.appid, ref, self.cache.base_dir)
                schema.img[slot] = str(local) if local else ref

            merged_rows = []
            title_map: dict[str, str] = {}
            desc_map: dict[str, str] = {}
            icon_map: dict[str, str] = {}
            all_refs: list[str] = []
            for row in rows:
                if row.icon:
                    all_refs.append(row.icon)
                if row.icongray:
                    all_refs.append(row.icongray)
            prefetched = prefetch_game_icons(candidate.appid, all_refs, self.cache.base_dir, max_workers=4)
            for row in rows:
                icon_local = prefetched.get(row.icon) or resolve_icon_path(candidate.appid, row.icon, self.cache.base_dir)
                gray_local = prefetched.get(row.icongray) or resolve_icon_path(
                    candidate.appid, row.icongray, self.cache.base_dir
                )
                row.icon = str(icon_local) if icon_local else row.icon
                row.icongray = str(gray_local) if gray_local else row.icongray
                merged_rows.append(row)
                title_map[row.name] = row.display_name
                desc_map[row.name] = row.description
                icon_map[row.name] = str(icon_local) if icon_local else ""

            game = MergedGame(
                appid=candidate.appid,
                name=schema.name or f"Steam {candidate.appid}",
                img=schema.img,
                achievements=merged_rows,
                unlocked=unlocked,
                total=total,
            )

            events = self._unlock_diff(
                appid=candidate.appid,
                game_name=game.name,
                previous=previous_state,
                current=current_state,
                title_map=title_map,
                desc_map=desc_map,
                icon_map=icon_map,
            )

            slog(
                self.logger,
                20,
                "refresh_candidate_ok",
                appid=candidate.appid,
                user=candidate.steam_user,
                unlocked=unlocked,
                total=total,
                new_unlocks=len(events),
            )
            if progress_cb:
                progress_cb(100)
            return game, events

    def refresh_all(self, progress_cb=None) -> list[tuple[MergedGame, list[UnlockEvent]]]:
        """Refresh all discovered candidates."""

        candidates = self.discover()
        if not candidates:
            return []
        out: list[tuple[MergedGame, list[UnlockEvent]]] = []
        total = len(candidates)
        for idx, candidate in enumerate(candidates, 1):
            if progress_cb:
                progress_cb(int(((idx - 1) / total) * 100))
            out.append(self.refresh_candidate(candidate))
        if progress_cb:
            progress_cb(100)
        return out

    def refresh_for_appid(self, appid: str, progress_cb=None) -> tuple[MergedGame, list[UnlockEvent]] | None:
        """Refresh first discovered candidate for appid."""

        for cand in self.discover():
            if str(cand.appid) == str(appid):
                return self.refresh_candidate(cand, progress_cb=progress_cb)
        return None

    @staticmethod
    def game_to_dict(game: MergedGame) -> dict:
        """Serialize merged game dataclass."""

        return asdict(game)
