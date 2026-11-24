import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TranslationTask:
    seq_id: int
    text: str
    src_lang: str
    tgt_lang: str
    created_at: float


class TranslationScheduler:
    """Bounded, latest-priority translation scheduler.
    
    Ensures that when dialogue progresses rapidly, the newest sentence takes precedence
    and outdated translations are never permitted to overwrite newer overlay content.
    """

    def __init__(self):
        self._latest_submitted_seq_id: int = 0
        self._latest_displayed_seq_id: int = 0
        self._pending_task: Optional[TranslationTask] = None
        self._history_log: List[Dict[str, Any]] = []

    @property
    def latest_displayed_seq_id(self) -> int:
        return self._latest_displayed_seq_id

    def submit(self, task: TranslationTask) -> Tuple[Optional[TranslationTask], Optional[TranslationTask]]:
        """Submits a new task.
        
        Returns:
            (new_task, discarded_outdated_task)
        """
        discarded = None
        if self._pending_task is not None and self._pending_task.seq_id < task.seq_id:
            discarded = self._pending_task
            logger.info(
                "Discarding outdated pending translation [Seq %d] for newer [Seq %d]",
                discarded.seq_id,
                task.seq_id,
            )

        self._pending_task = task
        self._latest_submitted_seq_id = max(self._latest_submitted_seq_id, task.seq_id)
        return task, discarded

    def validate_for_display(self, seq_id: int) -> bool:
        """Validates if a completed translation is still relevant for live display.
        
        Returns False if a newer dialogue has already been displayed on screen.
        """
        if seq_id < self._latest_displayed_seq_id:
            logger.warning(
                "Rejecting stale translation [Seq %d]; current visible is [Seq %d]",
                seq_id,
                self._latest_displayed_seq_id,
            )
            return False
        return True

    def mark_displayed(self, seq_id: int):
        """Records that this seq_id is now visibly shown."""
        if seq_id > self._latest_displayed_seq_id:
            self._latest_displayed_seq_id = seq_id

    def reset(self):
        self._latest_submitted_seq_id = 0
        self._latest_displayed_seq_id = 0
        self._pending_task = None
