from datetime import date

from agents.freshness import check_freshness


def test_check_freshness_passes_within_window():
    result = check_freshness(date(2026, 8, 1), date(2026, 9, 4), max_age_days=95)

    assert result["document_date"] == "2026-08-01"
    assert result["age_days"] == 34
    assert result["is_fresh"] is True


def test_check_freshness_fails_outside_window():
    result = check_freshness(date(2025, 1, 1), date(2026, 9, 4), max_age_days=95)

    assert result["is_fresh"] is False
