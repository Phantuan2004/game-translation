import time
import logging
from typing import Optional
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition

from ocr.ocr_engine import BaseOCREngine, get_ocr_engine
from ocr.change_detector import ImageChangeDetector
from ocr.dialogue_detector import DialogueDetector, DialogueEvent

logger = logging.getLogger(__name__)


class OCRWorker(QThread):
    """Background worker thread that performs change detection and OCR on captured frames.
    
    Operates with latest-frame priority to strictly prevent backlog accumulation.
    """

    # Signals
    # dialogue_detected(seq_id: int, original_text: str, confidence: float, latency_ms: float)
    dialogue_detected = pyqtSignal(int, str, float, float)
    ocr_skipped = pyqtSignal(float)  # diff_score
    ocr_completed = pyqtSignal(str, float, float)  # text, confidence, latency_ms
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        engine_name: str = "auto",
        min_confidence: float = 0.4,
        change_threshold: float = 3.5,
        parent=None,
    ):
        super().__init__(parent)
        self._mutex = QMutex()
        self._condition = QWaitCondition()

        self._engine_name = engine_name
        self._min_confidence = min_confidence
        self._change_threshold = change_threshold

        self._pending_frame: Optional[np.ndarray] = None
        self._running: bool = False
        self._enabled: bool = True

        self._change_detector = ImageChangeDetector(diff_threshold=change_threshold)
        self._dialogue_detector = DialogueDetector()
        self._engine: Optional[BaseOCREngine] = None

    def start(self, priority=QThread.Priority.InheritPriority):
        with QMutexLocker(self._mutex):
            self._running = True
        super().start(priority)

    def set_engine(self, engine_name: str):
        with QMutexLocker(self._mutex):
            self._engine_name = engine_name
            self._engine = None  # Will be reloaded on next cycle

    def set_min_confidence(self, conf: float):
        with QMutexLocker(self._mutex):
            self._min_confidence = max(0.0, min(1.0, conf))

    def set_enabled(self, enabled: bool):
        with QMutexLocker(self._mutex):
            self._enabled = enabled

    def reset_detectors(self):
        with QMutexLocker(self._mutex):
            self._change_detector.reset()
            self._dialogue_detector.reset()

    def enqueue_frame(self, frame: np.ndarray):
        """Submits the newest frame for OCR. Outdated pending frames are replaced immediately."""
        with QMutexLocker(self._mutex):
            if not self._enabled:
                return
            # Overwrite pending frame with latest frame (bounded queue of size 1)
            self._pending_frame = frame
            self._condition.wakeOne()

    def stop(self):
        with QMutexLocker(self._mutex):
            self._running = False
            self._pending_frame = None
            self._condition.wakeAll()
        self.wait(2000)
        logger.info("OCRWorker stopped.")

    def run(self):
        with QMutexLocker(self._mutex):
            self._running = True

        logger.info("OCRWorker thread started.")

        # Lazy initialize OCR engine inside this worker thread
        try:
            self._engine = get_ocr_engine(self._engine_name)
        except Exception as e:
            logger.error("Failed to initialize OCR engine '%s': %s", self._engine_name, e)
            self.error_occurred.emit(f"OCR init error: {e}")

        while True:
            frame = None
            with QMutexLocker(self._mutex):
                while self._running and self._pending_frame is None:
                    self._condition.wait(self._mutex)

                if not self._running:
                    break

                frame = self._pending_frame
                self._pending_frame = None
                enabled = self._enabled
                min_conf = self._min_confidence

                # Reload engine if changed
                if self._engine is None:
                    try:
                        self._engine = get_ocr_engine(self._engine_name)
                    except Exception as e:
                        logger.error("Failed to load OCR engine: %s", e)
                        self.error_occurred.emit(f"OCR error: {e}")
                        continue

            if not enabled or frame is None:
                continue

            try:
                # 1. Image Change Detection (sub-millisecond)
                changed, diff_score, change_lat = self._change_detector.has_changed(frame)
                if not changed:
                    self.ocr_skipped.emit(diff_score)
                    continue

                # 2. Local OCR Execution
                t_ocr_start = time.perf_counter()
                ocr_res = self._engine.recognize(frame)
                total_ocr_lat = (time.perf_counter() - t_ocr_start) * 1000.0

                self.ocr_completed.emit(ocr_res.text, ocr_res.confidence, total_ocr_lat)

                if not ocr_res.text or ocr_res.confidence < min_conf:
                    continue

                # 3. Text Normalization and Duplicate Dialogue Detection
                dialogue_event = self._dialogue_detector.process_text(
                    ocr_res.text,
                    ocr_res.confidence,
                )

                if dialogue_event is not None:
                    self.dialogue_detected.emit(
                        dialogue_event.seq_id,
                        dialogue_event.text,
                        dialogue_event.confidence,
                        total_ocr_lat,
                    )

            except Exception as ex:
                logger.error("Error in OCRWorker execution: %s", ex, exc_info=True)
                self.error_occurred.emit(f"OCR error: {ex}")

        with QMutexLocker(self._mutex):
            self._running = False
        logger.info("OCRWorker thread exited.")
