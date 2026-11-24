import re
import unicodedata
from typing import List


class TextNormalizer:
    """Normalizes OCR output text for clean display and reliable duplicate comparison."""

    # Common typographical quote replacements
    _QUOTE_REPLACEMENTS = {
        "“": '"',
        "”": '"',
        "„": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "`": "'",
        "—": "-",
        "–": "-",
        "…": "...",
    }

    @classmethod
    def normalize(cls, text: str) -> str:
        """Normalizes raw text by cleaning whitespace, unicode quotes, and noise."""
        if not text:
            return ""

        # Normalize unicode composition (NFKC)
        cleaned = unicodedata.normalize("NFKC", text)

        # Replace typographic quotes and dashes
        for old, new in cls._QUOTE_REPLACEMENTS.items():
            cleaned = cleaned.replace(old, new)

        # Remove control characters except newline
        cleaned = "".join(ch for ch in cleaned if unicodedata.category(ch)[0] != "C" or ch == "\n")

        # Collapse excessive horizontal spaces
        cleaned = re.sub(r"[ \t]+", " ", cleaned)

        # Strip noisy isolated characters at edges (e.g. '|', '~', '^', '_')
        cleaned = re.sub(r"^[\s\|\~\\\^\_]+", "", cleaned)
        cleaned = re.sub(r"[\s\|\~\\\^\_]+$", "", cleaned)

        return cleaned.strip()

    @classmethod
    def join_lines(cls, lines: List[str]) -> str:
        """Intelligently joins multi-line game dialogue into a unified string.
        
        Preserves words broken across line wraps (hyphenation) and joins wrapped lines.
        """
        if not lines:
            return ""

        processed_lines = []
        for line in lines:
            norm = cls.normalize(line)
            if norm:
                processed_lines.append(norm)

        if not processed_lines:
            return ""

        result = processed_lines[0]
        for next_line in processed_lines[1:]:
            if result.endswith("-") and len(result) > 1 and result[-2].isalnum():
                # Word broken across lines: e.g. "someth-" + "ing" -> "something"
                result = result[:-1] + next_line
            else:
                result = result + " " + next_line

        return result.strip()

    @classmethod
    def comparison_key(cls, text: str) -> str:
        """Produces a normalized key for fuzzy duplicate detection.
        
        Lowercases, collapses whitespace, and ignores subtle punctuation discrepancies.
        """
        norm = cls.normalize(text).lower()
        # Remove all punctuation and symbols for comparison
        clean_key = re.sub(r"[^\w\s]", "", norm)
        # Collapse whitespace
        return re.sub(r"\s+", " ", clean_key).strip()
