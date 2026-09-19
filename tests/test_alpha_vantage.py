from unittest.mock import Mock, patch

from agents.alpha_vantage import (
    get_earnings,
    get_latest_quarterly_earnings,
    get_company_overview,
    get_earnings_call_transcript,
)


EARNINGS_FIXTURE = {
    "symbol": "SNOW",
    "quarterlyEarnings": [
        {
            "fiscalDateEnding": "2026-07-31",
            "reportedDate": "2026-09-02",
            "reportedEPS": "0.35",
            "estimatedEPS": "0.29",
            "surprise": "0.06",
            "surprisePercentage": "20.6897",
        },
        {
            "fiscalDateEnding": "2026-04-30",
            "reportedDate": "2026-05-28",
            "reportedEPS": "0.30",
            "estimatedEPS": "0.26",
            "surprise": "0.04",
            "surprisePercentage": "15.3846",
        },
    ],
}


@patch("agents.alpha_vantage.requests.get")
def test_get_earnings_calls_correct_endpoint(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = EARNINGS_FIXTURE
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = get_earnings("snow", "test-api-key")

    assert result == EARNINGS_FIXTURE
    called_url = mock_get.call_args.args[0]
    called_params = mock_get.call_args.kwargs["params"]
    assert called_url == "https://www.alphavantage.co/query"
    assert called_params == {"function": "EARNINGS", "symbol": "SNOW", "apikey": "test-api-key"}


def test_get_latest_quarterly_earnings_returns_first_entry():
    result = get_latest_quarterly_earnings(EARNINGS_FIXTURE)

    assert result["fiscalDateEnding"] == "2026-07-31"
    assert result["reportedDate"] == "2026-09-02"


def test_get_latest_quarterly_earnings_returns_none_when_empty():
    assert get_latest_quarterly_earnings({"quarterlyEarnings": []}) is None


OVERVIEW_FIXTURE = {
    "Symbol": "SNOW",
    "MarketCapitalization": "118364398000",
    "EVToRevenue": "21.58",
    "PriceToSalesRatioTTM": "21.78",
    "TrailingPE": "-",
    "ForwardPE": "169.49",
    "RevenueTTM": "5434647000",
    "SharesOutstanding": "352800000",
    "AnalystTargetPrice": "413.29",
}


@patch("agents.alpha_vantage.requests.get")
def test_get_company_overview_calls_correct_endpoint(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = OVERVIEW_FIXTURE
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = get_company_overview("snow", "test-api-key")

    assert result == OVERVIEW_FIXTURE
    called_url = mock_get.call_args.args[0]
    called_params = mock_get.call_args.kwargs["params"]
    assert called_url == "https://www.alphavantage.co/query"
    assert called_params == {"function": "OVERVIEW", "symbol": "SNOW", "apikey": "test-api-key"}


TRANSCRIPT_FIXTURE = {
    "symbol": "SNOW",
    "quarter": "2027Q2",
    "transcript": [
        {"speaker": "Sridhar Ramaswamy", "title": "Chief Executive Officer (CEO)", "content": "Thanks, everyone."},
    ],
}


@patch("agents.alpha_vantage.requests.get")
def test_get_earnings_call_transcript_calls_correct_endpoint(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = TRANSCRIPT_FIXTURE
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = get_earnings_call_transcript("snow", "test-api-key", "2027Q2")

    assert result == TRANSCRIPT_FIXTURE
    called_url = mock_get.call_args.args[0]
    called_params = mock_get.call_args.kwargs["params"]
    assert called_url == "https://www.alphavantage.co/query"
    assert called_params == {
        "function": "EARNINGS_CALL_TRANSCRIPT",
        "symbol": "SNOW",
        "quarter": "2027Q2",
        "apikey": "test-api-key",
    }
