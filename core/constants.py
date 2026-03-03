"""
Constants and configuration for Game Library Tracker
"""
import platform
import sys
import os
from pathlib import Path

# Determine OS
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

def _resolve_data_root() -> Path:
    """
    Resolve persistent app data root.

    - Source run: project root (existing behavior).
    - Frozen run (PyInstaller): directory beside executable, so DB survives restarts.
    """
    env_override = None
    raw = os.environ.get("GAMETRACKER_DATA_DIR", "").strip()
    if raw:
        env_override = Path(raw).expanduser().resolve()
    if env_override:
        return env_override
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).parent.parent.resolve()


# Store data in persistent app directory
SCRIPT_DIR = _resolve_data_root()
TRACKING_FILE = SCRIPT_DIR / "process_tracking.json"
LIBRARY_FILE = SCRIPT_DIR / "game_library.json"
CONFIG_FILE = SCRIPT_DIR / "config.json"
EMULATORS_FILE = SCRIPT_DIR / "emulators.json"
DB_FILE = SCRIPT_DIR / "gametracker.db"
COVERS_DIR = SCRIPT_DIR / "covers"
TEMP_COVERS_DIR = SCRIPT_DIR / "temp_covers"
LOGOS_DIR = SCRIPT_DIR / "logos"
HEROES_DIR = SCRIPT_DIR / "heroes"

# Create directories
COVERS_DIR.mkdir(exist_ok=True)
TEMP_COVERS_DIR.mkdir(exist_ok=True)
LOGOS_DIR.mkdir(exist_ok=True)
HEROES_DIR.mkdir(exist_ok=True)

# Default Proton path for Linux
DEFAULT_PROTON_PATH = Path.home() / ".config/heroic/tools/proton/GE-Proton-latest"
