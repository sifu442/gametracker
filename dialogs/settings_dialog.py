"""
Settings Dialog - Application configuration interface
"""
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QMessageBox
)

from core.constants import CONFIG_FILE
from ui.styles import BUTTON_SUCCESS, BUTTON_PRIMARY
from utils.helpers import save_json


class SettingsWidget(QWidget):
    """Widget for application settings"""
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the settings interface"""
        layout = QVBoxLayout(self)
        
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        
        # Title
        title = QLabel("IGDB API Settings")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        form_layout.addRow(title)
        
        # Instructions
        instructions = QLabel(
            "To download covers from IGDB:\n\n"
            "1. Go to https://dev.twitch.tv/console/apps\n"
            "2. Register your application (free)\n"
            "3. Copy Client ID and Client Secret below"
        )
        instructions.setWordWrap(True)
        form_layout.addRow(instructions)
        
        # Client ID
        self.client_id_input = QLineEdit()
        self.client_id_input.setText(self.config.get('igdb_client_id', ''))
        form_layout.addRow("Client ID:", self.client_id_input)
        
        # Client Secret
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setText(self.config.get('igdb_client_secret', ''))
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Client Secret:", self.client_secret_input)
        
        # Save button
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setStyleSheet(BUTTON_SUCCESS)
        save_btn.clicked.connect(self.save_settings)
        form_layout.addRow(save_btn)
        
        # Test button
        test_btn = QPushButton("🔍 Test Connection")
        test_btn.setStyleSheet(BUTTON_PRIMARY)
        test_btn.clicked.connect(self.test_igdb)
        form_layout.addRow(test_btn)
        
        layout.addWidget(form_widget)
        layout.addStretch()
    
    def save_settings(self):
        """Save IGDB settings to config file"""
        self.config['igdb_client_id'] = self.client_id_input.text().strip()
        self.config['igdb_client_secret'] = self.client_secret_input.text().strip()
        
        if save_json(CONFIG_FILE, self.config):
            QMessageBox.information(self, "Success", "Settings saved!")
        else:
            QMessageBox.critical(self, "Error", "Failed to save settings")
    
    def test_igdb(self):
        """Test IGDB API connection"""
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()
        
        if not client_id or not client_secret:
            QMessageBox.warning(self, "Error", "Please enter both Client ID and Secret")
            return
        
        try:
            response = requests.post(
                'https://id.twitch.tv/oauth2/token',
                params={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'grant_type': 'client_credentials'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                QMessageBox.information(
                    self, "Success", 
                    "✓ Successfully connected to IGDB API!"
                )
            else:
                QMessageBox.critical(
                    self, "Error", 
                    f"Failed to connect (HTTP {response.status_code}). "
                    "Check your credentials."
                )
        except requests.exceptions.Timeout:
            QMessageBox.critical(
                self, "Error", 
                "Connection timed out. Check your internet connection."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed: {e}")
    
    def get_config(self):
        """Get current configuration"""
        return self.config
