from datetime import date

from agents.retrieval_agent import derive_year_quarter


def test_derive_year_quarter_q3_boundary():
    assert derive_year_quarter(date(2026, 7, 31)) == (2026, 3)


def test_derive_year_quarter_q1():
    assert derive_year_quarter(date(2026, 2, 15)) == (2026, 1)


def test_derive_year_quarter_q4():
    assert derive_year_quarter(date(2025, 12, 31)) == (2025, 4)
