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


from agents.analysis_agent import read_eps_consensus


def test_read_eps_consensus_returns_latest_quarter(tmp_path):
    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()
    earnings = {
        "symbol": "SNOW",
        "quarterlyEarnings": [
            {
                "fiscalDateEnding": "2026-07-31",
                "reportedDate": "2026-09-02",
                "reportedEPS": "0.62",
                "estimatedEPS": "0.55",
                "surprise": "0.07",
                "surprisePercentage": "12.7273",
            },
            {
                "fiscalDateEnding": "2026-04-30",
                "reportedDate": "2026-05-27",
                "reportedEPS": "0.39",
                "estimatedEPS": "0.21",
                "surprise": "0.18",
                "surprisePercentage": "85.7143",
            },
        ],
    }
    (data_dir / "SNOW_earnings_alphavantage.json").write_text(json.dumps(earnings), encoding="utf-8")

    result = read_eps_consensus("SNOW", base_dir=str(tmp_path))

    assert result["fiscalDateEnding"] == "2026-07-31"
    assert result["reportedEPS"] == "0.62"
    assert result["surprisePercentage"] == "12.7273"


def test_read_eps_consensus_returns_none_when_no_quarterly_earnings(tmp_path):
    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()
    (data_dir / "SNOW_earnings_alphavantage.json").write_text(
        json.dumps({"symbol": "SNOW", "quarterlyEarnings": []}), encoding="utf-8"
    )

    assert read_eps_consensus("SNOW", base_dir=str(tmp_path)) is None


def test_read_eps_consensus_raises_when_file_missing(tmp_path):
    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()

    try:
        read_eps_consensus("SNOW", base_dir=str(tmp_path))
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "retrieval agent" in str(exc).lower()
