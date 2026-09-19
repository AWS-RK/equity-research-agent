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
- **Stay lean in v0.** No Excel model, no multi-company comparison,
  no rating or price target (this project has no valuation model, and
  a specific recommendation without one would be exactly the kind of
  confidently-stated, unsupported claim the project exists to avoid).
  Charts were originally deferred too, but the user asked for them
  after M3 shipped -- see "M3.1: trend charts" below. Ticker in, one
  cited markdown note out.

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

**Not in scope for M3:** multi-ticker comparison, an Excel model.
Revenue consensus stays unavailable (no free source identified).

## M3.1: trend charts and report format refinement

After M3 shipped, the user asked for four changes to `note.md`: add
trendline charts, move the risk-factors diff to the bottom of the
note, follow the structural conventions of real sell-side research
reports, and add an Investment Thesis section on the company's
overarching trends. No rating or price target was added (see "Stay
lean in v0" above).

**Charts required historical data the pipeline didn't have.** M1/M2
only carry the current and prior quarter. Two new deterministic,
zero-LLM-cost or low-cost data sources were added:

- **`agents/sec_xbrl.py`**: `get_company_facts()` and
  `get_quarterly_metric_history()` pull multi-quarter GAAP figures
  (revenue, gross profit, operating income, net income, diluted EPS)
  directly from SEC's XBRL companyfacts API -- free, no LLM reading
  required. Verified live against SNOW: 21 quarters of clean revenue
  history back to 2019. This filer's 10-K doesn't separately tag a
  standalone fiscal Q4, so Q4 figures are calculated as the annual
  total less the sum of Q1-Q3 (arithmetic on two disclosed figures,
  not an estimate) -- checked against the company's own headline
  release figures for two historical Q4 periods and matched to within
  rounding both times.
- **`agents/sec_edgar.py`'s `find_historical_8k_item202()`** and
  **`agents/extraction_agent.py`'s `fetch_historical_press_releases()`**
  fetch press releases further back than the current/prior quarters,
  for non-GAAP margin, RPO, and NRR trend data that isn't in XBRL
  (non-GAAP figures aren't part of the standard GAAP taxonomy). Reading
  these for the specific figures needed is done by Claude directly in
  a session, same as M2/M3's other reading-comprehension work -- much
  lighter than a full M2-style extraction per historical quarter, since
  only a few headline numbers are needed, not the complete schema.

**`agents/analysis_agent.py`'s `generate_trend_charts()`** renders the
charts (matplotlib, a new real runtime dependency in `requirements.txt`)
as PNGs under `data/{TICKER}/charts/`, embedded in `note.md` via
relative markdown image links. The function only renders; it doesn't
care whether a given metric's history came from XBRL, Claude reading
press releases, or Alpha Vantage's saved data.

**Report structure** now follows the sell-side convention of Rating
(omitted here, see above) -> Executive Summary -> Investment Thesis ->
Quarterly Update -> Financial Exhibits -> Catalysts/New Guidance ->
Risk Factors -> Sources, researched via a web search on typical
equity-research report structure rather than assumed. The Investment
Thesis section synthesizes overarching trends across the data (for
SNOW's first note: the AI-driven margin inflection, decelerating RPO
against accelerating revenue, and the dependency/competitive tension
of relying on third-party frontier AI models) rather than restating
individual facts already covered elsewhere in the note.

## M3.2: valuation section

After M3.1, the user asked for a Valuation section: the stock's
trading multiples (P/E or EV/Sales as appropriate) and a comparison to
peer averages. This is descriptive, sourced market data (what multiple
the stock trades at, what the Street's published consensus is), not a
rating or recommendation of this note's own, so it doesn't conflict
with the "no rating or price target" decision in M3.1.

**`agents/alpha_vantage.py`'s `get_company_overview()`** calls Alpha
Vantage's OVERVIEW endpoint, which returns pre-computed EV/Revenue,
Price/Sales, forward and trailing P/E, market capitalization, TTM
financials, and the Street's consensus analyst rating distribution and
target price, for any ticker in one call. Confirmed live: SNOW's
`TrailingPE` comes back "-" (GAAP TTM earnings near breakeven, so
trailing P/E isn't meaningful), while `EVToRevenue` is well-defined --
consistent with how high-growth, GAAP-breakeven software companies are
usually valued, and the reason this note leads with EV/Revenue rather
than P/E.

**Peer set, chosen with the user:** Datadog (DDOG), MongoDB (MDB),
Confluent (CFLT), Cloudflare (NET), Elastic (ESTC) -- the closest
data-platform comparables to Snowflake's positioning, over a broader
high-growth-SaaS alternative that would have included less comparable
names (Palantir, Salesforce, Atlassian).

**Alpha Vantage's free tier caps at 25 requests per day (confirmed via
web search after live testing produced an inconsistent pattern of
empty responses)**, not the per-minute limit that was initially
suspected. CFLT, NET, and ESTC returned empty `{}` responses because
the day's quota was reached partway through fetching five peers, not
because those tickers lack coverage. Asked the user how to proceed:
they chose to publish today's note with the two available peers
(DDOG, MDB) rather than wait for the quota to reset, with the gap
explicitly flagged in the note rather than silently omitted or
papered over with three peers' worth of guessed figures.

## Known gaps / follow-ups

- **Earnings call transcript retrieval -- partially mitigated, not solved.**
  API Ninjas' free tier does not include the `earningstranscript` endpoint
  (confirmed live during M1: it returns `{"error": "This endpoint is
  available to premium subscribers only."}`). M1 saves that error as-is
  rather than crashing.

  `agents/retrieval_agent.py`'s `run()` now tries a free fallback when API
  Ninjas fails: Alpha Vantage's `EARNINGS_CALL_TRANSCRIPT` endpoint
  (`agents/alpha_vantage.py`'s `get_earnings_call_transcript()`), which
  works on the same key already used for `EARNINGS`/`OVERVIEW` and returns
  properly speaker-attributed transcripts. Its `quarter` parameter keys on
  the filer's own self-styled fiscal label (e.g. "2027Q2" for what the
  company calls "Q2 FY2027"), not a calendar quarter -- confirmed live by
  testing several labels against SNOW's actual press release titles.
  `derive_fiscal_quarter_guess()` computes this label with a heuristic
  tuned to January-fiscal-year-end filers (confirmed correct for SNOW);
  it is not guaranteed for filers with a different fiscal year end, but a
  wrong guess just returns no data, same as today, so trying it is free
  and harmless.

  **The real limit: Alpha Vantage's transcript data lags real filers by
  roughly one to two quarters** (confirmed live: as of 2026-09-19, SNOW's
  most recent available transcript was fiscal Q4 FY2026, reported
  February 2026 -- nothing yet for Q1 or Q2 FY2027). So this fallback
  will typically return nothing for the CURRENT quarter, the one this
  project actually needs, though it may catch up by the time a later
  quarter's note is drafted, and it already fills in verbal color for
  older quarters if that's ever wanted. Confirmed the lag is
  filer-specific, not universal, by checking MongoDB's data separately.

  If the current quarter's transcript is still needed sooner than Alpha
  Vantage catches up: (a) upgrade the API Ninjas plan
  (`get_transcript()` already calls the right endpoint, no code change
  needed), (b) add a fetcher for a different transcript provider, or
  (c) support a manually-pasted transcript as an extraction input.

- **Confluent (CFLT) missing from the valuation peer set.** NET and
  ESTC were added on 2026-09-19 once the daily quota reset, bringing
  the comparison to 4 of 5 intended peers (see M3.2 and the Valuation
  section of `data/SNOW/note.md`). CFLT alone returned an empty
  OVERVIEW response on two separate dates (2026-09-09 and 2026-09-19),
  including once as the very first call of a session when NET and
  ESTC succeeded immediately after it in the same run -- more
  consistent with a genuine per-ticker data-coverage gap on Alpha
  Vantage's side than with the quota that explained the original
  three-peer gap. Not fully confirmed either way. To retry: run
  `agents.alpha_vantage.get_company_overview("CFLT", api_key)` on a
  fresh day; if it still returns `{}`, treat CFLT as unavailable from
  this data source and either drop it from the peer set or find an
  alternative source for its multiples.

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
