import pytest
import time
from translation.translation_scheduler import TranslationScheduler, TranslationTask


def test_scheduler_discards_outdated_pending_task():
    scheduler = TranslationScheduler()

    task1 = TranslationTask(seq_id=1, text="Sentence 1", src_lang="en", tgt_lang="vi", created_at=time.time())
    task2 = TranslationTask(seq_id=2, text="Sentence 2", src_lang="en", tgt_lang="vi", created_at=time.time())

    # Submit task 1
    new_t1, disc1 = scheduler.submit(task1)
    assert new_t1.seq_id == 1
    assert disc1 is None

    # Submit task 2 while task 1 is still pending
    new_t2, disc2 = scheduler.submit(task2)
    assert new_t2.seq_id == 2
    # task 1 must be discarded from live overlay queue
    assert disc2 is not None
    assert disc2.seq_id == 1


def test_scheduler_prevents_stale_overwrite():
    scheduler = TranslationScheduler()

    # Sentence #2 was already translated and displayed
    scheduler.mark_displayed(seq_id=2)
    assert scheduler.latest_displayed_seq_id == 2

    # Late arriving result for sentence #1
    can_display_1 = scheduler.validate_for_display(seq_id=1)
    assert can_display_1 is False, "Older translation #1 must NEVER overwrite newer displayed #2"

    # Arriving result for sentence #2 (equal) or #3 (newer)
    assert scheduler.validate_for_display(seq_id=2) is True
    assert scheduler.validate_for_display(seq_id=3) is True


def test_scheduler_marks_displayed_monotonically():
    scheduler = TranslationScheduler()
    scheduler.mark_displayed(5)
    assert scheduler.latest_displayed_seq_id == 5

    # Should not regress if older seq_id is passed
    scheduler.mark_displayed(3)
    assert scheduler.latest_displayed_seq_id == 5
