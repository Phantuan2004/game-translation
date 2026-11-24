import json
import logging
import os
import copy
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "monitor_index": 1,
    "capture_region": None,  # dict: {"left": int, "top": int, "width": int, "height": int}
    "capture_interval_ms": 150,
    "ocr_enabled": True,
    "ocr_confidence_threshold": 0.5,
    "source_language": "auto",
    "target_language": "vi",
    "translation_provider": "google",
    "translation_api_key": "",
    "translation_timeout_sec": 3.0,
    "overlay_enabled": True,
    "overlay_position": {"x": 100, "y": 700},
    "overlay_size": {"width": 800, "height": 180},
    "overlay_font_size": 18,
    "overlay_text_color": "#FFFFFF",
    "overlay_bg_color": "#121212",
    "overlay_bg_opacity": 0.8,
    "overlay_click_through": True,
    "overlay_show_original": True,
    "txt_output_enabled": True,
    "txt_output_path": "game_translation.txt",
    "hotkeys": {
        "toggle_overlay": "F8",
        "pause_resume_capture": "F9",
        "translate_manual": "F10",
        "clear_translation": "F11",
    },
}


class SettingsManager:
    """Manages application configuration persistence with safe fallback and validation."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path("config") / "settings.json"

        self._settings: Dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> Dict[str, Any]:
        """Loads configuration from JSON file. Restores defaults if missing or corrupt."""
        if not self.config_path.exists():
            logger.info("Config file does not exist at %s. Creating with defaults.", self.config_path)
            self._settings = copy.deepcopy(DEFAULT_SETTINGS)
            self.save()
            return self._settings

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            if not isinstance(loaded, dict):
                raise ValueError("Config root must be a JSON object.")

            # Validate and merge with defaults
            merged = copy.deepcopy(DEFAULT_SETTINGS)
            self._deep_update(merged, loaded)
            self._validate(merged)
            self._settings = merged
            logger.info("Successfully loaded settings from %s", self.config_path)
        except Exception as e:
            logger.warning("Failed to load settings from %s: %s. Using default settings.", self.config_path, e)
            self._settings = copy.deepcopy(DEFAULT_SETTINGS)
            self.save()

        return self._settings

    def save(self) -> bool:
        """Saves current configuration to JSON file safely."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.config_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.config_path)
            logger.debug("Settings saved to %s", self.config_path)
            return True
        except Exception as e:
            logger.error("Failed to save settings to %s: %s", self.config_path, e)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        self._settings[key] = value
        if auto_save:
            self.save()

    @property
    def all_settings(self) -> Dict[str, Any]:
        return copy.deepcopy(self._settings)

    def reset_to_defaults(self, auto_save: bool = True) -> None:
        self._settings = copy.deepcopy(DEFAULT_SETTINGS)
        if auto_save:
            self.save()

    def _deep_update(self, target: dict, source: dict) -> None:
        for k, v in source.items():
            if k in target and isinstance(target[k], dict) and isinstance(v, dict):
                self._deep_update(target[k], v)
            else:
                target[k] = v

    def _validate(self, settings: Dict[str, Any]) -> None:
        # Validate capture interval
        interval = settings.get("capture_interval_ms", 150)
        if not isinstance(interval, (int, float)) or interval < 20 or interval > 5000:
            settings["capture_interval_ms"] = DEFAULT_SETTINGS["capture_interval_ms"]

        # Validate capture region
        reg = settings.get("capture_region")
        if reg is not None:
            if not isinstance(reg, dict) or not all(k in reg for k in ("left", "top", "width", "height")):
                settings["capture_region"] = None
            elif reg["width"] <= 0 or reg["height"] <= 0:
                settings["capture_region"] = None
