import logging
import time
from typing import Dict, Optional
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
from PyQt6.QtGui import QImage

from capture.screen_capture import ScreenCapture

logger = logging.getLogger(__name__)


class CaptureWorker(QThread):
    """Background worker thread that captures screen regions at configured intervals."""

    # Signals:
    # frame_ready(QImage for UI preview, np.ndarray BGRA for OCR/pipeline, latency_ms)
    frame_ready = pyqtSignal(QImage, object, float)
    fps_updated = pyqtSignal(float, float)  # (fps, avg_latency_ms)
    status_changed = pyqtSignal(bool, bool)  # (is_running, is_paused)
    error_occurred = pyqtSignal(str)

    def __init__(self, region: Optional[Dict[str, int]] = None, interval_ms: int = 150, parent=None):
        super().__init__(parent)
        self._mutex = QMutex()
        self._region: Optional[Dict[str, int]] = region
        self._interval_ms: int = max(20, interval_ms)
        self._running: bool = False
        self._paused: bool = False
        self._screen_cap: Optional[ScreenCapture] = None

    def set_region(self, region: Optional[Dict[str, int]]) -> None:
        with QMutexLocker(self._mutex):
            self._region = region
            logger.info("CaptureWorker region updated to: %s", self._region)

    def set_interval(self, interval_ms: int) -> None:
        with QMutexLocker(self._mutex):
            self._interval_ms = max(20, interval_ms)

    def pause_capture(self) -> None:
        with QMutexLocker(self._mutex):
            self._paused = True
        self.status_changed.emit(self._running, self._paused)
        logger.info("CaptureWorker paused.")

    def resume_capture(self) -> None:
        with QMutexLocker(self._mutex):
            self._paused = False
        self.status_changed.emit(self._running, self._paused)
        logger.info("CaptureWorker resumed.")

    def stop(self) -> None:
        with QMutexLocker(self._mutex):
            self._running = False
        self.wait(2000)
        self.status_changed.emit(False, False)
        logger.info("CaptureWorker stopped.")

    def run(self) -> None:
        with QMutexLocker(self._mutex):
            self._running = True
            self._paused = False

        self.status_changed.emit(True, False)
        logger.info("CaptureWorker thread started.")

        self._screen_cap = ScreenCapture()
        fps_timer = time.perf_counter()
        frame_counter = 0
        latency_accumulator = 0.0

        try:
            while True:
                with QMutexLocker(self._mutex):
                    if not self._running:
                        break
                    is_paused = self._paused
                    region = self._region
                    interval_s = self._interval_ms / 1000.0

                if is_paused or region is None:
                    time.sleep(0.05)
                    continue

                loop_start = time.perf_counter()
                try:
                    qimg, frame_array, latency_ms = self._screen_cap.capture_region(region)
                    self.frame_ready.emit(qimg, frame_array, latency_ms)

                    frame_counter += 1
                    latency_accumulator += latency_ms

                    # Calculate FPS every ~1.0 second
                    now = time.perf_counter()
                    elapsed = now - fps_timer
                    if elapsed >= 1.0:
                        fps = frame_counter / elapsed
                        avg_lat = latency_accumulator / frame_counter if frame_counter > 0 else 0.0
                        self.fps_updated.emit(fps, avg_lat)
                        frame_counter = 0
                        latency_accumulator = 0.0
                        fps_timer = now

                except Exception as ex:
                    logger.error("Error during frame capture: %s", ex)
                    self.error_occurred.emit(f"Capture error: {ex}")
                    time.sleep(0.2)

                # Sleep to maintain desired interval, accounting for elapsed time
                loop_elapsed = time.perf_counter() - loop_start
                sleep_needed = max(0.001, interval_s - loop_elapsed)
                time.sleep(sleep_needed)

        finally:
            if self._screen_cap:
                self._screen_cap.close()
                self._screen_cap = None
            with QMutexLocker(self._mutex):
                self._running = False
            self.status_changed.emit(False, False)
            logger.info("CaptureWorker thread exited.")
