import json

from agents.analysis_agent import read_extracted_data


def test_read_extracted_data_returns_parsed_json(tmp_path):
    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()
    (data_dir / "extracted.json").write_text(
        json.dumps({"ticker": "SNOW", "current_period": {"revenue": 1546.793}}),
        encoding="utf-8",
    )

    result = read_extracted_data("SNOW", base_dir=str(tmp_path))

    assert result == {"ticker": "SNOW", "current_period": {"revenue": 1546.793}}


def test_read_extracted_data_raises_when_missing(tmp_path):
    try:
        read_extracted_data("SNOW", base_dir=str(tmp_path))
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "extraction agent" in str(exc).lower()
