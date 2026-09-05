from agents.derived_metrics import compute_billings


def test_compute_billings_when_all_inputs_present():
    current = {"revenue": 1000.0, "deferred_revenue_balance": 500.0}
    prior = {"deferred_revenue_balance": 400.0}

    result = compute_billings(current, prior)

    assert result == {
        "revenue": 1000.0,
        "current_deferred_revenue": 500.0,
        "prior_deferred_revenue": 400.0,
        "value": 1100.0,
    }


def test_compute_billings_returns_none_when_revenue_missing():
    current = {"revenue": None, "deferred_revenue_balance": 500.0}
    prior = {"deferred_revenue_balance": 400.0}

    assert compute_billings(current, prior) is None


def test_compute_billings_returns_none_when_current_deferred_revenue_missing():
    current = {"revenue": 1000.0, "deferred_revenue_balance": None}
    prior = {"deferred_revenue_balance": 400.0}

    assert compute_billings(current, prior) is None


def test_compute_billings_returns_none_when_prior_deferred_revenue_missing():
    current = {"revenue": 1000.0, "deferred_revenue_balance": 500.0}
    prior = {"deferred_revenue_balance": None}

    assert compute_billings(current, prior) is None
