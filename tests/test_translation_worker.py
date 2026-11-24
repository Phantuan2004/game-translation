import time
import pytest
from PyQt6.QtWidgets import QApplication
from workers.translation_worker import TranslationWorker


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_translation_worker_cache_hit_fast_path(qapp, tmp_path):
    db_file = tmp_path / "worker_cache.db"
    worker = TranslationWorker(cache_db_path=str(db_file))

    # Pre-populate cache
    worker._cache.set("The night is dark.", "Đêm đen tối.", "en", "vi")

    results = []
    worker.translation_ready.connect(
        lambda seq, orig, trans, lat, is_cached: results.append((seq, trans, is_cached))
    )

    worker.start()

    # Request translation of cached sentence
    worker.request_translation(seq_id=1, text="The night is dark.", src_lang="en", tgt_lang="vi")
    qapp.processEvents()

    assert len(results) == 1
    assert results[0][0] == 1
    assert results[0][1] == "Đêm đen tối."
    assert results[0][2] is True  # is_cached

    worker.stop()
    assert not worker.isRunning()


def test_translation_worker_live_translation(qapp, tmp_path):
    db_file = tmp_path / "worker_cache.db"
    worker = TranslationWorker(provider_name="google", cache_db_path=str(db_file))

    results = []
    worker.translation_ready.connect(
        lambda seq, orig, trans, lat, is_cached: results.append((seq, trans, is_cached))
    )

    worker.start()

    # Request translation of uncached sentence
    worker.request_translation(seq_id=1, text="Good luck on your quest.", src_lang="en", tgt_lang="vi")

    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 5.0 and len(results) == 0:
        qapp.processEvents()
        time.sleep(0.05)

    assert len(results) == 1
    assert results[0][0] == 1
    assert len(results[0][1]) > 0
    assert results[0][2] is False  # is_cached = False on first network call

    # Verify that it was stored in SQLite cache
    cached_val = worker._cache.get("Good luck on your quest.", "en", "vi")
    assert cached_val == results[0][1]

    worker.stop()
    assert not worker.isRunning()
