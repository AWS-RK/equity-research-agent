import requests

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def _sec_headers(user_agent: str) -> dict:
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}


def get_cik_for_ticker(ticker: str, user_agent: str) -> int:
    response = requests.get(COMPANY_TICKERS_URL, headers=_sec_headers(user_agent), timeout=30)
    response.raise_for_status()
    data = response.json()

    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry["ticker"] == ticker_upper:
            return entry["cik_str"]

    raise ValueError(f"Ticker {ticker_upper!r} not found in SEC company_tickers.json")


SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


def get_submissions(cik: int, user_agent: str) -> dict:
    url = SUBMISSIONS_URL_TEMPLATE.format(cik=cik)
    response = requests.get(url, headers=_sec_headers(user_agent), timeout=30)
    response.raise_for_status()
    return response.json()
