def compute_billings(current: dict, prior: dict) -> dict | None:
    revenue = current.get("revenue")
    current_deferred_revenue = current.get("deferred_revenue_balance")
    prior_deferred_revenue = prior.get("deferred_revenue_balance")

    if revenue is None or current_deferred_revenue is None or prior_deferred_revenue is None:
        return None

    return {
        "revenue": revenue,
        "current_deferred_revenue": current_deferred_revenue,
        "prior_deferred_revenue": prior_deferred_revenue,
        "value": revenue + current_deferred_revenue - prior_deferred_revenue,
    }
