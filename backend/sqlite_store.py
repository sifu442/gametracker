"""
SQLite-backed storage with relational tables for library, tracking, and emulators.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class SQLiteStore:
    """Relational SQLite storage facade."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.revisions_dir = self.db_path.parent / "db_revisions"
        self.revisions_dir.mkdir(parents=True, exist_ok=True)
        self._last_revision_ts = 0.0
        self._revision_interval_seconds = 300  # keep one snapshot at most every 5 minutes
        self._revision_keep = 100
        self._init_db()
        self._migrate_kv_json_if_present()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    genre TEXT,
                    platform TEXT,
                    notes TEXT,
                    playtime INTEGER,
                    installed INTEGER,
                    hidden INTEGER,
                    is_emulated INTEGER,
                    emulator_id TEXT,
                    rom_path TEXT,
                    process_name TEXT,
                    steam_app_id TEXT,
                    source TEXT,
                    legendary_app_name TEXT,
                    serial TEXT,
                    added_date REAL,
                    cover TEXT,
                    logo TEXT,
                    hero TEXT,
                    install_path TEXT,
                    install_location TEXT,
                    proton_path TEXT,
                    windows_only INTEGER,
                    compat_tool TEXT,
                    wine_prefix TEXT,
                    wine_dll_overrides TEXT,
                    first_played REAL,
                    last_played REAL,
                    exe_paths_json TEXT,
                    raw_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS game_links (
                    game_id TEXT NOT NULL,
                    idx INTEGER NOT NULL,
                    type TEXT,
                    url TEXT,
                    PRIMARY KEY (game_id, idx),
                    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tracking (
                    process_name TEXT PRIMARY KEY,
                    total_runtime INTEGER,
                    last_session_start REAL,
                    last_session_end REAL,
                    first_opened REAL,
                    last_seen_pid INTEGER,
                    last_seen_start REAL,
                    raw_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS emulators (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    launch_type TEXT,
                    launch_type_windows TEXT,
                    launch_type_linux TEXT,
                    exe_path_windows TEXT,
                    exe_path_linux TEXT,
                    exe_path TEXT,
                    flatpak_id TEXT,
                    args_template TEXT,
                    platforms_json TEXT,
                    rom_extensions_json TEXT,
                    rom_dirs_json TEXT,
                    exe_paths_json TEXT,
                    raw_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_json (
                    dataset TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _loads(payload, default):
        try:
            return json.loads(payload)
        except Exception:
            return default

    def _table_count(self, conn, table: str) -> int:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0] if row else 0)

    def _migrate_kv_json_if_present(self):
        with self._connect() as conn:
            kv_rows = conn.execute("SELECT dataset, payload FROM kv_json").fetchall()
            if not kv_rows:
                return
            for dataset, payload in kv_rows:
                if dataset == "library" and self._table_count(conn, "games") == 0:
                    self._write_library(conn, self._loads(payload, {}))
                elif dataset == "tracking" and self._table_count(conn, "tracking") == 0:
                    self._write_tracking(conn, self._loads(payload, {}))
                elif dataset == "emulators" and self._table_count(conn, "emulators") == 0:
                    self._write_emulators(conn, self._loads(payload, {}))
            conn.commit()

    def read_dataset(self, dataset: str, default=None):
        if dataset == "library":
            return self._read_library(default if default is not None else {})
        if dataset == "tracking":
            return self._read_tracking(default if default is not None else {})
        if dataset == "emulators":
            return self._read_emulators(default if default is not None else {})
        return default

    def write_dataset(self, dataset: str, data) -> bool:
        try:
            with self._connect() as conn:
                if dataset == "library":
                    self._write_library(conn, data if isinstance(data, dict) else {})
                elif dataset == "tracking":
                    self._write_tracking(conn, data if isinstance(data, dict) else {})
                elif dataset == "emulators":
                    self._write_emulators(conn, data if isinstance(data, dict) else {})
                else:
                    return False
                conn.commit()
                self._maybe_create_revision(conn)
            return True
        except Exception:
            return False

    def _maybe_create_revision(self, conn):
        now = time.time()
        if (now - self._last_revision_ts) < self._revision_interval_seconds:
            return
        self._last_revision_ts = now
        stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
        revision_path = self.revisions_dir / f"{self.db_path.stem}_{stamp}.sqlite"
        try:
            with sqlite3.connect(str(revision_path)) as dst:
                conn.backup(dst)
        except Exception:
            return
        self._prune_old_revisions()

    def _prune_old_revisions(self):
        try:
            snapshots = sorted(
                self.revisions_dir.glob(f"{self.db_path.stem}_*.sqlite"),
                key=lambda p: p.stat().st_mtime,
            )
        except Exception:
            return
        overflow = max(0, len(snapshots) - int(self._revision_keep))
        for path in snapshots[:overflow]:
            try:
                path.unlink()
            except Exception:
                continue

    def _read_library(self, default):
        out = {}
        with self._connect() as conn:
            rows = conn.execute("SELECT id, raw_json FROM games").fetchall()
            links_by_game = {}
            for gid, idx, ltype, url in conn.execute(
                "SELECT game_id, idx, type, url FROM game_links ORDER BY game_id, idx"
            ).fetchall():
                links_by_game.setdefault(gid, []).append({"type": ltype or "", "url": url or ""})
        for gid, raw_json in rows:
            game = self._loads(raw_json or "{}", {})
            if not isinstance(game, dict):
                game = {}
            game.setdefault("id", gid)
            if (not isinstance(game.get("links"), list)) and gid in links_by_game:
                game["links"] = links_by_game[gid]
            out[gid] = game
        return out if out else default

    def _write_library(self, conn, data: dict):
        conn.execute("DELETE FROM game_links")
        conn.execute("DELETE FROM games")
        for gid, game in (data or {}).items():
            if not isinstance(game, dict):
                continue
            row = dict(game)
            row["id"] = gid
            conn.execute(
                """
                INSERT INTO games(
                    id, name, genre, platform, notes, playtime, installed, hidden,
                    is_emulated, emulator_id, rom_path, process_name, steam_app_id,
                    source, legendary_app_name, serial, added_date, cover, logo, hero,
                    install_path, install_location, proton_path, windows_only, compat_tool,
                    wine_prefix, wine_dll_overrides, first_played, last_played, exe_paths_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gid,
                    row.get("name"),
                    row.get("genre"),
                    row.get("platform"),
                    row.get("notes"),
                    int(row.get("playtime") or 0),
                    1 if bool(row.get("installed")) else 0,
                    1 if bool(row.get("hidden")) else 0,
                    1 if bool(row.get("is_emulated")) else 0,
                    row.get("emulator_id"),
                    row.get("rom_path"),
                    row.get("process_name"),
                    row.get("steam_app_id"),
                    row.get("source"),
                    row.get("legendary_app_name"),
                    row.get("serial"),
                    row.get("added_date"),
                    row.get("cover"),
                    row.get("logo"),
                    row.get("hero"),
                    row.get("install_path"),
                    row.get("install_location"),
                    row.get("proton_path"),
                    1 if bool(row.get("windows_only")) else 0,
                    row.get("compat_tool"),
                    row.get("wine_prefix"),
                    row.get("wine_dll_overrides"),
                    row.get("first_played"),
                    row.get("last_played"),
                    json.dumps(row.get("exe_paths", {}), ensure_ascii=False),
                    json.dumps(row, ensure_ascii=False),
                ),
            )
            links = row.get("links")
            if isinstance(links, list):
                for idx, link in enumerate(links):
                    if not isinstance(link, dict):
                        continue
                    conn.execute(
                        "INSERT INTO game_links(game_id, idx, type, url) VALUES (?, ?, ?, ?)",
                        (gid, idx, str(link.get("type") or ""), str(link.get("url") or "")),
                    )

    def _read_tracking(self, default):
        out = {}
        with self._connect() as conn:
            rows = conn.execute("SELECT process_name, raw_json FROM tracking").fetchall()
        for pname, raw_json in rows:
            obj = self._loads(raw_json or "{}", {})
            if not isinstance(obj, dict):
                obj = {}
            out[pname] = obj
        return out if out else default

    def _write_tracking(self, conn, data: dict):
        conn.execute("DELETE FROM tracking")
        for pname, row in (data or {}).items():
            if not isinstance(row, dict):
                continue
            conn.execute(
                """
                INSERT INTO tracking(
                    process_name, total_runtime, last_session_start, last_session_end,
                    first_opened, last_seen_pid, last_seen_start, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pname,
                    int(row.get("total_runtime") or 0),
                    row.get("last_session_start"),
                    row.get("last_session_end"),
                    row.get("first_opened"),
                    row.get("last_seen_pid"),
                    row.get("last_seen_start"),
                    json.dumps(row, ensure_ascii=False),
                ),
            )

    def _read_emulators(self, default):
        out = {}
        with self._connect() as conn:
            rows = conn.execute("SELECT id, raw_json FROM emulators").fetchall()
        for eid, raw_json in rows:
            obj = self._loads(raw_json or "{}", {})
            if not isinstance(obj, dict):
                obj = {}
            obj.setdefault("id", eid)
            out[eid] = obj
        return out if out else default

    def _write_emulators(self, conn, data: dict):
        conn.execute("DELETE FROM emulators")
        for eid, row in (data or {}).items():
            if not isinstance(row, dict):
                continue
            payload = dict(row)
            payload["id"] = eid
            conn.execute(
                """
                INSERT INTO emulators(
                    id, name, launch_type, launch_type_windows, launch_type_linux,
                    exe_path_windows, exe_path_linux, exe_path, flatpak_id, args_template,
                    platforms_json, rom_extensions_json, rom_dirs_json, exe_paths_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eid,
                    payload.get("name"),
                    payload.get("launch_type"),
                    payload.get("launch_type_windows"),
                    payload.get("launch_type_linux"),
                    payload.get("exe_path_windows"),
                    payload.get("exe_path_linux"),
                    payload.get("exe_path"),
                    payload.get("flatpak_id"),
                    payload.get("args_template"),
                    json.dumps(payload.get("platforms", []), ensure_ascii=False),
                    json.dumps(payload.get("rom_extensions", []), ensure_ascii=False),
                    json.dumps(payload.get("rom_dirs", []), ensure_ascii=False),
                    json.dumps(payload.get("exe_paths", {}), ensure_ascii=False),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
