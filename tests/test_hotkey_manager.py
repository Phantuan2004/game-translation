import pytest
from PySide6.QtWidgets import QApplication
from app.hotkey_manager import HotkeyManager, VK_MAP


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_hotkey_manager_initialization_and_cleanup(qapp):
    manager = HotkeyManager()
    manager.register_defaults()

    # Verify ID mapping
    assert 1001 in HotkeyManager.HOTKEY_IDS
    assert HotkeyManager.HOTKEY_IDS[1001] == "toggle_overlay"

    # Test trigger dispatcher
    triggered = []
    manager.toggle_overlay.connect(lambda: triggered.append("toggle"))
    manager._on_hotkey_triggered(1001)
    assert triggered == ["toggle"]

    manager.pause_resume.connect(lambda: triggered.append("pause"))
    manager._on_hotkey_triggered(1002)
    assert triggered == ["toggle", "pause"]

    manager.cleanup()
    assert len(manager._registered_keys) == 0


def test_vk_map_coverage():
    assert VK_MAP["F8"] == 0x77
    assert VK_MAP["F9"] == 0x78
    assert VK_MAP["F10"] == 0x79
    assert VK_MAP["F11"] == 0x7A
