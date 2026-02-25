"""
IGDB API integration thread
"""
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from core.constants import TEMP_COVERS_DIR


class IGDBDownloader(QThread):
    """Thread for downloading cover from IGDB"""
    finished = pyqtSignal(bool, str, str)  # success, image_path, game_name
    
    def __init__(self, game_name, client_id, client_secret):
        super().__init__()
        self.game_name = game_name
        self.client_id = client_id
        self.client_secret = client_secret
        
    def run(self):
        try:
            # Get access token
            response = requests.post(
                'https://id.twitch.tv/oauth2/token',
                params={
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'grant_type': 'client_credentials'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                self.finished.emit(False, "", "")
                return
            
            token = response.json()['access_token']
            
            # Search for game
            headers = {
                'Client-ID': self.client_id,
                'Authorization': f'Bearer {token}'
            }
            
            query = f'''
                search "{self.game_name}";
                fields name, cover.image_id;
                limit 5;
            '''
            
            response = requests.post(
                'https://api.igdb.com/v4/games',
                headers=headers,
                data=query,
                timeout=10
            )
            
            if response.status_code == 200:
                games = response.json()
                if games and len(games) > 0:
                    for game in games:
                        if 'cover' in game and 'image_id' in game['cover']:
                            image_id = game['cover']['image_id']
                            cover_url = f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
                            
                            # Download image
                            img_response = requests.get(cover_url, timeout=10)
                            if img_response.status_code == 200:
                                # Save to temp directory
                                temp_filename = f"{self.game_name.replace(' ', '_')}_temp.jpg"
                                temp_path = TEMP_COVERS_DIR / temp_filename
                                
                                with open(temp_path, 'wb') as f:
                                    f.write(img_response.content)
                                
                                self.finished.emit(True, str(temp_path), game['name'])
                                return
            
            self.finished.emit(False, "", "")
            
        except Exception as e:
            print(f"IGDB error: {e}")
            self.finished.emit(False, "", "")
