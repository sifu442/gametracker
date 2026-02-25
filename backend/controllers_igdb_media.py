"""
IGDB/media operations extracted from AppController.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.parse import quote
from typing import TYPE_CHECKING

import requests

from core.constants import COVERS_DIR, HEROES_DIR, LOGOS_DIR, SCRIPT_DIR, TEMP_COVERS_DIR
from threads.igdb_details import IGDBDetailsThread
from threads.igdb_downloader import IGDBDownloader
from threads.igdb_search import IGDBSearchThread
from utils.helpers import fix_path_str, sanitize_filename_component

if TYPE_CHECKING:
    from backend.controllers import AppController


class IgdbMediaControllerOps:
    """Encapsulates IGDB and media download/update methods."""

    def __init__(self, controller: "AppController") -> None:
        self._c = controller

    def update_game_media(self, new_entry, old_data, temp_path, media_type, game_name, media_dir):
        c = self._c
        try:
            src = Path(fix_path_str(temp_path))
            if src.exists():
                safe_name = sanitize_filename_component(game_name)
                dest_name = f"{safe_name}_{media_type}{src.suffix}"
                dest_path = media_dir / dest_name
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                if src.resolve() != dest_path.resolve():
                    dest_path.write_bytes(src.read_bytes())
                new_entry[media_type] = dest_path.name

            old_path = old_data.get(media_type)
            if old_path:
                old_file = Path(fix_path_str(old_path))
                if not old_file.is_absolute():
                    old_file = SCRIPT_DIR / old_file
                if old_file.exists() and old_file.resolve() != dest_path.resolve():
                    try:
                        old_file.unlink()
                    except Exception:
                        pass
        except Exception as e:
            c.errorMessage.emit(f"Failed to update {media_type}: {e}")

    def steamgriddb_request(self, url, api_key):
        try:
            resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data.get("data")
        except Exception:
            return None

    def steamgriddb_download(self, url, temp_dir, stem):
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code != 200:
                return ""
            suffix = Path(url).suffix or ".png"
            temp_path = Path(temp_dir) / f"{stem}{suffix}"
            temp_path.write_bytes(resp.content)
            return str(temp_path)
        except Exception:
            return ""

    def update_images_from_steamgriddb(self):
        c = self._c
        if c._images_update_running:
            return "Image update is already running."
        api_key = (c._config.get("steamgriddb_api_key") or "").strip()
        if not api_key:
            return "SteamGridDB API key not configured."
        c._images_update_running = True

        def worker():
            updated = 0
            try:
                for _, game_data in c._game_manager.library_data.items():
                    name = (game_data.get("name") or "").strip()
                    if not name:
                        continue
                    safe_name = sanitize_filename_component(name)
                    needs_cover = not game_data.get("cover")
                    needs_logo = not game_data.get("logo")
                    needs_hero = not game_data.get("hero")
                    if not (needs_cover or needs_logo or needs_hero):
                        continue

                    search_url = f"https://www.steamgriddb.com/api/v2/search/autocomplete/{quote(name)}"
                    search_data = self.steamgriddb_request(search_url, api_key)
                    if not search_data:
                        continue
                    sgdb_id = search_data[0].get("id")
                    if not sgdb_id:
                        continue

                    old_data = game_data.copy()
                    if needs_logo:
                        logo_data = self.steamgriddb_request(
                            f"https://www.steamgriddb.com/api/v2/icons/game/{sgdb_id}",
                            api_key,
                        )
                        if logo_data:
                            url = logo_data[0].get("url")
                            if url:
                                temp = self.steamgriddb_download(url, TEMP_COVERS_DIR, f"{safe_name}_logo_tmp")
                                if temp:
                                    self.update_game_media(game_data, old_data, temp, "logo", name, LOGOS_DIR)
                                    updated += 1

                    if needs_cover:
                        grid_data = self.steamgriddb_request(
                            f"https://www.steamgriddb.com/api/v2/grids/game/{sgdb_id}",
                            api_key,
                        )
                        if grid_data:
                            url = grid_data[0].get("url")
                            if url:
                                temp = self.steamgriddb_download(url, TEMP_COVERS_DIR, f"{safe_name}_cover_tmp")
                                if temp:
                                    self.update_game_media(game_data, old_data, temp, "cover", name, COVERS_DIR)
                                    updated += 1

                    if needs_hero:
                        hero_data = self.steamgriddb_request(
                            f"https://www.steamgriddb.com/api/v2/heroes/game/{sgdb_id}",
                            api_key,
                        )
                        if hero_data:
                            url = hero_data[0].get("url")
                            if url:
                                temp = self.steamgriddb_download(url, TEMP_COVERS_DIR, f"{safe_name}_hero_tmp")
                                if temp:
                                    self.update_game_media(game_data, old_data, temp, "hero", name, HEROES_DIR)
                                    updated += 1

                if updated:
                    c._game_manager.save_library()
                c.imagesUpdateFinished.emit(updated, f"Updated {updated} images from SteamGridDB.")
            except Exception as e:
                c.imagesUpdateFinished.emit(0, f"Image update failed: {e}")

        threading.Thread(target=worker, daemon=True).start()
        return "Updating images in background..."

    def on_images_update_finished(self, updated, message):
        c = self._c
        c._images_update_running = False
        if int(updated or 0) > 0:
            c._game_model.refresh()
            c.libraryChanged.emit()
        c.errorMessage.emit(message)

    def search_igdb(self, game_name):
        c = self._c
        name = (game_name or "").strip()
        if not name:
            c.errorMessage.emit("Please enter a game name first.")
            return
        client_id = c._config.get("igdb_client_id")
        client_secret = c._config.get("igdb_client_secret")
        if not client_id or not client_secret:
            c.errorMessage.emit("Please configure IGDB API in Settings first.")
            return
        c._igdb_thread = IGDBDownloader(name, client_id, client_secret)
        c._igdb_thread.finished.connect(c._on_igdb_finished)
        c._igdb_thread.start()

    def on_igdb_finished(self, success, image_path, game_name):
        c = self._c
        c.igdbCoverDownloaded.emit(success, image_path, game_name)
        c._igdb_thread = None

    def search_igdb_titles(self, query):
        c = self._c
        name = (query or "").strip()
        if not name:
            c.igdbSearchResults.emit([])
            return
        client_id = c._config.get("igdb_client_id")
        client_secret = c._config.get("igdb_client_secret")
        if not client_id or not client_secret:
            c.errorMessage.emit("Please configure IGDB API in Settings first.")
            c.igdbSearchResults.emit([])
            return
        c._igdb_search_query = name
        c._igdb_search_thread = IGDBSearchThread(name, client_id, client_secret)
        c._igdb_search_thread.finished.connect(c._on_igdb_search_finished)
        c._igdb_search_thread.start()

    def on_igdb_search_finished(self, success, results):
        c = self._c
        if success:
            c.igdbSearchResults.emit(results)
        else:
            c.igdbSearchResults.emit([])
        c._igdb_search_thread = None

    def fetch_igdb_game_details(self, game_id):
        c = self._c
        game_id = (game_id or "").strip()
        if not game_id:
            c.igdbGameDetails.emit({})
            return
        try:
            game_id_int = int(game_id)
        except Exception:
            c.errorMessage.emit("IGDB game id is invalid.")
            c.igdbGameDetails.emit({})
            return
        client_id = c._config.get("igdb_client_id")
        client_secret = c._config.get("igdb_client_secret")
        if not client_id or not client_secret:
            c.errorMessage.emit("Please configure IGDB API in Settings first.")
            c.igdbGameDetails.emit({})
            return
        c._igdb_details_thread = IGDBDetailsThread(game_id_int, client_id, client_secret)
        c._igdb_details_thread.finished.connect(c._on_igdb_details_finished)
        c._igdb_details_thread.start()

    def on_igdb_details_finished(self, success, details):
        c = self._c
        if success and details and isinstance(details, dict) and details.get("name"):
            try:
                safe_details = json.loads(json.dumps(details))
            except Exception:
                safe_details = details
            c.igdbGameDetails.emit(safe_details)
            try:
                c.igdbGameDetailsJson.emit(json.dumps(safe_details))
            except Exception:
                pass
        else:
            c.igdbGameDetails.emit({})
            error_text = ""
            if isinstance(details, dict):
                error_text = details.get("_error", "")
            if not error_text:
                error_text = "IGDB details lookup failed (empty or missing name)."
            c.errorMessage.emit(error_text)
        c._igdb_details_thread = None

    def download_media(self, media_type, url, game_name):
        c = self._c
        url = (url or "").strip()
        if not url:
            c.errorMessage.emit("Please enter a URL.")
            return ""
        if not url.startswith(("http://", "https://")):
            c.errorMessage.emit("URL must start with http:// or https://")
            return ""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                c.errorMessage.emit(f"Failed to download: HTTP {response.status_code}")
                return ""
            ext = ".jpg"
            ctype = response.headers.get("content-type", "").lower()
            if "png" in ctype:
                ext = ".png"
            elif "gif" in ctype:
                ext = ".gif"
            if media_type == "cover":
                target_dir = COVERS_DIR
            elif media_type == "logo":
                target_dir = LOGOS_DIR
            else:
                target_dir = HEROES_DIR
            safe_name = sanitize_filename_component(game_name or "media")
            filename = f"{safe_name}_{media_type}{ext}"
            filepath = target_dir / filename
            filepath.write_bytes(response.content)
            return str(filepath)
        except Exception as e:
            c.errorMessage.emit(f"Download failed: {e}")
            return ""
