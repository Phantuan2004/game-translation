import time
import cv2
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

from ocr.ocr_engine import get_ocr_engine
from workers.ocr_worker import OCRWorker


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def create_dialogue_image(text: str) -> np.ndarray:
    """Generates a realistic test game dialogue frame."""
    img = np.zeros((90, 640, 4), dtype=np.uint8)
    img[:, :, :3] = (20, 22, 28)  # Dark dialogue box
    img[:, :, 3] = 255
    cv2.putText(
        img,
        text,
        (25, 55),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.85,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return img


def test_ocr_engine_recognition():
    engine = get_ocr_engine("auto")
    img = create_dialogue_image("Stay vigilant, my friend.")
    res = engine.recognize(img)

    assert isinstance(res.text, str)
    assert len(res.text) > 0
    assert "vigilant" in res.text.lower() or "stay" in res.text.lower()
    assert res.latency_ms > 0.0


def test_ocr_worker_lifecycle(qapp):
    worker = OCRWorker(engine_name="auto", min_confidence=0.3)
    detected_events = []

    worker.dialogue_detected.connect(lambda seq, text, conf, lat: detected_events.append((seq, text)))
    worker.start()

    # Pump 1st frame with dialogue (allow up to 2.0s for first-time model init)
    img1 = create_dialogue_image("We must protect the artifact.")
    worker.enqueue_frame(img1)

    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 2.5 and len(detected_events) == 0:
        qapp.processEvents()
        time.sleep(0.03)

    assert len(detected_events) == 1
    assert detected_events[0][0] == 1  # seq_id 1
    assert "protect" in detected_events[0][1].lower() or "artifact" in detected_events[0][1].lower()

    # Pump exact same frame (should be skipped by change detector / dialogue detector)
    worker.enqueue_frame(img1)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.3:
        qapp.processEvents()
        time.sleep(0.02)

    # No duplicate dialogue event
    assert len(detected_events) == 1

    # Pump new distinct dialogue frame
    img2 = create_dialogue_image("The ancient gate is finally opening.")
    worker.enqueue_frame(img2)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 1.5 and len(detected_events) < 2:
        qapp.processEvents()
        time.sleep(0.02)

    assert len(detected_events) == 2
    assert detected_events[1][0] == 2  # seq_id 2

    worker.stop()
    assert not worker.isRunning()
