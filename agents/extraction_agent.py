import argparse
import json
from pathlib import Path

from agents.config import load_config, get_data_dir
from agents.sec_edgar import (
    get_cik_for_ticker,
    get_submissions,
    find_latest_10q_or_10k,
    find_latest_8k_item202,
    find_prior_10q_or_10k,
    find_prior_8k_item202,
    get_filing_index_html,
    find_exhibit_991_filename,
    download_document,
)
from agents.html_text import strip_html_to_text
from agents.derived_metrics import compute_billings


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


def _fetch_and_save_prior_filing(
    cik: int, prior_filing: dict, ticker: str, data_dir: Path, user_agent: str
) -> str:
    text = download_document(cik, prior_filing["accessionNumber"], prior_filing["primaryDocument"], user_agent)
    path = data_dir / f"{ticker.upper()}_{prior_filing['form']}_PRIOR_{prior_filing['filingDate']}.htm"
    path.write_text(text, encoding="utf-8")
    return strip_html_to_text(text)


def _fetch_and_save_prior_exhibit(
    cik: int, prior_8k: dict, ticker: str, data_dir: Path, user_agent: str
) -> str | None:
    index_html = get_filing_index_html(cik, prior_8k["accessionNumber"], user_agent)
    exhibit_filename = find_exhibit_991_filename(index_html)
    if exhibit_filename is None:
        return None
    text = download_document(cik, prior_8k["accessionNumber"], exhibit_filename, user_agent)
    path = data_dir / f"{ticker.upper()}_8K_EX99.1_PRIOR_{prior_8k['filingDate']}.htm"
    path.write_text(text, encoding="utf-8")
    return strip_html_to_text(text)


def fetch_prior_period_documents(ticker: str, base_dir: str = "data") -> dict:
    """Deterministic prep step: fetch and save the prior quarter's 10-Q/10-K and
    8-K Exhibit 99.1 (if any) alongside M1's current-period documents in
    data/{TICKER}/. Returns the saved file paths (or None where nothing was
    found) so the caller knows what's available to read.

    This does NOT do any extraction -- reading the documents (current and
    prior) and producing the structured data for save_extracted_result() is
    done by Claude directly in a session, not by this function.
    """
    config = load_config()
    data_dir = get_data_dir(ticker, base_dir)

    cik = get_cik_for_ticker(ticker, config.sec_user_agent)
    submissions = get_submissions(cik, config.sec_user_agent)
    current_filing = find_latest_10q_or_10k(submissions)
    current_8k = find_latest_8k_item202(submissions)

    prior_filing = find_prior_10q_or_10k(submissions, current_filing["accessionNumber"])
    prior_8k_exclude = current_8k["accessionNumber"] if current_8k is not None else None
    prior_8k = find_prior_8k_item202(submissions, prior_8k_exclude)

    result = {"prior_filing_path": None, "prior_press_release_path": None}

    if prior_filing is not None:
        _fetch_and_save_prior_filing(cik, prior_filing, ticker, data_dir, config.sec_user_agent)
        result["prior_filing_path"] = str(
            data_dir / f"{ticker.upper()}_{prior_filing['form']}_PRIOR_{prior_filing['filingDate']}.htm"
        )

        if prior_8k is not None:
            exhibit_text = _fetch_and_save_prior_exhibit(cik, prior_8k, ticker, data_dir, config.sec_user_agent)
            if exhibit_text is not None:
                result["prior_press_release_path"] = str(
                    data_dir / f"{ticker.upper()}_8K_EX99.1_PRIOR_{prior_8k['filingDate']}.htm"
                )

    return result


def save_extracted_result(
    ticker: str,
    base_dir: str,
    current_period: dict,
    prior_period: dict | None = None,
    diffs: dict | None = None,
) -> dict:
    """Deterministic finalize step: takes the structured current/prior period
    data (already produced by Claude reading the documents directly) and the
    risk-factor/guidance-language diff summaries, computes billings, assembles
    the final shape, and writes data/{TICKER}/extracted.json.
    """
    data_dir = get_data_dir(ticker, base_dir)

    billings = compute_billings(current_period, prior_period) if prior_period is not None else None
    result = {
        "ticker": ticker.upper(),
        "current_period": current_period,
        "prior_period": prior_period,
        "billings": billings,
        "diffs": diffs if diffs is not None else {"risk_factors": None, "guidance_language": None},
    }

    output_path = data_dir / "extracted.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare inputs for extraction: fetch and save the prior quarter's "
            "10-Q/10-K and 8-K exhibit alongside M1's current-period documents. "
            "Reading the documents and producing extracted.json is done by Claude "
            "directly in a session, not by this script."
        )
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker, e.g. SNOW")
    parser.add_argument("--data-dir", default="data", help="Base directory where M1 saved raw documents")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    result = fetch_prior_period_documents(args.ticker, args.data_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
