import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranslationResult:
    translated_text: str
    source_text: str
    src_lang: str
    tgt_lang: str
    latency_ms: float
    provider_name: str
    is_cached: bool = False
    success: bool = True
    error_message: Optional[str] = None


class BaseTranslationProvider(abc.ABC):
    """Abstract interface for pluggable translation providers."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @abc.abstractmethod
    def translate(
        self,
        text: str,
        src_lang: str = "auto",
        tgt_lang: str = "vi",
        timeout_sec: float = 3.0,
    ) -> TranslationResult:
        """Translates text from src_lang to tgt_lang."""
        pass
