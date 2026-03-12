"""
Utility functions for Game Library Tracker
"""
import json
import os
import platform
import re
from datetime import datetime
from pathlib import Path


def resolve_user_path(p):
    """Resolve user-home shorthands without hardcoding a username."""
    if p is None:
        return p
    path = str(p).strip()
    if not path:
        return path
    home = str(Path.home())
    if path == "~":
        return home
    if path.startswith("~/"):
        return home + path[1:]
    # Fix paths missing a leading slash (e.g. "home/user/...")
    if not path.startswith("/") and path.startswith("home/"):
        path = "/" + path
    # Accept common placeholder form used in docs/examples.
    if platform.system() == "Linux":
        if path == "/home/username":
            return home
        if path.startswith("/home/username/"):
            return home + path[len("/home/username"):]
    return path


def fix_path_str(p):
    """Normalize Windows backslashes to forward slashes safely"""
    if not p:
        return p
    path = resolve_user_path(p).replace("\\", "/")
    is_windows = platform.system() == "Windows"
    is_linux = platform.system() == "Linux"
    if is_linux and path.lower().startswith("d:/"):
        return "/media/SSD" + path[2:]
    if is_windows and path.startswith("/media/SSD"):
        return "D:" + path[len("/media/SSD"):]
    return path


def canonicalize_path(p):
    """Store paths in canonical Windows-style D:/ form when on shared SSD."""
    if not p:
        return p
    path = resolve_user_path(p).replace("\\", "/")
    if path.startswith("/media/SSD"):
        return "D:" + path[len("/media/SSD"):]
    return path


def debug_log(message):
    """Append debug logs when GAMETRACKER_DEBUG=1 (or true/yes/on)."""
    flag = str(os.environ.get("GAMETRACKER_DEBUG", "")).strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return
    try:
        preferred = str(os.environ.get("GAMETRACKER_DEBUG_FILE", "")).strip()
        if preferred:
            log_file = Path(preferred).expanduser()
        else:
            # Prefer project root when writable; fallback to user-local data dir.
            root = Path(__file__).resolve().parent.parent
            root_candidate = root / "launch_debug.log"
            try:
                root_candidate.parent.mkdir(parents=True, exist_ok=True)
                with root_candidate.open("a", encoding="utf-8"):
                    pass
                log_file = root_candidate
            except Exception:
                data_dir = Path.home() / ".local" / "share" / "gametracker"
                data_dir.mkdir(parents=True, exist_ok=True)
                log_file = data_dir / "launch_debug.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(f"[{ts}] {message}\n")
    except Exception:
        pass


def sanitized_subprocess_env(base_env=None):
    """Return env with problematic app/runtime Python vars removed."""
    env = dict(base_env if base_env is not None else os.environ)
    for key in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONUSERBASE",
        "PYTHONSTARTUP",
        "PYTHONEXECUTABLE",
        "PYTHONNOUSERSITE",
    ):
        env.pop(key, None)
    return env


def system_python_path_env(base_env=None):
    """Env sanitized for system scripts that use /usr/bin/env python3."""
    env = sanitized_subprocess_env(base_env)
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    return env


def load_json(filepath, default=None):
    """Load JSON data from file"""
    if default is None:
        default = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(filepath, data):
    """Save JSON data to file"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False


def format_playtime(minutes):
    """Format playtime in minutes to readable string"""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes / 60
    if hours < 100:
        return f"{hours:.1f}h"
    return f"{int(hours)}h"


def sanitize_filename_component(value):
    """Return a filesystem-safe filename component."""
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace(" ", "_")
    # Remove Windows-invalid and URL-problematic filename chars.
    text = re.sub(r'[<>:"/\\\\|?*]+', "_", text)
    text = re.sub(r"_+", "_", text).strip("._ ")
    return text or "media"
