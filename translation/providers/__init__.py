from typing import Optional
from translation.providers.base_provider import BaseTranslationProvider, TranslationResult
from translation.providers.google_provider import GoogleFreeProvider
from translation.providers.deepl_provider import DeepLProvider


def get_translation_provider(name: str = "google", api_key: str = "") -> BaseTranslationProvider:
    name_lower = name.lower()
    if "deepl" in name_lower:
        return DeepLProvider(api_key=api_key)
    else:
        return GoogleFreeProvider()
