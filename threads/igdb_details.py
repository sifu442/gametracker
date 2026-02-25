"""
IGDB API game details thread for populating metadata fields.
"""
import requests
from PyQt6.QtCore import QThread, pyqtSignal


class IGDBDetailsThread(QThread):
    """Thread for fetching a single game's details from IGDB."""
    finished = pyqtSignal(bool, dict)  # success, details

    def __init__(self, game_id, client_id, client_secret):
        super().__init__()
        self.game_id = game_id
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
                self.finished.emit(False, {"_error": f"Token request failed (HTTP {response.status_code})"})
                return

            token = response.json().get("access_token")
            if not token:
                self.finished.emit(False, {"_error": "Token response missing access_token"})
                return

            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {token}",
            }
            fields = [
                "name",
                "summary",
                "first_release_date",
                "platforms.name",
                "genres.name",
                "age_ratings.category",
                "age_ratings.rating",
                "involved_companies.company.name",
                "involved_companies.developer",
                "involved_companies.publisher",
                "collection.name",
                "release_dates.region",
                "game_modes.name",
                "themes.name",
                "keywords.name",
                "rating",
                "aggregated_rating",
                "category",
                "websites.category",
                "websites.url",
            ]
            query = f"fields {', '.join(fields)}; where id = {int(self.game_id)}; limit 1;"
            response = requests.post(
                "https://api.igdb.com/v4/games",
                headers=headers,
                data=query,
                timeout=10,
            )
            if response.status_code != 200:
                self.finished.emit(False, {"_error": f"IGDB games lookup failed (HTTP {response.status_code})"})
                return
            data = response.json() or []
            if not data:
                self.finished.emit(False, {"_error": "IGDB games lookup returned no data"})
                return
            if isinstance(data, list) and len(data) > 0:
                self.finished.emit(True, data[0])
                return
            if not data:
                self.finished.emit(False, {"_error": "IGDB games lookup returned no data"})
                return
            self.finished.emit(True, data[0])
        except Exception:
            self.finished.emit(False, {"_error": "IGDB details request failed"})
