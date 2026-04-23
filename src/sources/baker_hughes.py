"""Baker Hughes weekly rig count — placeholder for Phase 1.

The public Baker Hughes site publishes a weekly Excel/PDF; parsing is brittle
and not in the critical path for the first shipping brief. This module returns
``None`` when disabled, and the brief treats that as "data unavailable" rather
than erroring.

When ready, implement ``fetch_latest`` to return a ``RigCountSnapshot``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class RigCountSnapshot:
    as_of: date
    total_us: int
    permian: int
    permian_wow: int | None
    permian_yoy: int | None


def fetch_latest() -> RigCountSnapshot | None:
    logger.info("baker_hughes source not yet implemented")
    return None
