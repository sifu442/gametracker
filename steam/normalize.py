from __future__ import annotations

import xml.etree.ElementTree as ET

from steam.models import AchievementMeta, AchievementState, GameSchema, MergedAchievement


def normalize_schema_api(payload: dict, appid: str) -> GameSchema:
    """Normalize GetSchemaForGame response."""

    game = ((payload or {}).get("game") or {})
    stats = (game.get("availableGameStats") or {})
    raw = stats.get("achievements") or []
    achs: list[AchievementMeta] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        achs.append(
            AchievementMeta(
                name=str(item.get("name") or ""),
                display_name=str(item.get("displayName") or item.get("name") or ""),
                description=str(item.get("description") or ""),
                hidden=bool(int(item.get("hidden") or 0)),
                icon=str(item.get("icon") or ""),
                icongray=str(item.get("icongray") or ""),
            )
        )
    return GameSchema(
        appid=str(appid),
        name=str(game.get("gameName") or ""),
        img={"header": "", "background": "", "portrait": "", "icon": ""},
        achievements=achs,
    )


def normalize_state_api(payload: dict) -> dict[str, AchievementState]:
    """Normalize GetPlayerAchievements response."""

    player = ((payload or {}).get("playerstats") or {})
    raw = player.get("achievements") or []
    out: dict[str, AchievementState] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("apiname") or "")
        if not name:
            continue
        out[name] = AchievementState(
            achieved=int(item.get("achieved") or 0) == 1,
            cur_progress=int(item.get("curprogress") or 0),
            max_progress=int(item.get("maxprogress") or 0),
            unlock_time=int(item.get("unlocktime") or 0),
        )
    return out


def normalize_schema_xml(xml_text: str, appid: str) -> GameSchema:
    """Normalize schema-like metadata from community XML."""

    root = ET.fromstring(xml_text)
    name = root.findtext(".//gameName") or ""
    achs: list[AchievementMeta] = []
    for node in root.findall(".//achievement"):
        key = (node.findtext("apiname") or node.findtext("name") or "").strip()
        if not key:
            continue
        achs.append(
            AchievementMeta(
                name=key,
                display_name=(node.findtext("name") or key).strip(),
                description=(node.findtext("description") or "").strip(),
                hidden=(node.findtext("hidden") or "0").strip() in {"1", "true", "True"},
                icon=(node.findtext("iconClosed") or node.findtext("icon") or "").strip(),
                icongray=(node.findtext("iconOpen") or "").strip(),
            )
        )
    return GameSchema(
        appid=str(appid),
        name=name,
        img={"header": "", "background": "", "portrait": "", "icon": ""},
        achievements=achs,
    )


def normalize_state_xml(xml_text: str) -> dict[str, AchievementState]:
    """Normalize user state from community XML."""

    root = ET.fromstring(xml_text)
    out: dict[str, AchievementState] = {}
    for node in root.findall(".//achievement"):
        key = (node.findtext("apiname") or node.findtext("name") or "").strip()
        if not key:
            continue
        out[key] = AchievementState(
            achieved=(node.findtext("achieved") or "0").strip() in {"1", "true", "True"},
            cur_progress=0,
            max_progress=0,
            unlock_time=int((node.findtext("unlockTimestamp") or "0").strip() or 0),
        )
    return out


def normalize_store_metadata(payload: dict, appid: str) -> tuple[str, dict[str, str]]:
    """Extract canonical game name and image set from store API."""

    entry = (payload or {}).get(str(appid)) or {}
    data = entry.get("data") if isinstance(entry, dict) else {}
    if not isinstance(data, dict):
        return "", {"header": "", "background": "", "portrait": "", "icon": ""}
    imgs = {
        "header": str(data.get("header_image") or ""),
        "background": str(data.get("background_raw") or data.get("background") or ""),
        "portrait": str(data.get("capsule_imagev5") or data.get("capsule_image") or ""),
        "icon": str(data.get("capsule_image") or ""),
    }
    return str(data.get("name") or ""), imgs


def merge_schema_state(schema: GameSchema, state: dict[str, AchievementState]) -> tuple[list[MergedAchievement], int, int]:
    """Merge schema and state by API name."""

    by_name = {a.name: a for a in schema.achievements}
    keys = sorted(set(by_name.keys()) | set(state.keys()))
    rows: list[MergedAchievement] = []
    unlocked = 0
    for key in keys:
        m = by_name.get(key)
        s = state.get(key, AchievementState(False, 0, 0, 0))
        if s.achieved:
            unlocked += 1
        rows.append(
            MergedAchievement(
                name=key,
                display_name=(m.display_name if m else key),
                description=(m.description if m else ""),
                hidden=(m.hidden if m else False),
                icon=(m.icon if m else ""),
                icongray=(m.icongray if m else ""),
                achieved=bool(s.achieved),
                cur_progress=int(s.cur_progress),
                max_progress=int(s.max_progress),
                unlock_time=int(s.unlock_time),
            )
        )
    return rows, unlocked, len(keys)

