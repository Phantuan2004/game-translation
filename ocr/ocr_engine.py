import abc
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional
import numpy as np
from PIL import Image

from ocr.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    text: str
    confidence: float
    latency_ms: float
    engine_name: str
    lines: List[str] = field(default_factory=list)


class BaseOCREngine(abc.ABC):
    """Abstract base class for pluggable local OCR engines."""

    @abc.abstractmethod
    def recognize(self, frame: np.ndarray) -> OCRResult:
        """Extracts text from an image frame (NumPy BGRA/BGR array)."""
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the human-readable engine name."""
        pass


class WindowsMediaOCREngine(BaseOCREngine):
    """Local Windows Media OCR (built into Windows 10/11).
    
    Extremely fast (~5-15 ms) with zero cloud dependencies.
    """

    def __init__(self, lang: str = "en"):
        self.lang = lang
        import winocr
        self._winocr = winocr

    @property
    def name(self) -> str:
        return "Windows Media OCR (Fast)"

    def recognize(self, frame: np.ndarray) -> OCRResult:
        if frame is None or frame.size == 0:
            return OCRResult(text="", confidence=0.0, latency_ms=0.0, engine_name=self.name)

        start_time = time.perf_counter()

        # Convert BGRA/BGR to PIL Image RGB
        if frame.shape[2] == 4:
            # Drop alpha, convert BGR to RGB
            rgb = frame[:, :, [2, 1, 0]]
        else:
            rgb = frame[:, :, ::-1]

        pil_img = Image.fromarray(rgb)
        res = self._winocr.recognize_pil_sync(pil_img, lang=self.lang)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        raw_text = res.get("text", "")
        lines = [line.get("text", "") for line in res.get("lines", [])]
        joined = TextNormalizer.join_lines(lines) if lines else TextNormalizer.normalize(raw_text)

        # Windows Media OCR doesn't return numeric confidence; assume 0.95 on success
        confidence = 0.95 if joined else 0.0

        return OCRResult(
            text=joined,
            confidence=confidence,
            latency_ms=latency_ms,
            engine_name=self.name,
            lines=lines,
        )


class RapidOCREngine(BaseOCREngine):
    """Local RapidOCR engine (ONNX neural text detection & recognition)."""

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self._ocr = RapidOCR(use_angle_cls=False)

    @property
    def name(self) -> str:
        return "RapidOCR (ONNX)"

    def recognize(self, frame: np.ndarray) -> OCRResult:
        if frame is None or frame.size == 0:
            return OCRResult(text="", confidence=0.0, latency_ms=0.0, engine_name=self.name)

        start_time = time.perf_counter()

        # RapidOCR accepts BGR format
        if frame.shape[2] == 4:
            bgr = frame[:, :, :3]
        else:
            bgr = frame

        result, _ = self._ocr(bgr)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if not result:
            return OCRResult(text="", confidence=0.0, latency_ms=latency_ms, engine_name=self.name)

        # Result format: [[box, text, score], ...]
        lines = []
        scores = []
        for item in result:
            lines.append(item[1])
            try:
                scores.append(float(item[2]))
            except (ValueError, TypeError):
                scores.append(0.5)

        avg_confidence = float(np.mean(scores)) if scores else 0.0
        joined = TextNormalizer.join_lines(lines)

        return OCRResult(
            text=joined,
            confidence=avg_confidence,
            latency_ms=latency_ms,
            engine_name=self.name,
            lines=lines,
        )


class AutoOCREngine(BaseOCREngine):
    """Auto-selects the fastest available local OCR engine (WinOCR -> RapidOCR)."""

    def __init__(self):
        self._engine: Optional[BaseOCREngine] = None
        self._init_engine()

    def _init_engine(self):
        # Try Windows Media OCR first (fastest: 5-15ms)
        try:
            self._engine = WindowsMediaOCREngine()
            logger.info("AutoOCREngine selected: %s", self._engine.name)
            return
        except Exception as e:
            logger.warning("Windows Media OCR unavailable (%s). Falling back to RapidOCR.", e)

        # Fallback to RapidOCR
        try:
            self._engine = RapidOCREngine()
            logger.info("AutoOCREngine selected: %s", self._engine.name)
        except Exception as e:
            logger.error("RapidOCR unavailable: %s", e)
            raise RuntimeError("No local OCR engine could be initialized.")

    @property
    def name(self) -> str:
        return f"Auto ({self._engine.name if self._engine else 'None'})"

    def recognize(self, frame: np.ndarray) -> OCRResult:
        if self._engine is None:
            self._init_engine()
        return self._engine.recognize(frame)


def get_ocr_engine(engine_name: str = "auto") -> BaseOCREngine:
    """Factory function for OCR engines."""
    name_lower = engine_name.lower()
    if "win" in name_lower or "windows" in name_lower:
        return WindowsMediaOCREngine()
    elif "rapid" in name_lower:
        return RapidOCREngine()
    else:
        return AutoOCREngine()
