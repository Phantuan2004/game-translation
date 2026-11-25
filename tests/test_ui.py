import time
import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication
from app.settings_manager import SettingsManager
from app.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def pump(qapp, duration: float = 0.15):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < duration:
        qapp.processEvents()
        time.sleep(0.02)


def test_main_window_init(qapp, tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    
    window = MainWindow(settings_manager=mgr)
    assert window.windowTitle() == "Game Translator — Real-time Dialogue Translation"
    assert window.state_badge.text() == "STOPPED"
    assert window.start_btn.isEnabled()
    assert not window.pause_btn.isEnabled()
    assert not window.stop_btn.isEnabled()
    window.close()


def test_main_window_capture_workflow(qapp, tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    # Preset region so start capture can begin immediately
    mgr.set("capture_region", {"left": 0, "top": 0, "width": 120, "height": 80})

    window = MainWindow(settings_manager=mgr)
    assert "120x80" in window.region_label.text()

    # Start capture
    window._start_capture()
    pump(qapp, 0.2)
    assert window.capture_worker is not None
    assert window.capture_worker.isRunning()
    assert window.state_badge.text() == "CAPTURING"
    assert not window.start_btn.isEnabled()
    assert window.pause_btn.isEnabled()
    assert window.stop_btn.isEnabled()

    # Pause capture
    window._pause_capture()
    pump(qapp, 0.15)
    assert window.state_badge.text() == "PAUSED"

    # Stop capture
    window._stop_capture()
    pump(qapp, 0.15)
    assert window.state_badge.text() == "STOPPED"
    assert window.start_btn.isEnabled()

    window.close()


def test_main_window_ocr_integration(qapp, tmp_path):
    cfg_file = tmp_path / "settings.json"
    mgr = SettingsManager(str(cfg_file))
    mgr.set("capture_region", {"left": 0, "top": 0, "width": 200, "height": 100})

    window = MainWindow(settings_manager=mgr)
    window._start_capture()
    # Pause capture so we control injected frames
    window.capture_worker.pause_capture()

    assert window.ocr_worker is not None
    assert window.ocr_worker.isRunning()

    # Create synthetic dialogue
    img = np.zeros((100, 500, 4), dtype=np.uint8)
    img[:, :, :3] = (25, 25, 30)
    img[:, :, 3] = 255
    cv2.putText(img, "The journey begins now.", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    window.ocr_worker.enqueue_frame(img)

    # Allow time for initial OCR warm-up
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 3.0 and not window.detected_text_edit.toPlainText():
        qapp.processEvents()
        time.sleep(0.03)

    text = window.detected_text_edit.toPlainText()
    assert len(text) > 0
    assert "journey" in text.lower() or "begins" in text.lower()
    assert window.seq_badge.text() == "Seq: #1"

    window.close()
