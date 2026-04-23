"""Money/position logic — spec guardrail requires tests here."""
from __future__ import annotations

from src.analysis import position


def test_stop_distance_and_pl_basic():
    holdings = [
        position.Holding(ticker="PR", shares=100, cost_basis=15.00, trailing_stop=14.25)
    ]
    status = position.evaluate(holdings, {"PR": 15.50}, warning_pct=2.0)[0]

    assert status.last == 15.50
    assert status.unrealized_pl == (15.50 - 15.00) * 100
    assert round(status.unrealized_pct, 4) == round((15.50 / 15.00 - 1) * 100, 4)
    assert round(status.stop_distance_pct, 4) == round((15.50 - 14.25) / 15.50 * 100, 4)
    assert status.stop_warning is False


def test_stop_warning_triggers_within_threshold():
    holdings = [
        position.Holding(ticker="PR", shares=100, cost_basis=15.00, trailing_stop=15.00)
    ]
    status = position.evaluate(holdings, {"PR": 15.15}, warning_pct=2.0)[0]
    # distance = (15.15 - 15.00) / 15.15 * 100 ≈ 0.99% — within 2% warning band
    assert status.stop_warning is True


def test_stop_warning_not_triggered_outside_threshold():
    holdings = [
        position.Holding(ticker="PR", shares=100, cost_basis=15.00, trailing_stop=14.00)
    ]
    status = position.evaluate(holdings, {"PR": 15.50}, warning_pct=2.0)[0]
    # distance ≈ 9.68% > 2%
    assert status.stop_warning is False


def test_missing_price_yields_none_metrics():
    holdings = [
        position.Holding(ticker="FANG", shares=20, cost_basis=180.0, trailing_stop=172.0)
    ]
    status = position.evaluate(holdings, {}, warning_pct=2.0)[0]
    assert status.last is None
    assert status.unrealized_pl is None
    assert status.stop_distance_pct is None
    assert status.stop_warning is False


def test_load_holdings_from_yaml_shape():
    raw = [
        {"ticker": "pr", "shares": 100, "cost_basis": 15.0, "trailing_stop": 14.25},
        {"ticker": "FANG", "shares": 20, "cost_basis": 180.0, "trailing_stop": 172.0},
    ]
    holdings = position.load_holdings(raw)
    assert [h.ticker for h in holdings] == ["PR", "FANG"]
    assert holdings[0].shares == 100.0
