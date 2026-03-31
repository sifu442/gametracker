"""
QML-facing controller exposing backend logic to the UI layer.
"""

from PyQt6.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
    pyqtProperty,
    QTimer,
    QThreadPool,
)

from core.constants import (
    IS_WINDOWS,
    IS_LINUX,
    CONFIG_FILE,
    SCRIPT_DIR,
)
from utils.helpers import load_json, save_json

from backend.game_model import GameModel
from steam.service import SteamAchievementsService
from steam.emu_service import SteamEmuAchievementsService
from steam.emu_discovery import default_roots as default_steam_emu_roots
from ui.notifications import PopupManager
from backend.controllers_achievements import AchievementsControllerOps
from backend.controllers_launch import LaunchControllerOps
from backend.controllers_settings import SettingsControllerOps
from backend.controllers_igdb_media import IgdbMediaControllerOps
from backend.controllers_library import LibraryControllerOps
from backend.controllers_ra import RaControllerOps
from backend.controllers_steam import SteamControllerOps
from backend.controllers_viewmodel import ViewModelControllerOps
from backend.controllers_sync import SyncControllerOps
from backend.controllers_hltb import HltbControllerOps
from backend.controllers_helpers import (
    achievement_sort_key_desc,
    format_unix_utc,
    detect_steam_id64,
    normalize_links_json,
    extract_steam_app_id_from_links,
)


class AppController(QObject):
    """Expose game library data and actions to QML."""

    libraryChanged = pyqtSignal()
    trackingChanged = pyqtSignal()
    playbackChanged = pyqtSignal()
    emulatorsChanged = pyqtSignal()
    errorMessage = pyqtSignal(str)
    igdbCoverDownloaded = pyqtSignal(bool, str, str)
    igdbSearchResults = pyqtSignal(list)
    igdbGameDetails = pyqtSignal("QVariantMap")
    igdbGameDetailsJson = pyqtSignal(str)
    riotClientPathChanged = pyqtSignal()
    steamApiSettingsChanged = pyqtSignal()
    steamEmuRootsChanged = pyqtSignal()
    isWindowsChanged = pyqtSignal()
    isLinuxChanged = pyqtSignal()
    raProgressChanged = pyqtSignal()
    raProgressLoaded = pyqtSignal(int, int, object, object)
    imagesUpdateFinished = pyqtSignal(int, str)
    steamGridImagesReady = pyqtSignal(str, str, str, str)
    steamRefreshProgress = pyqtSignal(int)
    steamGameLoaded = pyqtSignal(str)
    steamUnlockEvent = pyqtSignal(str)
    steamRefreshFinished = pyqtSignal()
    steamEmuRefreshProgress = pyqtSignal(int)
    steamEmuGameLoaded = pyqtSignal(str)
    steamEmuUnlockEvent = pyqtSignal(str)
    steamEmuRefreshFinished = pyqtSignal()

    def __init__(self, game_manager):
        super().__init__()
        try:
            from utils.helpers import debug_log
        except Exception:
            debug_log = None
        self._game_manager = game_manager
        self._game_model = GameModel(game_manager)
        self._selected_game_id = ""
        self._config = load_json(CONFIG_FILE, {})
        self._igdb_thread = None
        self._igdb_search_thread = None
        self._igdb_search_query = ""
        self._igdb_details_thread = None
        self._is_monitoring = False
        self._monitor_thread = None
        self._current_game_id = None
        self._current_pid = None
        self._session_start = None
        if debug_log:
            debug_log("[debug] init: ra ops")
        self._ra_ops = RaControllerOps(self)
        self._steam_ops = SteamControllerOps(self)
        if debug_log:
            debug_log("[debug] init: viewmodel ops")
        self._viewmodel_ops = ViewModelControllerOps(self)
        if debug_log:
            debug_log("[debug] init: sync ops")
        self._sync_ops = SyncControllerOps(self)
        self._auto_save_timer = QTimer()
        self._auto_save_timer.timeout.connect(self._auto_save)
        self.raProgressLoaded.connect(self._on_ra_progress_loaded)
        self._ra_unlocked = 0
        self._ra_total = 0
        self._ra_progress_game_id = None
        self._ra_progress_cache = self._load_ra_progress_cache_from_config()
        self._ra_unlocked_list = []
        self._images_update_running = False
        self.imagesUpdateFinished.connect(self._on_images_update_finished)
        if debug_log:
            debug_log("[debug] init: steam services")
        self._steam_thread_pool = QThreadPool.globalInstance()
        self._steam_popup_manager = None
        try:
            self._steam_popup_manager = PopupManager(parent=None)
        except Exception:
            self._steam_popup_manager = None
        self._steam_service = SteamAchievementsService(
            cache_base=SCRIPT_DIR / "cache",
            api_key=(self._config.get("steam_web_api_key") or "").strip(),
            lang=(self._config.get("steam_lang") or "en").strip(),
        )
        self._steam_emu_service = SteamEmuAchievementsService(
            cache_base=SCRIPT_DIR / "cache",
            api_key=(self._config.get("steam_web_api_key") or "").strip(),
            lang=(self._config.get("steam_lang") or "en").strip(),
        )
        if debug_log:
            debug_log("[debug] init: steam emu roots")
        self._steam_emu_service.set_extra_roots(
            self._config.get("steam_emu_custom_roots") or []
        )
        self._steam_emu_service.prime_watch_index()
        self._steamemu_watch_running = False
        self._steamemu_manual_refresh_running = False
        self._steamemu_manual_games_loaded = 0
        self._steamemu_manual_unlock_events = 0
        self._steamemu_manual_started_at = 0.0
        self._steamemu_cache_refresh_requested_at = 0.0
        if debug_log:
            debug_log("[debug] init: steam emu watch timer")
        self._steamemu_watch_timer = QTimer()
        self._steamemu_watch_timer.setInterval(2000)
        self._steamemu_watch_timer.timeout.connect(self.poll_steamemu_achievements)
        self._steamemu_watch_timer.start()
        self._steam_merged_by_appid = {}
        if debug_log:
            debug_log("[debug] init: achievements ops")
        self._achievements_ops = AchievementsControllerOps(self)
        if debug_log:
            debug_log("[debug] init: launch ops")
        self._launch_ops = LaunchControllerOps(self)
        if debug_log:
            debug_log("[debug] init: settings ops")
        self._settings_ops = SettingsControllerOps(self)
        if debug_log:
            debug_log("[debug] init: igdb ops")
        self._igdb_media_ops = IgdbMediaControllerOps(self)
        if debug_log:
            debug_log("[debug] init: library ops")
        self._library_ops = LibraryControllerOps(self)
        if debug_log:
            debug_log("[debug] init: hltb ops")
        self._hltb_ops = HltbControllerOps(self)

    def _load_ra_progress_cache_from_config(self):
        return self._ra_ops.load_ra_progress_cache_from_config()

    def _save_ra_progress_cache_to_config(self):
        self._ra_ops.save_ra_progress_cache_to_config()

    def _achievement_sort_key_desc(self, item):
        return achievement_sort_key_desc(item)

    def _format_unix_utc(self, ts):
        return format_unix_utc(ts)

    def _get_steam_id64(self):
        detected = detect_steam_id64(
            self._config,
            self._game_manager._get_steam_root_candidates(),
        )
        if detected and self._config.get("steam_id64") != detected:
            self._config["steam_id64"] = detected
            save_json(CONFIG_FILE, self._config)
        return detected

    def _get_steam_achievements(self, app_id):
        return self._achievements_ops.get_steam_achievements(app_id)

    def _get_steamemu_achievements(self, app_id):
        return self._achievements_ops.get_steamemu_achievements(app_id)

    def _extract_epic_achievements_from_payload(self, payload):
        return self._achievements_ops.extract_epic_achievements_from_payload(payload)

    def _get_epic_achievements(self, app_name):
        return self._achievements_ops.get_epic_achievements(app_name)

    def _get_rpcs3_achievements(self, emulator_id, serial):
        return self._achievements_ops.get_rpcs3_achievements(emulator_id, serial)

    @pyqtProperty(object, notify=libraryChanged)
    def libraryData(self):
        return self._game_manager.get_all_games()

    @pyqtProperty(object, notify=trackingChanged)
    def trackingData(self):
        return self._game_manager.tracking_data

    @pyqtProperty("QVariantMap", notify=emulatorsChanged)
    def emulatorsData(self):
        return self._game_manager.get_all_emulators()

    @pyqtProperty(bool, notify=isWindowsChanged)
    def isWindows(self):
        return IS_WINDOWS

    @pyqtProperty(bool, notify=isLinuxChanged)
    def isLinux(self):
        return IS_LINUX

    @pyqtProperty(str, notify=riotClientPathChanged)
    def riotClientPath(self):
        return self._config.get("riot_client_path", "")

    @pyqtProperty(str, notify=steamApiSettingsChanged)
    def steamWebApiKey(self):
        return self._config.get("steam_web_api_key", "")

    @pyqtProperty(str, notify=steamApiSettingsChanged)
    def steamId64(self):
        return self._config.get("steam_id64", "")


    def _get_platforms_from_config(self):
        platforms = self._config.get("platforms")
        if isinstance(platforms, list):
            return [str(p).strip() for p in platforms if str(p).strip()]
        return []

    def _infer_installed(self, game):
        return self._viewmodel_ops.infer_installed(game)

    def _save_platforms_to_config(self, platforms):
        self._config["platforms"] = platforms
        save_json(CONFIG_FILE, self._config)

    def _get_ra_id_by_rom_path(self, rom_path):
        return self._ra_ops.get_ra_id_by_rom_path(rom_path)

    def _get_ra_id_by_game_id(self, game_id):
        return self._ra_ops.get_ra_id_by_game_id(game_id)

    def _apply_ra_mapping_to_library(self):
        return self._ra_ops.apply_ra_mapping_to_library()

    def _set_ra_id_by_rom_path(self, rom_path, ra_game_id):
        self._ra_ops.set_ra_id_by_rom_path(rom_path, ra_game_id)

    def _set_ra_id_by_game_id(self, game_id, ra_game_id):
        self._ra_ops.set_ra_id_by_game_id(game_id, ra_game_id)

    @pyqtSlot(str)
    def set_riot_client_path(self, path):
        self._settings_ops.set_riot_client_path(path)

    @pyqtSlot(str, str)
    def set_steam_api_settings(self, api_key, steam_id64):
        self._settings_ops.set_steam_api_settings(api_key, steam_id64)


    @pyqtProperty("QVariantList", notify=steamEmuRootsChanged)
    def steamEmuDefaultRoots(self):
        roots = []
        for p in default_steam_emu_roots():
            try:
                roots.append(str(p))
            except Exception:
                continue
        return roots

    @pyqtProperty("QVariantList", notify=steamEmuRootsChanged)
    def steamEmuCustomRoots(self):
        roots = self._config.get("steam_emu_custom_roots") or []
        if not isinstance(roots, list):
            return []
        return [str(r) for r in roots if str(r).strip()]

    def _persist_steam_emu_custom_roots(self, roots):
        self._settings_ops.persist_steam_emu_custom_roots(roots)

    @pyqtSlot(str, result=str)
    def add_steam_emu_custom_root(self, path):
        return self._settings_ops.add_steam_emu_custom_root(path)

    @pyqtSlot(str, result=str)
    def remove_steam_emu_custom_root(self, path):
        return self._settings_ops.remove_steam_emu_custom_root(path)

    @pyqtProperty(QObject, constant=True)
    def gameModel(self):
        return self._game_model

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameId(self):
        return self._selected_game_id

    @pyqtSlot(str)
    def select_game(self, game_id):
        if game_id != self._selected_game_id:
            self._selected_game_id = game_id
            self.libraryChanged.emit()
            # selectedGameRunning depends on selected game id and monitoring state
            self.playbackChanged.emit()
            self._kick_ra_progress_update()

    def _kick_ra_progress_update(self):
        self._achievements_ops.kick_ra_progress_update()

    @pyqtSlot(int, int, object, object)
    def _on_ra_progress_loaded(self, unlocked, total, game_id, unlocked_list):
        self._achievements_ops.on_ra_progress_loaded(
            unlocked, total, game_id, unlocked_list
        )

    def _set_ra_progress(self, unlocked, total, game_id, unlocked_list=None):
        self._achievements_ops.set_ra_progress(
            unlocked, total, game_id, unlocked_list
        )

    @pyqtSlot(str)
    def set_selected_ra_game_id(self, ra_game_id_text):
        self._ra_ops.set_selected_ra_game_id(ra_game_id_text)

    @pyqtProperty(object, notify=libraryChanged)
    def selectedGame(self):
        return self._viewmodel_ops.selected_game()

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameName(self):
        return self._viewmodel_ops.selected_game_str("name")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameGenre(self):
        return self._viewmodel_ops.selected_game_str("genre")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameDevelopers(self):
        return self._viewmodel_ops.selected_game_str("developers")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGamePublishers(self):
        return self._viewmodel_ops.selected_game_str("publishers")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameCategories(self):
        return self._viewmodel_ops.selected_game_str("categories")

    @pyqtProperty("QStringList", notify=libraryChanged)
    def genreOptions(self):
        return self._viewmodel_ops.collect_unique_list("genre")

    @pyqtProperty("QStringList", notify=libraryChanged)
    def developerOptions(self):
        return self._viewmodel_ops.collect_unique_list("developers")

    @pyqtProperty("QStringList", notify=libraryChanged)
    def publisherOptions(self):
        return self._viewmodel_ops.collect_unique_list("publishers")

    @pyqtProperty("QStringList", notify=libraryChanged)
    def categoryOptions(self):
        return self._viewmodel_ops.collect_unique_list("categories")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGamePlatform(self):
        return self._viewmodel_ops.selected_game_str("platform")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameSource(self):
        return self._viewmodel_ops.selected_game_str("source")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameNotes(self):
        return self._viewmodel_ops.selected_game_str("notes")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameCover(self):
        return self._viewmodel_ops.selected_game_str("cover")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameLogo(self):
        return self._viewmodel_ops.selected_game_str("logo")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameHero(self):
        return self._viewmodel_ops.selected_game_str("hero")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameSerial(self):
        return self._viewmodel_ops.selected_game_str("serial")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameLinksJson(self):
        return self._viewmodel_ops.selected_links_json()

    @pyqtProperty(bool, notify=libraryChanged)
    def selectedGameIsEmulated(self):
        return self._viewmodel_ops.selected_game_bool("is_emulated", False)

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameEmulatorId(self):
        return self._viewmodel_ops.selected_game_str("emulator_id")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameRomPath(self):
        return self._viewmodel_ops.selected_game_str("rom_path")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameRaGameId(self):
        game = self._viewmodel_ops.selected_game()
        val = game.get("ra_game_id") if game else None
        return str(val) if val is not None else ""

    @pyqtProperty(int, notify=raProgressChanged)
    def selectedGameRaUnlocked(self):
        return self._ra_unlocked

    @pyqtProperty(int, notify=raProgressChanged)
    def selectedGameRaTotal(self):
        return self._ra_total

    @pyqtProperty(float, notify=raProgressChanged)
    def selectedGameRaProgress(self):
        if self._ra_total <= 0:
            return 0.0
        return float(self._ra_unlocked) / float(self._ra_total)

    @pyqtProperty(str, notify=raProgressChanged)
    def selectedGameRaProgressText(self):
        if self._ra_total <= 0:
            return ""
        return f"{self._ra_unlocked}/{self._ra_total}"

    @pyqtProperty("QVariantList", notify=raProgressChanged)
    def selectedGameRaUnlockedList(self):
        return self._ra_unlocked_list

    def _resolve_media_url(self, rel_path):
        return self._viewmodel_ops.resolve_media_url(rel_path)

    @pyqtSlot(str, result=str)
    def resolve_media_url(self, rel_path):
        return self._resolve_media_url(rel_path)

    def _update_game_media(
        self, new_entry, old_data, temp_path, media_type, game_name, media_dir
    ):
        self._igdb_media_ops.update_game_media(
            new_entry, old_data, temp_path, media_type, game_name, media_dir
        )

    @pyqtSlot(result=str)
    def update_images_from_steamgriddb(self):
        return self._igdb_media_ops.update_images_from_steamgriddb()

    @pyqtSlot(str, str)
    def download_steamgriddb_images_for_game(self, game_name, target):
        return self._igdb_media_ops.download_steamgriddb_images_for_game(game_name, target)

    @pyqtSlot(int, str)
    def _on_images_update_finished(self, updated, message):
        self._igdb_media_ops.on_images_update_finished(updated, message)

    def _rename_game_media(self, new_entry, old_data, media_type, game_name):
        self._library_ops.rename_game_media(new_entry, old_data, media_type, game_name)

    def _find_media_by_name(self, media_dir, game_name, media_type):
        return self._library_ops.find_media_by_name(media_dir, game_name, media_type)

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameCoverUrl(self):
        return self._resolve_media_url(self.selectedGameCover)

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameHeroUrl(self):
        return self._resolve_media_url(self.selectedGameHero)

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameProcessName(self):
        return self._viewmodel_ops.selected_game_str("process_name")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameExeWindows(self):
        return self._viewmodel_ops.selected_exe_for("Windows")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameExeLinux(self):
        return self._viewmodel_ops.selected_exe_for("Linux")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameInstallLocation(self):
        return self._viewmodel_ops.selected_game_str("install_location")

    @pyqtProperty("QVariantList", notify=libraryChanged)
    def platformOptions(self):
        return self._viewmodel_ops.platform_options()

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameWinePrefix(self):
        return self._viewmodel_ops.selected_game_str("wine_prefix")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameEnvVars(self):
        return self._viewmodel_ops.selected_game_str("env_vars")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameLaunchOptions(self):
        return self._viewmodel_ops.selected_game_str("launch_options")

    @pyqtProperty(bool, notify=libraryChanged)
    def selectedGameWineEsync(self):
        return self._viewmodel_ops.selected_game_bool("wine_esync", False)

    @pyqtProperty(bool, notify=libraryChanged)
    def selectedGameWineFsync(self):
        return self._viewmodel_ops.selected_game_bool("wine_fsync", False)

    @pyqtProperty(bool, notify=libraryChanged)
    def selectedGameProtonWayland(self):
        return self._viewmodel_ops.selected_game_bool("proton_wayland", False)

    @pyqtProperty(bool, notify=libraryChanged)
    def selectedGameProtonDiscordRichPresence(self):
        return self._viewmodel_ops.selected_game_bool("proton_discord_rich_presence", False)

    @pyqtProperty(bool, notify=libraryChanged)
    def selectedGameWindowsOnly(self):
        return self._viewmodel_ops.selected_game_bool("windows_only", False)

    @pyqtProperty(bool, notify=libraryChanged)
    def selectedGameInstalledFlag(self):
        game = self._viewmodel_ops.selected_game()
        if not game:
            return False
        return self._infer_installed(game)

    @pyqtProperty(bool, notify=libraryChanged)
    def selectedGameHidden(self):
        return self._viewmodel_ops.selected_game_bool("hidden", False)

    @pyqtProperty(int, notify=libraryChanged)
    def selectedGamePlaytimeMinutes(self):
        return self._viewmodel_ops.selected_playtime_minutes()

    @pyqtProperty(int, notify=libraryChanged)
    def selectedGamePlaytimeSeconds(self):
        return self._viewmodel_ops.selected_playtime_seconds()

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameProtonPath(self):
        return self._viewmodel_ops.selected_game_str("proton_path")

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameCompatTool(self):
        return self._viewmodel_ops.selected_compat_tool()

    @pyqtProperty("QVariantList", notify=libraryChanged)
    def availableCompatOptions(self):
        return self._viewmodel_ops.available_compat_options()

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameLastPlayedText(self):
        return self._viewmodel_ops.selected_last_played_text()

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameFirstPlayedDate(self):
        return self._viewmodel_ops.selected_first_played_date()

    @pyqtProperty(str, notify=libraryChanged)
    def selectedGameLastPlayedDate(self):
        return self._viewmodel_ops.selected_last_played_date()

    @pyqtProperty(bool, notify=playbackChanged)
    def isMonitoring(self):
        return self._is_monitoring

    @pyqtProperty(bool, notify=playbackChanged)
    def selectedGameRunning(self):
        return bool(self._is_monitoring and self._current_game_id and self._current_game_id == self._selected_game_id)

    def _get_exe_path_for_platform(self, game_data):
        return self._launch_ops.get_exe_path_for_platform(game_data)

    def _normalize_launch_type(self, launch_type):
        return self._launch_ops.normalize_launch_type(launch_type)

    def _get_emulator_exec_path(self, emulator, launch_type):
        return self._launch_ops.get_emulator_exec_path(emulator, launch_type)

    def _start_tracking(self, game_id, pid, start_time, proc=None):
        self._launch_ops.start_tracking(game_id, pid, start_time, proc)

    def _auto_save(self):
        self._launch_ops.auto_save()

    def _on_game_ended(self):
        self._launch_ops.on_game_ended()

    def _stop_tracking(self):
        self._launch_ops.stop_tracking()

    @pyqtSlot()
    def reload(self):
        self._sync_ops.reload()

    @pyqtSlot(result=str)
    def update_library_from_emulators(self):
        return self._sync_ops.update_library_from_emulators()

    @pyqtSlot(result=str)
    def refresh_steam_achievements(self):
        return self._steam_ops.refresh_steam_achievements()

    @pyqtSlot(result=str)
    def test_notification(self):
        try:
            return self._achievements_ops.emit_test_notification()
        except Exception as exc:
            return f"Test notification failed: {exc}"

    @pyqtSlot(result=str)
    def refresh_steamemu_achievements(self):
        return self._steam_ops.refresh_steamemu_achievements()

    @pyqtSlot()
    def poll_steamemu_achievements(self):
        self._steam_ops.poll_steamemu_achievements()

    @pyqtSlot()
    def play_selected(self):
        self._launch_ops.play_selected()

    @pyqtSlot(str, result=str)
    def launch_game_by_id(self, game_id):
        return self._launch_ops.launch_game_by_id(game_id)

    @pyqtSlot(result=str)
    def create_desktop_shortcut(self):
        return self._launch_ops.create_desktop_shortcut()

    @pyqtSlot(result=str)
    def create_start_menu_shortcut(self):
        return self._launch_ops.create_start_menu_shortcut()

    @pyqtSlot(result=str)
    def sync_selected_hltb(self):
        return self._hltb_ops.sync_selected_hltb()

    @pyqtSlot(str, str, str, str, str, str, str, str)
    def add_emulator(
        self,
        name,
        launch_type,
        exe_path,
        args_template,
        platforms,
        rom_extensions,
        rom_dirs,
        flatpak_id,
    ):
        self._settings_ops.add_emulator(
            name,
            launch_type,
            exe_path,
            args_template,
            platforms,
            rom_extensions,
            rom_dirs,
            flatpak_id,
        )

    @pyqtSlot(str, str, str, str, str, str, str, str, str)
    def update_emulator_fields(
        self,
        emulator_id,
        name,
        launch_type,
        exe_path,
        args_template,
        platforms,
        rom_extensions,
        rom_dirs,
        flatpak_id,
    ):
        self._settings_ops.update_emulator_fields(
            emulator_id,
            name,
            launch_type,
            exe_path,
            args_template,
            platforms,
            rom_extensions,
            rom_dirs,
            flatpak_id,
        )

    @pyqtSlot(str)
    def remove_emulator(self, emulator_id):
        self._settings_ops.remove_emulator(emulator_id)

    @pyqtSlot()
    def stop_playing(self):
        if self._is_monitoring:
            self._stop_tracking()

    @pyqtSlot()
    def remove_selected(self):
        self._library_ops.remove_selected()

    @pyqtSlot()
    def edit_selected(self):
        # QML opens the edit dialog; no-op here for now.
        pass

    @pyqtSlot(str, str, str, str)
    def update_selected_basic(self, name, genre, platform, notes):
        self._library_ops.update_selected_basic(name, genre, platform, notes)

    @pyqtSlot(str)
    def search_igdb(self, game_name):
        self._igdb_media_ops.search_igdb(game_name)

    def _on_igdb_finished(self, success, image_path, game_name):
        self._igdb_media_ops.on_igdb_finished(success, image_path, game_name)

    @pyqtSlot(str)
    def search_igdb_titles(self, query):
        self._igdb_media_ops.search_igdb_titles(query)

    def _on_igdb_search_finished(self, success, results):
        self._igdb_media_ops.on_igdb_search_finished(success, results)

    @pyqtSlot(str)
    def fetch_igdb_game_details(self, game_id):
        self._igdb_media_ops.fetch_igdb_game_details(game_id)

    def _on_igdb_details_finished(self, success, details):
        self._igdb_media_ops.on_igdb_details_finished(success, details)

    @pyqtSlot(str)
    def set_game_sort_order(self, order):
        self._game_model.set_sort_order(order)

    @pyqtSlot(str)
    def set_game_install_filter(self, mode):
        self._game_model.set_install_filter(mode)

    @pyqtSlot(str, str, str, result=str)
    def download_media(self, media_type, url, game_name):
        return self._igdb_media_ops.download_media(media_type, url, game_name)

    def _normalize_links_json(self, links_json):
        return normalize_links_json(links_json)

    def _extract_steam_app_id_from_links(self, links):
        return extract_steam_app_id_from_links(links)

    @pyqtSlot(
        str,
        str,
        str,
        str,
        str,
        str,
        int,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        bool,
        bool,
        bool,
        bool,
        bool,
        bool,
        str,
        str,
        str,
        str,
        str,
        bool,
        str,
        str,
        str,
        str,
        str,
    )
    def add_game_full(
        self,
        name,
        genre,
        platform,
        developers,
        publishers,
        categories,
        playtime_minutes,
        notes,
        serial,
        exe_windows,
        exe_linux,
        install_location,
        launch_options,
        wine_prefix,
        env_vars,
        wine_esync,
        wine_fsync,
        proton_wayland,
        proton_discord_rich_presence,
        windows_only,
        installed,
        cover_path,
        logo_path,
        hero_path,
        compat_tool,
        proton_path,
        is_emulated,
        emulator_id,
        rom_path,
        links_json,
        first_played_date,
        last_played_date,
    ):
        self._library_ops.add_game_full(
            name,
            genre,
            platform,
            developers,
            publishers,
            categories,
            playtime_minutes,
            notes,
            serial,
            exe_windows,
            exe_linux,
            install_location,
            launch_options,
            wine_prefix,
            env_vars,
            wine_esync,
            wine_fsync,
            proton_wayland,
            proton_discord_rich_presence,
            windows_only,
            installed,
            cover_path,
            logo_path,
            hero_path,
            compat_tool,
            proton_path,
            is_emulated,
            emulator_id,
            rom_path,
            links_json,
            first_played_date,
            last_played_date,
        )

    @pyqtSlot(
        str,
        str,
        str,
        str,
        str,
        str,
        int,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        bool,
        bool,
        bool,
        bool,
        bool,
        bool,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
    )
    def update_selected_full(
        self,
        name,
        genre,
        platform,
        developers,
        publishers,
        categories,
        playtime_minutes,
        notes,
        serial,
        exe_windows,
        exe_linux,
        install_location,
        launch_options,
        wine_prefix,
        env_vars,
        wine_esync,
        wine_fsync,
        proton_wayland,
        proton_discord_rich_presence,
        windows_only,
        installed,
        cover_path,
        logo_path,
        hero_path,
        compat_tool,
        proton_path,
        links_json,
        first_played_date,
        last_played_date,
    ):
        self._library_ops.update_selected_full(
            name,
            genre,
            platform,
            developers,
            publishers,
            categories,
            playtime_minutes,
            notes,
            serial,
            exe_windows,
            exe_linux,
            install_location,
            launch_options,
            wine_prefix,
            env_vars,
            wine_esync,
            wine_fsync,
            proton_wayland,
            proton_discord_rich_presence,
            windows_only,
            installed,
            cover_path,
            logo_path,
            hero_path,
            compat_tool,
            proton_path,
            links_json,
            first_played_date,
            last_played_date,
        )

    @pyqtSlot(bool, str, str)
    def update_selected_emulation(self, is_emulated, emulator_id, rom_path):
        self._library_ops.update_selected_emulation(is_emulated, emulator_id, rom_path)

    @pyqtSlot(bool)
    def set_selected_hidden(self, hidden):
        self._library_ops.set_selected_hidden(bool(hidden))
