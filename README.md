# Agentic Equity Research Analyst

Given a stock ticker, this pipeline pulls the latest 10-Q/10-K, earnings
press release (with non-GAAP reconciliation), earnings call transcript,
and EPS consensus data, then produces a cited research note.

Status: **M1 complete, M2 code-complete (not yet live-verified)** —
retrieval agent pulls and saves raw source documents; extraction agent
turns them into structured, cited financial and operating data
(sector-generic, not SaaS-specific). All 55 tests pass against mocked
APIs, but M2 has not yet been run against a real Anthropic API key —
see "Usage (M2)" below before trusting its output on a real ticker.

## Setup

```bash
pip install -r requirements-dev.txt
cp .env.example .env
# then fill in .env with your API Ninjas, Alpha Vantage, and Anthropic keys
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

```bash
python -m agents.extraction_agent --ticker SNOW
```

Requires `data/SNOW/` to already contain M1's output (run the retrieval
agent first) and a real `ANTHROPIC_API_KEY` in `.env`. Saves
`data/SNOW/extracted.json` (current-period and prior-period financial/
operating data, computed billings, risk-factor and guidance-language
diffs) and prints it. Also fetches and saves the prior quarter's
10-Q/10-K and 8-K Exhibit 99.1 into `data/SNOW/` alongside M1's files
(named with a `_PRIOR_` marker).

Costs real money per run (~$1-1.50 estimated — the main extraction
calls read a 100K+ token filing on Sonnet 5). Override models with
`--extraction-model` / `--diff-model` if needed.

**Not yet live-verified**: this milestone's 55 tests all pass against a
mocked Anthropic client, but the extraction logic itself has not been
run against a real API key yet. Before relying on its output, run it
once against a real ticker and sanity-check `extracted.json` — do the
financial figures look right, do `disclosed_kpis` reflect metrics that
company actually reports (not a generic list), is `billings` either a
real computed number or `null` (never a guess)?

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
