import json

from agents.extraction_agent import (
    read_current_filing_text,
    read_current_press_release_text,
    read_current_transcript_text,
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


from unittest.mock import patch

from agents.extraction_agent import run


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

CURRENT_EXTRACTION = {
    "revenue": 1200.0,
    "deferred_revenue_balance": 500.0,
    "risk_factors_text": "No material changes.",
    "guidance_text": "Next quarter revenue of $X-$Y million.",
}

PRIOR_EXTRACTION = {
    "revenue": 900.0,
    "deferred_revenue_balance": 400.0,
    "risk_factors_text": "Prior risk factors text.",
    "guidance_text": "Prior guidance text.",
}

DIFF_RESULT = {"changes_summary": "No changes.", "material_change": False}


def test_run_produces_extracted_json(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test User test@example.com")
    monkeypatch.setenv("API_NINJAS_KEY", "test-ninjas-key")
    monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test-av-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")

    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()
    (data_dir / "SNOW_10-Q_2026-09-04.htm").write_text("<p>current filing</p>", encoding="utf-8")
    (data_dir / "SNOW_8K_EX99.1_2026-09-02.htm").write_text("<p>current press release</p>", encoding="utf-8")
    (data_dir / "SNOW_transcript_2026Q3.json").write_text(
        '{"transcript": "call text"}', encoding="utf-8"
    )

    with patch("agents.extraction_agent.get_cik_for_ticker", return_value=1640147), \
         patch("agents.extraction_agent.get_submissions", return_value=SUBMISSIONS_FIXTURE), \
         patch("agents.extraction_agent.get_filing_index_html", return_value=FIXTURE_INDEX_HTML), \
         patch("agents.extraction_agent.download_document", return_value="<p>prior filing</p>") as mock_download, \
         patch(
             "agents.extraction_agent.extract_period_data",
             side_effect=[CURRENT_EXTRACTION, PRIOR_EXTRACTION],
         ) as mock_extract, \
         patch("agents.extraction_agent.diff_language", return_value=DIFF_RESULT) as mock_diff:

        result = run("SNOW", base_dir=str(tmp_path))

    assert result["ticker"] == "SNOW"
    assert result["current_period"] == CURRENT_EXTRACTION
    assert result["prior_period"] == PRIOR_EXTRACTION
    assert result["billings"] == {
        "revenue": 1200.0,
        "current_deferred_revenue": 500.0,
        "prior_deferred_revenue": 400.0,
        "value": 1300.0,
    }
    assert result["diffs"]["risk_factors"] == DIFF_RESULT
    assert result["diffs"]["guidance_language"] == DIFF_RESULT

    assert mock_extract.call_count == 2
    current_call_docs = mock_extract.call_args_list[0].args[0]
    assert "transcript" in current_call_docs
    prior_call_docs = mock_extract.call_args_list[1].args[0]
    assert "transcript" not in prior_call_docs

    assert mock_diff.call_count == 2
    assert mock_download.call_count == 2  # prior filing + prior exhibit

    output_path = data_dir / "extracted.json"
    assert output_path.exists()
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == result

    prior_filing_path = data_dir / "SNOW_10-Q_PRIOR_2026-06-05.htm"
    assert prior_filing_path.exists()
    prior_exhibit_path = data_dir / "SNOW_8K_EX99.1_PRIOR_2026-06-01.htm"
    assert prior_exhibit_path.exists()
