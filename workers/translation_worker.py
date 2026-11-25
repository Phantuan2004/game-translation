import time
import logging
from typing import Optional
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker, QWaitCondition

from translation.translation_cache import TranslationCache
from translation.translation_scheduler import TranslationScheduler, TranslationTask
from translation.providers import get_translation_provider, BaseTranslationProvider

logger = logging.getLogger(__name__)


class TranslationWorker(QThread):
    """Background worker thread for asynchronous translation processing.
    
    Features:
    - Sub-millisecond SQLite persistent cache lookups
    - Latest-priority scheduler with strict stale-overwrite prevention
    - Pluggable provider backend (Google / DeepL / custom)
    """

    # Signals
    # translation_ready(seq_id, original_text, translated_text, latency_ms, is_cached)
    translation_ready = Signal(int, str, str, float, bool)
    translation_stale_discarded = Signal(int)  # seq_id
    translation_failed = Signal(int, str, str)  # seq_id, original_text, error_msg
    status_updated = Signal(str)

    def __init__(
        self,
        provider_name: str = "google",
        api_key: str = "",
        timeout_sec: float = 3.0,
        cache_db_path: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._mutex = QMutex()
        self._condition = QWaitCondition()

        self._provider_name = provider_name
        self._api_key = api_key
        self._timeout_sec = max(1.0, timeout_sec)

        self._cache = TranslationCache(db_path=cache_db_path)
        self._scheduler = TranslationScheduler()
        self._provider: Optional[BaseTranslationProvider] = None

        self._pending_task: Optional[TranslationTask] = None
        self._running: bool = False

    def set_provider(self, provider_name: str, api_key: str = ""):
        with QMutexLocker(self._mutex):
            self._provider_name = provider_name
            self._api_key = api_key
            self._provider = get_translation_provider(provider_name, api_key)
            logger.info("Translation provider switched to: %s", self._provider.name)

    def set_timeout(self, timeout_sec: float):
        with QMutexLocker(self._mutex):
            self._timeout_sec = max(1.0, timeout_sec)

    def reset_state(self):
        with QMutexLocker(self._mutex):
            self._scheduler.reset()
            self._pending_task = None

    def start(self, priority=QThread.Priority.InheritPriority):
        with QMutexLocker(self._mutex):
            self._running = True
        super().start(priority)

    def request_translation(self, seq_id: int, text: str, src_lang: str = "auto", tgt_lang: str = "vi"):
        """Submits a dialogue for translation.
        
        Fast-path: Checks SQLite cache immediately without waiting on worker thread!
        """
        clean_text = text.strip()
        if not clean_text:
            return

        # 1. Fast cache lookup
        cached = self._cache.get(clean_text, src_lang=src_lang, tgt_lang=tgt_lang)
        if cached:
            # Check scheduler validity before emitting
            with QMutexLocker(self._mutex):
                is_valid = self._scheduler.validate_for_display(seq_id)
                if is_valid:
                    self._scheduler.mark_displayed(seq_id)

            if is_valid:
                logger.info("Translation cache hit [Seq %d]: '%s' -> '%s'", seq_id, clean_text, cached)
                self.translation_ready.emit(seq_id, clean_text, cached, 0.5, True)
                return

        # 2. Enqueue for background translation
        task = TranslationTask(
            seq_id=seq_id,
            text=clean_text,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            created_at=time.time(),
        )

        with QMutexLocker(self._mutex):
            submitted_task, discarded = self._scheduler.submit(task)
            self._pending_task = submitted_task
            self._condition.wakeOne()

        if discarded is not None:
            self.translation_stale_discarded.emit(discarded.seq_id)

    def stop(self):
        with QMutexLocker(self._mutex):
            self._running = False
            self._pending_task = None
            self._condition.wakeAll()
        self.wait(2000)
        logger.info("TranslationWorker stopped.")

    def run(self):
        with QMutexLocker(self._mutex):
            self._running = True
            if self._provider is None:
                self._provider = get_translation_provider(self._provider_name, self._api_key)

        logger.info("TranslationWorker thread started with provider: %s", self._provider.name)

        while True:
            task = None
            with QMutexLocker(self._mutex):
                while self._running and self._pending_task is None:
                    self._condition.wait(self._mutex)

                if not self._running:
                    break

                task = self._pending_task
                self._pending_task = None
                provider = self._provider
                timeout = self._timeout_sec

            if task is None:
                continue

            # Check if this task is already stale before initiating network call
            with QMutexLocker(self._mutex):
                if not self._scheduler.validate_for_display(task.seq_id):
                    self.translation_stale_discarded.emit(task.seq_id)
                    continue

            try:
                self.status_updated.emit(f"Translating dialogue #{task.seq_id}...")
                result = provider.translate(
                    text=task.text,
                    src_lang=task.src_lang,
                    tgt_lang=task.tgt_lang,
                    timeout_sec=timeout,
                )

                if result.success and result.translated_text:
                    # Save to persistent SQLite cache
                    self._cache.set(
                        source_text=task.text,
                        translated_text=result.translated_text,
                        src_lang=task.src_lang,
                        tgt_lang=task.tgt_lang,
                        provider=provider.name,
                    )

                    # Validate sequence ID against visible overlay
                    with QMutexLocker(self._mutex):
                        is_valid = self._scheduler.validate_for_display(task.seq_id)
                        if is_valid:
                            self._scheduler.mark_displayed(task.seq_id)

                    if is_valid:
                        self.translation_ready.emit(
                            task.seq_id,
                            task.text,
                            result.translated_text,
                            result.latency_ms,
                            False,
                        )
                    else:
                        self.translation_stale_discarded.emit(task.seq_id)
                else:
                    err_msg = result.error_message or "Translation failed"
                    logger.warning("Translation failed [Seq %d]: %s", task.seq_id, err_msg)
                    self.translation_failed.emit(task.seq_id, task.text, err_msg)

            except Exception as ex:
                logger.error("Exception during translation [Seq %d]: %s", task.seq_id, ex, exc_info=True)
                self.translation_failed.emit(task.seq_id, task.text, str(ex))

        with QMutexLocker(self._mutex):
            self._running = False
        logger.info("TranslationWorker thread exited.")
