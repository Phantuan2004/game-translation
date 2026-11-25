import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPixmap, QGuiApplication

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Provides high-performance screen capture operations.
    
    Supports Qt QScreen capture (sub-millisecond, DPI-aware, robust on Windows 11)
    with MSS fallback/integration.
    """

    def __init__(self, preferred_backend: str = "qt"):
        self.preferred_backend = preferred_backend
        self._mss_sct = None
        self._mss_failed = False

    def _get_mss(self):
        if self._mss_failed:
            return None
        if self._mss_sct is None:
            try:
                import mss
                self._mss_sct = mss.mss()
            except Exception as e:
                logger.warning("Could not initialize MSS: %s", e)
                self._mss_failed = True
                return None
        return self._mss_sct

    def get_monitors(self) -> List[Dict[str, Any]]:
        """Returns the list of available monitors using Qt QScreen / MSS.
        
        Monitor 0: All Monitors Combined (Virtual Desktop)
        Monitor 1..N: Physical / Logical displays with DPI and resolution info.
        """
        monitors = []
        screens = QGuiApplication.screens()
        
        if screens:
            # Calculate combined desktop bounds
            combined_rect = screens[0].geometry()
            for s in screens[1:]:
                combined_rect = combined_rect.united(s.geometry())

            monitors.append({
                "id": 0,
                "name": f"All Monitors Combined ({combined_rect.width()}x{combined_rect.height()})",
                "left": combined_rect.left(),
                "top": combined_rect.top(),
                "width": combined_rect.width(),
                "height": combined_rect.height(),
            })

            for idx, screen in enumerate(screens, start=1):
                geo = screen.geometry()
                dpr = screen.devicePixelRatio()
                dpr_str = f" @ {int(dpr * 100)}% DPI" if dpr != 1.0 else ""
                name = f"Monitor {idx}: {screen.name()} ({geo.width()}x{geo.height()}{dpr_str})"
                monitors.append({
                    "id": idx,
                    "name": name,
                    "left": geo.left(),
                    "top": geo.top(),
                    "width": geo.width(),
                    "height": geo.height(),
                    "dpr": dpr,
                })
        else:
            # Fallback to basic virtual screen
            monitors.append({
                "id": 0,
                "name": "Primary Display",
                "left": 0,
                "top": 0,
                "width": 1920,
                "height": 1080,
            })

        return monitors

    def capture_region(self, region: Dict[str, int]) -> Tuple[QImage, np.ndarray, float]:
        """Captures a rectangular region.
        
        region: {'left': int, 'top': int, 'width': int, 'height': int}
        Returns:
            (qimage: QImage, bgra_array: np.ndarray, latency_ms: float)
        """
        left = int(region["left"])
        top = int(region["top"])
        width = int(region["width"])
        height = int(region["height"])

        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid capture dimensions: {width}x{height}")

        start_time = time.perf_counter()

        # Primary backend: Qt QScreen (native, DPI-aware, sub-millisecond)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            pixmap = screen.grabWindow(0, left, top, width, height)
            qimage = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Convert QImage buffer directly to NumPy array
            w, h = qimage.width(), qimage.height()
            ptr = qimage.constBits()
            # Memory layout: Format_ARGB32 in little endian is BGRA
            bgra_array = np.frombuffer(ptr, dtype=np.uint8, count=h * w * 4).reshape((h, w, 4)).copy()
            return qimage, bgra_array, latency_ms

        # Fallback to MSS if QScreen is not available
        sct = self._get_mss()
        if sct is not None:
            bbox = {"left": left, "top": top, "width": width, "height": height}
            shot = sct.grab(bbox)
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            bgra_array = np.array(shot, dtype=np.uint8)
            qimage = self.frame_to_qimage(bgra_array)
            return qimage, bgra_array, latency_ms

        raise RuntimeError("No screen capture backend available.")

    @staticmethod
    def frame_to_qimage(frame: np.ndarray) -> QImage:
        """Converts a BGRA numpy array into a PySide6 QImage."""
        if frame is None or frame.size == 0:
            return QImage()
        height, width, channels = frame.shape
        bytes_per_line = channels * width
        qimage = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_ARGB32)
        return qimage.copy()

    def close(self):
        if self._mss_sct is not None:
            try:
                self._mss_sct.close()
            except Exception:
                pass
            self._mss_sct = None
