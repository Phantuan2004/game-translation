import pytest
from translation.translation_cache import TranslationCache


def test_cache_set_and_get(tmp_path):
    db_file = tmp_path / "test_cache.db"
    cache = TranslationCache(str(db_file))

    assert cache.count() == 0
    assert cache.get("Hello world", "en", "vi") is None

    # Insert translation
    cache.set(
        source_text="Hello world",
        translated_text="Xin chào thế giới",
        src_lang="en",
        tgt_lang="vi",
        provider="google",
    )

    assert cache.count() == 1
    result = cache.get("Hello world", "en", "vi")
    assert result == "Xin chào thế giới"


def test_cache_fuzzy_normalized_key_hit(tmp_path):
    db_file = tmp_path / "test_cache.db"
    cache = TranslationCache(str(db_file))

    cache.set(
        source_text="I thought you would never come back.",
        translated_text="Tôi cứ nghĩ bạn sẽ không bao giờ quay lại.",
        src_lang="en",
        tgt_lang="vi",
    )

    # Lookup with minor punctuation / casing difference
    hit = cache.get("i thought you would never come back", "en", "vi")
    assert hit == "Tôi cứ nghĩ bạn sẽ không bao giờ quay lại."


def test_cache_persistence_across_instances(tmp_path):
    db_file = tmp_path / "test_cache.db"
    cache1 = TranslationCache(str(db_file))
    cache1.set("Stay vigilant.", "Hãy cảnh giác.", "en", "vi")

    # Open with a second instance pointing to same DB
    cache2 = TranslationCache(str(db_file))
    assert cache2.get("Stay vigilant.", "en", "vi") == "Hãy cảnh giác."


def test_cache_clear(tmp_path):
    db_file = tmp_path / "test_cache.db"
    cache = TranslationCache(str(db_file))
    cache.set("Sample", "Mẫu", "en", "vi")
    assert cache.count() == 1

    cache.clear()
    assert cache.count() == 0
    assert cache.get("Sample", "en", "vi") is None
