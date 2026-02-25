"""
HowLongToBeat integration operations for AppController.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import time
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from backend.controllers import AppController


class HltbControllerOps:
    """Fetch and store HLTB data for library games."""

    _INIT_URL = "https://howlongtobeat.com/api/finder/init"
    _FINDER_URL = "https://howlongtobeat.com/api/finder"
    _LEGACY_SEARCH_URL = "https://howlongtobeat.com/api/search"

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def _safe_int(self, value, default=0) -> int:
        try:
            if value is None or value == "":
                return default
            return int(value)
        except Exception:
            return default

    def _normalize_hours(self, value) -> float:
        """
        HLTB values are typically provided in seconds by the search API.
        Convert to hours with a tolerant fallback for already-hour values.
        """
        raw = self._safe_int(value, 0)
        if raw <= 0:
            return 0.0
        # If the value looks like a duration in seconds, convert to hours.
        if raw >= 600:
            return round(raw / 3600.0, 2)
        # Tiny values are usually already hours.
        return float(raw)

    def _search(self, game_name: str) -> list[dict]:
        base_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://howlongtobeat.com/",
            "User-Agent": "Mozilla/5.0",
        }
        payload = {
            "searchType": "games",
            "searchTerms": [part for part in game_name.split() if part],
            "searchPage": 1,
            "size": 20,
            "searchOptions": {
                "games": {
                    "userId": 0,
                    "platform": "",
                    "sortCategory": "popular",
                    "rangeCategory": "main",
                    "rangeTime": {"min": None, "max": None},
                    "gameplay": {
                        "perspective": "",
                        "flow": "",
                        "genre": "",
                        "difficulty": "",
                    },
                    "rangeYear": {"min": "", "max": ""},
                    "modifier": "",
                },
                "users": {"sortCategory": "postcount"},
                "filter": "",
                "sort": 0,
                "randomizer": 0,
            },
            "useCache": True,
        }
        session = requests.Session()
        session.headers.update(base_headers)

        # Current HLTB flow: initialize token, then post to /api/finder.
        try:
            init_resp = session.get(
                f"{self._INIT_URL}?t={int(time.time() * 1000)}",
                timeout=12,
            )
            init_resp.raise_for_status()
            init_data = init_resp.json() if init_resp.content else {}
            token = str(init_data.get("token") or "").strip()
            if token:
                finder_headers = dict(base_headers)
                finder_headers["x-auth-token"] = token
                resp = session.post(
                    self._FINDER_URL,
                    json=payload,
                    headers=finder_headers,
                    timeout=12,
                )
                resp.raise_for_status()
                data = resp.json() if resp.content else {}
                items = data.get("data")
                if isinstance(items, list):
                    return [x for x in items if isinstance(x, dict)]
        except Exception:
            pass

        # Legacy fallback (older endpoint shape).
        resp = session.post(
            self._LEGACY_SEARCH_URL,
            json=payload,
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        items = data.get("data")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
        return []

    def _best_match(self, game_name: str, rows: list[dict]) -> dict | None:
        if not rows:
            return None
        name_l = game_name.strip().lower()
        best = None
        best_score = -1.0
        for row in rows:
            candidate = str(row.get("game_name") or "").strip()
            if not candidate:
                continue
            cand_l = candidate.lower()
            if cand_l == name_l:
                return row
            score = SequenceMatcher(None, name_l, cand_l).ratio()
            if score > best_score:
                best = row
                best_score = score
        return best

    def sync_selected_hltb(self) -> str:
        c = self._c
        if not c._selected_game_id:
            return "No game selected."
        game = c._game_manager.get_game(c._selected_game_id) or {}
        game_name = str(game.get("name") or "").strip()
        if not game_name:
            return "Selected game has no name."

        try:
            rows = self._search(game_name)
        except Exception as exc:
            return f"HLTB lookup failed: {exc}"

        match = self._best_match(game_name, rows)
        if not match:
            return f"No HLTB result found for '{game_name}'."

        updated = game.copy()
        updated["hltb_id"] = str(match.get("game_id") or "")
        updated["hltb_name"] = str(match.get("game_name") or game_name)
        updated["hltb_main_hours"] = self._normalize_hours(
            match.get("comp_main", match.get("gameplay_main"))
        )
        updated["hltb_main_extra_hours"] = self._normalize_hours(
            match.get("comp_plus", match.get("gameplay_main_extra"))
        )
        updated["hltb_completionist_hours"] = self._normalize_hours(
            match.get("comp_100", match.get("gameplay_completionist"))
        )

        success, new_id, message = c._game_manager.update_game(c._selected_game_id, updated)
        if not success:
            return message or "Failed to save HLTB data."
        if new_id and new_id != c._selected_game_id:
            c._selected_game_id = new_id
        c._game_model.refresh()
        c.libraryChanged.emit()
        return (
            f"HLTB synced for '{updated.get('name', game_name)}' "
            f"(Main: {updated['hltb_main_hours']}h)."
        )
