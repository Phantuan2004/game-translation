import json
import time
import logging
import urllib.request
import urllib.parse
from translation.providers.base_provider import BaseTranslationProvider, TranslationResult

logger = logging.getLogger(__name__)


class DeepLProvider(BaseTranslationProvider):
    """DeepL API Translation Provider (Free and Pro)."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key.strip()

    @property
    def name(self) -> str:
        return "DeepL API"

    def translate(
        self,
        text: str,
        src_lang: str = "auto",
        tgt_lang: str = "vi",
        timeout_sec: float = 3.0,
    ) -> TranslationResult:
        if not self.api_key:
            return TranslationResult(
                translated_text="",
                source_text=text,
                src_lang=src_lang,
                tgt_lang=tgt_lang,
                latency_ms=0.0,
                provider_name=self.name,
                success=False,
                error_message="DeepL API Key is missing. Please configure it in Translation Settings.",
            )

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

        endpoint = (
            "https://api-free.deepl.com/v2/translate"
            if self.api_key.endswith(":fx")
            else "https://api.deepl.com/v2/translate"
        )

        # DeepL target languages: VI is Vietnamese
        target = "VI"
        payload = {
            "text": [clean_text],
            "target_lang": target,
        }

        # If source is specified
        if "en" in src_lang.lower():
            payload["source_lang"] = "EN"
        elif "ja" in src_lang.lower():
            payload["source_lang"] = "JA"
        elif "zh" in src_lang.lower():
            payload["source_lang"] = "ZH"

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={
                "Authorization": f"DeepL-Auth-Key {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as response:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                resp_json = json.loads(response.read().decode("utf-8"))
                translations = resp_json.get("translations", [])
                translated = translations[0].get("text", "") if translations else ""

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
