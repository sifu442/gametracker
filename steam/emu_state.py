from __future__ import annotations

import configparser
import json
import struct
import zlib
from pathlib import Path

from steam.models import AchievementState


def _parse_ini(path: Path) -> dict[str, AchievementState]:
    out: dict[str, AchievementState] = {}
    cp = configparser.ConfigParser()
    try:
        cp.read(path, encoding="utf-8", errors="ignore")
    except Exception:
        return out

    # Format variants:
    # [achievement_name] achieved=1 unlock_time=...
    # [Stats] ACH_XXX=1
    for section in cp.sections():
        sec_l = section.lower()
        if sec_l in ("steam", "settings", "config"):
            continue
        items = dict(cp.items(section))
        if "achieved" in items:
            key = section
            out[key] = AchievementState(
                achieved=str(items.get("achieved", "0")).strip() in {"1", "true", "True"},
                cur_progress=int(float(items.get("cur_progress", 0) or 0)),
                max_progress=int(float(items.get("max_progress", 0) or 0)),
                unlock_time=int(float(items.get("unlock_time", 0) or 0)),
            )
        else:
            for k, v in items.items():
                if k.lower() in ("appid", "steamappid"):
                    continue
                achieved = str(v).strip() in {"1", "true", "True"}
                out[k] = AchievementState(achieved=achieved, cur_progress=0, max_progress=0, unlock_time=0)
    return out


def _parse_json(path: Path) -> dict[str, AchievementState]:
    out: dict[str, AchievementState] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return out

    # Common variants:
    # {"ACH_NAME": true}
    # {"achievements":{"ACH_NAME":{"Achieved":true,...}}}
    # [{"name":"...","achieved":true}]
    if isinstance(data, dict):
        rows = data.get("achievements") if isinstance(data.get("achievements"), (dict, list)) else data
        if isinstance(rows, dict):
            for k, v in rows.items():
                if isinstance(v, bool):
                    out[str(k)] = AchievementState(v, 0, 0, 0)
                elif isinstance(v, dict):
                    achieved_val = v.get("achieved", v.get("Achieved", v.get("earned", v.get("Earned", False))))
                    unlock_val = v.get("unlock_time", v.get("UnlockTime", v.get("earned_time", v.get("EarnedTime", 0))))
                    out[str(k)] = AchievementState(
                        achieved=bool(achieved_val),
                        cur_progress=int(v.get("cur_progress", v.get("CurProgress", 0)) or 0),
                        max_progress=int(v.get("max_progress", v.get("MaxProgress", 0)) or 0),
                        unlock_time=int(unlock_val or 0),
                    )
        elif isinstance(rows, list):
            for r in rows:
                if not isinstance(r, dict):
                    continue
                name = str(
                    r.get("name")
                    or r.get("api_name")
                    or r.get("achievement_api")
                    or r.get("achievementApi")
                    or r.get("id")
                    or ""
                )
                if not name:
                    continue
                achieved_val = r.get("achieved", r.get("Achieved", r.get("earned", r.get("Earned", False))))
                unlock_val = r.get("unlock_time", r.get("UnlockTime", r.get("earned_time", r.get("EarnedTime", 0))))
                out[name] = AchievementState(
                    achieved=bool(achieved_val),
                    cur_progress=int(r.get("cur_progress", 0) or 0),
                    max_progress=int(r.get("max_progress", 0) or 0),
                    unlock_time=int(unlock_val or 0),
                )
    elif isinstance(data, list):
        for r in data:
            if not isinstance(r, dict):
                continue
            name = str(
                r.get("name")
                or r.get("api_name")
                or r.get("achievement_api")
                or r.get("achievementApi")
                or r.get("id")
                or ""
            )
            if not name:
                continue
            achieved_val = r.get("achieved", r.get("Achieved", r.get("earned", r.get("Earned", False))))
            unlock_val = r.get("unlock_time", r.get("UnlockTime", r.get("earned_time", r.get("EarnedTime", 0))))
            out[name] = AchievementState(
                achieved=bool(achieved_val),
                cur_progress=int(r.get("cur_progress", 0) or 0),
                max_progress=int(r.get("max_progress", 0) or 0),
                unlock_time=int(unlock_val or 0),
            )
    return out


def _crc_key_map(schema_names: list[str]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for name in schema_names:
        crc = zlib.crc32(name.encode("utf-8")) & 0xFFFFFFFF
        mapping[crc] = name
    return mapping


def _parse_bin(path: Path, schema_names: list[str]) -> dict[str, AchievementState]:
    out: dict[str, AchievementState] = {}
    try:
        buf = path.read_bytes()
    except Exception:
        return out
    if not buf:
        return out

    crc_map = _crc_key_map(schema_names)

    # Heuristic SSE-like format: repeated [u32 key][u8 achieved][u32 unlock_time?]
    # Parse as 12-byte stride first, then 8-byte fallback.
    for stride in (12, 8):
        parsed = {}
        pos = 0
        while pos + stride <= len(buf):
            try:
                key = struct.unpack_from("<I", buf, pos)[0]
                achieved = buf[pos + 4] != 0
                unlock = struct.unpack_from("<I", buf, pos + 8)[0] if stride >= 12 else 0
            except Exception:
                break
            name = crc_map.get(key) or f"crc_{key:08x}"
            parsed[name] = AchievementState(achieved=achieved, cur_progress=0, max_progress=0, unlock_time=int(unlock))
            pos += stride
        # Use parse only if non-trivial.
        if len(parsed) >= 1:
            out = parsed
            break
    return out


def load_local_state(path: Path, schema_names: list[str]) -> dict[str, AchievementState]:
    """Parse local emulator achievement file into canonical state map."""

    name = path.name.lower()
    if name.endswith(".json"):
        state = _parse_json(path)
    elif name.endswith(".ini"):
        state = _parse_ini(path)
    elif name.endswith(".bin") or name.endswith(".dat"):
        state = _parse_bin(path, schema_names)
    else:
        state = {}

    if not state or not schema_names:
        return state

    # Map numeric-only keys (achievement_api) to schema names.
    # Some emu formats store ordinal ids (1..N) instead of API names.
    crc_map = _crc_key_map(schema_names)
    remapped: dict[str, AchievementState] = {}
    for key, value in state.items():
        key_str = str(key).strip()
        if not key_str:
            continue
        mapped = None
        if key_str.isdigit():
            try:
                num = int(key_str)
                if 1 <= num <= len(schema_names):
                    mapped = schema_names[num - 1]
                elif 0 <= num < len(schema_names):
                    mapped = schema_names[num]
                else:
                    mapped = crc_map.get(num)
            except Exception:
                mapped = None
        else:
            try:
                if key_str.lower().startswith("0x"):
                    mapped = crc_map.get(int(key_str, 16))
            except Exception:
                mapped = None
        remapped[mapped or key_str] = value
    return remapped
