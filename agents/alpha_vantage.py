import requests

EARNINGS_URL = "https://www.alphavantage.co/query"
OVERVIEW_URL = "https://www.alphavantage.co/query"
TRANSCRIPT_URL = "https://www.alphavantage.co/query"


def get_earnings(ticker: str, api_key: str) -> dict:
    params = {"function": "EARNINGS", "symbol": ticker.upper(), "apikey": api_key}
    response = requests.get(EARNINGS_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_company_overview(ticker: str, api_key: str) -> dict:
    params = {"function": "OVERVIEW", "symbol": ticker.upper(), "apikey": api_key}
    response = requests.get(OVERVIEW_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_latest_quarterly_earnings(earnings_response: dict) -> dict | None:
    quarterly = earnings_response.get("quarterlyEarnings", [])
    if not quarterly:
        return None
    return quarterly[0]


def get_earnings_call_transcript(ticker: str, api_key: str, fiscal_quarter: str) -> dict:
    # fiscal_quarter uses the company's OWN self-styled fiscal year/quarter label
    # (e.g. "2027Q2" for what the company itself calls "Q2 FY2027"), not a
    # calendar quarter -- confirmed live: for a January-fiscal-year-end filer,
    # passing the calendar quarter of the report date returns the wrong period
    # entirely. See derive_fiscal_quarter_guess() in agents/retrieval_agent.py.
    params = {
        "function": "EARNINGS_CALL_TRANSCRIPT",
        "symbol": ticker.upper(),
        "quarter": fiscal_quarter,
        "apikey": api_key,
    }
    response = requests.get(TRANSCRIPT_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()
