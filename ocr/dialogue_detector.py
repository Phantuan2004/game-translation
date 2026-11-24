import time
import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from ocr.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)


@dataclass
class DialogueEvent:
    seq_id: int
    text: str
    confidence: float
    timestamp: float


class DialogueDetector:
    """Detects meaningful dialogue changes and filters out duplicate OCR events."""

    def __init__(self, similarity_threshold: float = 0.88, min_length: int = 2):
        self.similarity_threshold = similarity_threshold
        self.min_length = min_length
        self._last_text: str = ""
        self._last_key: str = ""
        self._current_seq_id: int = 0
        self._last_event_time: float = 0.0

    @property
    def current_sequence_id(self) -> int:
        return self._current_seq_id

    def process_text(self, raw_text: str, confidence: float = 1.0) -> Optional[DialogueEvent]:
        """Processes recognized text and returns a DialogueEvent if it is a new dialogue sentence.
        
        Returns None if text is duplicate, empty, or below threshold.
        """
        norm_text = TextNormalizer.normalize(raw_text)
        if len(norm_text) < self.min_length:
            return None

        key = TextNormalizer.comparison_key(norm_text)
        if not key:
            return None

        # Compare with previous dialogue
        if self._last_key:
            similarity = SequenceMatcher(None, self._last_key, key).ratio()
            # If similarity is above threshold, consider it the same sentence
            if similarity >= self.similarity_threshold:
                return None

        # If we reached here, it's a genuine new dialogue!
        self._current_seq_id += 1
        self._last_text = norm_text
        self._last_key = key
        self._last_event_time = time.time()

        event = DialogueEvent(
            seq_id=self._current_seq_id,
            text=norm_text,
            confidence=confidence,
            timestamp=self._last_event_time,
        )
        logger.info("New dialogue detected [Seq %d]: '%s' (conf: %.2f)", event.seq_id, event.text, confidence)
        return event

    def reset(self):
        """Resets dialogue history."""
        self._last_text = ""
        self._last_key = ""
        self._last_event_time = 0.0
