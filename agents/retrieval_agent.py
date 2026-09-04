from datetime import date


def derive_year_quarter(report_date: date) -> tuple[int, int]:
    quarter = (report_date.month - 1) // 3 + 1
    return report_date.year, quarter
