"""
Process monitoring thread
"""
import time
import psutil
from PyQt6.QtCore import QThread, pyqtSignal


class ProcessMonitor(QThread):
    """Thread for monitoring game process"""
    game_ended = pyqtSignal()
    
    def __init__(self, pid, start_time):
        super().__init__()
        self.pid = pid
        self.start_time = start_time
        self.running = True
        
    def run(self):
        while self.running:
            try:
                proc = psutil.Process(self.pid)
                if abs(proc.create_time() - self.start_time) > 1:
                    self.game_ended.emit()
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.game_ended.emit()
                break
            
            time.sleep(1)
    
    def stop(self):
        self.running = False
