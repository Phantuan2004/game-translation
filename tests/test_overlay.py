import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from app.settings_manager import SettingsManager
from overlay.translation_overlay import TranslationOverlay, GWL_EXSTYLE, WS_EX_TRANSPARENT
import ctypes


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_overlay_initialization(qapp, tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    mgr.set("overlay_position", {"x": 150, "y": 600})
    mgr.set("overlay_size", {"width": 700, "height": 160})

    overlay = TranslationOverlay(settings_manager=mgr)
    assert overlay.x() == 150
    assert overlay.y() == 600
    assert overlay.width() == 700
    assert overlay.height() == 160
    assert bool(overlay.windowFlags() & Qt.WindowType.FramelessWindowHint)
    assert bool(overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
    overlay.close()


def test_overlay_sequence_id_protection(qapp, tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    overlay = TranslationOverlay(settings_manager=mgr)

    # Initial update with sequence #1
    overlay.update_dialogue(seq_id=1, original_text="Hello", translated_text="Xin chào")
    assert overlay.trans_label.text() == "Xin chào"
    assert overlay.orig_label.text() == "Hello"

    # Update with newer sequence #2
    overlay.update_dialogue(seq_id=2, original_text="Goodbye", translated_text="Tạm biệt")
    assert overlay.trans_label.text() == "Tạm biệt"

    # Late-arriving sequence #1 must NOT overwrite #2
    overlay.update_dialogue(seq_id=1, original_text="Old", translated_text="Cũ")
    assert overlay.trans_label.text() == "Tạm biệt"
    overlay.close()


def test_overlay_styling_methods(qapp, tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    overlay = TranslationOverlay(settings_manager=mgr)

    overlay.set_font_size(24)
    assert mgr.get("overlay_font_size") == 24
    assert "24px" in overlay.trans_label.styleSheet()

    overlay.set_show_original(False)
    assert overlay.orig_label.isHidden() is True
    overlay.set_show_original(True)
    assert overlay.orig_label.isHidden() is False

    overlay.set_bg_opacity(0.5)
    assert mgr.get("overlay_bg_opacity") == 0.5
    overlay.close()


def test_overlay_click_through_toggle(qapp, tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    overlay = TranslationOverlay(settings_manager=mgr)
    overlay.show()

    # Enable click through
    overlay.set_click_through(True)
    hwnd = int(overlay.winId())
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    assert bool(style & WS_EX_TRANSPARENT) is True

    # Disable click through
    overlay.set_click_through(False)
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    assert bool(style & WS_EX_TRANSPARENT) is False

    overlay.close()
