# M1 Retrieval Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Given a ticker (SNOW first), fetch and save the latest 10-Q/10-K, the latest 8-K's Exhibit 99.1 press release, the latest earnings call transcript, and Alpha Vantage EPS consensus/surprise data to `data/{TICKER}/`, then print a freshness pass/fail report for each document.

**Architecture:** One `agents/` package with a thin module per data source (`sec_edgar.py`, `api_ninjas.py`, `alpha_vantage.py`), a pure `freshness.py` for the age check, a `config.py` for env/paths, and `retrieval_agent.py` as the CLI entrypoint that wires them together. Each network-calling function is a small, separately testable unit; HTTP calls are mocked in tests via `unittest.mock.patch`, so the test suite makes zero real network calls.

**Tech Stack:** Python 3, `requests`, `python-dotenv`, `pytest` (dev only). No new runtime dependencies beyond what's already in `requirements.txt`.

**Confirmed API details (verified live against SEC EDGAR on 2026-09-04, and against provider docs):**
- SEC `company_tickers.json` is `{"0": {"cik_str": 1640147, "ticker": "SNOW", "title": "Snowflake Inc."}, ...}` — `cik_str` is an unpadded int.
- SEC submissions JSON (`data.sec.gov/submissions/CIK{cik:010d}.json`) has `filings.recent` as parallel arrays including `form`, `filingDate`, `reportDate`, `accessionNumber`, `primaryDocument`, and `items` (comma-joined string, e.g. `"2.02,9.01"` for 8-Ks; empty string for non-8-Ks).
- The 8-K's Exhibit 99.1 filename is NOT in `index.json` (that only has generic MIME-icon types). It must be scraped from the human-readable `{accession}-index.htm` page's "Document Format Files" table, where the row whose Type cell is `EX-99.1` has an `<a href="...">` to the actual file.
- API Ninjas transcript endpoint is `https://api.api-ninjas.com/v1/earningstranscript` (note: not `earningscalltranscript` — that's just the docs page slug), header `X-Api-Key`, params `ticker` (required), `year`/`quarter` (optional), response field `date` for the call date.
- Alpha Vantage: `https://www.alphavantage.co/query?function=EARNINGS&symbol=X&apikey=Y`, response has `quarterlyEarnings` array (most recent first) with `fiscalDateEnding`, `reportedDate`, `reportedEPS`, `estimatedEPS`, `surprise`, `surprisePercentage`.

---

## Task 1: Project scaffolding, git init, and config module

**Files:**
- Create: `agents/__init__.py`
- Create: `agents/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`
- Create: `requirements-dev.txt`
- Modify: `.gitignore` (already created this session — verify it excludes `.env`, `__pycache__/`, `.pytest_cache/`, `data/`)

- [ ] **Step 1: Initialize git and make the first commit**

The project directory is not yet a git repository. Initialize it and commit the existing files (CLAUDE.md, README.md, requirements.txt, .env.example, .gitignore) before writing any code.

```bash
git init
git add CLAUDE.md README.md requirements.txt .env.example .gitignore
git commit -m "chore: initial project files"
```

- [ ] **Step 2: Create package `__init__.py` files**

`agents/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

- [ ] **Step 3: Add pytest as a dev dependency**

`requirements-dev.txt`:
```
-r requirements.txt
pytest>=7.4.0
```

- [ ] **Step 4: Write the failing test for config**

`tests/test_config.py`:
```python
import pytest

from agents.config import load_config, get_data_dir


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


def test_load_config_raises_on_missing_var(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("API_NINJAS_KEY", raising=False)
    monkeypatch.delenv("ALPHA_VANTAGE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SEC_USER_AGENT"):
        load_config()


def test_get_data_dir_creates_directory(tmp_path):
    data_dir = get_data_dir("snow", base_dir=str(tmp_path))

    assert data_dir == tmp_path / "SNOW"
    assert data_dir.is_dir()
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.config'` (or ImportError)

- [ ] **Step 6: Write minimal implementation**

`agents/config.py`:
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


def load_config() -> Config:
    # find_dotenv(usecwd=True): search for .env starting from the current working
    # directory, not from this module's file location (the default when no path is
    # given), so tests that chdir into a tmp_path see only their own fixture .env.
    # NOTE: load_dotenv() itself has no usecwd kwarg in this installed version of
    # python-dotenv -- usecwd belongs to find_dotenv(). Verified live during Task 1.
    load_dotenv(find_dotenv(usecwd=True))
    sec_user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    api_ninjas_key = os.environ.get("API_NINJAS_KEY", "").strip()
    alpha_vantage_key = os.environ.get("ALPHA_VANTAGE_KEY", "").strip()

    missing = [
        name
        for name, value in [
            ("SEC_USER_AGENT", sec_user_agent),
            ("API_NINJAS_KEY", api_ninjas_key),
            ("ALPHA_VANTAGE_KEY", alpha_vantage_key),
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
    )


def get_data_dir(ticker: str, base_dir: str = "data") -> Path:
    data_dir = Path(base_dir) / ticker.upper()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 8: Commit**

```bash
git add agents/__init__.py agents/config.py tests/__init__.py tests/test_config.py requirements-dev.txt
git commit -m "feat: add config loading and data dir helper"
```

---

## Task 2: SEC ticker-to-CIK resolution

**Files:**
- Create: `agents/sec_edgar.py`
- Create: `tests/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

`tests/test_sec_edgar.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.sec_edgar'`

- [ ] **Step 3: Write minimal implementation**

`agents/sec_edgar.py`:
```python
import requests

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def _sec_headers(user_agent: str) -> dict:
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}


def get_cik_for_ticker(ticker: str, user_agent: str) -> int:
    response = requests.get(COMPANY_TICKERS_URL, headers=_sec_headers(user_agent), timeout=30)
    response.raise_for_status()
    data = response.json()

    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry["ticker"] == ticker_upper:
            return entry["cik_str"]

    raise ValueError(f"Ticker {ticker_upper!r} not found in SEC company_tickers.json")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/sec_edgar.py tests/test_sec_edgar.py
git commit -m "feat: add SEC ticker-to-CIK resolution"
```

---

## Task 3: SEC submissions fetch

**Files:**
- Modify: `agents/sec_edgar.py`
- Modify: `tests/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sec_edgar.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_submissions'`

- [ ] **Step 3: Write minimal implementation**

Append to `agents/sec_edgar.py`:
```python
SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


def get_submissions(cik: int, user_agent: str) -> dict:
    url = SUBMISSIONS_URL_TEMPLATE.format(cik=cik)
    response = requests.get(url, headers=_sec_headers(user_agent), timeout=30)
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/sec_edgar.py tests/test_sec_edgar.py
git commit -m "feat: add SEC submissions fetch"
```

---

## Task 4: Latest 10-Q/10-K selection logic

**Files:**
- Modify: `agents/sec_edgar.py`
- Modify: `tests/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sec_edgar.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_latest_10q_or_10k'`

- [ ] **Step 3: Write minimal implementation**

Append to `agents/sec_edgar.py`:
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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/sec_edgar.py tests/test_sec_edgar.py
git commit -m "feat: add latest 10-Q/10-K selection logic"
```

---

## Task 5: Latest 8-K with Item 2.02 selection logic

**Files:**
- Modify: `agents/sec_edgar.py`
- Modify: `tests/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sec_edgar.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_latest_8k_item202'`

- [ ] **Step 3: Write minimal implementation**

Append to `agents/sec_edgar.py`:
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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/sec_edgar.py tests/test_sec_edgar.py
git commit -m "feat: add latest 8-K Item 2.02 selection logic"
```

---

## Task 6: Exhibit 99.1 filename extraction from the filing index page

**Files:**
- Modify: `agents/sec_edgar.py`
- Modify: `tests/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sec_edgar.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: FAIL with `ImportError: cannot import name 'find_exhibit_991_filename'`

- [ ] **Step 3: Write minimal implementation**

Add `import re` to the top of `agents/sec_edgar.py`, then append:
```python
def find_exhibit_991_filename(index_html: str) -> str | None:
    rows = re.split(r"<tr", index_html, flags=re.IGNORECASE)
    for row in rows[1:]:
        if re.search(r"EX-99\.1", row, flags=re.IGNORECASE):
            match = re.search(r'href="([^"]+)"', row)
            if match:
                return match.group(1).rsplit("/", 1)[-1]
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/sec_edgar.py tests/test_sec_edgar.py
git commit -m "feat: extract exhibit 99.1 filename from filing index page"
```

---

## Task 7: Filing index page fetch and document download

**Files:**
- Modify: `agents/sec_edgar.py`
- Modify: `tests/test_sec_edgar.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sec_edgar.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_filing_index_html'`

- [ ] **Step 3: Write minimal implementation**

Append to `agents/sec_edgar.py`:
```python
ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"


def get_filing_index_html(cik: int, accession_number: str, user_agent: str) -> str:
    accession_nodash = accession_number.replace("-", "")
    url = f"{ARCHIVES_BASE_URL}/{cik}/{accession_nodash}/{accession_number}-index.htm"
    response = requests.get(url, headers=_sec_headers(user_agent), timeout=30)
    response.raise_for_status()
    return response.text


def download_document(cik: int, accession_number: str, filename: str, user_agent: str) -> str:
    accession_nodash = accession_number.replace("-", "")
    url = f"{ARCHIVES_BASE_URL}/{cik}/{accession_nodash}/{filename}"
    response = requests.get(url, headers=_sec_headers(user_agent), timeout=30)
    response.raise_for_status()
    return response.text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_sec_edgar.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/sec_edgar.py tests/test_sec_edgar.py
git commit -m "feat: add filing index and document download fetches"
```

---

## Task 8: Freshness check

**Files:**
- Create: `agents/freshness.py`
- Create: `tests/test_freshness.py`

- [ ] **Step 1: Write the failing test**

`tests/test_freshness.py`:
```python
from datetime import date

from agents.freshness import check_freshness


def test_check_freshness_passes_within_window():
    result = check_freshness(date(2026, 8, 1), date(2026, 9, 4), max_age_days=95)

    assert result["document_date"] == "2026-08-01"
    assert result["age_days"] == 34
    assert result["is_fresh"] is True


def test_check_freshness_fails_outside_window():
    result = check_freshness(date(2025, 1, 1), date(2026, 9, 4), max_age_days=95)

    assert result["is_fresh"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_freshness.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.freshness'`

- [ ] **Step 3: Write minimal implementation**

`agents/freshness.py`:
```python
from datetime import date


def check_freshness(document_date: date, today: date, max_age_days: int = 95) -> dict:
    age_days = (today - document_date).days
    return {
        "document_date": document_date.isoformat(),
        "age_days": age_days,
        "is_fresh": age_days <= max_age_days,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_freshness.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/freshness.py tests/test_freshness.py
git commit -m "feat: add freshness check"
```

---

## Task 9: API Ninjas transcript fetch

**Files:**
- Create: `agents/api_ninjas.py`
- Create: `tests/test_api_ninjas.py`

- [ ] **Step 1: Write the failing test**

`tests/test_api_ninjas.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_ninjas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.api_ninjas'`

- [ ] **Step 3: Write minimal implementation**

`agents/api_ninjas.py`:
```python
import requests

TRANSCRIPT_URL = "https://api.api-ninjas.com/v1/earningstranscript"


def get_transcript(ticker: str, api_key: str, year: int | None = None, quarter: int | None = None) -> dict:
    params = {"ticker": ticker.upper()}
    if year is not None:
        params["year"] = year
    if quarter is not None:
        params["quarter"] = quarter

    response = requests.get(TRANSCRIPT_URL, headers={"X-Api-Key": api_key}, params=params, timeout=30)
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_ninjas.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/api_ninjas.py tests/test_api_ninjas.py
git commit -m "feat: add API Ninjas transcript fetch"
```

---

## Task 10: Alpha Vantage earnings fetch

**Files:**
- Create: `agents/alpha_vantage.py`
- Create: `tests/test_alpha_vantage.py`

- [ ] **Step 1: Write the failing test**

`tests/test_alpha_vantage.py`:
```python
from unittest.mock import Mock, patch

from agents.alpha_vantage import get_earnings, get_latest_quarterly_earnings


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alpha_vantage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.alpha_vantage'`

- [ ] **Step 3: Write minimal implementation**

`agents/alpha_vantage.py`:
```python
import requests

EARNINGS_URL = "https://www.alphavantage.co/query"


def get_earnings(ticker: str, api_key: str) -> dict:
    params = {"function": "EARNINGS", "symbol": ticker.upper(), "apikey": api_key}
    response = requests.get(EARNINGS_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_latest_quarterly_earnings(earnings_response: dict) -> dict | None:
    quarterly = earnings_response.get("quarterlyEarnings", [])
    if not quarterly:
        return None
    return quarterly[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alpha_vantage.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/alpha_vantage.py tests/test_alpha_vantage.py
git commit -m "feat: add Alpha Vantage earnings fetch"
```

---

## Task 11: Fiscal year/quarter derivation helper

**Files:**
- Create: `agents/retrieval_agent.py` (helper function only in this task; CLI orchestration comes in Task 12)
- Create: `tests/test_retrieval_agent.py`

- [ ] **Step 1: Write the failing test**

`tests/test_retrieval_agent.py`:
```python
from datetime import date

from agents.retrieval_agent import derive_year_quarter


def test_derive_year_quarter_q3_boundary():
    assert derive_year_quarter(date(2026, 7, 31)) == (2026, 3)


def test_derive_year_quarter_q1():
    assert derive_year_quarter(date(2026, 2, 15)) == (2026, 1)


def test_derive_year_quarter_q4():
    assert derive_year_quarter(date(2025, 12, 31)) == (2025, 4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retrieval_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.retrieval_agent'`

- [ ] **Step 3: Write minimal implementation**

`agents/retrieval_agent.py`:
```python
from datetime import date


def derive_year_quarter(report_date: date) -> tuple[int, int]:
    quarter = (report_date.month - 1) // 3 + 1
    return report_date.year, quarter
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_retrieval_agent.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/retrieval_agent.py tests/test_retrieval_agent.py
git commit -m "feat: add fiscal year/quarter derivation helper"
```

---

## Task 12: CLI orchestration (`run`, `main`) and end-to-end mocked test

**Files:**
- Modify: `agents/retrieval_agent.py`
- Modify: `tests/test_retrieval_agent.py`

- [ ] **Step 1: Write the failing end-to-end test**

Append to `tests/test_retrieval_agent.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retrieval_agent.py -v`
Expected: FAIL with `ImportError: cannot import name 'run'`

- [ ] **Step 3: Write minimal implementation**

Replace the full contents of `agents/retrieval_agent.py` with:
```python
import argparse
import json
from datetime import date, datetime

from agents.config import load_config, get_data_dir
from agents.sec_edgar import (
    get_cik_for_ticker,
    get_submissions,
    find_latest_10q_or_10k,
    find_latest_8k_item202,
    get_filing_index_html,
    find_exhibit_991_filename,
    download_document,
)
from agents.api_ninjas import get_transcript
from agents.alpha_vantage import get_earnings, get_latest_quarterly_earnings
from agents.freshness import check_freshness


def derive_year_quarter(report_date: date) -> tuple[int, int]:
    quarter = (report_date.month - 1) // 3 + 1
    return report_date.year, quarter


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def run(ticker: str, base_dir: str = "data", max_age_days: int = 95) -> list[dict]:
    config = load_config()
    data_dir = get_data_dir(ticker, base_dir)
    today = date.today()
    freshness_report = []

    cik = get_cik_for_ticker(ticker, config.sec_user_agent)
    submissions = get_submissions(cik, config.sec_user_agent)

    filing = find_latest_10q_or_10k(submissions)
    filing_text = download_document(cik, filing["accessionNumber"], filing["primaryDocument"], config.sec_user_agent)
    filing_path = data_dir / f"{ticker.upper()}_{filing['form']}_{filing['filingDate']}.htm"
    filing_path.write_text(filing_text, encoding="utf-8")
    freshness_report.append(
        {"document": filing_path.name, **check_freshness(_parse_date(filing["filingDate"]), today, max_age_days)}
    )

    eightk = find_latest_8k_item202(submissions)
    if eightk is not None:
        index_html = get_filing_index_html(cik, eightk["accessionNumber"], config.sec_user_agent)
        exhibit_filename = find_exhibit_991_filename(index_html)
        if exhibit_filename is not None:
            exhibit_text = download_document(cik, eightk["accessionNumber"], exhibit_filename, config.sec_user_agent)
            exhibit_path = data_dir / f"{ticker.upper()}_8K_EX99.1_{eightk['filingDate']}.htm"
            exhibit_path.write_text(exhibit_text, encoding="utf-8")
            freshness_report.append(
                {
                    "document": exhibit_path.name,
                    **check_freshness(_parse_date(eightk["filingDate"]), today, max_age_days),
                }
            )

    report_date = _parse_date(filing["reportDate"])
    year, quarter = derive_year_quarter(report_date)
    transcript = get_transcript(ticker, config.api_ninjas_key, year=year, quarter=quarter)
    transcript_path = data_dir / f"{ticker.upper()}_transcript_{year}Q{quarter}.json"
    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    transcript_date_str = transcript.get("date")
    if isinstance(transcript_date_str, str):
        freshness_report.append(
            {"document": transcript_path.name, **check_freshness(_parse_date(transcript_date_str), today, max_age_days)}
        )

    earnings = get_earnings(ticker, config.alpha_vantage_key)
    earnings_path = data_dir / f"{ticker.upper()}_earnings_alphavantage.json"
    earnings_path.write_text(json.dumps(earnings, indent=2), encoding="utf-8")
    latest_quarter = get_latest_quarterly_earnings(earnings)
    if latest_quarter is not None and latest_quarter.get("reportedDate"):
        freshness_report.append(
            {
                "document": earnings_path.name,
                **check_freshness(_parse_date(latest_quarter["reportedDate"]), today, max_age_days),
            }
        )

    return freshness_report


def print_freshness_report(freshness_report: list[dict]) -> None:
    print(f"\n{'Document':<40} {'Date':<12} {'Age (days)':<12} {'Status'}")
    print("-" * 80)
    for entry in freshness_report:
        status = "PASS" if entry["is_fresh"] else "FAIL"
        print(f"{entry['document']:<40} {entry['document_date']:<12} {entry['age_days']:<12} {status}")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve latest SEC filings, earnings transcript, and EPS data for a ticker."
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker, e.g. SNOW")
    parser.add_argument("--data-dir", default="data", help="Base directory to save documents into")
    parser.add_argument("--max-age-days", type=int, default=95, help="Freshness threshold in days (~3 months)")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    freshness_report = run(args.ticker, args.data_dir, args.max_age_days)
    print_freshness_report(freshness_report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_retrieval_agent.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests across all modules PASS (~27 passed), zero real network calls made

- [ ] **Step 6: Commit**

```bash
git add agents/retrieval_agent.py tests/test_retrieval_agent.py
git commit -m "feat: wire up retrieval agent CLI orchestration"
```

---

## Task 13: Live smoke test against SNOW and final commit

**Files:** none created; this task exercises the real CLI against live APIs.

- [ ] **Step 1: Ensure `.env` has all three real values**

Confirm `SEC_USER_AGENT`, `API_NINJAS_KEY`, and `ALPHA_VANTAGE_KEY` are all filled in `.env` (not `.env.example`). If `API_NINJAS_KEY` is still blank, get a free key from https://api-ninjas.com and add it before this step.

- [ ] **Step 2: Install dependencies**

```bash
pip install -r requirements-dev.txt
```

- [ ] **Step 3: Run the retrieval agent against SNOW**

```bash
python -m agents.retrieval_agent --ticker SNOW
```

Expected: no unhandled exceptions; a freshness report table prints to stdout; `data/SNOW/` contains four files (10-Q or 10-K htm, 8-K exhibit htm, transcript json, earnings json).

- [ ] **Step 4: Manually inspect saved files**

Confirm each file in `data/SNOW/` is non-empty and looks like the expected content (open the `.htm` files in a browser or text editor; open the `.json` files and confirm they parse and contain the expected fields).

- [ ] **Step 5: Fix forward if the live smoke test reveals a schema mismatch**

Real API responses can differ slightly from fixtures (e.g. API Ninjas may return an error JSON if the transcript for that exact year/quarter isn't available yet, since the 8-K was just filed and the transcript API may lag). If `get_transcript` returns an error body instead of a transcript, that's an M1-acceptable outcome — record it as-is in the saved JSON and note the gap; do not silently retry with guessed parameters, per the "never estimate what isn't disclosed" principle.

- [ ] **Step 6: Update README status line**

`README.md` line 7 currently reads "Status: **M1 in progress**". Change it to "Status: **M1 complete** — retrieval agent pulls and saves raw source documents; extraction and analysis come next."

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: mark M1 retrieval agent complete"
```
