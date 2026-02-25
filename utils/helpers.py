"""
Utility functions for Game Library Tracker
"""
import json
import platform
import re
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
