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


def find_latest_10q_or_10k(submissions: dict) -> dict:
    recent = submissions["filings"]["recent"]
    candidates = []
    for i, form in enumerate(recent["form"]):
        if form in ("10-Q", "10-K"):
            candidates.append(
                {
                    "form": form,
                    "filingDate": recent["filingDate"][i],
                    "reportDate": recent["reportDate"][i],
                    "accessionNumber": recent["accessionNumber"][i],
                    "primaryDocument": recent["primaryDocument"][i],
                }
            )

    if not candidates:
        raise ValueError("No 10-Q or 10-K filings found in submissions")

    candidates.sort(key=lambda c: c["filingDate"], reverse=True)
    return candidates[0]


def find_latest_8k_item202(submissions: dict) -> dict | None:
    recent = submissions["filings"]["recent"]
    candidates = []
    for i, form in enumerate(recent["form"]):
        items = recent["items"][i].split(",") if recent["items"][i] else []
        if form == "8-K" and "2.02" in items:
            candidates.append(
                {
                    "form": form,
                    "filingDate": recent["filingDate"][i],
                    "reportDate": recent["reportDate"][i],
                    "accessionNumber": recent["accessionNumber"][i],
                    "primaryDocument": recent["primaryDocument"][i],
                }
            )

    if not candidates:
        return None

    candidates.sort(key=lambda c: c["filingDate"], reverse=True)
    return candidates[0]
