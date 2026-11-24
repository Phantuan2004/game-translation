import pytest
from ocr.dialogue_detector import DialogueDetector


def test_first_dialogue_emits_event():
    detector = DialogueDetector(similarity_threshold=0.88)
    event = detector.process_text("Welcome to the city of light.", confidence=0.92)
    assert event is not None
    assert event.seq_id == 1
    assert event.text == "Welcome to the city of light."
    assert event.confidence == 0.92


def test_exact_duplicate_suppressed():
    detector = DialogueDetector(similarity_threshold=0.88)
    e1 = detector.process_text("Welcome to the city of light.", confidence=0.92)
    assert e1 is not None

    # Repeated identical dialogue while dialogue box remains on screen
    e2 = detector.process_text("Welcome to the city of light.", confidence=0.94)
    assert e2 is None


def test_minor_ocr_variation_suppressed():
    detector = DialogueDetector(similarity_threshold=0.88)
    e1 = detector.process_text("I thought you would never come back.", confidence=0.90)
    assert e1 is not None

    # Minor OCR noise: period missing, capitalization diff
    e2 = detector.process_text("i thought you would never come back", confidence=0.89)
    assert e2 is None


def test_meaningful_change_increments_seq_id():
    detector = DialogueDetector(similarity_threshold=0.88)
    e1 = detector.process_text("I thought you would never come back.", confidence=0.90)
    assert e1.seq_id == 1

    e2 = detector.process_text("We need to leave this place immediately.", confidence=0.95)
    assert e2 is not None
    assert e2.seq_id == 2
    assert e2.text == "We need to leave this place immediately."


def test_too_short_text_ignored():
    detector = DialogueDetector()
    event = detector.process_text("A", confidence=0.9)
    assert event is None
