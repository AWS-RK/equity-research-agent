# M3 Analysis Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the thin, deterministic Python module M3 needs — read M2's `extracted.json` and M1's EPS consensus data, and save the final drafted markdown note — so that drafting the actual note (thesis, benchmarks, citations) can happen via Claude directly in a session, the same architecture M2 uses.

**Architecture:** `agents/analysis_agent.py` gets three small functions with no orchestrating `run()`/CLI, because unlike M1/M2 there's no automatable pipeline step here — the drafting itself is the work, done by Claude reading the two JSON files and writing markdown, not by a script. The three functions are the file I/O boundary Claude calls into: read the two inputs, save the output.

**Tech Stack:** No new dependencies. Pure file I/O — no network calls, no mocking needed anywhere in this module's tests.

**Full design rationale:** see `docs/superpowers/specs/2026-09-07-analysis-agent-m3-design.md` (approved).

**Verified facts locked into this plan:**
- M1 always saves EPS data to `data/{TICKER}/{TICKER}_earnings_alphavantage.json` (confirmed in `agents/retrieval_agent.py`) — the file's format is `{"symbol": ..., "quarterlyEarnings": [{"fiscalDateEnding", "reportedDate", "reportedEPS", "estimatedEPS", "surprise", "surprisePercentage"}, ...]}`, most recent quarter first.
- `agents.alpha_vantage.get_latest_quarterly_earnings(earnings_response: dict) -> dict | None` already exists (built in M1) and returns `None` when `quarterlyEarnings` is empty — reused here, not reimplemented.
- M2 saves its output to `data/{TICKER}/extracted.json` (confirmed in `agents/extraction_agent.py`'s `save_extracted_result`).

---

## Task 1: `read_extracted_data`

**Files:**
- Create: `agents/analysis_agent.py` (this function only; Tasks 2-3 add the rest)
- Create: `tests/test_analysis_agent.py`

- [ ] **Step 1: Write the failing test**

`tests/test_analysis_agent.py`:
```python
import json

from agents.analysis_agent import read_extracted_data


def test_read_extracted_data_returns_parsed_json(tmp_path):
    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()
    (data_dir / "extracted.json").write_text(
        json.dumps({"ticker": "SNOW", "current_period": {"revenue": 1546.793}}),
        encoding="utf-8",
    )

    result = read_extracted_data("SNOW", base_dir=str(tmp_path))

    assert result == {"ticker": "SNOW", "current_period": {"revenue": 1546.793}}


def test_read_extracted_data_raises_when_missing(tmp_path):
    try:
        read_extracted_data("SNOW", base_dir=str(tmp_path))
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "extraction agent" in str(exc).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analysis_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agents.analysis_agent'`

- [ ] **Step 3: Write minimal implementation**

`agents/analysis_agent.py`:
```python
import json
from pathlib import Path


def read_extracted_data(ticker: str, base_dir: str = "data") -> dict:
    extracted_path = Path(base_dir) / ticker.upper() / "extracted.json"
    if not extracted_path.exists():
        raise FileNotFoundError(
            f"No extracted.json found in {extracted_path.parent} -- run the extraction agent (M2) first."
        )
    return json.loads(extracted_path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analysis_agent.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/analysis_agent.py tests/test_analysis_agent.py
git commit -m "feat: add read_extracted_data for the analysis agent"
```

---

## Task 2: `read_eps_consensus`

**Files:**
- Modify: `agents/analysis_agent.py` (append to it, don't rewrite existing content)
- Modify: `tests/test_analysis_agent.py` (append to it, don't rewrite existing content)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_analysis_agent.py`:
```python
from agents.analysis_agent import read_eps_consensus


def test_read_eps_consensus_returns_latest_quarter(tmp_path):
    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()
    earnings = {
        "symbol": "SNOW",
        "quarterlyEarnings": [
            {
                "fiscalDateEnding": "2026-07-31",
                "reportedDate": "2026-09-02",
                "reportedEPS": "0.62",
                "estimatedEPS": "0.55",
                "surprise": "0.07",
                "surprisePercentage": "12.7273",
            },
            {
                "fiscalDateEnding": "2026-04-30",
                "reportedDate": "2026-05-27",
                "reportedEPS": "0.39",
                "estimatedEPS": "0.21",
                "surprise": "0.18",
                "surprisePercentage": "85.7143",
            },
        ],
    }
    (data_dir / "SNOW_earnings_alphavantage.json").write_text(json.dumps(earnings), encoding="utf-8")

    result = read_eps_consensus("SNOW", base_dir=str(tmp_path))

    assert result["fiscalDateEnding"] == "2026-07-31"
    assert result["reportedEPS"] == "0.62"
    assert result["surprisePercentage"] == "12.7273"


def test_read_eps_consensus_returns_none_when_no_quarterly_earnings(tmp_path):
    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()
    (data_dir / "SNOW_earnings_alphavantage.json").write_text(
        json.dumps({"symbol": "SNOW", "quarterlyEarnings": []}), encoding="utf-8"
    )

    assert read_eps_consensus("SNOW", base_dir=str(tmp_path)) is None


def test_read_eps_consensus_raises_when_file_missing(tmp_path):
    data_dir = tmp_path / "SNOW"
    data_dir.mkdir()

    try:
        read_eps_consensus("SNOW", base_dir=str(tmp_path))
        assert False, "expected FileNotFoundError"
    except FileNotFoundError as exc:
        assert "retrieval agent" in str(exc).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analysis_agent.py -v`
Expected: FAIL with `ImportError: cannot import name 'read_eps_consensus'`

- [ ] **Step 3: Write minimal implementation**

Add this import to the top of `agents/analysis_agent.py`, alongside the existing `import json` / `from pathlib import Path`:
```python
from agents.alpha_vantage import get_latest_quarterly_earnings
```

Then append to `agents/analysis_agent.py`:
```python
def read_eps_consensus(ticker: str, base_dir: str = "data") -> dict | None:
    data_dir = Path(base_dir) / ticker.upper()
    earnings_path = data_dir / f"{ticker.upper()}_earnings_alphavantage.json"
    if not earnings_path.exists():
        raise FileNotFoundError(
            f"No {earnings_path.name} found in {data_dir} -- run the retrieval agent (M1) first."
        )
    earnings_response = json.loads(earnings_path.read_text(encoding="utf-8"))
    return get_latest_quarterly_earnings(earnings_response)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analysis_agent.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add agents/analysis_agent.py tests/test_analysis_agent.py
git commit -m "feat: add read_eps_consensus, reusing M1's get_latest_quarterly_earnings"
```

---

## Task 3: `save_note`

**Files:**
- Modify: `agents/analysis_agent.py` (append to it, don't rewrite existing content)
- Modify: `tests/test_analysis_agent.py` (append to it, don't rewrite existing content)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_analysis_agent.py`:
```python
from agents.analysis_agent import save_note


def test_save_note_writes_file_and_returns_path(tmp_path):
    markdown_text = "# SNOW Q2 FY2027\n\nThesis goes here.\n"

    result_path = save_note("SNOW", str(tmp_path), markdown_text)

    assert result_path == tmp_path / "SNOW" / "note.md"
    assert result_path.exists()
    assert result_path.read_text(encoding="utf-8") == markdown_text


def test_save_note_creates_data_dir_if_missing(tmp_path):
    assert not (tmp_path / "SNOW").exists()

    save_note("SNOW", str(tmp_path), "# Note\n")

    assert (tmp_path / "SNOW" / "note.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_analysis_agent.py -v`
Expected: FAIL with `ImportError: cannot import name 'save_note'`

- [ ] **Step 3: Write minimal implementation**

Add this import to the top of `agents/analysis_agent.py`, alongside the existing imports:
```python
from agents.config import get_data_dir
```

Then append to `agents/analysis_agent.py`:
```python
def save_note(ticker: str, base_dir: str, markdown_text: str) -> Path:
    data_dir = get_data_dir(ticker, base_dir)
    note_path = data_dir / "note.md"
    note_path.write_text(markdown_text, encoding="utf-8")
    return note_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_analysis_agent.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass, zero real network/API calls (this whole module has none)

- [ ] **Step 6: Commit**

```bash
git add agents/analysis_agent.py tests/test_analysis_agent.py
git commit -m "feat: add save_note to write the drafted markdown note"
```

---

## Task 4: Update CLAUDE.md and README.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Update the pipeline diagram in CLAUDE.md**

In `CLAUDE.md`, the four-stage pipeline diagram currently shows `[3. Analysis Agent]` and `[4. Output]` as two separate boxes. Since Claude drafts the complete markdown (including Sources) directly and there's no separate assembly stage, merge them into one box. Replace:
```
[3. Analysis Agent]
   - Draft the note: thesis, results vs. THREE benchmarks —
     (a) consensus estimates (EPS beat/miss vs. Street; revenue
         consensus explicitly marked unavailable in v0, no paid
         source yet), (b) prior guidance (vs. what management said
         last quarter), (c) QoQ/YoY trend
   - New forward guidance surfaced as its own section, since that's
     what moves the stock going forward, not just the trailing quarter
   - Every factual claim carries an inline citation to its exact
     source (filing section, or transcript speaker + quote)
   |
   v
[4. Output]
   - Single markdown file, non-GAAP-led, with a Sources section
     listing every citation
```

with:
```
[3. Analysis Agent]  (produces the final output directly -- see below)
   - Draft the note: thesis, results vs. THREE benchmarks —
     (a) consensus estimates (EPS beat/miss vs. Street; revenue
         consensus explicitly marked unavailable in v0, no paid
         source yet), (b) prior guidance (vs. what management said
         last quarter), (c) QoQ/YoY trend
   - New forward guidance surfaced as its own section, since that's
     what moves the stock going forward, not just the trailing quarter
   - Every factual claim carries an inline citation to its exact
     source (filing section, or transcript speaker + quote)
   - Output: a single markdown file, non-GAAP-led, with a Sources
     section listing every citation (originally scoped as a separate
     "M4 Output" stage; collapsed into this one once M3's architecture
     had Claude draft the complete file directly -- there was no
     separate assembly step left for M4 to own)
```

- [ ] **Step 2: Add an M3 scope section to CLAUDE.md**

Add this new section immediately after the existing `## M2 scope: Extraction Agent` section (before `## Known gaps / follow-ups`):
```
## M3 scope: Analysis Agent

**Input:** M2's `data/{TICKER}/extracted.json` and M1's
`data/{TICKER}/{TICKER}_earnings_alphavantage.json`.

**Output:** `data/{TICKER}/note.md` -- a single cited markdown research
note: thesis, results vs. three benchmarks, new forward guidance as its
own section, notable risk-factor/guidance-language changes, and a
numbered-footnote Sources section resolving every citation.

**Approach:** same architecture as M2's pivot -- `agents/analysis_agent.py`
is a thin, deterministic Python module (`read_extracted_data`,
`read_eps_consensus`, `save_note`) with no orchestrating `run()`/CLI,
because unlike M1/M2 there's no automatable pipeline step here. The
drafting itself -- the thesis, matching prior guidance to actual
results by metric name, getting every citation right -- is done by
Claude directly in a session, not by a script. No new API key.

No new computation is needed for the EPS-vs-Street benchmark: Alpha
Vantage's `quarterlyEarnings` entries already include `surprise` and
`surprisePercentage`, pre-computed by M1's data source.

Full design: `docs/superpowers/specs/2026-09-07-analysis-agent-m3-design.md`.

**Not in scope for M3:** multi-ticker comparison, charts, an Excel
model. Revenue consensus stays unavailable (no free source identified).
```

- [ ] **Step 3: Run the full test suite**

Run: `pytest -v`
Expected: all tests still pass (docs-only changes, but confirms nothing else broke)

- [ ] **Step 4: Update README.md**

Update the status line and add a "Usage (M3)" section. Replace:
```
Status: **M1 complete, M2 code-complete** — retrieval agent pulls and
saves raw source documents; extraction agent turns them into
structured, cited financial and operating data (sector-generic, not
SaaS-specific). All 51 tests pass. The deterministic parts (fetching
the prior quarter's filing, computing billings, writing the output
JSON) are a tested Python module; the reading-comprehension part
(financials, KPI discovery, guidance/risk-factor diffing) is done by
Claude directly in a session — see "Usage (M2)" below.
```

with:
```
Status: **M1 complete, M2 complete, M3 code-complete** — retrieval
agent pulls and saves raw source documents; extraction agent turns
them into structured, cited financial and operating data
(sector-generic, not SaaS-specific); analysis agent drafts the final
cited markdown note. All tests pass. As with M2, the deterministic
parts of M3 (reading the two JSON inputs, saving the final note) are a
tested Python module; the actual drafting is done by Claude directly
in a session — see "Usage (M3)" below.
```

Then add this new section after "## Usage (M2)":
```
## Usage (M3)

Like M2, this is a two-step, Claude-in-the-loop process — no CLI
command runs the whole thing, because the drafting itself (thesis,
benchmark comparisons, getting every citation right) is the work.

1. **Prerequisite:** `data/SNOW/extracted.json` must already exist (run
   M1 then M2 first).
2. **Draft (Claude-in-the-loop):** ask Claude Code to read
   `data/SNOW/extracted.json` and `data/SNOW/SNOW_earnings_alphavantage.json`
   (via `agents.analysis_agent.read_extracted_data` and
   `read_eps_consensus`), draft the note per the structure in
   `docs/superpowers/specs/2026-09-07-analysis-agent-m3-design.md`
   (thesis, three benchmarks, new guidance, notable changes, numbered
   Sources), then call `agents.analysis_agent.save_note(ticker,
   base_dir, markdown_text)` to write `data/SNOW/note.md`.
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: mark M3 code-complete, collapse M3/M4 in the pipeline diagram"
```
