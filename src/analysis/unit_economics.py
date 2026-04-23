"""Compute per-peer unit economics from SEC XBRL + market cap.

Metrics (Phase 2 MVP):
- **TTM operating cash flow** — ``NetCashProvidedByOperatingActivities``
- **TTM CapEx** — falls back across several GAAP tags
- **Free cash flow** — OCF − CapEx
- **FCF yield** — TTM FCF / market cap
- **Net debt** — (LT debt + current portion) − cash & equivalents, latest balance
- **EBITDAX proxy** — Net Income + Interest Expense + Tax + D&A + Exploration Expense (TTM).
  Several components rely on GAAP tags that aren't uniformly used, so this is
  best-effort. Missing components are set to 0 and surfaced in ``components``.
- **Net debt / EBITDAX** — standard leverage ratio

Deliberately *not* attempted here (requires custom XBRL extensions or narrative
parsing):
- Hedged % of next-12-month volumes (derivatives-footnote heuristic)
- CapEx per BOE (production volumes are filer-custom tags, no reliable standard)
- PV-10 / EV (reserves disclosure, mostly custom tags)
- D&C cost per lateral foot (not in GAAP taxonomy)

These are captured as ``None`` fields and marked "—" in the rendered table so
we degrade cleanly instead of inventing numbers.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from src.sources import sec

logger = logging.getLogger(__name__)

OCF_TAGS = ("NetCashProvidedByOperatingActivities",)

CAPEX_TAGS = (
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireOilAndGasProperty",
    "CapitalExpenditures",
    "PaymentsToAcquireProductiveAssets",
)

CASH_TAGS = (
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
)

LONG_TERM_DEBT_TAGS = (
    "LongTermDebt",
    "LongTermDebtNoncurrent",
)

CURRENT_DEBT_TAGS = (
    "LongTermDebtCurrent",
    "DebtCurrent",
)

NET_INCOME_TAGS = (
    "NetIncomeLoss",
    "ProfitLoss",
)

INTEREST_EXPENSE_TAGS = (
    "InterestExpense",
    "InterestExpenseDebt",
)

TAX_EXPENSE_TAGS = (
    "IncomeTaxExpenseBenefit",
)

DA_TAGS = (
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "Depreciation",
)

EXPLORATION_TAGS = (
    "ExplorationExpense",
    "ExplorationAbandonmentAndImpairmentExpense",
)

SHARES_TAGS = (
    "CommonStockSharesOutstanding",
    "EntityCommonStockSharesOutstanding",
)


@dataclass
class PeerMetrics:
    ticker: str
    cik: str
    entity_name: str | None = None
    as_of: date | None = None
    ttm_ocf: float | None = None
    ttm_capex: float | None = None
    fcf: float | None = None
    fcf_yield: float | None = None
    market_cap: float | None = None
    net_debt: float | None = None
    ebitdax: float | None = None
    net_debt_to_ebitdax: float | None = None
    components: dict[str, float | None] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "cik": self.cik,
            "entity_name": self.entity_name,
            "as_of": self.as_of,
            "ttm_ocf": self.ttm_ocf,
            "ttm_capex": self.ttm_capex,
            "fcf": self.fcf,
            "fcf_yield": self.fcf_yield,
            "market_cap": self.market_cap,
            "net_debt": self.net_debt,
            "ebitdax": self.ebitdax,
            "net_debt_to_ebitdax": self.net_debt_to_ebitdax,
        }


def _ttm(payload: dict, tags: tuple[str, ...]) -> tuple[float, date] | None:
    tag = sec.first_matching_tag(payload, tags)
    if not tag:
        return None
    return sec.ttm_sum(payload, tag)


def _latest_balance(payload: dict, tags: tuple[str, ...]) -> tuple[float, date] | None:
    tag = sec.first_matching_tag(payload, tags)
    if not tag:
        return None
    entry = sec.latest_fact(payload, tag)
    if not entry:
        return None
    end = sec._parse_date(entry.get("end"))
    return float(entry["val"]), end or date.today()


def compute(
    *,
    ticker: str,
    cik: str,
    payload: dict | None,
    market_cap: float | None = None,
) -> PeerMetrics:
    metrics = PeerMetrics(ticker=ticker.upper(), cik=cik)
    if not payload:
        return metrics
    metrics.entity_name = payload.get("entityName")

    ocf = _ttm(payload, OCF_TAGS)
    capex = _ttm(payload, CAPEX_TAGS)

    if ocf:
        metrics.ttm_ocf, metrics.as_of = ocf
    if capex:
        # CapEx is usually a *payment* (positive outflow in XBRL). FCF = OCF − CapEx.
        metrics.ttm_capex = abs(capex[0])
        if metrics.as_of is None or (capex[1] and capex[1] > metrics.as_of):
            metrics.as_of = capex[1]
    if metrics.ttm_ocf is not None and metrics.ttm_capex is not None:
        metrics.fcf = metrics.ttm_ocf - metrics.ttm_capex
    if metrics.fcf is not None and market_cap and market_cap > 0:
        metrics.market_cap = market_cap
        metrics.fcf_yield = metrics.fcf / market_cap

    cash = _latest_balance(payload, CASH_TAGS)
    lt_debt = _latest_balance(payload, LONG_TERM_DEBT_TAGS)
    current_debt = _latest_balance(payload, CURRENT_DEBT_TAGS)

    debt_total = 0.0
    has_debt = False
    if lt_debt:
        debt_total += lt_debt[0]
        has_debt = True
    if current_debt:
        debt_total += current_debt[0]
        has_debt = True
    if has_debt:
        cash_val = cash[0] if cash else 0.0
        metrics.net_debt = debt_total - cash_val

    ni = _ttm(payload, NET_INCOME_TAGS)
    interest = _ttm(payload, INTEREST_EXPENSE_TAGS)
    tax = _ttm(payload, TAX_EXPENSE_TAGS)
    da = _ttm(payload, DA_TAGS)
    exploration = _ttm(payload, EXPLORATION_TAGS)

    components = {
        "net_income": ni[0] if ni else None,
        "interest_expense": interest[0] if interest else None,
        "tax_expense": tax[0] if tax else None,
        "d_and_a": da[0] if da else None,
        "exploration": exploration[0] if exploration else None,
    }
    metrics.components = components

    # Require at least net income + D&A to build a usable EBITDAX proxy.
    if components["net_income"] is not None and components["d_and_a"] is not None:
        metrics.ebitdax = (
            (components["net_income"] or 0.0)
            + (components["interest_expense"] or 0.0)
            + (components["tax_expense"] or 0.0)
            + (components["d_and_a"] or 0.0)
            + (components["exploration"] or 0.0)
        )

    if metrics.net_debt is not None and metrics.ebitdax and metrics.ebitdax > 0:
        metrics.net_debt_to_ebitdax = metrics.net_debt / metrics.ebitdax

    return metrics
