from datetime import date


def check_freshness(document_date: date, today: date, max_age_days: int = 95) -> dict:
    age_days = (today - document_date).days
    return {
        "document_date": document_date.isoformat(),
        "age_days": age_days,
        "is_fresh": age_days <= max_age_days,
    }
