# Agentic Equity Research Analyst

Given a stock ticker, this pipeline pulls the latest 10-Q/10-K, earnings
press release (with non-GAAP reconciliation), earnings call transcript,
and EPS consensus data, then produces a cited research note.

Status: **M1 complete, M2 complete, M3 code-complete** — retrieval
agent pulls and saves raw source documents; extraction agent turns
them into structured, cited financial and operating data
(sector-generic, not SaaS-specific); analysis agent drafts the final
cited markdown note. All tests pass. As with M2, the deterministic
parts of M3 (reading the two JSON inputs, saving the final note) are a
tested Python module; the actual drafting is done by Claude directly
in a session — see "Usage (M3)" below.

## Setup

```bash
pip install -r requirements-dev.txt
cp .env.example .env
# then fill in .env with your API Ninjas and Alpha Vantage keys
# (SEC EDGAR needs no key, just a real name/email in SEC_USER_AGENT)
```

## Usage (M1)

```bash
python -m agents.retrieval_agent --ticker SNOW
```

Run as a module (`-m`), not as a script path — the package uses absolute
imports (`from agents.config import ...`), which only resolve when the
project root is on `sys.path`, and `-m` is what puts it there.

Saves raw source documents to `data/SNOW/` and prints a freshness report.

## Usage (M2)

M2 is not a single command — it's a two-step, Claude-in-the-loop process,
because the reading-comprehension work (financials, sector-generic KPI
discovery, guidance and risk-factor diffing) is done by Claude directly
in a session rather than by a script calling the Anthropic API. This
avoids needing a separate `ANTHROPIC_API_KEY` billed outside your
existing Claude subscription — the trade-off is that it isn't a fully
standalone, non-interactively-runnable script.

1. **Prep (deterministic, scriptable):**
   ```bash
   python -m agents.extraction_agent --ticker SNOW
   ```
   Requires `data/SNOW/` to already contain M1's output (run the
   retrieval agent first). Fetches and saves the prior quarter's
   10-Q/10-K and 8-K Exhibit 99.1 into `data/SNOW/` alongside M1's files
   (named with a `_PRIOR_` marker) and prints their paths.

2. **Extraction (Claude-in-the-loop):** ask Claude Code to read the
   current- and prior-period documents in `data/SNOW/` and produce the
   structured `current_period`/`prior_period` dicts and risk-factor/
   guidance-language diffs per the schema in
   `docs/superpowers/specs/2026-09-04-extraction-agent-m2-design.md`,
   then call `agents.extraction_agent.save_extracted_result(ticker,
   base_dir, current_period, prior_period, diffs)` to compute billings
   and write `data/SNOW/extracted.json`.

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

## Data sources

- **SEC EDGAR** — 10-Q/10-K and 8-K Exhibit 99.1 press releases (free, no key)
- **API Ninjas** — earnings call transcripts. Confirmed live: the free tier
  does NOT include this endpoint (`{"error": "This endpoint is available to
  premium subscribers only."}`) — a paid plan is required. The retrieval
  agent handles this gracefully: it records the error as-is in the saved
  transcript JSON and continues with every other data source rather than
  crashing the run.
- **Alpha Vantage** — EPS consensus and surprise (free tier; confirmed live
  against SNOW that the EARNINGS endpoint works on the free tier)

Revenue consensus is intentionally left unsourced in v0; the note will
mark it as unavailable rather than estimate it.
