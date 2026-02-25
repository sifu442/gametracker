from __future__ import annotations

import threading
from pathlib import Path

from steam.image_fetcher import resolve_icon_path


class _Resp:
    def __init__(self, status=200, headers=None, body=b"img"):
        self.status_code = status
        self.headers = headers or {"content-type": "image/png"}
        self._body = body

    def iter_content(self, chunk_size=65536):
        yield self._body

    def close(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Session:
    def __init__(self):
        self.head_calls = 0
        self.get_calls = 0
        self.urls = []
        self.lock = threading.Lock()
        self.mode = "ok"

    def head(self, url, timeout=10, allow_redirects=True):
        with self.lock:
            self.head_calls += 1
            self.urls.append(url)
        if self.mode == "bad":
            return _Resp(status=404, headers={"content-type": "text/plain"})
        if self.mode == "json":
            return _Resp(status=200, headers={"content-type": "application/json"})
        return _Resp(status=200, headers={"content-type": "image/png"})

    def get(self, url, timeout=10, stream=False, allow_redirects=True):
        with self.lock:
            self.get_calls += 1
            self.urls.append(url)
        if self.mode == "bad":
            return _Resp(status=404, headers={"content-type": "text/plain"}, body=b"")
        if self.mode == "json":
            return _Resp(status=200, headers={"content-type": "application/json"}, body=b"{}")
        return _Resp(status=200, headers={"content-type": "image/png"}, body=b"pngbytes")

    def close(self):
        return None


def test_cache_hit_no_network(tmp_path: Path):
    cache_root = tmp_path / "cache"
    icon = cache_root / "icon" / "730" / "abc.png"
    icon.parent.mkdir(parents=True, exist_ok=True)
    icon.write_bytes(b"x")
    s = _Session()
    out = resolve_icon_path("730", "abc.png", cache_root, s)
    assert out == icon
    assert s.head_calls == 0
    assert s.get_calls == 0


def test_url_valid_download_then_cache_hit(tmp_path: Path):
    cache_root = tmp_path / "cache"
    s = _Session()
    url = "https://cdn.akamai.steamstatic.com/steam/apps/730/icon.png"
    out1 = resolve_icon_path("730", url, cache_root, s)
    out2 = resolve_icon_path("730", url, cache_root, s)
    assert out1 is not None and out1.exists()
    assert out2 == out1
    assert s.get_calls >= 1


def test_basename_only_uses_cdn_probe(tmp_path: Path):
    cache_root = tmp_path / "cache"
    s = _Session()
    out = resolve_icon_path("730", "abcdef12345", cache_root, s)
    assert out is not None and out.exists()
    assert any("steam/apps/730/abcdef12345" in u for u in s.urls)


def test_invalid_content_type_returns_none(tmp_path: Path):
    cache_root = tmp_path / "cache"
    s = _Session()
    s.mode = "json"
    out = resolve_icon_path("730", "abcdef12345", cache_root, s)
    assert out is None


def test_concurrent_same_icon_single_download(tmp_path: Path):
    cache_root = tmp_path / "cache"
    s = _Session()
    results = []

    def worker():
        results.append(resolve_icon_path("730", "sameicon", cache_root, s))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert results[0] is not None
    assert results[1] is not None
    assert results[0] == results[1]
    # one downloader path should run; second should hit cache after lock.
    assert s.get_calls <= 2
