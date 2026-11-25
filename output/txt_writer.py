import os
import time
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TxtWriter:
    """Thread-safe writer for persisting chronological dialogue translations to a UTF-8 text file."""

    def __init__(self, file_path: str = "game_translation.txt"):
        self.file_path = Path(file_path) if file_path else Path("game_translation.txt")
        self._lock = threading.Lock()
        self._last_original: str = ""
        self._last_seq_id: int = 0
        if not self._ensure_parent_dir():
            fallback = Path("game_translation.txt")
            logger.warning(
                "Falling back from inaccessible TXT output path '%s' to '%s'.",
                self.file_path,
                fallback,
            )
            self.file_path = fallback
            self._ensure_parent_dir()

    def set_file_path(self, new_path: str):
        with self._lock:
            target = Path(new_path) if new_path else Path("game_translation.txt")
            try:
                if target.parent:
                    target.parent.mkdir(parents=True, exist_ok=True)
                self.file_path = target
                logger.info("TxtWriter file path changed to: %s", self.file_path)
            except OSError as e:
                logger.warning(
                    "Cannot use TXT output path '%s' (%s). Keeping '%s'.",
                    target,
                    e,
                    self.file_path,
                )

    def _ensure_parent_dir(self) -> bool:
        try:
            if self.file_path.parent:
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as e:
            logger.warning("Failed to prepare directory for '%s': %s", self.file_path, e)
            return False

    def append_dialogue(
        self,
        seq_id: int,
        original_text: str,
        translated_text: str,
        status: str = "success",
        timestamp: Optional[float] = None,
    ) -> bool:
        """Appends a new dialogue entry in chronological order with UTF-8 encoding.
        
        Format:
        [HH:MM:SS]
        EN: Original dialogue
        VI: Vietnamese translation
        ---
        """
        orig_clean = original_text.strip()
        trans_clean = translated_text.strip()

        if not orig_clean:
            return False

        with self._lock:
            # Duplicate prevention: avoid appending consecutive identical dialogues
            if orig_clean == self._last_original and seq_id == self._last_seq_id:
                return False

            self._last_original = orig_clean
            self._last_seq_id = seq_id

            ts = timestamp or time.time()
            time_str = time.strftime("%H:%M:%S", time.localtime(ts))

            # Format status representation
            if status == "failed":
                trans_line = f"VI: [Translation Failed: {trans_clean or 'Unknown error'}]"
            elif status == "skipped":
                trans_line = f"VI: [Translation Skipped: Game advanced rapidly]"
            else:
                trans_line = f"VI: {trans_clean}"

            entry = f"[{time_str}]\nEN: {orig_clean}\n{trans_line}\n---\n\n"

            try:
                self._ensure_parent_dir()
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(entry)
                logger.debug("Appended dialogue #%d to %s", seq_id, self.file_path)
                return True
            except Exception as e:
                logger.error("Failed to write dialogue to %s: %s", self.file_path, e)
                return False

    def open_in_editor(self) -> bool:
        """Opens the text file in the default Windows text editor (e.g. Notepad)."""
        with self._lock:
            if not self.file_path.exists():
                try:
                    self._ensure_parent_dir()
                    self.file_path.write_text(
                        "# Game Translator Dialogue History\n\n", encoding="utf-8"
                    )
                except Exception as e:
                    logger.error("Failed to create file for editor: %s", e)
                    return False

            try:
                os.startfile(str(self.file_path.resolve()))
                return True
            except Exception as e:
                logger.error("Failed to open file in editor: %s", e)
                return False

    def clear_session(self) -> bool:
        """Clears or adds a session reset marker to the file."""
        with self._lock:
            self._last_original = ""
            self._last_seq_id = 0
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            reset_marker = f"=== SESSION RESET [{time_str}] ===\n\n"
            try:
                self._ensure_parent_dir()
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(reset_marker)
                return True
            except Exception as e:
                logger.error("Failed to append session reset marker: %s", e)
                return False
