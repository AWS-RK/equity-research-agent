import json
from pathlib import Path


def read_extracted_data(ticker: str, base_dir: str = "data") -> dict:
    extracted_path = Path(base_dir) / ticker.upper() / "extracted.json"
    if not extracted_path.exists():
        raise FileNotFoundError(
            f"No extracted.json found in {extracted_path.parent} -- run the extraction agent (M2) first."
        )
    return json.loads(extracted_path.read_text(encoding="utf-8"))
