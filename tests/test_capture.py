import time
import pytest
import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage
from capture.screen_capture import ScreenCapture
from workers.capture_worker import CaptureWorker


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def pump_events(qapp, duration_sec: float = 0.1, step: float = 0.02):
    """Pumps Qt event loop so queued cross-thread signals are dispatched."""
    start = time.perf_counter()
    while time.perf_counter() - start < duration_sec:
        qapp.processEvents()
        time.sleep(step)


def test_get_monitors(qapp):
    sc = ScreenCapture()
    try:
        monitors = sc.get_monitors()
        assert len(monitors) >= 1
        assert monitors[0]["id"] == 0
        assert monitors[0]["width"] > 0
        assert monitors[0]["height"] > 0
    finally:
        sc.close()


def test_capture_region(qapp):
    sc = ScreenCapture()
    try:
        region = {"left": 0, "top": 0, "width": 100, "height": 100}
        qimg, frame, latency_ms = sc.capture_region(region)
        assert isinstance(qimg, QImage)
        assert not qimg.isNull()
        assert isinstance(frame, np.ndarray)
        assert frame.shape[2] == 4  # BGRA 4 channels
        assert latency_ms >= 0.0
        # Target metric check: capture selected region should be < 50ms
        assert latency_ms < 50.0
    finally:
        sc.close()


def test_capture_invalid_dimensions(qapp):
    sc = ScreenCapture()
    try:
        with pytest.raises(ValueError):
            sc.capture_region({"left": 0, "top": 0, "width": 0, "height": 100})
    finally:
        sc.close()


def test_frame_to_qimage(qapp):
    sc = ScreenCapture()
    try:
        dummy_frame = np.zeros((60, 80, 4), dtype=np.uint8)
        dummy_frame[:, :, 0] = 255  # Blue channel
        qimg = sc.frame_to_qimage(dummy_frame)
        assert isinstance(qimg, QImage)
        assert not qimg.isNull()
        assert qimg.width() == 80
        assert qimg.height() == 60
    finally:
        sc.close()


def test_capture_worker_lifecycle(qapp):
    region = {"left": 0, "top": 0, "width": 50, "height": 50}
    worker = CaptureWorker(region=region, interval_ms=50)

    received_frames = []

    def on_frame(qimg, arr, lat):
        received_frames.append(lat)

    worker.frame_ready.connect(on_frame)

    worker.start()
    pump_events(qapp, duration_sec=0.3)

    assert worker.isRunning()
    assert len(received_frames) > 0

    # Test pause
    worker.pause_capture()
    pump_events(qapp, duration_sec=0.1)
    count_after_pause = len(received_frames)
    pump_events(qapp, duration_sec=0.15)
    assert len(received_frames) == count_after_pause  # No new frames while paused

    # Test resume
    worker.resume_capture()
    pump_events(qapp, duration_sec=0.2)
    assert len(received_frames) > count_after_pause

    # Test stop
    worker.stop()
    pump_events(qapp, duration_sec=0.05)
    assert not worker.isRunning()
