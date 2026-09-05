# M2 Extraction Agent — Design Spec

## Goal

Given the raw documents M1 already fetched and saved for a ticker
(`data/{TICKER}/`), extract structured financial and operating data —
generic across sectors, not SaaS-specific — into a single cited JSON
file, using Claude for the parts that require reading comprehension
(financials in prose/tables, forward guidance, sector-specific KPIs,
risk-factor and guidance-language changes) and plain Python for the
one part that's pure arithmetic (billings).

## Why LLM-based extraction (not rule-based)

Confirmed with the user: reconciling GAAP/non-GAAP figures, judging
what operating metrics a company actually disclosed, and diffing
free-text risk factors/guidance language all require reading
comprehension that fragile regex/table-position heuristics can't
reliably provide across different companies' filing formats. Rule-based
parsing was rejected; LLM-based extraction (via the Anthropic API,
using structured tool-use — not free-text JSON parsing) was chosen.

## Why sector-generic, not SaaS-specific

CLAUDE.md's original draft named SaaS metrics (billings, RPO) as the
operating-metrics target. The user explicitly rejected limiting this to
SaaS: companies across tech, internet, and other sectors disclose their
own relevant KPIs (GMV/take rate for marketplaces, DAU/MAU/ARPU for ads
businesses, Gross Bookings/Trips for rides, RPO/NRR for SaaS, same-store
sales for retail, units shipped/ASP for hardware, etc.). The schema
must not hardcode a fixed metric catalog.

**Resolution:** operating metrics are extracted as an open-ended list
(`disclosed_kpis`), each with the name *as the company itself uses it*,
not selected from a predefined enum. A hint list of common metric
*categories* (retention/churn, volume, engagement, pricing, backlog)
lives in the LLM prompt to aid recall, not in the schema, so it never
constrains what can be reported.

The one exception is `billings` (revenue + change in deferred revenue),
which stays a named, deterministically *computed* field — not because
the company is SaaS, but because it's pure arithmetic over two
disclosed balance-sheet figures. It's computed whenever both periods'
deferred-revenue balances were extracted, and simply absent otherwise.
No sector detection anywhere in the code.

## Architecture

```
data/{TICKER}/ (from M1)          agents/extraction_agent.py (orchestrator)
  {TICKER}_10-Q_*.htm      ─┐            │
  {TICKER}_8K_EX99.1_*.htm  ├─ read ─────┤
  {TICKER}_transcript_*.json│            │
  {TICKER}_earnings_*.json ─┘            │
                                          ├─ fetch prior 10-Q/10-K + 8-K
                                          │  (agents/sec_edgar.py, new
                                          │  find_prior_* functions;
                                          │  save alongside M1's files)
                                          │
                                          ├─ strip_html_to_text() on all
                                          │  four HTML/text documents
                                          │  (agents/html_text.py)
                                          │
                                          ├─ extract_period_data(current
                                          │  docs incl. transcript)
                                          ├─ extract_period_data(prior
                                          │  docs, no transcript)
                                          │  (agents/claude_extraction.py,
                                          │  same schema both times)
                                          │
                                          ├─ diff_language(risk factors)
                                          ├─ diff_language(guidance text)
                                          │  (agents/claude_extraction.py)
                                          │
                                          ├─ compute_billings(current,
                                          │  prior) (agents/derived_metrics.py,
                                          │  pure function, no LLM)
                                          │
                                          └─ write data/{TICKER}/extracted.json
```

## File structure

- **`agents/html_text.py`** (new) — `strip_html_to_text(html: str) -> str`.
  Removes the inline-XBRL `<ix:header>` metadata block and `<script>`/`<style>`
  blocks, strips remaining tags, unescapes entities, collapses whitespace.
  Verified live against the real SNOW 10-Q: 2.5MB HTML → ~411K chars
  (~103K estimated tokens) of genuine document text.

- **`agents/claude_extraction.py`** (new) — wraps the Anthropic API using
  structured tool-use (forces a single tool call with `tool_choice`,
  avoiding free-text JSON parsing):
  - `extract_period_data(docs: dict[str, str], model: str = "claude-sonnet-5") -> dict` —
    `docs` keys are `"filing"`, `"press_release"`, and optionally
    `"transcript"` (prior-period calls omit it). Same schema for both
    current and prior periods (see below). Defaults to Sonnet 5: this is
    the accuracy-critical call — a 100-150K-token document, GAAP/non-GAAP
    reconciliation judgment, and open-ended KPI discovery all benefit
    from the more capable model, and it's where nearly all of this
    project's per-run token cost lives.
  - `diff_language(current_text: str, prior_text: str, field_label: str, model: str = "claude-haiku-4-5-20251001") -> dict` —
    returns `{"changes_summary": str, "material_change": bool}`.
    Defaults to Haiku 4.5: comparing two already-extracted text fields
    and judging materiality is a small-input, lower-stakes task well
    suited to the cheaper/faster model — decided with the user
    specifically to optimize cost, since this call's own token volume
    is already small regardless of model (the savings here are about
    picking the right tier for the task, not about total dollars, which
    are dominated by the extraction calls).

- **`agents/derived_metrics.py`** (new, generically named — not
  `saas_metrics.py`) — `compute_billings(current: dict, prior: dict) -> dict | None`.
  Pure function: `billings = current["revenue"] + current["deferred_revenue_balance"]
  - prior["deferred_revenue_balance"]`. Returns `None` if `revenue` or
  either deferred-revenue balance is missing — never estimates.

- **`agents/extraction_agent.py`** (new) — CLI orchestrator, same shape
  as `retrieval_agent.py`: `run(ticker, base_dir="data", extraction_model="claude-sonnet-5", diff_model="claude-haiku-4-5-20251001") -> dict`,
  `main()`/`parse_args()` for `python -m agents.extraction_agent --ticker SNOW
  [--extraction-model claude-sonnet-5] [--diff-model claude-haiku-4-5-20251001]`.
  Reads M1's already-saved current-period files from disk (no
  re-download); fetches and saves only the new prior-period documents.

- **`agents/sec_edgar.py`** (modify) — add `find_prior_10q_or_10k(submissions, exclude_accession: str) -> dict | None`
  and `find_prior_8k_item202(submissions, exclude_accession: str) -> dict | None`.
  Refactor the shared candidate-collection logic out of the existing
  `find_latest_*` functions into private helpers so both "latest" and
  "prior" share one filter/sort implementation. Existing tests and
  public function signatures are unchanged — purely additive from the
  outside.

- **`agents/config.py`** (modify) — add `anthropic_api_key: str` to
  `Config`; `load_config()` requires it like the other three keys.

- **`requirements.txt`** (modify) — add `anthropic` SDK.
  **`.env.example`** / **`.env`** (modify) — add `ANTHROPIC_API_KEY`.

## Extraction schema (used for both current and prior period)

```
{
  "revenue": number | null,
  "revenue_yoy_growth_pct": number | null,
  "gross_margin_gaap_pct": number | null,
  "gross_margin_non_gaap_pct": number | null,
  "operating_margin_gaap_pct": number | null,
  "operating_margin_non_gaap_pct": number | null,
  "net_income_gaap": number | null,
  "net_income_non_gaap": number | null,
  "eps_gaap": number | null,
  "eps_non_gaap": number | null,
  "operating_cash_flow": number | null,
  "free_cash_flow": number | null,
  "deferred_revenue_balance": number | null,
  "segment_revenues": [{"segment_name": str, "revenue": number, "yoy_growth_pct": number | null}],
  "guidance": [{"period": "next_quarter" | "next_year", "metric_name": str,
                "low": number | null, "high": number | null,
                "source": "press_release" | "call", "source_quote": str}],
  "disclosed_kpis": [{"name": str, "value": str, "unit": str | null,
                        "period": str | null, "yoy_change": str | null,
                        "source_quote": str}],
  "risk_factors_text": str,
  "guidance_text": str,
  "unavailable": [str]
}
```

`unavailable` lists which of the *named, expected-to-be-common* fields
(revenue, margins, cash flow, guidance) were looked for but not found —
this is the "flag the gap, don't estimate" mechanism for the core
financial fields. `disclosed_kpis` has no such gap-list, since it's
inherently open-ended (there's no fixed catalog to fall short of).

## Output: `data/{TICKER}/extracted.json`

```
{
  "ticker": str,
  "current_period": { ...extraction schema... },
  "prior_period": { ...extraction schema... },
  "billings": {"revenue": number, "current_deferred_revenue": number,
                "prior_deferred_revenue": number, "value": number} | null,
  "diffs": {
    "risk_factors": {"changes_summary": str, "material_change": bool},
    "guidance_language": {"changes_summary": str, "material_change": bool}
  }
}
```

## Error handling

Unlike M1 (where one gated source shouldn't sink the others — M1's
whole job is independent mechanical fetches), a failed extraction call
here IS the core deliverable failing. LLM call failures raise clearly;
no silent partial output. This is a deliberate asymmetry from M1's
per-source resilience, not an inconsistency.

## Testing

Mock the Anthropic client the same way M1 mocked `requests.get` —
patch `agents.claude_extraction.Anthropic` (or the client instance) so
the test suite makes zero real API calls, consistent with M1's
approach. `compute_billings` and the new `sec_edgar.py` functions are
pure-function unit tests with fixture data, same pattern as M1's
`find_latest_10q_or_10k`/`find_latest_8k_item202` tests.

## CLAUDE.md update

The Extraction Agent bullet currently reads "SaaS metrics computed only
where actually disclosed: billings ..., RPO, YoY growth by segment."
This will be updated to reflect the generalized, sector-agnostic
design once this spec is approved.
