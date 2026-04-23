"""Tests for per-peer unit economics computation."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.analysis import unit_economics

FIXTURE = Path(__file__).parent / "fixtures" / "sec_company_facts.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text())


def test_compute_ttm_ocf_and_capex():
    metrics = unit_economics.compute(
        ticker="PR",
        cik="0001658566",
        payload=_load(),
        market_cap=10_000_000_000,
    )
    # TTM OCF = Q4'24 + Q1'25 + Q2'25 + Q3'25 = 2,840M
    assert metrics.ttm_ocf == 2_840_000_000
    # TTM CapEx = 490 + 500 + 510 + 520 = 2,020M
    assert metrics.ttm_capex == 2_020_000_000
    assert metrics.fcf == 820_000_000


def test_compute_fcf_yield_uses_market_cap():
    metrics = unit_economics.compute(
        ticker="PR",
        cik="0001658566",
        payload=_load(),
        market_cap=10_000_000_000,
    )
    assert metrics.fcf_yield is not None
    assert round(metrics.fcf_yield, 4) == round(820_000_000 / 10_000_000_000, 4)


def test_compute_net_debt():
    metrics = unit_economics.compute(
        ticker="PR", cik="0001658566", payload=_load()
    )
    # LT debt 4.2B + current 50M − cash 250M = 4.0B
    assert metrics.net_debt == 4_000_000_000


def test_compute_ebitdax_and_leverage():
    metrics = unit_economics.compute(
        ticker="PR", cik="0001658566", payload=_load()
    )
    # TTM components (all summed Q4'24 + Q1-Q3'25):
    #   NI: 210 + 230 + 240 + 260 = 940
    #   Interest: 55 + 58 + 60 + 62 = 235
    #   Tax: 52 + 55 + 58 + 61 = 226
    #   DD&A: 310 + 320 + 330 + 340 = 1,300
    #   Exploration: missing → 0
    expected_ebitdax = (940 + 235 + 226 + 1300) * 1_000_000
    assert metrics.ebitdax == expected_ebitdax
    # ND/EBITDAX = 4,000M / 2,701M ≈ 1.48
    assert metrics.net_debt_to_ebitdax is not None
    assert round(metrics.net_debt_to_ebitdax, 2) == round(4_000_000_000 / expected_ebitdax, 2)


def test_compute_handles_missing_payload():
    metrics = unit_economics.compute(
        ticker="PR", cik="0001658566", payload=None, market_cap=10e9
    )
    assert metrics.ttm_ocf is None
    assert metrics.fcf is None
    assert metrics.fcf_yield is None
    assert metrics.net_debt is None
    assert metrics.ebitdax is None


def test_compute_no_market_cap_leaves_yield_blank():
    metrics = unit_economics.compute(
        ticker="PR", cik="0001658566", payload=_load(), market_cap=None
    )
    assert metrics.fcf is not None
    assert metrics.fcf_yield is None


def test_compute_as_of_uses_latest_quarter():
    metrics = unit_economics.compute(
        ticker="PR", cik="0001658566", payload=_load()
    )
    assert metrics.as_of == date(2025, 9, 30)
