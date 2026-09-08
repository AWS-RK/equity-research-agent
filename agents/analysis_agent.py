import json
from pathlib import Path

from agents.alpha_vantage import get_latest_quarterly_earnings


def read_extracted_data(ticker: str, base_dir: str = "data") -> dict:
    extracted_path = Path(base_dir) / ticker.upper() / "extracted.json"
    if not extracted_path.exists():
        raise FileNotFoundError(
            f"No extracted.json found in {extracted_path.parent} -- run the extraction agent (M2) first."
        )
    return json.loads(extracted_path.read_text(encoding="utf-8"))


def read_eps_consensus(ticker: str, base_dir: str = "data") -> dict | None:
    data_dir = Path(base_dir) / ticker.upper()
    earnings_path = data_dir / f"{ticker.upper()}_earnings_alphavantage.json"
    if not earnings_path.exists():
        raise FileNotFoundError(
            f"No {earnings_path.name} found in {data_dir} -- run the retrieval agent (M1) first."
        )
    earnings_response = json.loads(earnings_path.read_text(encoding="utf-8"))
    return get_latest_quarterly_earnings(earnings_response)
