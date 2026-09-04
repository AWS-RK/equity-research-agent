from unittest.mock import Mock, patch

from agents.api_ninjas import get_transcript


@patch("agents.api_ninjas.requests.get")
def test_get_transcript_passes_ticker_year_quarter_and_api_key(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {"ticker": "SNOW", "year": 2026, "quarter": 2, "transcript": "..."}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = get_transcript("snow", "test-api-key", year=2026, quarter=2)

    assert result["ticker"] == "SNOW"
    called_url = mock_get.call_args.args[0]
    called_kwargs = mock_get.call_args.kwargs
    assert called_url == "https://api.api-ninjas.com/v1/earningstranscript"
    assert called_kwargs["headers"] == {"X-Api-Key": "test-api-key"}
    assert called_kwargs["params"] == {"ticker": "SNOW", "year": 2026, "quarter": 2}


@patch("agents.api_ninjas.requests.get")
def test_get_transcript_omits_year_quarter_when_not_given(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {"ticker": "SNOW"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    get_transcript("SNOW", "test-api-key")

    called_kwargs = mock_get.call_args.kwargs
    assert called_kwargs["params"] == {"ticker": "SNOW"}
