import time
import pytest
from pathlib import Path
from output.txt_writer import TxtWriter


def test_txt_writer_append_format_and_utf8(tmp_path):
    out_file = tmp_path / "test_history.txt"
    writer = TxtWriter(str(out_file))

    # Append entry
    ok = writer.append_dialogue(
        seq_id=1,
        original_text="I thought you would never come back.",
        translated_text="Tôi cứ nghĩ anh sẽ không bao giờ quay lại.",
        status="success",
        timestamp=1700000000.0,
    )
    assert ok is True
    assert out_file.exists()

    content = out_file.read_text(encoding="utf-8")
    assert "EN: I thought you would never come back." in content
    assert "VI: Tôi cứ nghĩ anh sẽ không bao giờ quay lại." in content
    assert "---" in content


def test_txt_writer_duplicate_prevention(tmp_path):
    out_file = tmp_path / "test_history.txt"
    writer = TxtWriter(str(out_file))

    # Append once
    assert writer.append_dialogue(1, "Stay alert.", "Hãy cảnh giác.", "success") is True
    # Append exact duplicate with same seq_id
    assert writer.append_dialogue(1, "Stay alert.", "Hãy cảnh giác.", "success") is False

    lines = [line for line in out_file.read_text(encoding="utf-8").splitlines() if line.startswith("EN:")]
    assert len(lines) == 1


def test_txt_writer_status_formatting(tmp_path):
    out_file = tmp_path / "test_history.txt"
    writer = TxtWriter(str(out_file))

    # Failed translation
    writer.append_dialogue(1, "Sentence 1", "Timeout exceeded", status="failed")
    # Skipped translation
    writer.append_dialogue(2, "Sentence 2", "", status="skipped")

    content = out_file.read_text(encoding="utf-8")
    assert "VI: [Translation Failed: Timeout exceeded]" in content
    assert "VI: [Translation Skipped: Game advanced rapidly]" in content


def test_txt_writer_session_reset(tmp_path):
    out_file = tmp_path / "test_history.txt"
    writer = TxtWriter(str(out_file))

    writer.append_dialogue(1, "Initial dialogue", "Hội thoại ban đầu")
    writer.clear_session()
    writer.append_dialogue(2, "Next dialogue", "Hội thoại tiếp theo")

    content = out_file.read_text(encoding="utf-8")
    assert "=== SESSION RESET" in content
    assert "Initial dialogue" in content
    assert "Next dialogue" in content


def test_txt_writer_change_file_path(tmp_path):
    file1 = tmp_path / "file1.txt"
    file2 = tmp_path / "file2.txt"

    writer = TxtWriter(str(file1))
    writer.append_dialogue(1, "Text 1", "Dịch 1")
    assert file1.exists()

    writer.set_file_path(str(file2))
    writer.append_dialogue(2, "Text 2", "Dịch 2")
    assert file2.exists()
    assert "Text 2" in file2.read_text(encoding="utf-8")
