import pytest
from ocr.text_normalizer import TextNormalizer


def test_normalize_whitespace():
    raw = "   This   is   a \t game dialogue.  \n "
    assert TextNormalizer.normalize(raw) == "This is a game dialogue."


def test_normalize_curly_quotes_and_dashes():
    raw = "“I didn’t expect this—” he whispered."
    expected = '"I didn\'t expect this-" he whispered.'
    assert TextNormalizer.normalize(raw) == expected


def test_strip_edge_noise():
    raw = "|~ What are you waiting for? _"
    assert TextNormalizer.normalize(raw) == "What are you waiting for?"


def test_join_lines_with_hyphenation():
    lines = [
        "This is an unexpect-",
        "ed journey through the",
        "ancient kingdom.",
    ]
    joined = TextNormalizer.join_lines(lines)
    assert joined == "This is an unexpected journey through the ancient kingdom."


def test_comparison_key():
    key1 = TextNormalizer.comparison_key("Hello, brave adventurer!")
    key2 = TextNormalizer.comparison_key("hello brave adventurer")
    assert key1 == key2
