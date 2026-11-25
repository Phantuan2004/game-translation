import ctypes
import logging
from ctypes import wintypes
from typing import Dict, Optional, Callable

from PySide6.QtCore import QObject, Signal, QAbstractNativeEventFilter
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

# Virtual key codes for common hotkeys
VK_MAP = {
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
}

WM_HOTKEY = 0x0312


class _WindowsNativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, dispatcher: Callable[[int], None]):
        super().__init__()
        self._dispatcher = dispatcher

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    hotkey_id = int(msg.wParam)
                    self._dispatcher(hotkey_id)
            except Exception as e:
                logger.error("Error in native hotkey event filter: %s", e)
        return False, 0


class HotkeyManager(QObject):
    """Manages system-wide Windows global hotkeys for gameplay control."""

    toggle_overlay = Signal()
    pause_resume = Signal()
    manual_translate = Signal()
    clear_translation = Signal()

    HOTKEY_IDS = {
        1001: "toggle_overlay",
        1002: "pause_resume",
        1003: "manual_translate",
        1004: "clear_translation",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registered_keys: Dict[int, int] = {}
        self._native_filter: Optional[_WindowsNativeHotkeyFilter] = None
        self._setup_filter()

    def _setup_filter(self):
        app = QApplication.instance()
        if app is not None:
            self._native_filter = _WindowsNativeHotkeyFilter(self._on_hotkey_triggered)
            app.installNativeEventFilter(self._native_filter)

    def register_defaults(self, hotkeys_dict: Optional[Dict[str, str]] = None):
        """Registers default or configured hotkeys."""
        cfg = hotkeys_dict or {
            "toggle_overlay": "F8",
            "pause_resume_capture": "F9",
            "translate_manual": "F10",
            "clear_translation": "F11",
        }

        self.unregister_all()

        user32 = ctypes.windll.user32
        mapping = {
            1001: cfg.get("toggle_overlay", "F8"),
            1002: cfg.get("pause_resume_capture", "F9"),
            1003: cfg.get("translate_manual", "F10"),
            1004: cfg.get("clear_translation", "F11"),
        }

        for hid, key_name in mapping.items():
            vk = VK_MAP.get(key_name.upper())
            if vk is not None:
                # Modifiers = 0 (no Alt/Ctrl required for F-keys)
                res = user32.RegisterHotKey(None, hid, 0, vk)
                if res:
                    self._registered_keys[hid] = vk
                    logger.info("Registered global hotkey %s (ID %d)", key_name, hid)
                else:
                    err = ctypes.GetLastError()
                    logger.warning("Could not register hotkey %s (Error code: %d)", key_name, err)

    def _on_hotkey_triggered(self, hotkey_id: int):
        action = self.HOTKEY_IDS.get(hotkey_id)
        if action == "toggle_overlay":
            self.toggle_overlay.emit()
        elif action == "pause_resume":
            self.pause_resume.emit()
        elif action == "manual_translate":
            self.manual_translate.emit()
        elif action == "clear_translation":
            self.clear_translation.emit()

    def unregister_all(self):
        user32 = ctypes.windll.user32
        for hid in list(self._registered_keys.keys()):
            user32.UnregisterHotKey(None, hid)
        self._registered_keys.clear()

    def cleanup(self):
        self.unregister_all()
        app = QApplication.instance()
        if app and self._native_filter:
            app.removeNativeEventFilter(self._native_filter)
            self._native_filter = None
