import json

from agents.extraction_agent import (
    read_current_filing_text,
    read_current_press_release_text,
    read_current_transcript_text,
)


def test_read_current_filing_text_strips_html(tmp_path):
    (tmp_path / "SNOW_10-Q_2026-09-04.htm").write_text("<p>Revenue was $100 million.</p>", encoding="utf-8")

    result = read_current_filing_text(tmp_path, "SNOW")

    assert "Revenue was $100 million." in result
    assert "<p>" not in result


def test_read_current_filing_text_ignores_prior_files(tmp_path):
    (tmp_path / "SNOW_10-Q_2026-09-04.htm").write_text("<p>current filing</p>", encoding="utf-8")
    (tmp_path / "SNOW_10-Q_PRIOR_2026-06-05.htm").write_text("<p>prior filing</p>", encoding="utf-8")

    result = read_current_filing_text(tmp_path, "SNOW")

    assert "current filing" in result
    assert "prior filing" not in result


def test_read_current_filing_text_raises_when_missing(tmp_path):
    try:
        read_current_filing_text(tmp_path, "SNOW")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "retrieval agent" in str(exc).lower()


def test_read_current_press_release_text_returns_none_when_missing(tmp_path):
    assert read_current_press_release_text(tmp_path, "SNOW") is None


def test_read_current_press_release_text_ignores_prior_files(tmp_path):
    (tmp_path / "SNOW_8K_EX99.1_2026-09-02.htm").write_text("<p>current press release</p>", encoding="utf-8")
    (tmp_path / "SNOW_8K_EX99.1_PRIOR_2026-06-01.htm").write_text("<p>prior press release</p>", encoding="utf-8")

    result = read_current_press_release_text(tmp_path, "SNOW")

    assert "current press release" in result
    assert "prior press release" not in result


def test_read_current_transcript_text_returns_none_when_no_transcript_field(tmp_path):
    (tmp_path / "SNOW_transcript_2026Q3.json").write_text(
        json.dumps({"error": "premium subscribers only"}), encoding="utf-8"
    )

    assert read_current_transcript_text(tmp_path, "SNOW") is None


def test_read_current_transcript_text_returns_transcript_when_present(tmp_path):
    (tmp_path / "SNOW_transcript_2026Q3.json").write_text(
        json.dumps({"transcript": "Operator: Welcome to the call..."}), encoding="utf-8"
    )

    assert read_current_transcript_text(tmp_path, "SNOW") == "Operator: Welcome to the call..."


def test_read_current_transcript_text_returns_none_when_no_file(tmp_path):
    assert read_current_transcript_text(tmp_path, "SNOW") is None
