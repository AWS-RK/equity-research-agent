from unittest.mock import Mock, patch

import pytest

from agents.sec_edgar import get_cik_for_ticker


COMPANY_TICKERS_FIXTURE = {
    "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "2": {"cik_str": 1640147, "ticker": "SNOW", "title": "Snowflake Inc."},
}


@patch("agents.sec_edgar.requests.get")
def test_get_cik_for_ticker_finds_match(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = COMPANY_TICKERS_FIXTURE
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    cik = get_cik_for_ticker("snow", "Test User test@example.com")

    assert cik == 1640147
    called_url = mock_get.call_args.args[0]
    called_headers = mock_get.call_args.kwargs["headers"]
    assert called_url == "https://www.sec.gov/files/company_tickers.json"
    assert called_headers["User-Agent"] == "Test User test@example.com"


@patch("agents.sec_edgar.requests.get")
def test_get_cik_for_ticker_raises_when_not_found(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = COMPANY_TICKERS_FIXTURE
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    with pytest.raises(ValueError, match="NOPE"):
        get_cik_for_ticker("NOPE", "Test User test@example.com")


from agents.sec_edgar import get_submissions


@patch("agents.sec_edgar.requests.get")
def test_get_submissions_builds_padded_cik_url(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {"name": "Snowflake Inc."}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = get_submissions(1640147, "Test User test@example.com")

    assert result == {"name": "Snowflake Inc."}
    called_url = mock_get.call_args.args[0]
    assert called_url == "https://data.sec.gov/submissions/CIK0001640147.json"


from agents.sec_edgar import find_latest_10q_or_10k


SUBMISSIONS_FIXTURE = {
    "filings": {
        "recent": {
            "form": ["144", "10-Q", "4", "8-K", "10-K", "10-Q"],
            "filingDate": [
                "2026-09-04",
                "2026-09-04",
                "2026-09-03",
                "2026-09-02",
                "2025-03-01",
                "2026-06-05",
            ],
            "reportDate": ["", "2026-07-31", "2026-09-01", "2026-09-02", "2024-12-31", "2026-04-30"],
            "accessionNumber": [
                "0001973251-26-000034",
                "0001640147-26-000037",
                "0001979088-26-000018",
                "0001640147-26-000033",
                "0001640147-25-000010",
                "0001640147-26-000020",
            ],
            "items": ["", "", "", "2.02,9.01", "", ""],
            "primaryDocument": [
                "xsl144X01/primary_doc.xml",
                "snow-20260731.htm",
                "xslF345X06/wk-form4.xml",
                "snow-20260902.htm",
                "snow-20241231.htm",
                "snow-20260430.htm",
            ],
        }
    }
}


def test_find_latest_10q_or_10k_picks_most_recent_by_date():
    result = find_latest_10q_or_10k(SUBMISSIONS_FIXTURE)

    assert result["form"] == "10-Q"
    assert result["filingDate"] == "2026-09-04"
    assert result["reportDate"] == "2026-07-31"
    assert result["accessionNumber"] == "0001640147-26-000037"
    assert result["primaryDocument"] == "snow-20260731.htm"


def test_find_latest_10q_or_10k_raises_when_none_found():
    empty_fixture = {
        "filings": {
            "recent": {
                "form": ["144"],
                "filingDate": ["2026-09-04"],
                "reportDate": [""],
                "accessionNumber": ["0001973251-26-000034"],
                "items": [""],
                "primaryDocument": ["xsl144X01/primary_doc.xml"],
            }
        }
    }
    with pytest.raises(ValueError, match="No 10-Q or 10-K"):
        find_latest_10q_or_10k(empty_fixture)


from agents.sec_edgar import find_latest_8k_item202


def test_find_latest_8k_item202_picks_matching_filing():
    result = find_latest_8k_item202(SUBMISSIONS_FIXTURE)

    assert result["form"] == "8-K"
    assert result["filingDate"] == "2026-09-02"
    assert result["accessionNumber"] == "0001640147-26-000033"
    assert result["primaryDocument"] == "snow-20260902.htm"


def test_find_latest_8k_item202_returns_none_when_absent():
    fixture_without_8k = {
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
    assert find_latest_8k_item202(fixture_without_8k) is None
