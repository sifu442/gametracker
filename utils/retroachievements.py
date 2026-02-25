import hashlib
import json
import io
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request


API_BASE = "https://retroachievements.org/API/"


def _extract_achievements_map(game_extended_payload):
    """
    Normalize achievement metadata payload into a dict keyed by achievement id (string).
    Supports both wrapped and unwrapped payload shapes.
    """
    if not isinstance(game_extended_payload, dict):
        return {}

    raw = game_extended_payload.get("Achievements", game_extended_payload)
    out = {}

    if isinstance(raw, dict):
        # Wrapped dict: {"Achievements": {"1": {...}}}
        # Or direct dict keyed by id.
        for key, value in raw.items():
            # Ignore non-achievement sections if payload is top-level.
            if key in ("Success", "Error", "Title", "ID"):
                continue
            out[str(key)] = value if isinstance(value, dict) else {}
        return out

    if isinstance(raw, list):
        # Some shapes may use a list of achievement objects.
        for item in raw:
            if not isinstance(item, dict):
                continue
            ach_id = item.get("ID") or item.get("AchievementID") or item.get("id")
            if ach_id is None:
                continue
            out[str(ach_id)] = item
    return out


def _fetch_game_info_with_user_progress(username, api_key, game_id):
    """
    Fetch API_GetGameInfoAndUserProgress response.
    Returns parsed dict or {} on failure.
    """
    params = urlencode({"z": username, "y": api_key, "u": username, "g": game_id})
    url = f"{API_BASE}API_GetGameInfoAndUserProgress.php?{params}"
    req = Request(url, headers={"User-Agent": "GameTracker/1.0"})
    with urlopen(req, timeout=20) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    try:
        data = json.loads(payload)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _extract_unlocks_map(unlocks_payload):
    """
    Normalize unlock payload into a dict keyed by achievement id (string).
    Supports wrapped and unwrapped API_GetAchievementUnlocks responses.
    """
    if not isinstance(unlocks_payload, dict):
        return {}

    # Seen shapes:
    # 1) {"Achievements": {...}}
    # 2) {"Unlocks": {...}}
    # 3) {"UserUnlocks": [ids]}
    # 4) unwrapped dict/list payloads
    if "Achievements" in unlocks_payload:
        raw = unlocks_payload.get("Achievements")
    elif "Unlocks" in unlocks_payload:
        raw = unlocks_payload.get("Unlocks")
    elif "UserUnlocks" in unlocks_payload:
        raw = unlocks_payload.get("UserUnlocks")
    else:
        raw = unlocks_payload
    out = {}

    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in ("Success", "Error", "User"):
                continue
            out[str(key)] = value
        return out

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                ach_id = item.get("ID") or item.get("AchievementID") or item.get("id")
                if ach_id is None:
                    continue
                out[str(ach_id)] = item
                continue
            # Some responses can be a plain list of achievement IDs.
            ach_id = str(item).strip()
            if ach_id:
                out[ach_id] = True
        return out

    if isinstance(raw, str):
        # Some responses can be comma-separated achievement IDs.
        for item in raw.split(","):
            ach_id = item.strip()
            if ach_id:
                out[ach_id] = True
    return out


def _extract_earned_value(unlock_info):
    """Return a truthy earned marker/date if unlocked, else None."""
    if isinstance(unlock_info, dict):
        # Known RA keys first
        earned = unlock_info.get("DateEarned") or unlock_info.get("DateEarnedHardcore")
        if earned:
            return earned
        # Fallback: any date-like earned key
        for key, value in unlock_info.items():
            key_lower = str(key).lower()
            if "dateearned" in key_lower and value:
                return value
        return None
    if unlock_info is None:
        return None
    if isinstance(unlock_info, bool):
        return "1" if unlock_info else None
    text = str(unlock_info).strip()
    return text or None


def hash_rom_md5(rom_path, chunk_size=8 * 1024 * 1024):
    """Return MD5 hash for a ROM file, or None if missing."""
    path = Path(rom_path)
    if not path.exists() or not path.is_file():
        return None
    md5 = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            md5.update(chunk)
    return md5.hexdigest()


def _read_iso_file_bytes(iso, iso_path):
    out = io.BytesIO()
    iso.get_file_from_iso_fp(out, iso_path=iso_path)
    return out.getvalue()


def _find_system_cnf_iso_path(iso):
    candidates = [
        "/SYSTEM.CNF;1",
        "/system.cnf;1",
    ]
    for candidate in candidates:
        try:
            _ = _read_iso_file_bytes(iso, candidate)
            return candidate
        except Exception:
            continue
    return None


def _boot2_to_iso_path(boot2_value):
    # Example: cdrom0:\\SLUS_203.12;1
    value = (boot2_value or "").strip().strip('"').strip("'")
    value = value.replace("\\", "/")
    value = re.sub(r"^cdrom0:\s*", "", value, flags=re.IGNORECASE)
    if not value.startswith("/"):
        value = "/" + value
    if ";" not in value:
        value = value + ";1"
    return value


def hash_ps2_disc_primary_executable(rom_path):
    """
    Compute PS2-style hash:
    1) Read SYSTEM.CNF, parse BOOT2=
    2) Append executable path string bytes
    3) Append executable file bytes
    4) MD5 hash buffer
    """
    try:
        import pycdlib
    except Exception:
        return None

    path = Path(rom_path)
    if not path.exists() or not path.is_file():
        return None
    if path.suffix.lower() != ".iso":
        return None

    iso = pycdlib.PyCdlib()
    try:
        iso.open(str(path))
        system_cnf_iso_path = _find_system_cnf_iso_path(iso)
        if not system_cnf_iso_path:
            return None

        system_cnf_bytes = _read_iso_file_bytes(iso, system_cnf_iso_path)
        text = system_cnf_bytes.decode("utf-8", errors="ignore")

        boot2_value = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.upper().startswith("BOOT2"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    boot2_value = parts[1].strip()
                    break
        if not boot2_value:
            return None

        exe_iso_path = _boot2_to_iso_path(boot2_value)
        exe_bytes = _read_iso_file_bytes(iso, exe_iso_path)

        buffer = bytearray()
        buffer.extend(exe_iso_path.encode("utf-8", errors="ignore"))
        buffer.extend(exe_bytes)
        return hashlib.md5(buffer).hexdigest()
    except Exception:
        return None
    finally:
        try:
            iso.close()
        except Exception:
            pass


def get_rom_hash_for_ra(rom_path, platform=""):
    platform_name = (platform or "").strip().lower()
    if platform_name in ("playstation 2", "ps2"):
        custom_hash = hash_ps2_disc_primary_executable(rom_path)
        if custom_hash:
            return custom_hash
    return hash_rom_md5(rom_path)


def get_game_id_by_hash(username, api_key, rom_md5):
    """Return RetroAchievements game ID for a ROM hash, or None."""
    if not username or not api_key or not rom_md5:
        return None
    params = urlencode({"z": username, "y": api_key, "s": rom_md5})
    url = f"{API_BASE}API_GetGameID.php?{params}"
    req = Request(url, headers={"User-Agent": "GameTracker/1.0"})
    with urlopen(req, timeout=20) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    try:
        data = json.loads(payload)
    except Exception:
        return None
    game_id = data.get("GameID")
    try:
        game_id = int(game_id)
    except Exception:
        return None
    return game_id if game_id > 0 else None


def get_achievement_progress(username, api_key, game_id):
    """Return (unlocked, total) achievements for a game."""
    if not username or not api_key or not game_id:
        return 0, 0

    params_game = urlencode({"z": username, "y": api_key, "i": game_id})
    url_game = f"{API_BASE}API_GetGameExtended.php?{params_game}"
    req_game = Request(url_game, headers={"User-Agent": "GameTracker/1.0"})
    with urlopen(req_game, timeout=20) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    try:
        data = json.loads(payload)
    except Exception:
        return 0, 0

    achievements = _extract_achievements_map(data)
    total = len(achievements)

    unlocks_data = {}
    unlocks = {}
    for game_param in ("i", "g"):
        params_unlocks = urlencode({"z": username, "y": api_key, "u": username, game_param: game_id})
        url_unlocks = f"{API_BASE}API_GetAchievementUnlocks.php?{params_unlocks}"
        req_unlocks = Request(url_unlocks, headers={"User-Agent": "GameTracker/1.0"})
        with urlopen(req_unlocks, timeout=20) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        try:
            unlocks_data = json.loads(payload)
        except Exception:
            unlocks_data = {}
        unlocks = _extract_unlocks_map(unlocks_data)
        if unlocks:
            break

    unlocked = 0
    for _, info in unlocks.items():
        if _extract_earned_value(info):
            unlocked += 1

    # Fallback: some accounts/platforms provide user progress here more reliably.
    if unlocked == 0 and total > 0:
        try:
            progress_data = _fetch_game_info_with_user_progress(username, api_key, game_id)
            progress_achievements = _extract_achievements_map(progress_data)
            if progress_achievements:
                total = len(progress_achievements)
                unlocked = 0
                for _, info in progress_achievements.items():
                    if _extract_earned_value(info):
                        unlocked += 1
        except Exception:
            pass
    return unlocked, total


def get_unlocked_achievements(username, api_key, game_id):
    """Return (unlocked_list, total) where list has unlocked achievement details."""
    if not username or not api_key or not game_id:
        return [], 0

    params_game = urlencode({"z": username, "y": api_key, "i": game_id})
    url_game = f"{API_BASE}API_GetGameExtended.php?{params_game}"
    req_game = Request(url_game, headers={"User-Agent": "GameTracker/1.0"})
    with urlopen(req_game, timeout=20) as resp:
        payload = resp.read().decode("utf-8", errors="ignore")
    try:
        data = json.loads(payload)
    except Exception:
        return [], 0

    achievements = _extract_achievements_map(data)
    total = len(achievements)

    unlocks_data = {}
    unlocks = {}
    for game_param in ("i", "g"):
        params_unlocks = urlencode({"z": username, "y": api_key, "u": username, game_param: game_id})
        url_unlocks = f"{API_BASE}API_GetAchievementUnlocks.php?{params_unlocks}"
        req_unlocks = Request(url_unlocks, headers={"User-Agent": "GameTracker/1.0"})
        with urlopen(req_unlocks, timeout=20) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        try:
            unlocks_data = json.loads(payload)
        except Exception:
            unlocks_data = {}
        unlocks = _extract_unlocks_map(unlocks_data)
        if unlocks:
            break

    unlocked_list = []
    for ach_id, info in unlocks.items():
        earned = _extract_earned_value(info)
        if not earned:
            continue
        meta = achievements.get(str(ach_id)) or achievements.get(ach_id) or {}
        badge = meta.get("BadgeName") or ""
        unlocked_list.append(
            {
                "id": ach_id,
                "title": meta.get("Title") or "",
                "description": meta.get("Description") or "",
                "earned": earned,
                "points": meta.get("Points") or 0,
                "icon": f"https://media.retroachievements.org/Badge/{badge}.png" if badge else "",
            }
        )

    # Fallback to API_GetGameInfoAndUserProgress when unlock endpoint doesn't expose user unlocks.
    if not unlocked_list and total > 0:
        try:
            progress_data = _fetch_game_info_with_user_progress(username, api_key, game_id)
            progress_achievements = _extract_achievements_map(progress_data)
            if progress_achievements:
                total = len(progress_achievements)
                for ach_id, info in progress_achievements.items():
                    earned = _extract_earned_value(info)
                    if not earned:
                        continue
                    meta = achievements.get(str(ach_id)) or achievements.get(ach_id) or info or {}
                    badge = meta.get("BadgeName") or ""
                    unlocked_list.append(
                        {
                            "id": ach_id,
                            "title": meta.get("Title") or "",
                            "description": meta.get("Description") or "",
                            "earned": earned,
                            "points": meta.get("Points") or 0,
                            "icon": f"https://media.retroachievements.org/Badge/{badge}.png" if badge else "",
                        }
                    )
        except Exception:
            pass

    unlocked_list.sort(key=lambda x: x.get("earned") or "")
    return unlocked_list, total
