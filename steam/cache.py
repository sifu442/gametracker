from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class CacheStore:
    """Filesystem cache helper with safe JSON I/O."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.schema_root = self.base_dir / "schema"
        self.user_root = self.base_dir / "user"
        self.icon_root = self.base_dir / "icon"

    def ensure_dirs(self) -> None:
        """Ensure cache roots exist."""

        self.schema_root.mkdir(parents=True, exist_ok=True)
        self.user_root.mkdir(parents=True, exist_ok=True)
        self.icon_root.mkdir(parents=True, exist_ok=True)

    def schema_path(self, lang: str, appid: str) -> Path:
        """Return schema cache path."""

        return self.schema_root / lang / f"{appid}.json"

    def user_state_path(self, steam_user: str, appid: str) -> Path:
        """Return user-state cache path."""

        return self.user_root / steam_user / f"{appid}.json"

    def icon_dir(self, appid: str) -> Path:
        """Return icon cache directory."""

        return self.icon_root / appid

    def read_json(self, path: Path) -> dict[str, Any] | None:
        """Read JSON document or None."""

        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        """Write JSON atomically."""

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        tmp.replace(path)

    def is_stale(self, path: Path, ttl_seconds: int) -> bool:
        """Return True if path is missing or older than ttl."""

        if not path.exists():
            return True
        return (time.time() - path.stat().st_mtime) > ttl_seconds

    def newer_than(self, a: Path, b: Path) -> bool:
        """Return True if file a is newer than file b."""

        if not a.exists() or not b.exists():
            return False
        return a.stat().st_mtime > b.stat().st_mtime

