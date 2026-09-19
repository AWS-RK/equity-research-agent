import argparse
import json
from datetime import date, datetime

import requests

from agents.config import load_config, get_data_dir
from agents.sec_edgar import (
    get_cik_for_ticker,
    get_submissions,
    find_latest_10q_or_10k,
    find_latest_8k_item202,
    get_filing_index_html,
    find_exhibit_991_filename,
    download_document,
)
from agents.api_ninjas import get_transcript
from agents.alpha_vantage import get_earnings, get_latest_quarterly_earnings, get_earnings_call_transcript
from agents.freshness import check_freshness


def derive_year_quarter(report_date: date) -> tuple[int, int]:
    quarter = (report_date.month - 1) // 3 + 1
    return report_date.year, quarter


def derive_fiscal_quarter_guess(report_date: date) -> str:
    """Best-effort guess at a January-fiscal-year-end filer's own self-styled
    fiscal year/quarter label (e.g. "2027Q2"), for Alpha Vantage's
    EARNINGS_CALL_TRANSCRIPT endpoint, which keys on that label rather than a
    calendar quarter -- confirmed live for SNOW (fiscal year ends Jan 31).
    NOT guaranteed correct for filers with a different fiscal year end; a
    wrong guess just returns no transcript data, the same as today's
    unavailable state, so trying it is harmless.
    """
    calendar_year, calendar_quarter = derive_year_quarter(report_date)
    if calendar_quarter == 1:
        return f"{calendar_year}Q4"
    return f"{calendar_year + 1}Q{calendar_quarter - 1}"


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def run(ticker: str, base_dir: str = "data", max_age_days: int = 95) -> list[dict]:
    config = load_config()
    data_dir = get_data_dir(ticker, base_dir)
    today = date.today()
    freshness_report = []

    cik = get_cik_for_ticker(ticker, config.sec_user_agent)
    submissions = get_submissions(cik, config.sec_user_agent)

    filing = find_latest_10q_or_10k(submissions)
    filing_text = download_document(cik, filing["accessionNumber"], filing["primaryDocument"], config.sec_user_agent)
    filing_path = data_dir / f"{ticker.upper()}_{filing['form']}_{filing['filingDate']}.htm"
    filing_path.write_text(filing_text, encoding="utf-8")
    freshness_report.append(
        {"document": filing_path.name, **check_freshness(_parse_date(filing["filingDate"]), today, max_age_days)}
    )

    eightk = find_latest_8k_item202(submissions)
    if eightk is not None:
        index_html = get_filing_index_html(cik, eightk["accessionNumber"], config.sec_user_agent)
        exhibit_filename = find_exhibit_991_filename(index_html)
        if exhibit_filename is not None:
            exhibit_text = download_document(cik, eightk["accessionNumber"], exhibit_filename, config.sec_user_agent)
            exhibit_path = data_dir / f"{ticker.upper()}_8K_EX99.1_{eightk['filingDate']}.htm"
            exhibit_path.write_text(exhibit_text, encoding="utf-8")
            freshness_report.append(
                {
                    "document": exhibit_path.name,
                    **check_freshness(_parse_date(eightk["filingDate"]), today, max_age_days),
                }
            )

    report_date = _parse_date(filing["reportDate"])
    year, quarter = derive_year_quarter(report_date)
    try:
        transcript = get_transcript(ticker, config.api_ninjas_key, year=year, quarter=quarter)
    except requests.exceptions.HTTPError as exc:
        # A gated or unavailable transcript is a known, non-fatal outcome (e.g. API
        # Ninjas' earnings transcript endpoint requires a paid tier). Record the
        # failure as-is rather than guessing at a transcript, and let every other
        # independent data source in this run still complete.
        transcript = {"error": str(exc)}
        # Alpha Vantage's transcript endpoint is a free fallback we already have a
        # key for, but its data lags real filers by roughly a quarter or two, so
        # it frequently has nothing for the current quarter yet. Try it anyway --
        # a miss just leaves the API Ninjas error in place, same as before.
        try:
            fallback = get_earnings_call_transcript(
                ticker, config.alpha_vantage_key, derive_fiscal_quarter_guess(report_date)
            )
        except requests.exceptions.HTTPError:
            fallback = {}
        if fallback.get("transcript"):
            transcript = fallback
    transcript_path = data_dir / f"{ticker.upper()}_transcript_{year}Q{quarter}.json"
    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    transcript_date_str = transcript.get("date")
    if isinstance(transcript_date_str, str):
        freshness_report.append(
            {"document": transcript_path.name, **check_freshness(_parse_date(transcript_date_str), today, max_age_days)}
        )

    earnings = get_earnings(ticker, config.alpha_vantage_key)
    earnings_path = data_dir / f"{ticker.upper()}_earnings_alphavantage.json"
    earnings_path.write_text(json.dumps(earnings, indent=2), encoding="utf-8")
    latest_quarter = get_latest_quarterly_earnings(earnings)
    if latest_quarter is not None and latest_quarter.get("reportedDate"):
        freshness_report.append(
            {
                "document": earnings_path.name,
                **check_freshness(_parse_date(latest_quarter["reportedDate"]), today, max_age_days),
            }
        )

    return freshness_report


def print_freshness_report(freshness_report: list[dict]) -> None:
    print(f"\n{'Document':<40} {'Date':<12} {'Age (days)':<12} {'Status'}")
    print("-" * 80)
    for entry in freshness_report:
        status = "PASS" if entry["is_fresh"] else "FAIL"
        print(f"{entry['document']:<40} {entry['document_date']:<12} {entry['age_days']:<12} {status}")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrieve latest SEC filings, earnings transcript, and EPS data for a ticker."
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker, e.g. SNOW")
    parser.add_argument("--data-dir", default="data", help="Base directory to save documents into")
    parser.add_argument("--max-age-days", type=int, default=95, help="Freshness threshold in days (~3 months)")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    freshness_report = run(args.ticker, args.data_dir, args.max_age_days)
    print_freshness_report(freshness_report)


if __name__ == "__main__":
    main()
