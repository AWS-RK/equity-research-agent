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
from agents.claude_extraction import extract_period_data, diff_language
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


def run(
    ticker: str,
    base_dir: str = "data",
    extraction_model: str = "claude-sonnet-5",
    diff_model: str = "claude-haiku-4-5-20251001",
) -> dict:
    config = load_config()
    data_dir = get_data_dir(ticker, base_dir)

    current_docs = {"filing": read_current_filing_text(data_dir, ticker)}
    press_release_text = read_current_press_release_text(data_dir, ticker)
    if press_release_text is not None:
        current_docs["press_release"] = press_release_text
    transcript_text = read_current_transcript_text(data_dir, ticker)
    if transcript_text is not None:
        current_docs["transcript"] = transcript_text

    current_period = extract_period_data(current_docs, model=extraction_model)

    cik = get_cik_for_ticker(ticker, config.sec_user_agent)
    submissions = get_submissions(cik, config.sec_user_agent)
    current_filing = find_latest_10q_or_10k(submissions)
    current_8k = find_latest_8k_item202(submissions)

    prior_filing = find_prior_10q_or_10k(submissions, current_filing["accessionNumber"])
    prior_8k_exclude = current_8k["accessionNumber"] if current_8k is not None else None
    prior_8k = find_prior_8k_item202(submissions, prior_8k_exclude)

    prior_period = None
    billings = None
    diffs = {"risk_factors": None, "guidance_language": None}

    if prior_filing is not None:
        prior_docs = {
            "filing": _fetch_and_save_prior_filing(cik, prior_filing, ticker, data_dir, config.sec_user_agent)
        }
        if prior_8k is not None:
            prior_press_release_text = _fetch_and_save_prior_exhibit(
                cik, prior_8k, ticker, data_dir, config.sec_user_agent
            )
            if prior_press_release_text is not None:
                prior_docs["press_release"] = prior_press_release_text

        prior_period = extract_period_data(prior_docs, model=extraction_model)
        billings = compute_billings(current_period, prior_period)
        diffs["risk_factors"] = diff_language(
            current_period["risk_factors_text"], prior_period["risk_factors_text"], "risk factors", model=diff_model
        )
        diffs["guidance_language"] = diff_language(
            current_period["guidance_text"], prior_period["guidance_text"], "guidance", model=diff_model
        )

    result = {
        "ticker": ticker.upper(),
        "current_period": current_period,
        "prior_period": prior_period,
        "billings": billings,
        "diffs": diffs,
    }

    output_path = data_dir / "extracted.json"
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result
