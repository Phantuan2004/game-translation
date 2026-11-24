import sqlite3
import time
import logging
from pathlib import Path
from typing import Optional, Tuple
from ocr.text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)


class TranslationCache:
    """Thread-safe SQLite persistent cache for dialogue translations."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path("config") / "translation_cache.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        # SQLite connection per call with short timeout for concurrency safety
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    source_key TEXT NOT NULL,
                    src_lang TEXT NOT NULL,
                    tgt_lang TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    hit_count INTEGER DEFAULT 1,
                    PRIMARY KEY (source_key, src_lang, tgt_lang)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trans_lookup 
                ON translations (source_key, src_lang, tgt_lang)
            """)
            conn.commit()

    def get(self, source_text: str, src_lang: str = "auto", tgt_lang: str = "vi") -> Optional[str]:
        """Looks up cached translation by normalized comparison key."""
        key = TextNormalizer.comparison_key(source_text)
        if not key:
            return None

        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT translated_text, hit_count 
                    FROM translations 
                    WHERE source_key = ? AND src_lang = ? AND tgt_lang = ?
                    """,
                    (key, src_lang.lower(), tgt_lang.lower()),
                )
                row = cur.fetchone()
                if row:
                    translated = row["translated_text"]
                    # Increment hit counter
                    conn.execute(
                        """
                        UPDATE translations 
                        SET hit_count = hit_count + 1 
                        WHERE source_key = ? AND src_lang = ? AND tgt_lang = ?
                        """,
                        (key, src_lang.lower(), tgt_lang.lower()),
                    )
                    conn.commit()
                    logger.debug("Cache hit for key '%s'", key)
                    return translated
        except Exception as e:
            logger.warning("Cache lookup error: %s", e)

        return None

    def set(
        self,
        source_text: str,
        translated_text: str,
        src_lang: str = "auto",
        tgt_lang: str = "vi",
        provider: str = "google",
    ) -> bool:
        """Stores a translation in cache."""
        key = TextNormalizer.comparison_key(source_text)
        if not key or not translated_text:
            return False

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO translations (
                        source_key, src_lang, tgt_lang, source_text, translated_text, provider, created_at, hit_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(source_key, src_lang, tgt_lang) DO UPDATE SET
                        translated_text = excluded.translated_text,
                        provider = excluded.provider,
                        hit_count = hit_count + 1
                    """,
                    (
                        key,
                        src_lang.lower(),
                        tgt_lang.lower(),
                        TextNormalizer.normalize(source_text),
                        translated_text.strip(),
                        provider,
                        time.time(),
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.warning("Cache write error: %s", e)
            return False

    def count(self) -> int:
        try:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT COUNT(*) as cnt FROM translations")
                return cur.fetchone()["cnt"]
        except Exception:
            return 0

    def clear(self):
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM translations")
                conn.commit()
        except Exception as e:
            logger.warning("Cache clear error: %s", e)
