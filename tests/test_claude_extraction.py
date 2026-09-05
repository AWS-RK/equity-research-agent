from unittest.mock import MagicMock, patch

from agents.claude_extraction import extract_period_data


def _mock_tool_response(tool_input: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    return response


FAKE_EXTRACTION = {
    "revenue": 1200.5,
    "revenue_yoy_growth_pct": 30.0,
    "gross_margin_gaap_pct": 68.0,
    "gross_margin_non_gaap_pct": 76.0,
    "operating_margin_gaap_pct": -5.0,
    "operating_margin_non_gaap_pct": 10.0,
    "net_income_gaap": -10.0,
    "net_income_non_gaap": 100.0,
    "eps_gaap": -0.03,
    "eps_non_gaap": 0.30,
    "operating_cash_flow": 200.0,
    "free_cash_flow": 150.0,
    "deferred_revenue_balance": 500.0,
    "segment_revenues": [],
    "guidance": [],
    "disclosed_kpis": [],
    "risk_factors_text": "No material changes.",
    "guidance_text": "We expect next quarter revenue of $X-$Y million.",
    "unavailable": [],
}


@patch("agents.claude_extraction.Anthropic")
def test_extract_period_data_returns_tool_input(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_response(FAKE_EXTRACTION)
    mock_anthropic_cls.return_value = mock_client

    result = extract_period_data({"filing": "some filing text"})

    assert result == FAKE_EXTRACTION
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-5"
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "record_period_extraction"}
    assert len(call_kwargs["tools"]) == 1
    assert call_kwargs["tools"][0]["name"] == "record_period_extraction"


@patch("agents.claude_extraction.Anthropic")
def test_extract_period_data_uses_given_model(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_response(FAKE_EXTRACTION)
    mock_anthropic_cls.return_value = mock_client

    extract_period_data({"filing": "text"}, model="claude-haiku-4-5-20251001")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


@patch("agents.claude_extraction.Anthropic")
def test_extract_period_data_includes_transcript_section_only_when_given(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_response(FAKE_EXTRACTION)
    mock_anthropic_cls.return_value = mock_client

    extract_period_data({"filing": "filing text", "transcript": "call transcript text"})

    prompt_sent = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "call transcript text" in prompt_sent
    assert "TRANSCRIPT" in prompt_sent.upper()

    mock_client.reset_mock()
    extract_period_data({"filing": "filing text"})

    prompt_sent = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "TRANSCRIPT" not in prompt_sent.upper()


@patch("agents.claude_extraction.Anthropic")
def test_extract_period_data_raises_when_no_tool_use_block(mock_anthropic_cls):
    mock_client = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    response = MagicMock()
    response.content = [text_block]
    mock_client.messages.create.return_value = response
    mock_anthropic_cls.return_value = mock_client

    try:
        extract_period_data({"filing": "text"})
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "tool_use" in str(exc)
