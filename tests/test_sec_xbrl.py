from unittest.mock import Mock, patch

from agents.sec_xbrl import get_company_facts, get_quarterly_metric_history


@patch("agents.sec_xbrl.requests.get")
def test_get_company_facts_builds_padded_cik_url(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {"entityName": "Snowflake Inc."}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = get_company_facts(1640147, "Test User test@example.com")

    assert result == {"entityName": "Snowflake Inc."}
    called_url = mock_get.call_args.args[0]
    assert called_url == "https://data.sec.gov/api/xbrl/companyfacts/CIK0001640147.json"


COMPANY_FACTS_FIXTURE = {
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        # quarterly (3-month) entries
                        {"start": "2025-02-01", "end": "2025-04-30", "val": 1042074000, "form": "10-Q"},
                        {"start": "2025-05-01", "end": "2025-07-31", "val": 1144969000, "form": "10-Q"},
                        {"start": "2026-02-01", "end": "2026-04-30", "val": 1390951000, "form": "10-Q"},
                        {"start": "2026-05-01", "end": "2026-07-31", "val": 1546793000, "form": "10-Q"},
                        # cumulative 6-month entry -- must be excluded by the duration filter
                        {"start": "2026-02-01", "end": "2026-07-31", "val": 2937744000, "form": "10-Q"},
                        # duplicate of a quarterly entry re-reported in a later filing
                        {"start": "2025-05-01", "end": "2025-07-31", "val": 1144969000, "form": "10-Q"},
                        # wrong form type -- must be excluded
                        {"start": "2026-05-01", "end": "2026-07-31", "val": 1546793000, "form": "8-K"},
                    ]
                }
            },
            "EarningsPerShareDiluted": {
                "units": {
                    "USD/shares": [
                        {"start": "2026-02-01", "end": "2026-04-30", "val": -0.86, "form": "10-Q"},
                        {"start": "2026-05-01", "end": "2026-07-31", "val": -0.55, "form": "10-Q"},
                    ]
                }
            },
            "SomeInstantOnlyTag": {
                "units": {
                    "USD": [
                        {"end": "2026-07-31", "val": 999, "form": "10-Q"},
                    ]
                }
            },
        }
    }
}


def test_get_quarterly_metric_history_filters_to_three_month_periods():
    result = get_quarterly_metric_history(
        COMPANY_FACTS_FIXTURE, "RevenueFromContractWithCustomerExcludingAssessedTax"
    )

    assert result == [
        {"quarter_end": "2025-04-30", "value": 1042074000},
        {"quarter_end": "2025-07-31", "value": 1144969000},
        {"quarter_end": "2026-04-30", "value": 1390951000},
        {"quarter_end": "2026-07-31", "value": 1546793000},
    ]


def test_get_quarterly_metric_history_respects_max_quarters():
    result = get_quarterly_metric_history(
        COMPANY_FACTS_FIXTURE, "RevenueFromContractWithCustomerExcludingAssessedTax", max_quarters=2
    )

    assert result == [
        {"quarter_end": "2026-04-30", "value": 1390951000},
        {"quarter_end": "2026-07-31", "value": 1546793000},
    ]


def test_get_quarterly_metric_history_works_for_eps_shares_unit():
    result = get_quarterly_metric_history(COMPANY_FACTS_FIXTURE, "EarningsPerShareDiluted")

    assert result == [
        {"quarter_end": "2026-04-30", "value": -0.86},
        {"quarter_end": "2026-07-31", "value": -0.55},
    ]


def test_get_quarterly_metric_history_returns_empty_for_unknown_tag():
    assert get_quarterly_metric_history(COMPANY_FACTS_FIXTURE, "NotARealTag") == []


def test_get_quarterly_metric_history_skips_instant_only_facts():
    assert get_quarterly_metric_history(COMPANY_FACTS_FIXTURE, "SomeInstantOnlyTag") == []
