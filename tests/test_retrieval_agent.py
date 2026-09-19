import json
from datetime import date

import requests

from agents.retrieval_agent import derive_year_quarter, derive_fiscal_quarter_guess


def test_derive_year_quarter_q3_boundary():
    assert derive_year_quarter(date(2026, 7, 31)) == (2026, 3)


def test_derive_year_quarter_q1():
    assert derive_year_quarter(date(2026, 2, 15)) == (2026, 1)


def test_derive_year_quarter_q4():
    assert derive_year_quarter(date(2025, 12, 31)) == (2025, 4)


def test_derive_fiscal_quarter_guess_matches_snow_q2_fy2027():
    # Confirmed live against Alpha Vantage: SNOW's own "Second Quarter of
    # Fiscal 2027" press release covers the period ended July 31, 2026.
    assert derive_fiscal_quarter_guess(date(2026, 7, 31)) == "2027Q2"


def test_derive_fiscal_quarter_guess_matches_snow_q4_fy2026():
    # Confirmed live: SNOW's "Fourth Quarter and Full-Year of Fiscal 2026"
    # covers the period ended January 31, 2026.
    assert derive_fiscal_quarter_guess(date(2026, 1, 31)) == "2026Q4"


def test_derive_fiscal_quarter_guess_matches_snow_q1_fy2027():
    assert derive_fiscal_quarter_guess(date(2026, 4, 30)) == "2027Q1"


from unittest.mock import patch

from agents.retrieval_agent import run


FIXTURE_SUBMISSIONS = {
    "filings": {
        "recent": {
            "form": ["10-Q", "8-K"],
            "filingDate": ["2026-09-04", "2026-09-02"],
            "reportDate": ["2026-07-31", "2026-09-02"],
            "accessionNumber": ["0001640147-26-000037", "0001640147-26-000033"],
            "items": ["", "2.02,9.01"],
            "primaryDocument": ["snow-20260731.htm", "snow-20260902.htm"],
        }
    }
}

FIXTURE_INDEX_HTML = """
<tr><td>1</td><td>8-K</td><td><a href="/Archives/edgar/data/1640147/000164014726000033/snow-20260902.htm">snow-20260902.htm</a></td><td>8-K</td></tr>
<tr><td>2</td><td>EX-99.1</td><td><a href="/Archives/edgar/data/1640147/000164014726000033/fy2027q2earnings.htm">fy2027q2earnings.htm</a></td><td>EX-99.1</td></tr>
"""

FIXTURE_TRANSCRIPT = {"ticker": "SNOW", "date": "2026-09-02", "transcript": "..."}

FIXTURE_EARNINGS = {
    "symbol": "SNOW",
    "quarterlyEarnings": [
        {"fiscalDateEnding": "2026-07-31", "reportedDate": "2026-09-02", "reportedEPS": "0.35"}
    ],
}


def test_run_saves_all_documents_and_builds_freshness_report(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test User test@example.com")
    monkeypatch.setenv("API_NINJAS_KEY", "test-ninjas-key")
    monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test-av-key")

    with patch("agents.retrieval_agent.get_cik_for_ticker", return_value=1640147) as mock_cik, \
         patch("agents.retrieval_agent.get_submissions", return_value=FIXTURE_SUBMISSIONS), \
         patch("agents.retrieval_agent.download_document", return_value="<html>doc</html>") as mock_download, \
         patch("agents.retrieval_agent.get_filing_index_html", return_value=FIXTURE_INDEX_HTML), \
         patch("agents.retrieval_agent.get_transcript", return_value=FIXTURE_TRANSCRIPT) as mock_transcript, \
         patch("agents.retrieval_agent.get_earnings", return_value=FIXTURE_EARNINGS):

        freshness_report = run("SNOW", base_dir=str(tmp_path), max_age_days=95)

    mock_cik.assert_called_once_with("SNOW", "Test User test@example.com")
    mock_transcript.assert_called_once_with("SNOW", "test-ninjas-key", year=2026, quarter=3)
    assert mock_download.call_count == 2

    data_dir = tmp_path / "SNOW"
    saved_files = {p.name for p in data_dir.iterdir()}
    assert "SNOW_10-Q_2026-09-04.htm" in saved_files
    assert "SNOW_8K_EX99.1_2026-09-02.htm" in saved_files
    assert "SNOW_transcript_2026Q3.json" in saved_files
    assert "SNOW_earnings_alphavantage.json" in saved_files

    documents_reported = {entry["document"] for entry in freshness_report}
    assert documents_reported == set(saved_files)
    for entry in freshness_report:
        assert "is_fresh" in entry
        assert "age_days" in entry


def test_run_continues_when_transcript_endpoint_is_gated(tmp_path, monkeypatch):
    # Discovered live against the real API Ninjas free tier: the earnings
    # transcript endpoint returns 400 with an error body for accounts without
    # a paid subscription. A gated/unavailable transcript must not crash the
    # whole run -- every other independent data source should still complete.
    monkeypatch.setenv("SEC_USER_AGENT", "Test User test@example.com")
    monkeypatch.setenv("API_NINJAS_KEY", "test-ninjas-key")
    monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test-av-key")

    http_error = requests.exceptions.HTTPError("400 Client Error: Bad Request")

    with patch("agents.retrieval_agent.get_cik_for_ticker", return_value=1640147), \
         patch("agents.retrieval_agent.get_submissions", return_value=FIXTURE_SUBMISSIONS), \
         patch("agents.retrieval_agent.download_document", return_value="<html>doc</html>"), \
         patch("agents.retrieval_agent.get_filing_index_html", return_value=FIXTURE_INDEX_HTML), \
         patch("agents.retrieval_agent.get_transcript", side_effect=http_error), \
         patch("agents.retrieval_agent.get_earnings_call_transcript", return_value={}) as mock_fallback, \
         patch("agents.retrieval_agent.get_earnings", return_value=FIXTURE_EARNINGS) as mock_earnings:

        freshness_report = run("SNOW", base_dir=str(tmp_path), max_age_days=95)

    mock_earnings.assert_called_once_with("SNOW", "test-av-key")
    mock_fallback.assert_called_once_with("SNOW", "test-av-key", "2027Q2")

    data_dir = tmp_path / "SNOW"
    transcript_path = data_dir / "SNOW_transcript_2026Q3.json"
    assert transcript_path.exists()
    saved = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert "error" in saved

    documents_reported = {entry["document"] for entry in freshness_report}
    assert transcript_path.name not in documents_reported
    assert "SNOW_earnings_alphavantage.json" in documents_reported


def test_run_uses_alpha_vantage_fallback_when_it_has_the_transcript(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test User test@example.com")
    monkeypatch.setenv("API_NINJAS_KEY", "test-ninjas-key")
    monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test-av-key")

    http_error = requests.exceptions.HTTPError("400 Client Error: Bad Request")
    fallback_transcript = {
        "symbol": "SNOW",
        "quarter": "2027Q2",
        "transcript": [{"speaker": "Sridhar Ramaswamy", "title": "CEO", "content": "Thanks, everyone."}],
    }

    with patch("agents.retrieval_agent.get_cik_for_ticker", return_value=1640147), \
         patch("agents.retrieval_agent.get_submissions", return_value=FIXTURE_SUBMISSIONS), \
         patch("agents.retrieval_agent.download_document", return_value="<html>doc</html>"), \
         patch("agents.retrieval_agent.get_filing_index_html", return_value=FIXTURE_INDEX_HTML), \
         patch("agents.retrieval_agent.get_transcript", side_effect=http_error), \
         patch("agents.retrieval_agent.get_earnings_call_transcript", return_value=fallback_transcript), \
         patch("agents.retrieval_agent.get_earnings", return_value=FIXTURE_EARNINGS):

        run("SNOW", base_dir=str(tmp_path), max_age_days=95)

    data_dir = tmp_path / "SNOW"
    transcript_path = data_dir / "SNOW_transcript_2026Q3.json"
    saved = json.loads(transcript_path.read_text(encoding="utf-8"))
    assert "error" not in saved
    assert saved == fallback_transcript
