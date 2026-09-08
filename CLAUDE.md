# Agentic Equity Research Analyst — Build Spec for Claude Code

Use this as your opening prompt/context for Claude Code (or save it as
`CLAUDE.md` in your project root so Claude Code picks it up automatically).
This was planned in Claude Cowork; building happens here in Claude Code.

## Project goal

Given a stock ticker, produce a short, fully-cited equity research note
covering the company's latest quarter, modeled on how a real sell-side
software analyst approaches the research-and-monitoring side of the job
(not the client-relationship side). First test ticker: **SNOW (Snowflake)**.

## Architecture: four-stage pipeline

```
Ticker in
   |
   v
[1. Retrieval Agent]  <-- BUILDING THIS FIRST (M1)
   - Latest 10-Q/10-K from SEC EDGAR
   - Latest 8-K Item 2.02 / Exhibit 99.1 (earnings press release,
     includes the GAAP-to-non-GAAP reconciliation table)
   - Latest earnings call transcript (API Ninjas)
   - EPS consensus + surprise (Alpha Vantage EARNINGS endpoint)
   - FRESHNESS CHECK: confirm today's date, confirm each document's
     date is within ~3 months; do not rely on training-data knowledge
     of the company's last known quarter
   |
   v
[2. Extraction Agent]
   - Core financials (revenue, margins, cash flow)
   - GAAP AND non-GAAP figures, from the 8-K reconciliation table
     (non-GAAP is the PRIMARY figure used downstream, matching how
     the Street actually talks about these companies; GAAP is kept
     for reference)
   - Forward guidance: next-quarter and next-year ranges, from both
     the press release and anything management adds verbally on the
     call (these can differ)
   - Sector-generic operating metrics, not a fixed SaaS catalog:
     the agent reports whatever KPIs the company itself discloses
     and names (GMV/take rate, DAU/MAU/ARPU, Gross Bookings, RPO/NRR,
     same-store sales, units/ASP, etc.), never a predefined list.
     Billings (revenue + change in deferred revenue) is the one
     exception -- a deterministically computed field, attempted
     whenever both periods' deferred-revenue balances were disclosed,
     regardless of sector. Anything not disclosed is flagged as
     unavailable, never estimated.
   - Diff risk factors and guidance language against the prior filing
   |
   v
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

## Why these design choices (context for whoever builds this)

- **Citation is mandatory, not optional.** This is the credibility
  feature of the whole project. No claim without a traceable source.
- **Freshness verification is explicit**, because the most likely
  failure mode is an LLM quietly using stale training-data knowledge
  of a company's last reported quarter instead of the actual latest one.
- **Non-GAAP leads, GAAP is kept for reference.** Matches how real
  analyst notes are written; the SEC's Reg G reconciliation requirement
  means the non-GAAP numbers are always traceable back to GAAP anyway.
- **Never estimate a metric that isn't disclosed.** If ARR or NRR
  isn't reported, say so. A confidently wrong number is worse than an
  honest gap.
- **Stay lean in v0.** No charts, no Excel model, no multi-company
  comparison yet. Ticker in, one cited markdown note out.

## Data sources (M1 specifically)

| Source | What it provides | Auth |
|---|---|---|
| SEC EDGAR | 10-Q/10-K, 8-K Exhibit 99.1 press release | No key; requires a compliant `User-Agent` header with a real name + email per SEC's fair-access policy |
| API Ninjas | Earnings call transcript | Free API key |
| Alpha Vantage | EPS consensus + surprise (`EARNINGS` endpoint) | Free API key (confirm this specific endpoint isn't gated behind their paid Alpha Intelligence tier once you have a key) |

Revenue consensus has no confirmed free source yet — leave it explicitly
marked unavailable in the output rather than adding a paid subscription
this early.

## M1 scope: Retrieval Agent

**Input:** a ticker (start with SNOW).

**Output:** raw source documents saved locally, plus a printed freshness
report (each document's date, and pass/fail against the ~3-month
freshness check).

**Steps:**
1. Resolve ticker → CIK using SEC's ticker-to-CIK mapping
   (`https://www.sec.gov/files/company_tickers.json`).
2. Pull the company's recent filings via SEC EDGAR's submissions API
   (`https://data.sec.gov/submissions/CIK##########.json`), find the
   latest 10-Q (or 10-K if more recent) and the latest 8-K with an
   Item 2.02 press release exhibit.
3. Download and save the 10-Q/10-K text and the 8-K Exhibit 99.1 text.
4. Call API Ninjas for the latest transcript; save it.
5. Call Alpha Vantage's EARNINGS endpoint for SNOW; save the EPS
   consensus/surprise data.
6. Run the freshness check against all fetched documents; print a
   clear pass/fail summary with dates.

**Not in scope for M1:** extraction, analysis, note generation. Those
are later milestones. M1 succeeds when it reliably fetches and saves
clean source documents for a given ticker with a working freshness check.

## M2 scope: Extraction Agent

**Input:** the raw documents M1 already saved to `data/{TICKER}/`.

**Output:** `data/{TICKER}/extracted.json` -- structured financial and
operating data for the current period and the prior period, computed
billings (when the inputs are disclosed), and risk-factor/guidance
language diffs between the two periods.

**Approach:** LLM-based extraction rather than rule-based parsing --
reconciling GAAP/non-GAAP figures, judging what operating metrics a
company actually disclosed, and diffing free-text risk factors/guidance
language all require reading comprehension that regex/table-position
heuristics can't reliably provide across different companies' filing
formats. The reading-comprehension work (financials, sector-generic
KPIs, guidance, risk-factor/guidance-language diffing) is done by
Claude directly in a session -- not by a Python script calling the
Anthropic API. That was the original design (see the superseded-note
in the M2 design spec below), reversed after the user pointed out a
separate `ANTHROPIC_API_KEY` bills separately from their existing
Claude subscription; running the extraction inside a Claude Code
session uses that subscription instead of incurring new per-run API
cost, at the cost of the extraction step no longer being a fully
standalone, non-interactively-runnable script.

`agents/extraction_agent.py` keeps only the deterministic halves as
plain, tested Python: `fetch_prior_period_documents()` (fetch and save
the prior quarter's 10-Q/10-K and 8-K Exhibit 99.1, reusing M1's SEC
EDGAR functions -- needed both for the language diffs and because
billings requires the prior period's own deferred-revenue balance,
which a standalone 10-Q doesn't show) and `save_extracted_result()`
(computes billings from the current/prior period dicts Claude
produced, assembles the final shape, writes `extracted.json`).

Full design: `docs/superpowers/specs/2026-09-04-extraction-agent-m2-design.md`
(superseded on the LLM-calling mechanism -- see the note at its top).

**Not in scope for M2:** analysis, note generation, revenue consensus.
Those are later milestones or explicitly deferred (see above).

## Known gaps / follow-ups

- **Earnings call transcript retrieval.** API Ninjas' free tier does not
  include the `earningstranscript` endpoint (confirmed live during M1:
  it returns `{"error": "This endpoint is available to premium
  subscribers only."}`). M1 saves that error as-is rather than
  crashing, so M2 correctly reads "no transcript available" and flags
  verbal/call-sourced guidance as unavailable rather than guessing.
  Deferred, not fixed -- if this needs addressing later, options are:
  (a) upgrade the API Ninjas plan (`agents/api_ninjas.py`'s
  `get_transcript()` already calls the right endpoint, no code change
  needed), (b) add a fetcher for a different transcript provider, or
  (c) support a manually-pasted transcript as an extraction input.

## Environment

```bash
pip install -r requirements-dev.txt
```

`.env` needs:
```
SEC_USER_AGENT="Your Name your.email@example.com"
API_NINJAS_KEY=
ALPHA_VANTAGE_KEY=
```

No `ANTHROPIC_API_KEY` -- M2's extraction step runs as part of a Claude
Code session (billed under the existing Claude subscription), not as a
standalone script calling the Anthropic API.
