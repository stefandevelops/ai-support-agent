from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from support_copilot.models import Order, PolicyChunk, Ticket, order_from_dict, ticket_from_dict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_json(name: str):
    path = DATA_DIR / name
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_orders() -> list[Order]:
    return [order_from_dict(row) for row in _load_json("orders.json")]


@lru_cache(maxsize=1)
def load_tickets() -> list[Ticket]:
    return [ticket_from_dict(row) for row in _load_json("tickets.json")]


@lru_cache(maxsize=1)
def load_policies() -> list[PolicyChunk]:
    payload = _load_json("policies.json")
    return [PolicyChunk(**chunk) for chunk in payload["chunks"]]
