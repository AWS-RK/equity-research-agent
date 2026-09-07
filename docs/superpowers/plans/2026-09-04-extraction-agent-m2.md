# M2 Extraction Agent Implementation Plan

> **SUPERSEDED (2026-09-07):** Tasks 6, 7, and part of 9/10 below built
> `agents/claude_extraction.py` (an Anthropic API wrapper) and wired it into
> `agents/extraction_agent.py`'s `run()`. That module has been deleted and
> `run()` replaced with `fetch_prior_period_documents()` +
> `save_extracted_result()` -- the reading-comprehension work now happens via
> Claude directly in a session instead of a separate billed API key. Tasks
> 1-5 and 8 (config scaffolding note aside -- Task 1's `ANTHROPIC_API_KEY`
> addition was later reverted -- , html_text, derived_metrics, the two
> sec_edgar prior-filing refactors, and the current-period file readers) are
> still accurate as executed. See the superseded-note in
> `docs/superpowers/specs/2026-09-04-extraction-agent-m2-design.md` for the
> full rationale.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a ticker whose raw documents M1 already saved to `data/{TICKER}/`, extract structured financial and operating data — generic across sectors, not SaaS-specific — into `data/{TICKER}/extracted.json`, using Claude (Sonnet 5) for the parts that require reading comprehension across a 100K+ token filing, and plain deterministic Python for the one part that's pure arithmetic (billings).

**Architecture:** `agents/html_text.py` strips SEC's inline-XBRL HTML down to clean text. `agents/claude_extraction.py` wraps the Anthropic API with forced tool-use (never free-text JSON parsing) for two call types: `extract_period_data` (Sonnet 5, same schema for current and prior period) and `diff_language` (Haiku 4.5, compares two already-extracted text fields). `agents/sec_edgar.py` gains `find_prior_10q_or_10k`/`find_prior_8k_item202` (refactored from the existing `find_latest_*` functions' shared candidate-collection logic) so the prior quarter's filing/press-release can be fetched and saved the same way M1 fetched the current one. `agents/derived_metrics.py` computes billings from the two periods' extracted deferred-revenue balances. `agents/extraction_agent.py` orchestrates all of it as a CLI, mirroring `retrieval_agent.py`'s shape.

**Tech Stack:** Adds the `anthropic` SDK as a new runtime dependency. No other new dependencies.

**Full design rationale:** see `docs/superpowers/specs/2026-09-04-extraction-agent-m2-design.md` (approved).

**Verified facts locked into this plan:**
- The real SNOW 10-Q (2.5MB HTML) strips to ~411K chars (~103K estimated tokens) after removing the inline-XBRL `<ix:header>` block and all tags — this is genuine document content (footnotes, MD&A, risk factors), not further compressible without risky section-guessing heuristics.
- `extract_period_data` defaults to `"claude-sonnet-5"`; `diff_language` defaults to `"claude-haiku-4-5-20251001"` — decided with the user specifically to tier cost against task complexity.
- M1's saved filenames are `{TICKER}_{form}_{filingDate}.htm` (10-Q/10-K), `{TICKER}_8K_EX99.1_{filingDate}.htm`, `{TICKER}_transcript_{year}Q{quarter}.json`, `{TICKER}_earnings_alphavantage.json`, all directly under `data/{TICKER}/`.

---

## Task 1: Add `ANTHROPIC_API_KEY` to config and dependencies

**Files:**
- Modify: `agents/config.py`
- Modify: `tests/test_config.py`
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing test**

In `tests/test_config.py`, update `test_load_config_reads_all_three_vars` (rename it and add the fourth var) and `test_load_config_raises_on_missing_var`:

Replace:
```python
def test_load_config_reads_all_three_vars(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'SEC_USER_AGENT="Test User test@example.com"\n'
        "API_NINJAS_KEY=abc123\n"
        "ALPHA_VANTAGE_KEY=xyz789\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("API_NINJAS_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_KEY", raising=False)

    config = load_config()

    assert config.sec_user_agent == "Test User test@example.com"
    assert config.api_ninjas_key == "abc123"
    assert config.alpha_vantage_key == "xyz789"
```

with:
```python
def test_load_config_reads_all_four_vars(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        'SEC_USER_AGENT="Test User test@example.com"\n'
        "API_NINJAS_KEY=abc123\n"
        "ALPHA_VANTAGE_KEY=xyz789\n"
        "ANTHROPIC_API_KEY=sk-ant-test123\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("API_NINJAS_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    config = load_config()

    assert config.sec_user_agent == "Test User test@example.com"
    assert config.api_ninjas_key == "abc123"
    assert config.alpha_vantage_key == "xyz789"
    assert config.anthropic_api_key == "sk-ant-test123"
```

And update `test_load_config_raises_on_missing_var` to also clear the new var:
```python
def test_load_config_raises_on_missing_var(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("API_NINJAS_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        load_config()
```

(Leave `test_get_data_dir_creates_directory` untouched.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `test_load_config_reads_all_four_vars` fails with `AttributeError: 'Config' object has no attribute 'anthropic_api_key'`

- [ ] **Step 3: Write minimal implementation**

Replace the full contents of `agents/config.py` with:
```python
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


@dataclass
class Config:
    sec_user_agent: str
    api_ninjas_key: str
    alpha_vantage_key: str
    anthropic_api_key: str


def load_config() -> Config:
    # find_dotenv(usecwd=True): search for .env starting from the current working
    # directory, not from this module's file location (the default when no path is
    # given), so tests that chdir into a tmp_path see only their own fixture .env.
    load_dotenv(find_dotenv(usecwd=True))
    sec_user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    api_ninjas_key = os.environ.get("API_NINJAS_KEY", "").strip()
    alpha_vantage_key = os.environ.get("ALPHA_VANTAGE_KEY", "").strip()
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    missing = [
        name
        for name, value in [
            ("SEC_USER_AGENT", sec_user_agent),
            ("API_NINJAS_KEY", api_ninjas_key),
            ("ALPHA_VANTAGE_KEY", alpha_vantage_key),
            ("ANTHROPIC_API_KEY", anthropic_api_key),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
        )

    return Config(
        sec_user_agent=sec_user_agent,
        api_ninjas_key=api_ninjas_key,
        alpha_vantage_key=alpha_vantage_key,
        anthropic_api_key=anthropic_api_key,
    )


def get_data_dir(ticker: str, base_dir: str = "data") -> Path:
    data_dir = Path(base_dir) / ticker.upper()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Add the `anthropic` SDK dependency**

Append to `requirements.txt`:
```
anthropic>=0.40.0
```

- [ ] **Step 6: Document the new env var**

Append to `.env.example`:
```

# Anthropic API (used by the M2 extraction agent): https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=
```

- [ ] **Step 7: Install the new dependency and run the full suite**

Run: `pip install -r requirements-dev.txt`
Run: `pytest -v`
Expected: all 26 existing tests still pass (this task only touched config, which is exercised by `tests/test_config.py`)

- [ ] **Step 8: Commit**

```bash
git add agents/config.py tests/test_config.py requirements.txt .env.example
git commit -m "feat: add ANTHROPIC_API_KEY config and anthropic SDK dependency"
```

## IMPORTANT — update your local `.env` too

`.env` is gitignored, so this step doesn't touch it, but `load_config()` will now
raise until `ANTHROPIC_API_KEY` is set there too. Add a real key from
https://console.anthropic.com/settings/keys before Task 10's live smoke test.

---

## Task 2: HTML-to-text stripping

**Files:**
- Create: `agents/html_text.py`
- Create: `tests/test_html_text.py`

- [ ] **Step 1: Write the failing test**

`tests/test_html_text.py`:
```python
from agents.html_text import strip_html_to_text


def test_strip_html_to_text_removes_ix_header_block():
    html = (
        "<html><ix:header>"
        "<ix:hidden>lots of xbrl context junk here that should vanish</ix:hidden>"
        "</ix:header><body><p>Revenue was $100 million.</p></body></html>"
    )

    result = strip_html_to_text(html)

    assert "xbrl context junk" not in result
    assert "Revenue was $100 million." in result


def test_strip_html_to_text_removes_script_and_style():
    html = (
        "<html><head><style>.x { color: red; }</style>"
        "<script>alert('hi');</script></head>"
        "<body><p>Net income increased.</p></body></html>"
    )

    result = strip_html_to_text(html)

    assert "color: red" not in result
    assert "alert" not in result
    assert "Net income increased." in result


def test_strip_html_to_text_unescapes_entities_and_collapses_whitespace():
    html = "<p>Stockholders&#8217; equity   was    $5&nbsp;million.</p>"

    result = strip_html_to_text(html)

    assert "Stockholders’ equity was $5 million." in " ".join(result.split()) or \
        "Stockholders" in result
    assert "&#8217;" not in result
    assert "&nbsp;" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_html_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.html_text'`

- [ ] **Step 3: Write minimal implementation**

`agents/html_text.py`:
```python
import html
import re


def strip_html_to_text(raw_html: str) -> str:
    text = re.sub(r"<ix:header.*?</ix:header>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_html_text.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/html_text.py tests/test_html_text.py
git commit -m "feat: add HTML-to-text stripping for filing documents"
```

---

## Task 3: Derived metrics (billings)

**Files:**
- Create: `agents/derived_metrics.py`
- Create: `tests/test_derived_metrics.py`

- [ ] **Step 1: Write the failing test**

`tests/test_derived_metrics.py`:
```python
from agents.derived_metrics import compute_billings


def test_compute_billings_when_all_inputs_present():
    current = {"revenue": 1000.0, "deferred_revenue_balance": 500.0}
    prior = {"deferred_revenue_balance": 400.0}

    result = compute_billings(current, prior)

    assert result == {
        "revenue": 1000.0,
        "current_deferred_revenue": 500.0,
        "prior_deferred_revenue": 400.0,
        "value": 1100.0,
    }


def test_compute_billings_returns_none_when_revenue_missing():
    current = {"revenue": None, "deferred_revenue_balance": 500.0}
    prior = {"deferred_revenue_balance": 400.0}

    assert compute_billings(current, prior) is None


def test_compute_billings_returns_none_when_current_deferred_revenue_missing():
    current = {"revenue": 1000.0, "deferred_revenue_balance": None}
    prior = {"deferred_revenue_balance": 400.0}

    assert compute_billings(current, prior) is None


def test_compute_billings_returns_none_when_prior_deferred_revenue_missing():
    current = {"revenue": 1000.0, "deferred_revenue_balance": 500.0}
    prior = {"deferred_revenue_balance": None}

    assert compute_billings(current, prior) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_derived_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.derived_metrics'`

- [ ] **Step 3: Write minimal implementation**

`agents/derived_metrics.py`:
```python
def compute_billings(current: dict, prior: dict) -> dict | None:
    revenue = current.get("revenue")
    current_deferred_revenue = current.get("deferred_revenue_balance")
    prior_deferred_revenue = prior.get("deferred_revenue_balance")

    if revenue is None or current_deferred_revenue is None or prior_deferred_revenue is None:
        return None

    return {
        "revenue": revenue,
        "current_deferred_revenue": current_deferred_revenue,
        "prior_deferred_revenue": prior_deferred_revenue,
        "value": revenue + current_deferred_revenue - prior_deferred_revenue,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_derived_metrics.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/derived_metrics.py tests/test_derived_metrics.py
git commit -m "feat: add billings computation (generic, not SaaS-gated)"
```

---

## Task 4: Refactor `sec_edgar.py` for shared candidate-collection + `find_prior_10q_or_10k`

**Files:**
- Modify: `agents/sec_edgar.py`
- Modify: `tests/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sec_edgar.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_prior_10q_or_10k'`

- [ ] **Step 3: Refactor and add the new function**

Replace this section of `agents/sec_edgar.py`:
```python
def find_latest_10q_or_10k(submissions: dict) -> dict:
    recent = submissions["filings"]["recent"]
    candidates = []
    for i, form in enumerate(recent["form"]):
        if form in ("10-Q", "10-K"):
            candidates.append(
                {
                    "form": form,
                    "filingDate": recent["filingDate"][i],
                    "reportDate": recent["reportDate"][i],
                    "accessionNumber": recent["accessionNumber"][i],
                    "primaryDocument": recent["primaryDocument"][i],
                }
            )

    if not candidates:
        raise ValueError("No 10-Q or 10-K filings found in submissions")

    candidates.sort(key=lambda c: c["filingDate"], reverse=True)
    return candidates[0]
```

with:
```python
def _collect_10q_10k_candidates(submissions: dict) -> list[dict]:
    recent = submissions["filings"]["recent"]
    candidates = []
    for i, form in enumerate(recent["form"]):
        if form in ("10-Q", "10-K"):
            candidates.append(
                {
                    "form": form,
                    "filingDate": recent["filingDate"][i],
                    "reportDate": recent["reportDate"][i],
                    "accessionNumber": recent["accessionNumber"][i],
                    "primaryDocument": recent["primaryDocument"][i],
                }
            )

    candidates.sort(key=lambda c: c["filingDate"], reverse=True)
    return candidates


def find_latest_10q_or_10k(submissions: dict) -> dict:
    candidates = _collect_10q_10k_candidates(submissions)

    if not candidates:
        raise ValueError("No 10-Q or 10-K filings found in submissions")

    return candidates[0]


def find_prior_10q_or_10k(submissions: dict, exclude_accession: str | None = None) -> dict | None:
    candidates = _collect_10q_10k_candidates(submissions)
    remaining = [c for c in candidates if c["accessionNumber"] != exclude_accession]

    if not remaining:
        return None

    return remaining[0]
```

- [ ] **Step 4: Run the full test suite to verify nothing broke and the new tests pass**

Run: `pytest -v`
Expected: all existing tests still pass (this is a pure refactor of `find_latest_10q_or_10k`'s internals — same signature, same behavior, same error message) plus 3 new tests pass (29 total)

- [ ] **Step 5: Commit**

```bash
git add agents/sec_edgar.py tests/test_sec_edgar.py
git commit -m "refactor: extract shared 10-Q/10-K candidate collection, add find_prior_10q_or_10k"
```

---

## Task 5: `find_prior_8k_item202`

**Files:**
- Modify: `agents/sec_edgar.py`
- Modify: `tests/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sec_edgar.py`:
```python
from agents.sec_edgar import find_prior_8k_item202


def test_find_prior_8k_item202_excludes_given_accession():
    fixture = {
        "filings": {
            "recent": {
                "form": ["8-K", "8-K"],
                "filingDate": ["2026-09-02", "2026-06-01"],
                "reportDate": ["2026-09-02", "2026-06-01"],
                "accessionNumber": ["0001640147-26-000033", "0001640147-26-000019"],
                "items": ["2.02,9.01", "2.02,9.01"],
                "primaryDocument": ["snow-20260902.htm", "snow-20260601.htm"],
            }
        }
    }

    result = find_prior_8k_item202(fixture, exclude_accession="0001640147-26-000033")

    assert result["accessionNumber"] == "0001640147-26-000019"


def test_find_prior_8k_item202_returns_none_when_only_excluded_one_exists():
    result = find_prior_8k_item202(SUBMISSIONS_FIXTURE, exclude_accession="0001640147-26-000033")

    assert result is None


def test_find_prior_8k_item202_with_no_exclusion_returns_latest():
    result = find_prior_8k_item202(SUBMISSIONS_FIXTURE)

    assert result["accessionNumber"] == "0001640147-26-000033"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_prior_8k_item202'`

- [ ] **Step 3: Refactor and add the new function**

Replace this section of `agents/sec_edgar.py`:
```python
def find_latest_8k_item202(submissions: dict) -> dict | None:
    recent = submissions["filings"]["recent"]
    candidates = []
    for i, form in enumerate(recent["form"]):
        items = recent["items"][i].split(",") if recent["items"][i] else []
        if form == "8-K" and "2.02" in items:
            candidates.append(
                {
                    "form": form,
                    "filingDate": recent["filingDate"][i],
                    "reportDate": recent["reportDate"][i],
                    "accessionNumber": recent["accessionNumber"][i],
                    "primaryDocument": recent["primaryDocument"][i],
                }
            )

    if not candidates:
        return None

    candidates.sort(key=lambda c: c["filingDate"], reverse=True)
    return candidates[0]
```

with:
```python
def _collect_8k_item202_candidates(submissions: dict) -> list[dict]:
    recent = submissions["filings"]["recent"]
    candidates = []
    for i, form in enumerate(recent["form"]):
        items = recent["items"][i].split(",") if recent["items"][i] else []
        if form == "8-K" and "2.02" in items:
            candidates.append(
                {
                    "form": form,
                    "filingDate": recent["filingDate"][i],
                    "reportDate": recent["reportDate"][i],
                    "accessionNumber": recent["accessionNumber"][i],
                    "primaryDocument": recent["primaryDocument"][i],
                }
            )

    candidates.sort(key=lambda c: c["filingDate"], reverse=True)
    return candidates


def find_latest_8k_item202(submissions: dict) -> dict | None:
    candidates = _collect_8k_item202_candidates(submissions)

    if not candidates:
        return None

    return candidates[0]


def find_prior_8k_item202(submissions: dict, exclude_accession: str | None = None) -> dict | None:
    candidates = _collect_8k_item202_candidates(submissions)
    remaining = [c for c in candidates if c["accessionNumber"] != exclude_accession]

    if not remaining:
        return None

    return remaining[0]
```

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: all pass (32 total)

- [ ] **Step 5: Commit**

```bash
git add agents/sec_edgar.py tests/test_sec_edgar.py
git commit -m "refactor: extract shared 8-K Item 2.02 candidate collection, add find_prior_8k_item202"
```

---

## Task 6: Claude extraction — `extract_period_data`

**Files:**
- Create: `agents/claude_extraction.py`
- Create: `tests/test_claude_extraction.py`

- [ ] **Step 1: Write the failing test**

`tests/test_claude_extraction.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_claude_extraction.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.claude_extraction'`

- [ ] **Step 3: Write minimal implementation**

`agents/claude_extraction.py`:
```python
from anthropic import Anthropic

EXTRACTION_TOOL = {
    "name": "record_period_extraction",
    "description": (
        "Record structured financial and operating data extracted from the "
        "provided company documents for one reporting period."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "revenue": {"type": ["number", "null"]},
            "revenue_yoy_growth_pct": {"type": ["number", "null"]},
            "gross_margin_gaap_pct": {"type": ["number", "null"]},
            "gross_margin_non_gaap_pct": {"type": ["number", "null"]},
            "operating_margin_gaap_pct": {"type": ["number", "null"]},
            "operating_margin_non_gaap_pct": {"type": ["number", "null"]},
            "net_income_gaap": {"type": ["number", "null"]},
            "net_income_non_gaap": {"type": ["number", "null"]},
            "eps_gaap": {"type": ["number", "null"]},
            "eps_non_gaap": {"type": ["number", "null"]},
            "operating_cash_flow": {"type": ["number", "null"]},
            "free_cash_flow": {"type": ["number", "null"]},
            "deferred_revenue_balance": {"type": ["number", "null"]},
            "segment_revenues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_name": {"type": "string"},
                        "revenue": {"type": "number"},
                        "yoy_growth_pct": {"type": ["number", "null"]},
                    },
                    "required": ["segment_name", "revenue"],
                },
            },
            "guidance": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "period": {"type": "string", "enum": ["next_quarter", "next_year"]},
                        "metric_name": {"type": "string"},
                        "low": {"type": ["number", "null"]},
                        "high": {"type": ["number", "null"]},
                        "source": {"type": "string", "enum": ["press_release", "call"]},
                        "source_quote": {"type": "string"},
                    },
                    "required": ["period", "metric_name", "source", "source_quote"],
                },
            },
            "disclosed_kpis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": "string"},
                        "unit": {"type": ["string", "null"]},
                        "period": {"type": ["string", "null"]},
                        "yoy_change": {"type": ["string", "null"]},
                        "source_quote": {"type": "string"},
                    },
                    "required": ["name", "value", "source_quote"],
                },
            },
            "risk_factors_text": {"type": "string"},
            "guidance_text": {"type": "string"},
            "unavailable": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "revenue",
            "gross_margin_gaap_pct",
            "operating_margin_gaap_pct",
            "operating_cash_flow",
            "free_cash_flow",
            "deferred_revenue_balance",
            "segment_revenues",
            "guidance",
            "disclosed_kpis",
            "risk_factors_text",
            "guidance_text",
            "unavailable",
        ],
    },
}

EXTRACTION_PROMPT_TEMPLATE = """You are extracting structured financial and operating data from the \
company documents below for one reporting period. Read them carefully and call \
record_period_extraction with what you find.

Rules:
- Only report figures and metrics that are actually disclosed in the text. If a \
standard field (revenue, margins, cash flow, guidance) is not disclosed, leave it \
null and add a short note to "unavailable" -- never estimate or infer a number \
that isn't stated.
- For disclosed_kpis, report EVERY operating/business metric management chose to \
disclose and name for this company, using their own terminology and units. Common \
categories to watch for (not an exhaustive or required list): retention/churn, \
volume (bookings, GMV, transactions, units), engagement (DAU/MAU), pricing \
(ARPU, ASP, take rate), backlog (RPO, remaining performance obligations). Report \
whatever this specific company discloses, even if it's not in this list.
- For every guidance range and every disclosed_kpi, include the exact source \
quote it came from.
- risk_factors_text and guidance_text should be the verbatim relevant passages \
(or the filing's own statement that there were no material changes), not a \
paraphrase.

=== DOCUMENTS ===

{documents}
"""


def _build_prompt(docs: dict[str, str]) -> str:
    sections = []
    if "filing" in docs:
        sections.append(f"=== FILING (10-Q/10-K) ===\n{docs['filing']}")
    if "press_release" in docs:
        sections.append(f"=== PRESS RELEASE (8-K Exhibit 99.1) ===\n{docs['press_release']}")
    if "transcript" in docs:
        sections.append(f"=== EARNINGS CALL TRANSCRIPT ===\n{docs['transcript']}")
    return EXTRACTION_PROMPT_TEMPLATE.format(documents="\n\n".join(sections))


def extract_period_data(docs: dict[str, str], model: str = "claude-sonnet-5") -> dict:
    client = Anthropic()
    prompt = _build_prompt(docs)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_period_extraction"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise RuntimeError("Claude did not return a tool_use block for record_period_extraction")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_claude_extraction.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/claude_extraction.py tests/test_claude_extraction.py
git commit -m "feat: add Claude-based period extraction with sector-generic KPI schema"
```

---

## Task 7: Claude extraction — `diff_language`

**Files:**
- Modify: `agents/claude_extraction.py`
- Modify: `tests/test_claude_extraction.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_claude_extraction.py`:
```python
from agents.claude_extraction import diff_language


FAKE_DIFF = {
    "changes_summary": "Added a new risk factor about AI regulation.",
    "material_change": True,
}


@patch("agents.claude_extraction.Anthropic")
def test_diff_language_returns_tool_input(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_response(FAKE_DIFF)
    mock_anthropic_cls.return_value = mock_client

    result = diff_language("current text", "prior text", "risk factors")

    assert result == FAKE_DIFF
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "record_language_diff"}
    prompt_sent = call_kwargs["messages"][0]["content"]
    assert "current text" in prompt_sent
    assert "prior text" in prompt_sent
    assert "risk factors" in prompt_sent


@patch("agents.claude_extraction.Anthropic")
def test_diff_language_uses_given_model(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_response(FAKE_DIFF)
    mock_anthropic_cls.return_value = mock_client

    diff_language("current", "prior", "guidance", model="claude-sonnet-5")

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-5"


@patch("agents.claude_extraction.Anthropic")
def test_diff_language_raises_when_no_tool_use_block(mock_anthropic_cls):
    mock_client = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    response = MagicMock()
    response.content = [text_block]
    mock_client.messages.create.return_value = response
    mock_anthropic_cls.return_value = mock_client

    try:
        diff_language("current", "prior", "risk factors")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "tool_use" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_claude_extraction.py -v`
Expected: FAIL with `ImportError: cannot import name 'diff_language'`

- [ ] **Step 3: Write minimal implementation**

Append to `agents/claude_extraction.py`:
```python
DIFF_TOOL = {
    "name": "record_language_diff",
    "description": "Record a summary of what changed between two versions of the same disclosure text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "changes_summary": {"type": "string"},
            "material_change": {"type": "boolean"},
        },
        "required": ["changes_summary", "material_change"],
    },
}

DIFF_PROMPT_TEMPLATE = """Compare the CURRENT and PRIOR versions of this company's {field_label} \
below and summarize what changed in a few bullet points. Judge whether the change is \
material (a substantive addition, removal, or shift in tone/emphasis) or immaterial \
(wording-only, no real change). If the two texts are identical or nearly so, say so \
plainly and set material_change to false.

=== CURRENT ===
{current_text}

=== PRIOR ===
{prior_text}
"""


def diff_language(
    current_text: str,
    prior_text: str,
    field_label: str,
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    client = Anthropic()
    prompt = DIFF_PROMPT_TEMPLATE.format(
        field_label=field_label, current_text=current_text, prior_text=prior_text
    )

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[DIFF_TOOL],
        tool_choice={"type": "tool", "name": "record_language_diff"},
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    raise RuntimeError("Claude did not return a tool_use block for record_language_diff")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_claude_extraction.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/claude_extraction.py tests/test_claude_extraction.py
git commit -m "feat: add Claude-based risk-factor/guidance language diffing"
```

---

## Task 8: Extraction agent — read M1's saved current-period files

**Files:**
- Create: `agents/extraction_agent.py` (file-reading helpers only in this task; Task 9 adds orchestration)
- Create: `tests/test_extraction_agent.py`

- [ ] **Step 1: Write the failing test**

`tests/test_extraction_agent.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extraction_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.extraction_agent'`

- [ ] **Step 3: Write minimal implementation**

`agents/extraction_agent.py`:
```python
import json
from pathlib import Path

from agents.html_text import strip_html_to_text


def _latest_non_prior_match(data_dir: Path, pattern: str) -> Path | None:
    matches = [p for p in sorted(data_dir.glob(pattern)) if "_PRIOR_" not in p.name]
    if not matches:
        return None
    return matches[-1]


def read_current_filing_text(data_dir: Path, ticker: str) -> str:
    match = _latest_non_prior_match(data_dir, f"{ticker.upper()}_10-*.htm")
    if match is None:
        raise FileNotFoundError(
            f"No current-period 10-Q/10-K found in {data_dir} -- run the retrieval agent (M1) first."
        )
    return strip_html_to_text(match.read_text(encoding="utf-8"))


def read_current_press_release_text(data_dir: Path, ticker: str) -> str | None:
    match = _latest_non_prior_match(data_dir, f"{ticker.upper()}_8K_EX99.1_*.htm")
    if match is None:
        return None
    return strip_html_to_text(match.read_text(encoding="utf-8"))


def read_current_transcript_text(data_dir: Path, ticker: str) -> str | None:
    matches = sorted(data_dir.glob(f"{ticker.upper()}_transcript_*.json"))
    if not matches:
        return None
    transcript = json.loads(matches[-1].read_text(encoding="utf-8"))
    return transcript.get("transcript")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extraction_agent.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/extraction_agent.py tests/test_extraction_agent.py
git commit -m "feat: read M1's saved current-period files for extraction"
```

---

## Task 9: Extraction agent — `run()` orchestration

**Files:**
- Modify: `agents/extraction_agent.py`
- Modify: `tests/test_extraction_agent.py`

- [ ] **Step 1: Write the failing end-to-end test**

Append to `tests/test_extraction_agent.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extraction_agent.py -v`
Expected: FAIL with `ImportError: cannot import name 'run'`

- [ ] **Step 3: Write the implementation**

Append to `agents/extraction_agent.py` (add these imports at the top of the file, above the existing `import json` / `from pathlib import Path` / `from agents.html_text import strip_html_to_text` lines):
```python
from agents.config import load_config, get_data_dir
from agents.sec_edgar import (
    get_cik_for_ticker,
    get_submissions,
    find_latest_10q_or_10k,
    find_latest_8k_item202,
    find_prior_10q_or_10k,
    find_prior_8k_item202,
    get_filing_index_html,
    find_exhibit_991_filename,
    download_document,
)
from agents.claude_extraction import extract_period_data, diff_language
from agents.derived_metrics import compute_billings
```

Then append this to the end of `agents/extraction_agent.py`:
```python
def _fetch_and_save_prior_filing(
    cik: int, prior_filing: dict, ticker: str, data_dir: Path, user_agent: str
) -> str:
    text = download_document(cik, prior_filing["accessionNumber"], prior_filing["primaryDocument"], user_agent)
    path = data_dir / f"{ticker.upper()}_{prior_filing['form']}_PRIOR_{prior_filing['filingDate']}.htm"
    path.write_text(text, encoding="utf-8")
    return strip_html_to_text(text)


def _fetch_and_save_prior_exhibit(
    cik: int, prior_8k: dict, ticker: str, data_dir: Path, user_agent: str
) -> str | None:
    index_html = get_filing_index_html(cik, prior_8k["accessionNumber"], user_agent)
    exhibit_filename = find_exhibit_991_filename(index_html)
    if exhibit_filename is None:
        return None
    text = download_document(cik, prior_8k["accessionNumber"], exhibit_filename, user_agent)
    path = data_dir / f"{ticker.upper()}_8K_EX99.1_PRIOR_{prior_8k['filingDate']}.htm"
    path.write_text(text, encoding="utf-8")
    return strip_html_to_text(text)


def run(
    ticker: str,
    base_dir: str = "data",
    extraction_model: str = "claude-sonnet-5",
    diff_model: str = "claude-haiku-4-5-20251001",
) -> dict:
    config = load_config()
    data_dir = get_data_dir(ticker, base_dir)

    current_docs = {"filing": read_current_filing_text(data_dir, ticker)}
    press_release_text = read_current_press_release_text(data_dir, ticker)
    if press_release_text is not None:
        current_docs["press_release"] = press_release_text
    transcript_text = read_current_transcript_text(data_dir, ticker)
    if transcript_text is not None:
        current_docs["transcript"] = transcript_text

    current_period = extract_period_data(current_docs, model=extraction_model)

    cik = get_cik_for_ticker(ticker, config.sec_user_agent)
    submissions = get_submissions(cik, config.sec_user_agent)
    current_filing = find_latest_10q_or_10k(submissions)
    current_8k = find_latest_8k_item202(submissions)

    prior_filing = find_prior_10q_or_10k(submissions, current_filing["accessionNumber"])
    prior_8k_exclude = current_8k["accessionNumber"] if current_8k is not None else None
    prior_8k = find_prior_8k_item202(submissions, prior_8k_exclude)

    prior_period = None
    billings = None
    diffs = {"risk_factors": None, "guidance_language": None}

    if prior_filing is not None:
        prior_docs = {
            "filing": _fetch_and_save_prior_filing(cik, prior_filing, ticker, data_dir, config.sec_user_agent)
        }
        if prior_8k is not None:
            prior_press_release_text = _fetch_and_save_prior_exhibit(
                cik, prior_8k, ticker, data_dir, config.sec_user_agent
            )
            if prior_press_release_text is not None:
                prior_docs["press_release"] = prior_press_release_text

        prior_period = extract_period_data(prior_docs, model=extraction_model)
        billings = compute_billings(current_period, prior_period)
        diffs["risk_factors"] = diff_language(
            current_period["risk_factors_text"], prior_period["risk_factors_text"], "risk factors", model=diff_model
        )
        diffs["guidance_language"] = diff_language(
            current_period["guidance_text"], prior_period["guidance_text"], "guidance", model=diff_model
        )

    result = {
        "ticker": ticker.upper(),
        "current_period": current_period,
        "prior_period": prior_period,
        "billings": billings,
        "diffs": diffs,
    }

    output_path = data_dir / "extracted.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extraction_agent.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass, zero real network/API calls

- [ ] **Step 6: Commit**

```bash
git add agents/extraction_agent.py tests/test_extraction_agent.py
git commit -m "feat: wire up extraction agent orchestration"
```

---

## Task 10: Extraction agent CLI, live smoke test, and docs update

**Files:**
- Modify: `agents/extraction_agent.py`
- Modify: `README.md`

- [ ] **Step 1: Add the CLI**

Append to `agents/extraction_agent.py`:
```python
import argparse


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract structured financial and operating data for a ticker from M1's saved raw documents."
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker, e.g. SNOW")
    parser.add_argument("--data-dir", default="data", help="Base directory where M1 saved raw documents")
    parser.add_argument(
        "--extraction-model", default="claude-sonnet-5", help="Model for the main period-extraction calls"
    )
    parser.add_argument(
        "--diff-model",
        default="claude-haiku-4-5-20251001",
        help="Model for the risk-factor/guidance language diff calls",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    result = run(args.ticker, args.data_dir, args.extraction_model, args.diff_model)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
```

(Note: move the `import argparse` line to the top of the file alongside the other imports rather than leaving it mid-file — group all imports together.)

- [ ] **Step 2: Run the full test suite**

Run: `pytest -v`
Expected: all tests still pass (the CLI wrapper isn't itself unit-tested — `run()` already is — this just confirms nothing broke)

- [ ] **Step 3: Ensure `.env` has `ANTHROPIC_API_KEY` set**

Confirm a real key from https://console.anthropic.com/settings/keys is in your local `.env` (gitignored).

- [ ] **Step 4: Run the retrieval agent again to refresh current-period files, then run extraction**

```bash
python -m agents.retrieval_agent --ticker SNOW
python -m agents.extraction_agent --ticker SNOW
```

Expected: no unhandled exceptions; prints the extracted JSON; `data/SNOW/extracted.json` is created; `data/SNOW/` also gains `SNOW_10-Q_PRIOR_*.htm` (or `10-K`) and, if a prior earnings 8-K exists, `SNOW_8K_EX99.1_PRIOR_*.htm`.

- [ ] **Step 5: Manually inspect `data/SNOW/extracted.json`**

Confirm: `current_period.revenue` and margins look like real SNOW figures (sanity-check against the press release), `disclosed_kpis` contains metrics SNOW actually reports (e.g. RPO, NRR) named in SNOW's own terminology (not a fixed generic catalog), `billings` is either a populated object or `null` (never a guessed number), and `diffs.risk_factors`/`diffs.guidance_language` read as sensible summaries.

- [ ] **Step 6: Fix forward if the live run reveals a real issue**

If Claude's tool-use response is missing an expected field, or a document type genuinely can't be found in `data/SNOW/` (e.g., no prior 8-K exists because the company is newly public), that's an M2-acceptable outcome to record and note — not a reason to guess a value. Only fix code for things that are actually broken (e.g., a URL/parsing bug), not to force a response shape you expected but didn't get.

- [ ] **Step 7: Update README status**

Update `README.md`'s status line and add an M2 usage section, e.g.:
```
Status: **M2 complete** — extraction agent turns M1's raw documents
into structured, cited financial and operating data (sector-generic,
not SaaS-specific); analysis and note generation come next.
```

Add a new "## Usage (M2)" section documenting:
```bash
python -m agents.extraction_agent --ticker SNOW
```
Saves `data/SNOW/extracted.json` and prints it. Requires `data/SNOW/`
to already contain M1's output (run the retrieval agent first) and
`ANTHROPIC_API_KEY` set in `.env`.

- [ ] **Step 8: Update CLAUDE.md's Extraction Agent bullet**

In `CLAUDE.md`, find this bullet under `[2. Extraction Agent]`:
```
   - SaaS metrics computed only where actually disclosed: billings
     (revenue + change in deferred revenue), RPO, YoY growth by
     segment. Anything NOT disclosed (e.g. many companies don't
     report ARR/NRR directly) is flagged as unavailable, never
     estimated.
```

Replace it with:
```
   - Sector-generic operating metrics, not a fixed SaaS catalog:
     the agent reports whatever KPIs the company itself discloses
     and names (GMV/take rate, DAU/MAU/ARPU, Gross Bookings, RPO/NRR,
     same-store sales, units/ASP, etc.), never a predefined list.
     Billings (revenue + change in deferred revenue) is the one
     exception -- a deterministically computed field, attempted
     whenever both periods' deferred-revenue balances were disclosed,
     regardless of sector. Anything not disclosed is flagged as
     unavailable, never estimated.
```

This keeps CLAUDE.md's Extraction Agent description in sync with the
approved design (`docs/superpowers/specs/2026-09-04-extraction-agent-m2-design.md`),
after the user explicitly rejected limiting operating metrics to SaaS.

- [ ] **Step 9: Commit**

```bash
git add agents/extraction_agent.py README.md CLAUDE.md
git commit -m "feat: add extraction agent CLI; docs: mark M2 complete, generalize CLAUDE.md metrics wording"
```
