import json
from pathlib import Path

from agents.html_text import strip_html_to_text


def _latest_non_prior_match(data_dir: Path, pattern: str) -> Path | None:
    matches = [p for p in sorted(data_dir.glob(pattern)) if "_PRIOR_" not in p.name]
    if not matches:
        return None
    return matches[-1]


def read_current_filing_text(data_dir: Path, ticker: str) -> str:
    match = _latest_non_prior_match(data_dir, f"{ticker.upper()}_10-*.htm")
    if match is None:
        raise FileNotFoundError(
            f"No current-period 10-Q/10-K found in {data_dir} -- run the retrieval agent (M1) first."
        )
    return strip_html_to_text(match.read_text(encoding="utf-8"))


def read_current_press_release_text(data_dir: Path, ticker: str) -> str | None:
    match = _latest_non_prior_match(data_dir, f"{ticker.upper()}_8K_EX99.1_*.htm")
    if match is None:
        return None
    return strip_html_to_text(match.read_text(encoding="utf-8"))


def read_current_transcript_text(data_dir: Path, ticker: str) -> str | None:
    matches = sorted(data_dir.glob(f"{ticker.upper()}_transcript_*.json"))
    if not matches:
        return None
    transcript = json.loads(matches[-1].read_text(encoding="utf-8"))
    return transcript.get("transcript")
