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
