"""
QAbstractListModel for games in the library.
"""
from PyQt6.QtCore import Qt, QAbstractListModel, QModelIndex, pyqtSignal

from core.constants import IS_LINUX


class GameModel(QAbstractListModel):
    IdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    GenreRole = Qt.ItemDataRole.UserRole + 3
    PlatformRole = Qt.ItemDataRole.UserRole + 4
    CoverRole = Qt.ItemDataRole.UserRole + 5
    LogoRole = Qt.ItemDataRole.UserRole + 6
    HeroRole = Qt.ItemDataRole.UserRole + 7
    ProcessNameRole = Qt.ItemDataRole.UserRole + 8
    NotesRole = Qt.ItemDataRole.UserRole + 9

    dataChangedSignal = pyqtSignal()

    def __init__(self, game_manager):
        super().__init__()
        self._game_manager = game_manager
        self._items = []
        self._sort_order = "last_played"
        self._install_filter = "installed"
        self.refresh()

    def roleNames(self):
        return {
            self.IdRole: b"id",
            self.NameRole: b"name",
            self.GenreRole: b"genre",
            self.PlatformRole: b"platform",
            self.CoverRole: b"cover",
            self.LogoRole: b"logo",
            self.HeroRole: b"hero",
            self.ProcessNameRole: b"processName",
            self.NotesRole: b"notes",
        }

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        item = self._items[row]
        if role == self.IdRole:
            return item.get("id")
        if role == self.NameRole:
            return item.get("name")
        if role == self.GenreRole:
            return item.get("genre")
        if role == self.PlatformRole:
            return item.get("platform")
        if role == self.CoverRole:
            return item.get("cover")
        if role == self.LogoRole:
            return item.get("logo")
        if role == self.HeroRole:
            return item.get("hero")
        if role == self.ProcessNameRole:
            return item.get("process_name")
        if role == self.NotesRole:
            return item.get("notes")
        return None

    def get(self, row):
        if row < 0 or row >= len(self._items):
            return {}
        return self._items[row]

    def set_sort_order(self, order):
        order = (order or "").strip().lower()
        if order not in ("last_played", "az", "za"):
            order = "last_played"
        if self._sort_order == order:
            return
        self._sort_order = order
        self.refresh()

    def set_install_filter(self, mode):
        mode = (mode or "").strip().lower()
        if mode not in ("all", "installed", "not_installed", "hidden"):
            mode = "all"
        if self._install_filter == mode:
            return
        self._install_filter = mode
        self.refresh()

    def _is_installed(self, game_data):
        if not isinstance(game_data, dict):
            return False
        if "installed" in game_data:
            return bool(game_data.get("installed"))
        if game_data.get("is_emulated"):
            return bool(game_data.get("rom_path"))
        if game_data.get("install_path") or game_data.get("install_location"):
            return True
        exe_paths = game_data.get("exe_paths")
        if isinstance(exe_paths, dict):
            return any(bool(p) for p in exe_paths.values())
        if isinstance(exe_paths, str):
            return bool(exe_paths)
        return False

    def refresh(self):
        self.beginResetModel()
        library = self._game_manager.get_all_games()
        self._items = []
        for game_id, game_data in library.items():
            if IS_LINUX and game_data.get("windows_only"):
                continue
            hidden = bool(game_data.get("hidden"))
            if self._install_filter == "hidden":
                if not hidden:
                    continue
            elif hidden:
                continue
            if self._install_filter != "all":
                installed = self._is_installed(game_data)
                if self._install_filter == "installed" and not installed:
                    continue
                if self._install_filter == "not_installed" and installed:
                    continue
            entry = {"id": game_id}
            entry.update(game_data)
            self._items.append(entry)
        def _name_key(item):
            return (item.get("name") or item.get("id") or "").casefold()

        def _last_played_ts(item):
            process_name = (item.get("process_name") or "").strip()
            if process_name:
                try:
                    ts = float(
                        self._game_manager.tracking_data.get(process_name, {}).get("last_session_end") or 0
                    )
                    if ts > 0:
                        return ts
                except Exception:
                    pass
            try:
                return float(item.get("last_played") or 0)
            except Exception:
                return 0.0

        if self._sort_order == "last_played":
            self._items.sort(key=lambda item: (_last_played_ts(item), _name_key(item)), reverse=True)
        else:
            self._items.sort(key=_name_key, reverse=(self._sort_order == "za"))
        self.endResetModel()
        self.dataChangedSignal.emit()
