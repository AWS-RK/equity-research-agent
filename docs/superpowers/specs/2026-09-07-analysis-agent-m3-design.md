# M3 Analysis Agent — Design Spec

## Goal

Given M2's `extracted.json` (current/prior period financials, guidance,
sector-generic KPIs, and risk-factor/guidance-language diffs) and M1's
saved EPS consensus data, draft a short, fully-cited equity research
note as a single markdown file: thesis, results benchmarked three ways,
new forward guidance as its own section, and a Sources list resolving
every citation.

## Architecture

Same pattern as M2's pivot: a thin, deterministic Python module
(`agents/analysis_agent.py`) handles file I/O only — loading the two
JSON inputs and saving the final markdown. The actual drafting (the
thesis, the benchmark comparisons, the prose, and getting every
citation right) is done by Claude directly in a session, not by a
script calling the Anthropic API. No new API key, no new dependency.

**Note on the four-stage pipeline in CLAUDE.md:** M3 ("Analysis
Agent — draft the note") and M4 ("Output — single markdown file") were
originally scoped as separate stages. With this architecture, they
collapse into one: Claude drafts the complete markdown (including the
Sources section) and `save_note()` writes it — there's no separate
assembly/formatting step left for a distinct M4 to do. CLAUDE.md's
milestone list will be updated to reflect this once M3 ships.

## File structure

- **`agents/analysis_agent.py`** (new):
  - `read_extracted_data(ticker: str, base_dir: str = "data") -> dict` —
    loads and parses `data/{TICKER}/extracted.json` (M2's output).
    Raises `FileNotFoundError` with a clear message ("run the
    extraction agent (M2) first") if missing.
  - `read_eps_consensus(ticker: str, base_dir: str = "data") -> dict | None` —
    loads `data/{TICKER}/{TICKER}_earnings_alphavantage.json` (M1's
    output) and returns the latest quarter's entry via the existing
    `agents.alpha_vantage.get_latest_quarterly_earnings()` (already
    built in M1 — reused, not reimplemented). Raises `FileNotFoundError`
    if the file itself is missing (M1 always saves it); returns `None`
    only if the file exists but has no `quarterlyEarnings` entries,
    mirroring `get_latest_quarterly_earnings()`'s own behavior.
  - `save_note(ticker: str, base_dir: str, markdown_text: str) -> Path` —
    writes `data/{TICKER}/note.md` and returns its path.

No new computation is needed for the EPS-vs-Street benchmark: Alpha
Vantage's `quarterlyEarnings` entries already include `surprise` and
`surprisePercentage`, pre-computed. Revenue consensus stays explicitly
unavailable in v0 (no free source), per CLAUDE.md.

## Note structure (`data/{TICKER}/note.md`)

1. **Header** — ticker, company name, period, filing date
2. **Thesis** — 2-4 sentence headline take
3. **Results vs. Benchmarks** — three subsections:
   - (a) EPS vs. Street (from Alpha Vantage's `surprise`/
     `surprisePercentage`; revenue consensus marked unavailable)
   - (b) actual vs. prior-quarter guidance (matching `extracted.json`'s
     `prior_period.guidance` entries to the corresponding current-period
     actuals by metric name — done by Claude during drafting, not by
     fragile automated string-matching in Python, since metric naming
     isn't guaranteed to align cleanly across arbitrary companies)
   - (c) QoQ/YoY trend (pulled from `extracted.json`'s already-computed
     growth figures)
4. **New Forward Guidance** — its own section (current_period.guidance),
   since CLAUDE.md flags this as what moves the stock next
5. **Notable Changes** — risk-factor/guidance-language diffs from
   `extracted.json`, surfaced only where `material_change` is `true`
   (an unchanged risk-factors section isn't worth a note section)
6. **Sources** — numbered list resolving every `[N]` used above:
   document name + section/table (e.g. "[1] SNOW_10-Q_2026-09-04.htm,
   Condensed Consolidated Statements of Operations") or, for a KPI/quote,
   the disclosed source_quote already captured in `extracted.json`

## Citation mechanism

Numbered footnotes (`[1]`, `[2]`, ...) inline in the prose, resolved in
the Sources section at the bottom — decided with the user over inline
parenthetical citations, for cleaner prose when the same source is
cited many times.

## Error handling

`read_extracted_data`/`read_eps_consensus` raise clearly on missing
inputs (consistent with M2's `read_current_filing_text` precedent) —
no silent fallback. `save_note` has no failure modes worth handling
beyond what `Path.write_text` already raises on its own (e.g. disk
full, permissions) — not worth wrapping.

## Testing

All three functions are pure file I/O with no network calls, so tests
are straightforward: write fixture JSON files to `tmp_path`, call the
function, assert the parsed/returned result; `save_note` tests check
the file is written with the exact given content and the returned path
is correct. No mocking needed (unlike M1/M2, there's no HTTP or SDK
boundary in this module at all).

## Not in scope for M3

Multi-ticker comparison, charts, an Excel model — all explicitly
deferred per CLAUDE.md's "stay lean in v0" principle. Revenue consensus
stays unavailable (no free source identified).
