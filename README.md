# Agentic Equity Research Analyst

Given a stock ticker, this pipeline pulls the latest 10-Q/10-K, earnings
press release (with non-GAAP reconciliation), earnings call transcript,
and EPS consensus data, then produces a cited research note.

Status: **M1 in progress** — retrieval agent (this milestone pulls and
saves the raw source documents; extraction and analysis come next).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# then fill in .env with your API Ninjas and Alpha Vantage keys
# (SEC EDGAR needs no key, just a real name/email in SEC_USER_AGENT)
```

## Usage (M1)

```bash
python agents/retrieval_agent.py --ticker SNOW
```

Saves raw source documents to `data/SNOW/` and prints a freshness report.

## Data sources

- **SEC EDGAR** — 10-Q/10-K and 8-K Exhibit 99.1 press releases (free, no key)
- **API Ninjas** — earnings call transcripts (free tier)
- **Alpha Vantage** — EPS consensus and surprise (free tier, unconfirmed
  whether the EARNINGS endpoint is gated)

Revenue consensus is intentionally left unsourced in v0; the note will
mark it as unavailable rather than estimate it.
