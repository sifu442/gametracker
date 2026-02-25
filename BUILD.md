# Build Executables

This project should be built natively on each OS:
- Build on Windows for Windows executable
- Build on Linux for Linux executable

## Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

Output:
- `dist/GameTracker/`

Run:
- `dist/GameTracker/GameTracker.exe`

## Linux

```bash
chmod +x ./build_linux.sh
./build_linux.sh
```

Output:
- `dist/GameTracker/`

Run:
- `dist/GameTracker/GameTracker`

## Notes

- Build mode is `onedir` for reliability with PyQt6/QML.
- The spec includes `ui/`, `covers/`, `logos/`, `heroes/`, and JSON data files.
- If SmartScreen or antivirus warns on Windows, code-signing is required for trust.
