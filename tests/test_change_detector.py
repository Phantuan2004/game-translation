import cv2
import numpy as np
import pytest
from ocr.change_detector import ImageChangeDetector


def test_initial_frame_detected_as_changed():
    detector = ImageChangeDetector(diff_threshold=3.5)
    frame = np.zeros((100, 300, 3), dtype=np.uint8)
    changed, diff, lat = detector.has_changed(frame)
    assert changed is True
    assert lat >= 0.0


def test_identical_frame_detected_as_unchanged():
    detector = ImageChangeDetector(diff_threshold=3.5)
    frame = np.ones((100, 300, 3), dtype=np.uint8) * 50
    # First frame
    detector.has_changed(frame)
    # Second identical frame
    changed, diff, lat = detector.has_changed(frame)
    assert changed is False
    assert diff == 0.0
    assert lat < 10.0  # sub-10ms performance target


def test_minor_noise_ignored():
    detector = ImageChangeDetector(diff_threshold=5.0)
    frame1 = np.ones((100, 300, 3), dtype=np.uint8) * 100
    detector.has_changed(frame1)

    # Add very small random noise (subtle gradient/compression artifact)
    noise = np.random.randint(-1, 2, size=(100, 300, 3)).astype(np.int16)
    frame2 = np.clip(frame1.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    changed, diff, lat = detector.has_changed(frame2)
    assert changed is False


def test_meaningful_change_detected():
    detector = ImageChangeDetector(diff_threshold=3.5)
    frame1 = np.zeros((100, 400, 3), dtype=np.uint8)
    detector.has_changed(frame1)

    # Frame 2 has dialogue text drawn
    frame2 = frame1.copy()
    cv2.putText(frame2, "New Dialogue Sentence", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    changed, diff, lat = detector.has_changed(frame2)
    assert changed is True
    assert diff > 3.5
