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


from agents.sec_edgar import find_exhibit_991_filename


INDEX_HTML_FIXTURE = """
<table class="tableFile" summary="Document Format Files">
  <tr>
    <th scope="col">Seq</th>
    <th scope="col">Description</th>
    <th scope="col">Document</th>
    <th scope="col">Type</th>
    <th scope="col">Size</th>
  </tr>
  <tr>
    <td scope="row">1</td>
    <td scope="row">8-K</td>
    <td scope="row"><a href="/ix?doc=/Archives/edgar/data/1640147/000164014726000033/snow-20260902.htm">snow-20260902.htm</a></td>
    <td scope="row">8-K</td>
    <td scope="row">29666</td>
  </tr>
  <tr class="evenRow">
    <td scope="row">2</td>
    <td scope="row">EX-99.1</td>
    <td scope="row"><a href="/Archives/edgar/data/1640147/000164014726000033/fy2027q2earnings.htm">fy2027q2earnings.htm</a></td>
    <td scope="row">EX-99.1</td>
    <td scope="row">613720</td>
  </tr>
  <tr>
    <td scope="row">6</td>
    <td scope="row"></td>
    <td scope="row"><a href="/Archives/edgar/data/1640147/000164014726000033/imagea.jpg">imagea.jpg</a></td>
    <td scope="row">GRAPHIC</td>
    <td scope="row">3840</td>
  </tr>
</table>
"""


def test_find_exhibit_991_filename_extracts_correct_file():
    result = find_exhibit_991_filename(INDEX_HTML_FIXTURE)

    assert result == "fy2027q2earnings.htm"


def test_find_exhibit_991_filename_returns_none_when_absent():
    html_without_exhibit = "<table><tr><td>8-K</td></tr></table>"
    assert find_exhibit_991_filename(html_without_exhibit) is None


from agents.sec_edgar import get_filing_index_html, download_document


@patch("agents.sec_edgar.requests.get")
def test_get_filing_index_html_builds_correct_url(mock_get):
    mock_response = Mock()
    mock_response.text = "<html>index</html>"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = get_filing_index_html(1640147, "0001640147-26-000033", "Test User test@example.com")

    assert result == "<html>index</html>"
    called_url = mock_get.call_args.args[0]
    assert called_url == (
        "https://www.sec.gov/Archives/edgar/data/1640147/000164014726000033/"
        "0001640147-26-000033-index.htm"
    )


@patch("agents.sec_edgar.requests.get")
def test_download_document_builds_correct_url(mock_get):
    mock_response = Mock()
    mock_response.text = "<html>document body</html>"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = download_document(1640147, "0001640147-26-000033", "snow-20260902.htm", "Test User test@example.com")

    assert result == "<html>document body</html>"
    called_url = mock_get.call_args.args[0]
    assert called_url == (
        "https://www.sec.gov/Archives/edgar/data/1640147/000164014726000033/snow-20260902.htm"
    )


from agents.sec_edgar import find_prior_10q_or_10k


def test_find_prior_10q_or_10k_excludes_given_accession():
    result = find_prior_10q_or_10k(SUBMISSIONS_FIXTURE, exclude_accession="0001640147-26-000037")

    assert result["form"] == "10-Q"
    assert result["filingDate"] == "2026-06-05"
    assert result["accessionNumber"] == "0001640147-26-000020"


def test_find_prior_10q_or_10k_returns_none_when_only_excluded_one_exists():
    fixture = {
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
    assert find_prior_10q_or_10k(fixture, exclude_accession="0001640147-26-000037") is None


def test_find_prior_10q_or_10k_with_no_exclusion_returns_latest():
    result = find_prior_10q_or_10k(SUBMISSIONS_FIXTURE)

    assert result["accessionNumber"] == "0001640147-26-000037"
