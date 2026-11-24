import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
from PyQt6.QtWidgets import QApplication

from capture.screen_capture import ScreenCapture
from ocr.change_detector import ImageChangeDetector
from ocr.ocr_engine import get_ocr_engine
from translation.translation_cache import TranslationCache
from translation.providers.google_provider import GoogleFreeProvider
from overlay.translation_overlay import TranslationOverlay


def run_benchmarks():
    print("=" * 70)
    print("GAME TRANSLATOR PERFORMANCE BENCHMARK (WINDOWS 11 / PC)")
    print("=" * 70)

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    results = {}

    # 1. Screen Capture Latency
    sc = ScreenCapture()
    region = {"left": 100, "top": 100, "width": 600, "height": 180}
    cap_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        qimg, arr, _ = sc.capture_region(region)
        cap_times.append((time.perf_counter() - t0) * 1000.0)
    results["Capture Region (600x180)"] = {
        "avg": float(np.mean(cap_times)),
        "min": float(np.min(cap_times)),
        "max": float(np.max(cap_times)),
        "target": "10 - 50 ms",
    }

    # 2. Image Change Detection Latency
    cd = ImageChangeDetector(diff_threshold=3.5)
    test_frame = np.zeros((180, 600, 4), dtype=np.uint8)
    cd.has_changed(test_frame)  # baseline

    cd_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        changed, diff, _ = cd.has_changed(test_frame)
        cd_times.append((time.perf_counter() - t0) * 1000.0)
    results["Change Detection (MAD)"] = {
        "avg": float(np.mean(cd_times)),
        "min": float(np.min(cd_times)),
        "max": float(np.max(cd_times)),
        "target": "5 - 30 ms",
    }

    # 3. Local OCR Latency (Windows Media OCR)
    engine = get_ocr_engine("auto")
    dialogue_frame = test_frame.copy()
    cv2.putText(
        dialogue_frame,
        "The ancient gate will only open with the golden key.",
        (20, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )
    # Warmup
    engine.recognize(dialogue_frame)

    ocr_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        res = engine.recognize(dialogue_frame)
        ocr_times.append((time.perf_counter() - t0) * 1000.0)
    results[f"Local OCR ({engine.name})"] = {
        "avg": float(np.mean(ocr_times)),
        "min": float(np.min(ocr_times)),
        "max": float(np.max(ocr_times)),
        "target": "50 - 250 ms",
    }

    # 4. Translation Latency (Cache Hit)
    cache = TranslationCache("config/test_bench_cache.db")
    cache.set(
        "The ancient gate will only open with the golden key.",
        "Cánh cổng cổ xưa sẽ chỉ mở ra bằng chiếc chìa khóa vàng.",
        "en",
        "vi",
    )
    cache_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        c_res = cache.get("The ancient gate will only open with the golden key.", "en", "vi")
        cache_times.append((time.perf_counter() - t0) * 1000.0)
    results["Translation Cache (SQLite Hit)"] = {
        "avg": float(np.mean(cache_times)),
        "min": float(np.min(cache_times)),
        "max": float(np.max(cache_times)),
        "target": "< 2 ms",
    }
    cache.clear()

    # 5. Translation Latency (Live Google Free Provider)
    google_p = GoogleFreeProvider()
    trans_times = []
    for _ in range(3):
        t_res = google_p.translate("I will return before sunset.", "en", "vi", timeout_sec=5.0)
        if t_res.success:
            trans_times.append(t_res.latency_ms)
    results["Live Translation (Google Free)"] = {
        "avg": float(np.mean(trans_times)) if trans_times else 0.0,
        "min": float(np.min(trans_times)) if trans_times else 0.0,
        "max": float(np.max(trans_times)) if trans_times else 0.0,
        "target": "100 - 300 ms",
    }

    # 6. Overlay UI Update Latency
    overlay = TranslationOverlay()
    overlay.show()
    overlay_times = []
    for i in range(20):
        t0 = time.perf_counter()
        overlay.update_dialogue(i + 1, "Testing dialogue", "Bản dịch thử nghiệm")
        overlay_times.append((time.perf_counter() - t0) * 1000.0)
    results["Overlay Render Update"] = {
        "avg": float(np.mean(overlay_times)),
        "min": float(np.min(overlay_times)),
        "max": float(np.max(overlay_times)),
        "target": "< 5 ms",
    }
    overlay.close()

    # Print Report Table
    print(f"{'Operation':<38} | {'Avg (ms)':<9} | {'Min (ms)':<9} | {'Max (ms)':<9} | {'Design Target'}")
    print("-" * 88)
    for op, data in results.items():
        print(
            f"{op:<38} | {data['avg']:<9.2f} | {data['min']:<9.2f} | {data['max']:<9.2f} | {data['target']}"
        )
    print("=" * 88)

    # End-to-end total (Cached vs Live)
    e2e_cached = (
        results["Capture Region (600x180)"]["avg"]
        + results["Change Detection (MAD)"]["avg"]
        + results[f"Local OCR ({engine.name})"]["avg"]
        + results["Translation Cache (SQLite Hit)"]["avg"]
        + results["Overlay Render Update"]["avg"]
    )
    e2e_live = (
        results["Capture Region (600x180)"]["avg"]
        + results["Change Detection (MAD)"]["avg"]
        + results[f"Local OCR ({engine.name})"]["avg"]
        + results["Live Translation (Google Free)"]["avg"]
        + results["Overlay Render Update"]["avg"]
    )

    print(f"\n>>> Estimated End-to-End Latency (CACHED):  {e2e_cached:.1f} ms")
    print(f">>> Estimated End-to-End Latency (LIVE NET): {e2e_live:.1f} ms\n")


if __name__ == "__main__":
    run_benchmarks()
