"""
Constants and configuration for Game Library Tracker
"""
import platform
from pathlib import Path

# Determine OS
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

# Store data in the project root directory
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
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
