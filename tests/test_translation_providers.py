import pytest
from translation.providers import get_translation_provider
from translation.providers.google_provider import GoogleFreeProvider
from translation.providers.deepl_provider import DeepLProvider


def test_google_free_provider_translation():
    provider = GoogleFreeProvider()
    res = provider.translate("Hello, my friend.", src_lang="en", tgt_lang="vi", timeout_sec=5.0)

    assert res.success is True
    assert len(res.translated_text) > 0
    assert "chào" in res.translated_text.lower() or "bạn" in res.translated_text.lower()
    assert res.latency_ms > 0.0


def test_google_empty_text():
    provider = GoogleFreeProvider()
    res = provider.translate("   ", src_lang="en", tgt_lang="vi")
    assert res.success is True
    assert res.translated_text == ""


def test_deepl_missing_api_key():
    provider = DeepLProvider(api_key="")
    res = provider.translate("Hello", src_lang="en", tgt_lang="vi")
    assert res.success is False
    assert "missing" in res.error_message.lower() or "required" in res.error_message.lower()


def test_provider_factory():
    p1 = get_translation_provider("google")
    assert isinstance(p1, GoogleFreeProvider)

    p2 = get_translation_provider("deepl", api_key="abc:fx")
    assert isinstance(p2, DeepLProvider)
