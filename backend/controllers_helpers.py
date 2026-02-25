"""
Helper functions for AppController.

These are intentionally pure and stateless so controller methods can stay thin.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any


def achievement_sort_key_desc(item: Any) -> float:
    """Return a comparable timestamp-like key for achievement sorting."""
    if not isinstance(item, dict):
        return 0.0
    raw = item.get("earned")
    if raw is None:
        return 0.0

    if isinstance(raw, (int, float)):
        val = float(raw)
        if val > 1e12:
            val = val / 1000.0
        return val

    text = str(raw).strip()
    if not text:
        return 0.0

    if text.isdigit():
        val = float(text)
        if val > 1e12:
            val = val / 1000.0
        return val

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(text[: len(fmt)], fmt)
            return dt.timestamp()
        except Exception:
            continue

    try:
        iso_text = text.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(iso_text).timestamp()
    except Exception:
        return 0.0


def format_unix_utc(ts: Any) -> str:
    """Format unix timestamp (seconds) into UTC datetime text."""
    try:
        ts_int = int(ts or 0)
    except Exception:
        return ""
    if ts_int <= 0:
        return ""
    try:
        return datetime.datetime.utcfromtimestamp(ts_int).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def detect_steam_id64(config: dict[str, Any], steam_roots: list[Path]) -> str:
    """Return steam64 id from config or by scanning userdata folders."""
    steam_id = str(config.get("steam_id64") or "").strip()
    if steam_id.isdigit():
        return steam_id

    steam64_base = 76561197960265728
    for root in steam_roots:
        userdata_root = root / "userdata"
        if not userdata_root.exists():
            continue
        try:
            for user_dir in userdata_root.iterdir():
                if not user_dir.is_dir():
                    continue
                name = user_dir.name.strip()
                if not name.isdigit():
                    continue
                val = int(name)
                return str(val if val > steam64_base else steam64_base + val)
        except Exception:
            continue
    return ""


def normalize_links_json(links_json: str) -> list[dict[str, str]]:
    """Normalize links payload into [{'type': str, 'url': str}, ...]."""
    normalized: list[dict[str, str]] = []
    try:
        raw = json.loads(links_json or "[]")
    except Exception:
        raw = []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return normalized
    for item in raw:
        if not isinstance(item, dict):
            continue
        link_type = str(item.get("type", "")).strip()
        url = str(item.get("url", "")).strip()
        if not link_type and not url:
            continue
        normalized.append({"type": link_type, "url": url})
    return normalized


def extract_steam_app_id_from_links(links: Any) -> str | None:
    """Extract a Steam app id from known Steam URL patterns."""
    if not isinstance(links, list):
        return None
    patterns = (
        r"store\.steampowered\.com/app/(\d+)",
        r"steamcommunity\.com/app/(\d+)",
        r"steam://rungameid/(\d+)",
        r"/steam/apps/(\d+)",
    )
    for item in links:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        for pat in patterns:
            m = re.search(pat, url, flags=re.IGNORECASE)
            if m:
                return m.group(1)
    return None
