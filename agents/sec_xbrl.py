from datetime import date

import requests

COMPANY_FACTS_URL_TEMPLATE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


def _sec_headers(user_agent: str) -> dict:
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}


def get_company_facts(cik: int, user_agent: str) -> dict:
    url = COMPANY_FACTS_URL_TEMPLATE.format(cik=cik)
    response = requests.get(url, headers=_sec_headers(user_agent), timeout=30)
    response.raise_for_status()
    return response.json()


def _parse_date(value: str) -> date:
    year, month, day = value.split("-")
    return date(int(year), int(month), int(day))


def get_quarterly_metric_history(company_facts: dict, tag: str, max_quarters: int = 8) -> list[dict]:
    """Extract a clean quarterly (3-month duration) time series for one us-gaap XBRL
    tag from a companyfacts response, deduplicated by period end date and limited to
    the most recent max_quarters. Returns [] if the tag isn't present for this filer.
    """
    tag_data = company_facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if tag_data is None:
        return []

    units = tag_data.get("units", {})
    values = next(iter(units.values()), [])

    quarterly = {}
    for entry in values:
        if entry.get("form") not in ("10-Q", "10-K"):
            continue
        start, end = entry.get("start"), entry.get("end")
        if not start or not end:
            continue
        days = (_parse_date(end) - _parse_date(start)).days
        if 80 <= days <= 100:
            quarterly[end] = entry["val"]

    recent_ends = sorted(quarterly.keys(), reverse=True)[:max_quarters]
    return [{"quarter_end": end, "value": quarterly[end]} for end in sorted(recent_ends)]
