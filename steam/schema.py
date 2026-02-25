from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

import requests

from steam.cache import CacheStore
from steam.logging import slog
from steam.models import AchievementMeta, GameSchema
from steam.normalize import normalize_schema_api, normalize_schema_xml, normalize_store_metadata


class SteamSchemaLoader:
    """Load game schema with cache-first and API/XML fallbacks."""

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

    def load(self, appid: str, lang: str, api_key: str, steam64: str | None = None, ttl_seconds: int = 604800) -> GameSchema:
        """Load schema; never throw on upstream failure."""

        cpath = self.cache.schema_path(lang, appid)
        cached = self.cache.read_json(cpath)
        if cached and not self.cache.is_stale(cpath, ttl_seconds):
            try:
                achs = [AchievementMeta(**row) for row in (cached.get("achievements") or [])]
                return GameSchema(
                    appid=str(cached.get("appid") or appid),
                    name=str(cached.get("name") or ""),
                    img=dict(cached.get("img") or {"header": "", "background": "", "portrait": "", "icon": ""}),
                    achievements=achs,
                )
            except Exception:
                pass

        schema = GameSchema(appid=appid, name="", img={"header": "", "background": "", "portrait": "", "icon": ""}, achievements=[])

        if api_key:
            payload = self._get_json(
                "https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v0002/",
                {"key": api_key, "appid": appid, "l": lang, "format": "json"},
            )
            if payload and payload.get("game"):
                schema = normalize_schema_api(payload, appid)
                slog(self.logger, 20, "schema_api_ok", appid=appid, lang=lang)

        if not schema.achievements and steam64:
            xml = self._get_text(f"https://steamcommunity.com/profiles/{steam64}/stats/{appid}/?xml=1")
            if xml:
                try:
                    schema = normalize_schema_xml(xml, appid)
                    slog(self.logger, 20, "schema_xml_ok", appid=appid, steam64=steam64)
                except Exception as exc:
                    slog(self.logger, 30, "schema_xml_parse_failed", appid=appid, error=str(exc))

        store = self._get_json(
            "https://store.steampowered.com/api/appdetails",
            {"appids": appid, "cc": "us", "l": lang},
        )
        if store:
            s_name, s_img = normalize_store_metadata(store, appid)
            if s_name and not schema.name:
                schema.name = s_name
            schema.img.update(s_img)

        self.cache.write_json(
            cpath,
            {
                "appid": schema.appid,
                "name": schema.name,
                "img": schema.img,
                "achievements": [asdict(a) for a in schema.achievements],
                "fetched_at": int(time.time()),
            },
        )
        return schema

