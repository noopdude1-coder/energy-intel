"""Tests for the SEC XBRL helpers. No live HTTP."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.sources import sec

FIXTURE = Path(__file__).parent / "fixtures" / "sec_company_facts.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text())


def test_normalize_cik_pads_to_ten_digits():
    assert sec._normalize_cik("1658566") == "0001658566"
    assert sec._normalize_cik("0001658566") == "0001658566"
    assert sec._normalize_cik(1658566) == "0001658566"


def test_latest_fact_returns_most_recent():
    payload = _load()
    entry = sec.latest_fact(payload, "NetCashProvidedByOperatingActivities")
    assert entry is not None
    # Most recent period end in fixture is 2025-09-30
    assert entry["end"] == "2025-09-30"
    assert entry["val"] == 740000000


def test_latest_fact_filtered_by_form():
    payload = _load()
    ten_k = sec.latest_fact(payload, "NetCashProvidedByOperatingActivities", form="10-K")
    assert ten_k is not None
    assert ten_k["form"] == "10-K"
    assert ten_k["val"] == 2500000000


def test_latest_annual():
    payload = _load()
    entry = sec.latest_annual(payload, "NetCashProvidedByOperatingActivities")
    assert entry is not None
    assert entry["fp"] == "FY"
    assert entry["val"] == 2500000000


def test_ttm_sum_prefers_quarterly_if_more_recent():
    payload = _load()
    result = sec.ttm_sum(payload, "NetCashProvidedByOperatingActivities")
    assert result is not None
    total, as_of = result
    # Q4 2024 (680M) + Q1-Q3 2025 (700 + 720 + 740) = 2,840M
    assert total == 2_840_000_000
    assert as_of == date(2025, 9, 30)


def test_ttm_sum_returns_annual_when_its_more_recent():
    """Remove the 2025 quarters; then 10-K end 2024-12-31 should win."""
    payload = _load()
    units = payload["facts"]["us-gaap"]["NetCashProvidedByOperatingActivities"]["units"]
    units["USD"] = [v for v in units["USD"] if v["fy"] == 2024]
    result = sec.ttm_sum(payload, "NetCashProvidedByOperatingActivities")
    assert result is not None
    total, as_of = result
    assert total == 2_500_000_000
    assert as_of == date(2024, 12, 31)


def test_ttm_sum_missing_tag_returns_none():
    payload = _load()
    assert sec.ttm_sum(payload, "DoesNotExist") is None


def test_first_matching_tag_preserves_priority():
    payload = _load()
    assert sec.first_matching_tag(
        payload,
        ("DoesNotExist", "PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpenditures"),
    ) == "PaymentsToAcquirePropertyPlantAndEquipment"


def test_load_peer_ciks_normalizes(tmp_path):
    import yaml

    path = tmp_path / "peers.yml"
    path.write_text(yaml.safe_dump({"ciks": {"PR": "1658566", "fang": 1539838}}))
    loaded = sec.load_peer_ciks(path)
    assert loaded == {"PR": "0001658566", "FANG": "0001539838"}


def test_fetch_company_facts_handles_error(monkeypatch):
    class BadClient:
        def company_facts(self, cik):
            raise RuntimeError("403")

    assert sec.fetch_company_facts("0001658566", client=BadClient()) is None
