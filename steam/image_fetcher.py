from __future__ import annotations

import hashlib
import mimetypes
import os
import threading
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests

from steam.logging import get_logger, slog

MAX_ICON_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT = 10

_logger = get_logger("steam.image")
_inflight_guard = threading.Lock()
_inflight_locks: dict[tuple[str, str], threading.Lock] = {}

_CDN_TEMPLATES = [
    "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/{name}{ext}",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/{name}{ext}",
    "https://media.steampowered.com/steam/apps/{appid}/{name}{ext}",
    "https://steamcdn-a.akamaihd.net/steam/apps/{appid}/{name}{ext}",
    "https://shared.fastly.steamstatic.com/steam/apps/{appid}/{name}{ext}",
    "https://shared.fastly.steamstatic.com/community_assets/images/apps/{appid}/{name}{ext}",
    "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/{name}{ext}",
    "https://steampipe.akamaized.net/steam/apps/{appid}/{name}{ext}",
    "https://google2.cdn.steampipe.steamcontent.com/steam/apps/{appid}/{name}{ext}",
]


def _lock_for(appid: str, icon_ref: str) -> threading.Lock:
    key = (str(appid), str(icon_ref))
    with _inflight_guard:
        lock = _inflight_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _inflight_locks[key] = lock
        return lock


def _icon_dir(cache_root: Path, appid: str) -> Path:
    return cache_root / "icon" / str(appid)


def _is_http(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_", ".", " ")).strip() or hashlib.sha1(
        name.encode("utf-8")
    ).hexdigest()


def _split_name_ext(icon_ref: str) -> tuple[str, str]:
    parsed = urlparse(icon_ref)
    raw = os.path.basename(parsed.path) if parsed.path else icon_ref
    raw = raw.strip()
    if not raw:
        return "", ""
    stem = Path(raw).stem
    ext = Path(raw).suffix.lower()
    return stem, ext


def _cached_candidates(icon_dir: Path, icon_ref: str) -> list[Path]:
    stem, ext = _split_name_ext(icon_ref)
    if not stem and not ext:
        return []
    if ext:
        return [icon_dir / f"{stem}{ext}"]
    return [icon_dir / f"{stem}.jpg", icon_dir / f"{stem}.png"]


def _content_ext(content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct == "image/jpeg":
        return ".jpg"
    if ct == "image/png":
        return ".png"
    guessed = mimetypes.guess_extension(ct) or ""
    return ".jpg" if guessed == ".jpe" else guessed


def _probe_image_url(url: str, session: requests.Session) -> tuple[bool, str]:
    try:
        r = session.head(url, timeout=DEFAULT_TIMEOUT, allow_redirects=True)
        ctype = r.headers.get("content-type", "")
        if r.status_code == 200 and ctype.lower().startswith("image/"):
            return True, ctype
    except Exception:
        pass
    try:
        r = session.get(url, timeout=DEFAULT_TIMEOUT, stream=True, allow_redirects=True)
        ctype = r.headers.get("content-type", "")
        ok = r.status_code == 200 and ctype.lower().startswith("image/")
        r.close()
        if ok:
            return True, ctype
    except Exception:
        return False, ""
    return False, ""


def _download_atomic(url: str, out_path: Path, session: requests.Session) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    for attempt in range(3):
        try:
            with session.get(url, timeout=DEFAULT_TIMEOUT, stream=True, allow_redirects=True) as r:
                ctype = r.headers.get("content-type", "")
                if r.status_code != 200 or not ctype.lower().startswith("image/"):
                    raise ValueError(f"invalid_response status={r.status_code} ctype={ctype}")
                total = 0
                with tmp.open("wb") as fh:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_ICON_BYTES:
                            raise ValueError("icon_too_large")
                        fh.write(chunk)
                if total <= 0:
                    raise ValueError("icon_empty")
                tmp.replace(out_path)
                return True
        except Exception:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
            if attempt < 2:
                time.sleep(0.5 * (2**attempt))
    return False


def _probe_urls(appid: str, icon_ref: str) -> Iterable[str]:
    value = (icon_ref or "").strip()
    if not value:
        return []
    if _is_http(value):
        stem, ext = _split_name_ext(value)
        if ext:
            return [value]
        return [f"{value}.jpg", f"{value}.png"]

    stem, ext = _split_name_ext(value)
    if not stem:
        return []
    exts = [ext] if ext in (".jpg", ".png") else [".jpg", ".png"]
    urls: list[str] = []
    for tmpl in _CDN_TEMPLATES:
        for e in exts:
            urls.append(tmpl.format(appid=appid, name=stem, ext=e))
    return urls


def resolve_icon_path(
    appid: str,
    icon_ref: str | None,
    cache_root: Path,
    session: requests.Session | None = None,
    fetch_if_missing: bool = True,
) -> Path | None:
    """Resolve one achievement icon to a local cache file path."""
    if not appid or not icon_ref:
        return None
    icon_ref = str(icon_ref).strip()
    if not icon_ref:
        return None

    icon_dir = _icon_dir(cache_root, appid)
    for cand in _cached_candidates(icon_dir, icon_ref):
        if cand.exists():
            return cand
    if not fetch_if_missing:
        return None

    lock = _lock_for(appid, icon_ref)
    with lock:
        for cand in _cached_candidates(icon_dir, icon_ref):
            if cand.exists():
                return cand
        if not fetch_if_missing:
            return None

        local_session = session or requests.Session()
        try:
            for url in _probe_urls(str(appid), icon_ref):
                ok, ctype = _probe_image_url(url, local_session)
                if not ok:
                    continue
                stem, ext = _split_name_ext(url)
                ext = ext or _content_ext(ctype) or ".jpg"
                out = icon_dir / f"{_safe_name(stem)}{ext}"
                if out.exists():
                    return out
                if _download_atomic(url, out, local_session):
                    slog(_logger, 20, "icon_cached", appid=appid, icon_ref=icon_ref, url=url, file=str(out))
                    return out
        except Exception as exc:
            slog(_logger, 30, "icon_resolve_failed", appid=appid, icon_ref=icon_ref, error=str(exc))
            return None
        finally:
            if session is None:
                local_session.close()

    slog(_logger, 20, "icon_not_found", appid=appid, icon_ref=icon_ref)
    return None


def prefetch_game_icons(appid: str, icon_refs: list[str], cache_root: Path, max_workers: int = 4) -> dict[str, Path | None]:
    """Prefetch and cache achievement icons for one game."""
    results: dict[str, Path | None] = {}
    unique_refs = []
    seen = set()
    for ref in icon_refs:
        key = str(ref or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique_refs.append(key)

    if not unique_refs:
        return results

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with requests.Session() as sess:
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
            future_map = {
                pool.submit(resolve_icon_path, str(appid), ref, cache_root, sess): ref for ref in unique_refs
            }
            for fut in as_completed(future_map):
                ref = future_map[fut]
                try:
                    results[ref] = fut.result()
                except Exception as exc:
                    slog(_logger, 30, "icon_prefetch_failed", appid=appid, icon_ref=ref, error=str(exc))
                    results[ref] = None
    return results
