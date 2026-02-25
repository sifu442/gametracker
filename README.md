# GameTracker

Cross-platform game library tracker with QML UI, emulator support, and achievements.

## Features
1. Game library management (native + emulated)
2. Metadata and media (covers, logos, heroes)
3. Emulator configuration + ROM scanning
4. Playtime tracking
5. Achievements (Steam/SteamEmu/RetroAchievements and emulator trophies)

## Requirements
1. Python 3.11+
2. PyQt6

## Run
```powershell
.\.venv\Scripts\python.exe main.py
```

## Build (Windows, PyInstaller)
```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean gametracker.spec
```

## Project Structure
```
project/
  main.py
  backend/
  ui/
  utils/
  steam/
  dialogs/
  threads/
```

## Notes
User data such as covers/logos/heroes, caches, and shortcuts are ignored via `.gitignore`.
# gametracker
# gametracker
# gametracker
