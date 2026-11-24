import json
import time
import logging
import urllib.request
import urllib.parse
from translation.providers.base_provider import BaseTranslationProvider, TranslationResult

logger = logging.getLogger(__name__)


class GoogleFreeProvider(BaseTranslationProvider):
    """Fast, free Google Translate provider utilizing public endpoint with zero API key required."""

    _ENDPOINT = "https://translate.googleapis.com/translate_a/single"

    @property
    def name(self) -> str:
        return "Google Translate (Free)"

    def translate(
        self,
        text: str,
        src_lang: str = "auto",
        tgt_lang: str = "vi",
        timeout_sec: float = 3.0,
    ) -> TranslationResult:
        clean_text = text.strip()
        if not clean_text:
            return TranslationResult(
                translated_text="",
                source_text=text,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                latency_ms=0.0,
                provider_name=self.name,
                success=True,
            )

        start_time = time.perf_counter()

        # Map language codes
        sl = src_lang.lower()
        if sl.startswith("auto"):
            sl = "auto"
        elif "en" in sl:
            sl = "en"
        elif "ja" in sl:
            sl = "ja"
        elif "zh" in sl:
            sl = "zh"

        tl = tgt_lang.lower()
        if "vi" in tl:
            tl = "vi"

        params = {
            "client": "gtx",
            "sl": sl,
            "tl": tl,
            "dt": "t",
            "q": clean_text,
        }

        url = f"{self._ENDPOINT}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as response:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                raw_data = response.read().decode("utf-8")
                data = json.loads(raw_data)

                # Structure: [[[translated_chunk, orig_chunk], ...], ...]
                translated_parts = []
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                    for part in data[0]:
                        if isinstance(part, list) and len(part) > 0 and part[0]:
                            translated_parts.append(part[0])

                translated = "".join(translated_parts).strip()
                return TranslationResult(
                    translated_text=translated,
                    source_text=text,
                    src_lang=src_lang,
                    tgt_lang=tgt_lang,
                    latency_ms=latency_ms,
                    provider_name=self.name,
                    success=True,
                )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error("GoogleFreeProvider error: %s", e)
            return TranslationResult(
                translated_text="",
                source_text=text,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                latency_ms=latency_ms,
                provider_name=self.name,
                success=False,
                error_message=str(e),
            )
