import requests

TRANSCRIPT_URL = "https://api.api-ninjas.com/v1/earningstranscript"


def get_transcript(ticker: str, api_key: str, year: int | None = None, quarter: int | None = None) -> dict:
    params = {"ticker": ticker.upper()}
    if year is not None:
        params["year"] = year
    if quarter is not None:
        params["quarter"] = quarter

    response = requests.get(TRANSCRIPT_URL, headers={"X-Api-Key": api_key}, params=params, timeout=30)
    response.raise_for_status()
    return response.json()
