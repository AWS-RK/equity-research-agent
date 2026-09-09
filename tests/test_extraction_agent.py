import json
from unittest.mock import patch

from agents.extraction_agent import (
    read_current_filing_text,
    read_current_press_release_text,
    read_current_transcript_text,
    fetch_prior_period_documents,
    save_extracted_result,
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


SUBMISSIONS_FIXTURE = {
    "filings": {
        "recent": {
            "form": ["10-Q", "8-K", "10-Q", "8-K"],
            "filingDate": ["2026-09-04", "2026-09-02", "2026-06-05", "2026-06-01"],
            "reportDate": ["2026-07-31", "2026-09-02", "2026-04-30", "2026-06-01"],
            "accessionNumber": [
                "0001640147-26-000037",
                "0001640147-26-000033",
                "0001640147-26-000020",
                "0001640147-26-000019",
            ],
            "items": ["", "2.02,9.01", "", "2.02,9.01"],
            "primaryDocument": [
                "snow-20260731.htm",
                "snow-20260902.htm",
                "snow-20260430.htm",
                "snow-20260601.htm",
            ],
        }
    }
}

FIXTURE_INDEX_HTML = (
    '<tr><td>2</td><td>EX-99.1</td>'
    '<td><a href="/Archives/edgar/data/1640147/x/prior-earnings.htm">prior-earnings.htm</a></td>'
    '<td>EX-99.1</td></tr>'
)


def test_fetch_prior_period_documents_saves_prior_filing_and_exhibit(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test User test@example.com")
    monkeypatch.setenv("API_NINJAS_KEY", "test-ninjas-key")
    monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test-av-key")

    with patch("agents.extraction_agent.get_cik_for_ticker", return_value=1640147), \
         patch("agents.extraction_agent.get_submissions", return_value=SUBMISSIONS_FIXTURE), \
         patch("agents.extraction_agent.get_filing_index_html", return_value=FIXTURE_INDEX_HTML), \
         patch("agents.extraction_agent.download_document", return_value="<p>prior document</p>") as mock_download:

        result = fetch_prior_period_documents("SNOW", base_dir=str(tmp_path))

    assert mock_download.call_count == 2  # prior filing + prior exhibit

    data_dir = tmp_path / "SNOW"
    expected_filing_path = data_dir / "SNOW_10-Q_PRIOR_2026-06-05.htm"
    expected_exhibit_path = data_dir / "SNOW_8K_EX99.1_PRIOR_2026-06-01.htm"

    assert result["prior_filing_path"] == str(expected_filing_path)
    assert result["prior_press_release_path"] == str(expected_exhibit_path)
    assert expected_filing_path.exists()
    assert expected_exhibit_path.exists()


def test_fetch_prior_period_documents_returns_none_paths_when_no_prior_filing(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test User test@example.com")
    monkeypatch.setenv("API_NINJAS_KEY", "test-ninjas-key")
    monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test-av-key")

    single_filing_fixture = {
        "filings": {
            "recent": {
                "form": ["10-Q"],
                "filingDate": ["2026-09-04"],
                "reportDate": ["2026-07-31"],
                "accessionNumber": ["0001640147-26-000037"],
                "items": [""],
                "primaryDocument": ["snow-20260731.htm"],
            }
        }
    }

    with patch("agents.extraction_agent.get_cik_for_ticker", return_value=1640147), \
         patch("agents.extraction_agent.get_submissions", return_value=single_filing_fixture):

        result = fetch_prior_period_documents("SNOW", base_dir=str(tmp_path))

    assert result == {"prior_filing_path": None, "prior_press_release_path": None}


def test_save_extracted_result_computes_billings_and_writes_json(tmp_path):
    current_period = {"revenue": 1200.0, "deferred_revenue_balance": 500.0}
    prior_period = {"revenue": 900.0, "deferred_revenue_balance": 400.0}
    diffs = {
        "risk_factors": {"changes_summary": "No changes.", "material_change": False},
        "guidance_language": {"changes_summary": "Raised the range.", "material_change": True},
    }

    result = save_extracted_result("SNOW", str(tmp_path), current_period, prior_period, diffs)

    assert result["ticker"] == "SNOW"
    assert result["current_period"] == current_period
    assert result["prior_period"] == prior_period
    assert result["billings"] == {
        "revenue": 1200.0,
        "current_deferred_revenue": 500.0,
        "prior_deferred_revenue": 400.0,
        "value": 1300.0,
    }
    assert result["diffs"] == diffs

    output_path = tmp_path / "SNOW" / "extracted.json"
    assert output_path.exists()
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == result


def test_save_extracted_result_handles_no_prior_period(tmp_path):
    current_period = {"revenue": 1200.0, "deferred_revenue_balance": 500.0}

    result = save_extracted_result("SNOW", str(tmp_path), current_period)

    assert result["prior_period"] is None
    assert result["billings"] is None
    assert result["diffs"] == {"risk_factors": None, "guidance_language": None}


from agents.extraction_agent import fetch_historical_press_releases


FOUR_8K_SUBMISSIONS_FIXTURE = {
    "filings": {
        "recent": {
            "form": ["8-K", "8-K", "8-K", "8-K"],
            "filingDate": ["2026-09-02", "2026-06-01", "2026-03-01", "2025-12-01"],
            "reportDate": ["2026-09-02", "2026-06-01", "2026-03-01", "2025-12-01"],
            "accessionNumber": [
                "0001640147-26-000033",
                "0001640147-26-000019",
                "0001640147-26-000010",
                "0001640147-25-000090",
            ],
            "items": ["2.02,9.01", "2.02,9.01", "2.02,9.01", "2.02,9.01"],
            "primaryDocument": [
                "snow-20260902.htm",
                "snow-20260601.htm",
                "snow-20260301.htm",
                "snow-20251201.htm",
            ],
        }
    }
}


def test_fetch_historical_press_releases_skips_current_and_prior_quarters(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test User test@example.com")
    monkeypatch.setenv("API_NINJAS_KEY", "test-ninjas-key")
    monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test-av-key")

    with patch("agents.extraction_agent.get_cik_for_ticker", return_value=1640147), \
         patch("agents.extraction_agent.get_submissions", return_value=FOUR_8K_SUBMISSIONS_FIXTURE), \
         patch("agents.extraction_agent.get_filing_index_html", return_value=FIXTURE_INDEX_HTML), \
         patch("agents.extraction_agent.download_document", return_value="<p>historical document</p>") as mock_download:

        result = fetch_historical_press_releases("SNOW", base_dir=str(tmp_path), count=2)

    assert mock_download.call_count == 2

    data_dir = tmp_path / "SNOW"
    assert result == [
        {"filing_date": "2026-03-01", "path": str(data_dir / "SNOW_8K_EX99.1_HIST_2026-03-01.htm")},
        {"filing_date": "2025-12-01", "path": str(data_dir / "SNOW_8K_EX99.1_HIST_2025-12-01.htm")},
    ]
    assert (data_dir / "SNOW_8K_EX99.1_HIST_2026-03-01.htm").read_text(encoding="utf-8") == "<p>historical document</p>"
    assert (data_dir / "SNOW_8K_EX99.1_HIST_2025-12-01.htm").exists()
