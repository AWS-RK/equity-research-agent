import requests

EARNINGS_URL = "https://www.alphavantage.co/query"


def get_earnings(ticker: str, api_key: str) -> dict:
    params = {"function": "EARNINGS", "symbol": ticker.upper(), "apikey": api_key}
    response = requests.get(EARNINGS_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_latest_quarterly_earnings(earnings_response: dict) -> dict | None:
    quarterly = earnings_response.get("quarterlyEarnings", [])
    if not quarterly:
        return None
    return quarterly[0]
