"""
IGDB API search thread for listing games.
"""
import requests
from PyQt6.QtCore import QThread, pyqtSignal


class IGDBSearchThread(QThread):
    """Thread for searching IGDB titles."""
    finished = pyqtSignal(bool, list)  # success, results list

    def __init__(self, query, client_id, client_secret):
        super().__init__()
        self.query = query
        self.client_id = client_id
        self.client_secret = client_secret

    def run(self):
        try:
            response = requests.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )
            if response.status_code != 200:
                self.finished.emit(False, [])
                return

            token = response.json().get("access_token")
            if not token:
                self.finished.emit(False, [])
                return

            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {token}",
            }
            query = f'''
                search "{self.query}";
                fields id, name, first_release_date, cover.image_id;
                limit 20;
            '''
            response = requests.post(
                "https://api.igdb.com/v4/games",
                headers=headers,
                data=query,
                timeout=10,
            )
            if response.status_code != 200:
                self.finished.emit(False, [])
                return

            results = []
            for game in response.json() or []:
                name = game.get("name") or ""
                if not name:
                    continue
                first_release = game.get("first_release_date")
                year = ""
                if isinstance(first_release, (int, float)) and first_release > 0:
                    try:
                        from datetime import datetime
                        year = str(datetime.utcfromtimestamp(first_release).year)
                    except Exception:
                        year = ""
                cover_url = ""
                cover = game.get("cover") or {}
                image_id = cover.get("image_id") if isinstance(cover, dict) else None
                if image_id:
                    cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_small/{image_id}.jpg"
                results.append({
                    "game_id": game.get("id"),
                    "name": name,
                    "year": year,
                    "cover_url": cover_url,
                })
            self.finished.emit(True, results)
        except Exception:
            self.finished.emit(False, [])
