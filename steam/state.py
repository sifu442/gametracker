from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests

from steam.cache import CacheStore
from steam.logging import slog
from steam.models import AchievementState
from steam.normalize import normalize_state_api, normalize_state_xml


class SteamStateLoader:
    """Load user achievement state with cache freshness and fallbacks."""

    def __init__(self, cache: CacheStore, logger: Any) -> None:
        self.cache = cache
        self.logger = logger

    def _get_json(self, url: str, params: dict[str, str], retries: int = 2, timeout: int = 15) -> dict | None:
        for attempt in range(retries + 1):
            try:
                resp = requests.get(url, params=params, timeout=timeout)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
        return None

    def _get_text(self, url: str, retries: int = 2, timeout: int = 15) -> str | None:
        for attempt in range(retries + 1):
            try:
                resp = requests.get(url, timeout=timeout)
                if resp.status_code == 200:
                    return resp.text
            except Exception:
                pass
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
        return None

    @staticmethod
    def _decode_state(payload: dict | None) -> dict[str, AchievementState]:
        if not payload:
            return {}
        rows = payload.get("state") or {}
        if not isinstance(rows, dict):
            return {}
        out: dict[str, AchievementState] = {}
        for key, row in rows.items():
            if not isinstance(row, dict):
                continue
            out[str(key)] = AchievementState(
                achieved=bool(row.get("achieved", False)),
                cur_progress=int(row.get("cur_progress", 0)),
                max_progress=int(row.get("max_progress", 0)),
                unlock_time=int(row.get("unlock_time", 0)),
            )
        return out

    def load(
        self,
        appid: str,
        steam_user: str,
        steam64: str,
        stats_file: Path,
        api_key: str,
        ttl_seconds: int = 3600,
    ) -> tuple[dict[str, AchievementState], dict[str, AchievementState]]:
        """Return current state and previous state for diffing."""

        cpath = self.cache.user_state_path(steam_user, appid)
        previous = self._decode_state(self.cache.read_json(cpath))

        refresh_needed = True
        if cpath.exists():
            if stats_file.exists() and self.cache.newer_than(stats_file, cpath):
                refresh_needed = True
            else:
                refresh_needed = self.cache.is_stale(cpath, ttl_seconds)
        if not refresh_needed:
            return previous, previous

        current: dict[str, AchievementState] = {}
        if api_key:
            payload = self._get_json(
                "https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v0001/",
                {"appid": appid, "key": api_key, "steamid": steam64},
            )
            if payload:
                try:
                    current = normalize_state_api(payload)
                    slog(self.logger, 20, "state_api_ok", appid=appid, user=steam_user)
                except Exception as exc:
                    slog(self.logger, 30, "state_api_parse_failed", appid=appid, user=steam_user, error=str(exc))

        if not current:
            xml = self._get_text(f"https://steamcommunity.com/profiles/{steam64}/stats/{appid}/?xml=1")
            if xml:
                try:
                    current = normalize_state_xml(xml)
                    slog(self.logger, 20, "state_xml_ok", appid=appid, user=steam_user)
                except Exception as exc:
                    slog(self.logger, 30, "state_xml_parse_failed", appid=appid, user=steam_user, error=str(exc))

        if current:
            self.cache.write_json(
                cpath,
                {
                    "appid": appid,
                    "steam_user": steam_user,
                    "steam64": steam64,
                    "stats_mtime": int(stats_file.stat().st_mtime) if stats_file.exists() else 0,
                    "fetched_at": int(time.time()),
                    "state": {k: asdict(v) for k, v in current.items()},
                },
            )
            return current, previous

        return previous, previous

