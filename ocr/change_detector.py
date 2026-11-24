import time
import logging
from typing import Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImageChangeDetector:
    """Lightweight image change detector to prevent redundant OCR computation.
    
    Downsamples dialogue regions and calculates mean absolute differences.
    Runs in < 2 ms.
    """

    def __init__(self, diff_threshold: float = 3.5, thumbnail_size: Tuple[int, int] = (120, 40)):
        self.diff_threshold = diff_threshold
        self.thumbnail_size = thumbnail_size
        self._previous_thumb: Optional[np.ndarray] = None
        self._last_change_time: float = 0.0

    def has_changed(self, frame: np.ndarray) -> Tuple[bool, float, float]:
        """Evaluates whether the given frame has changed significantly from the previous one.
        
        Args:
            frame: BGRA or BGR numpy array
            
        Returns:
            (changed: bool, diff_score: float, latency_ms: float)
        """
        if frame is None or frame.size == 0:
            return False, 0.0, 0.0

        start_time = time.perf_counter()

        # Convert to grayscale
        if len(frame.shape) == 3:
            if frame.shape[2] == 4:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # Downsample to thumbnail to eliminate micro pixel noise and compression jitter
        thumb = cv2.resize(gray, self.thumbnail_size, interpolation=cv2.INTER_AREA)

        if self._previous_thumb is None or self._previous_thumb.shape != thumb.shape:
            self._previous_thumb = thumb
            self._last_change_time = time.perf_counter()
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            # First frame is always considered a change
            return True, 100.0, latency_ms

        # Compute Mean Absolute Difference
        diff = np.mean(np.abs(thumb.astype(np.int16) - self._previous_thumb.astype(np.int16)))
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        changed = float(diff) >= self.diff_threshold

        if changed:
            self._previous_thumb = thumb
            self._last_change_time = time.perf_counter()

        return changed, float(diff), latency_ms

    def reset(self):
        """Resets the baseline image."""
        self._previous_thumb = None
        self._last_change_time = 0.0
