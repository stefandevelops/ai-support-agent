"""Deterministic 'today' so the demo does not rot when the calendar moves on."""

from __future__ import annotations

import os
from datetime import date

DEMO_TODAY = date(2026, 10, 17)


def today() -> date:
    override = os.getenv("SUPPORT_COPILOT_TODAY")
    if override:
        return date.fromisoformat(override)
    return DEMO_TODAY
