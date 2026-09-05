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
