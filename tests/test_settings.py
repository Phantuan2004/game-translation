import json
import pytest
from pathlib import Path
from app.settings_manager import SettingsManager, DEFAULT_SETTINGS


def test_settings_default(tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    assert mgr.get("capture_interval_ms") == 150
    assert mgr.get("target_language") == "vi"
    assert mgr.get("capture_region") is None
    assert cfg_file.exists()


def test_settings_save_and_reload(tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    
    test_region = {"left": 100, "top": 200, "width": 400, "height": 300}
    mgr.set("capture_region", test_region)
    mgr.set("capture_interval_ms", 250)

    # Reload in a new manager
    mgr2 = SettingsManager(str(cfg_file))
    assert mgr2.get("capture_region") == test_region
    assert mgr2.get("capture_interval_ms") == 250


def test_corrupt_json_fallback(tmp_path):
    cfg_file = tmp_path / "settings.json"
    cfg_file.write_text("{ this is corrupt json syntax ...", encoding="utf-8")

    mgr = SettingsManager(str(cfg_file))
    # Should restore defaults without crashing
    assert mgr.get("capture_interval_ms") == DEFAULT_SETTINGS["capture_interval_ms"]
    assert mgr.get("target_language") == "vi"


def test_settings_validation(tmp_path):
    cfg_file = tmp_path / "settings.json"
    # Write invalid values
    bad_data = {
        "capture_interval_ms": -999,
        "capture_region": {"left": 0, "top": 0, "width": -50, "height": 100},
    }
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(bad_data, f)

    mgr = SettingsManager(str(cfg_file))
    # Validation should fix interval and invalidate negative width
    assert mgr.get("capture_interval_ms") == DEFAULT_SETTINGS["capture_interval_ms"]
    assert mgr.get("capture_region") is None


def test_settings_inaccessible_txt_path_fallback(monkeypatch, tmp_path):
    cfg_file = tmp_path / "settings.json"
    bad_data = {
        "txt_output_path": "C:\\Users\\phanh\\OneDrive\\Máy tính\\Code\\game translate\\test_run_output.txt",
    }
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(bad_data, f)

    orig_mkdir = Path.mkdir

    def fake_mkdir(self, *args, **kwargs):
        if "phanh" in str(self):
            raise PermissionError("Access is denied")
        return orig_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)
    mgr = SettingsManager(str(cfg_file))
    assert mgr.get("txt_output_path") == DEFAULT_SETTINGS["txt_output_path"]


def test_settings_empty_txt_path_fallback(tmp_path):
    cfg_file = tmp_path / "settings.json"
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump({"txt_output_path": "   "}, f)

    mgr = SettingsManager(str(cfg_file))
    assert mgr.get("txt_output_path") == DEFAULT_SETTINGS["txt_output_path"]
